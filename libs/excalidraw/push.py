"""YAML push system for Excalidraw canvas.

Converts a declarative YAML diagram spec into Excalidraw elements and pushes
them to the canvas via the REST API. Tracks state in a .state.json file for
incremental updates.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import yaml


# ============ Defaults ============

# Excalidraw expects numeric font family IDs, not strings
FONT_FAMILY = {
    "Virgil": 1,
    "Helvetica": 2,
    "Cascadia": 3,
}

SHAPE_DEFAULTS = {
    "fillStyle": "solid",
    "strokeWidth": 2,
    "strokeStyle": "solid",
    "roughness": 1,
    "opacity": 100,
}

LABEL_DEFAULTS = {
    "fontSize": 16,
    "fontFamily": 1,  # Virgil
}

TEXT_DEFAULTS = {
    "fontSize": 20,
    "fontFamily": 1,  # Virgil
}


def resolve_font_family(value):
    """Resolve a font family name to its numeric ID."""
    if isinstance(value, int):
        return value
    return FONT_FAMILY.get(value, LABEL_DEFAULTS["fontFamily"])


# ============ Parsing ============

def parse_pos(pos):
    """Parse pos field: [x, y, 'WIDTHxHEIGHT'] or [x, y]."""
    x, y = int(pos[0]), int(pos[1])
    if len(pos) >= 3:
        dim = str(pos[2])
        if 'x' in dim:
            w, h = dim.split('x')
            return x, y, int(w), int(h)
    return x, y, None, None


def compute_hash(entry):
    """Hash a YAML entry for change detection."""
    canonical = json.dumps(entry, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def validate_yaml(data):
    """Validate YAML structure and return all entries with IDs."""
    shapes = data.get('shapes', [])
    texts = data.get('texts', [])
    connectors = data.get('connectors', [])

    # Collect shape IDs
    shape_ids = set()
    for s in shapes:
        if 'id' not in s:
            raise ValueError(f"Shape missing 'id': {s}")
        if 'type' not in s:
            raise ValueError(f"Shape '{s['id']}' missing 'type'")
        if 'pos' not in s:
            raise ValueError(f"Shape '{s['id']}' missing 'pos'")
        shape_ids.add(s['id'])

    # Auto-generate text IDs
    for i, t in enumerate(texts):
        if 'id' not in t:
            t['id'] = f"_text_{i}"
        if 'text' not in t:
            raise ValueError(f"Text '{t['id']}' missing 'text'")
        if 'pos' not in t:
            raise ValueError(f"Text '{t['id']}' missing 'pos'")

    # Auto-generate connector IDs, validate references
    for c in connectors:
        if 'from' not in c or 'to' not in c:
            raise ValueError(f"Connector missing 'from' or 'to': {c}")
        if 'id' not in c:
            c['id'] = f"{c['from']}-to-{c['to']}"
        if 'type' not in c:
            c['type'] = 'arrow'
        if c['from'] not in shape_ids:
            raise ValueError(f"Connector '{c['id']}': 'from' references unknown shape '{c['from']}'")
        if c['to'] not in shape_ids:
            raise ValueError(f"Connector '{c['id']}': 'to' references unknown shape '{c['to']}'")

    return shapes, texts, connectors


# ============ Skeleton Conversion ============

def shape_to_skeleton(shape):
    """Convert a YAML shape to an Excalidraw skeleton element."""
    x, y, w, h = parse_pos(shape['pos'])
    color = shape.get('color', {})
    style = shape.get('style', {})

    skeleton = {
        "type": shape["type"],
        "x": x, "y": y,
        "width": w, "height": h,
        "strokeColor": color.get("stroke", "#1e1e1e"),
        "backgroundColor": color.get("bg", "transparent"),
    }

    for key, default in SHAPE_DEFAULTS.items():
        skeleton[key] = style.get(key, default)

    if shape.get("label"):
        label = {"text": shape["label"]}
        label["fontSize"] = shape.get("fontSize", LABEL_DEFAULTS["fontSize"])
        label["fontFamily"] = resolve_font_family(shape.get("fontFamily", LABEL_DEFAULTS["fontFamily"]))
        skeleton["label"] = label

    return skeleton


def text_to_skeleton(text_entry):
    """Convert a YAML text to an Excalidraw skeleton element."""
    x, y, _, _ = parse_pos(text_entry['pos'])
    color = text_entry.get('color', {})

    return {
        "type": "text",
        "x": x, "y": y,
        "text": text_entry["text"],
        "fontSize": text_entry.get("fontSize", TEXT_DEFAULTS["fontSize"]),
        "fontFamily": resolve_font_family(text_entry.get("fontFamily", TEXT_DEFAULTS["fontFamily"])),
        "strokeColor": color.get("stroke", "#1e1e1e"),
    }


def connector_to_skeleton(connector, shapes_lookup):
    """Convert a YAML connector to an Excalidraw skeleton element."""
    from_shape = shapes_lookup[connector["from"]]
    to_shape = shapes_lookup[connector["to"]]
    geom = compute_arrow(from_shape, to_shape)
    color = connector.get('color', {})
    style = connector.get('style', {})

    skeleton = {
        "type": connector["type"],
        "x": geom["x"], "y": geom["y"],
        "width": geom["width"], "height": geom["height"],
        "points": geom["points"],
        "strokeColor": color.get("stroke", "#1e1e1e"),
        "strokeWidth": style.get("strokeWidth", 2),
        "strokeStyle": style.get("strokeStyle", "solid"),
        "startArrowhead": connector.get("startArrowhead", None),
        "endArrowhead": connector.get("endArrowhead",
                                       "arrow" if connector["type"] == "arrow" else None),
    }

    if connector.get("label"):
        skeleton["label"] = {
            "text": connector["label"],
            "fontFamily": resolve_font_family(connector.get("fontFamily", LABEL_DEFAULTS["fontFamily"])),
        }

    return skeleton


# ============ Arrow Geometry ============

def clip_to_rect(cx, cy, tx, ty, rx, ry, rw, rh, pad=5):
    """Find where ray from (cx,cy) toward (tx,ty) exits rectangle + padding."""
    dx = tx - cx
    dy = ty - cy

    if dx == 0 and dy == 0:
        return cx, cy

    candidates = []

    # Right edge
    if dx > 0:
        t = (rx + rw + pad - cx) / dx
        y_at = cy + t * dy
        if ry - pad <= y_at <= ry + rh + pad:
            candidates.append((t, rx + rw + pad, y_at))

    # Left edge
    if dx < 0:
        t = (rx - pad - cx) / dx
        y_at = cy + t * dy
        if ry - pad <= y_at <= ry + rh + pad:
            candidates.append((t, rx - pad, y_at))

    # Bottom edge
    if dy > 0:
        t = (ry + rh + pad - cy) / dy
        x_at = cx + t * dx
        if rx - pad <= x_at <= rx + rw + pad:
            candidates.append((t, x_at, ry + rh + pad))

    # Top edge
    if dy < 0:
        t = (ry - pad - cy) / dy
        x_at = cx + t * dx
        if rx - pad <= x_at <= rx + rw + pad:
            candidates.append((t, x_at, ry - pad))

    if not candidates:
        return cx, cy

    candidates.sort(key=lambda c: c[0])
    _, x, y = candidates[0]
    return x, y


def compute_arrow(from_shape, to_shape):
    """Compute arrow geometry between two shapes (center-to-center, edge-clipped)."""
    fx, fy, fw, fh = parse_pos(from_shape['pos'])
    tx, ty, tw, th = parse_pos(to_shape['pos'])

    # Centers
    fcx, fcy = fx + fw / 2, fy + fh / 2
    tcx, tcy = tx + tw / 2, ty + th / 2

    # Clip to edges
    sx, sy = clip_to_rect(fcx, fcy, tcx, tcy, fx, fy, fw, fh)
    ex, ey = clip_to_rect(tcx, tcy, fcx, fcy, tx, ty, tw, th)

    return {
        "x": sx,
        "y": sy,
        "width": abs(ex - sx),
        "height": abs(ey - sy),
        "points": [[0, 0], [ex - sx, ey - sy]],
    }


# ============ State Management ============

def state_path_for(yaml_path):
    """Return the .state.json path for a given YAML file."""
    p = Path(yaml_path)
    return p.parent / f"{p.stem}.state.json"


def load_state(yaml_path):
    """Load state file, or return empty state."""
    sp = state_path_for(yaml_path)
    if sp.exists():
        return json.loads(sp.read_text())
    return {"version": 1, "pushed_at": None, "mappings": {}}


def save_state(yaml_path, state):
    """Write state file."""
    state["pushed_at"] = datetime.now(timezone.utc).isoformat()
    sp = state_path_for(yaml_path)
    sp.write_text(json.dumps(state, indent=2))


# ============ Diff ============

def compute_diff(yaml_entries, old_state):
    """Compare YAML entries against state. Returns (to_create, to_update, to_delete, unchanged).

    Each entry in to_create/to_update is (yaml_id, yaml_entry, hash).
    to_delete is a list of (yaml_id, excalidraw_id).
    unchanged is a list of yaml_id.
    """
    mappings = old_state.get("mappings", {})
    current_ids = set()

    to_create = []
    to_update = []
    unchanged = []

    for yaml_id, entry in yaml_entries.items():
        current_ids.add(yaml_id)
        h = compute_hash(entry)

        if yaml_id not in mappings:
            to_create.append((yaml_id, entry, h))
        elif mappings[yaml_id]["hash"] != h:
            to_update.append((yaml_id, entry, h))
        else:
            unchanged.append(yaml_id)

    to_delete = [
        (yid, m["excalidraw_id"])
        for yid, m in mappings.items()
        if yid not in current_ids
    ]

    return to_create, to_update, to_delete, unchanged


# ============ Push ============

def push(yaml_path, client, clear=False):
    """Push a YAML diagram spec to the Excalidraw canvas."""
    # Parse YAML
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    shapes, texts, connectors = validate_yaml(data)

    # Build shapes lookup for connector resolution
    shapes_lookup = {s['id']: s for s in shapes}

    # Collect all YAML entries with their IDs
    yaml_entries = {}
    skeletons = {}  # yaml_id -> skeleton element

    for s in shapes:
        yaml_entries[s['id']] = s
        skeletons[s['id']] = shape_to_skeleton(s)

    for t in texts:
        yaml_entries[t['id']] = t
        skeletons[t['id']] = text_to_skeleton(t)

    for c in connectors:
        yaml_entries[c['id']] = c
        skeletons[c['id']] = connector_to_skeleton(c, shapes_lookup)

    if clear:
        # Full clear + recreate
        client.clear()
        all_skeletons = [skeletons[yid] for yid in yaml_entries]
        created = client.create_elements(all_skeletons)

        # Build fresh state
        state = {"version": 1, "mappings": {}}
        yaml_ids = list(yaml_entries.keys())
        for i, yid in enumerate(yaml_ids):
            state["mappings"][yid] = {
                "excalidraw_id": created[i].get("id", ""),
                "hash": compute_hash(yaml_entries[yid]),
            }
        save_state(yaml_path, state)

        print(f"Pushed {yaml_path} (clear mode)")
        print(f"  Created: {len(yaml_entries)}")
        return

    # Incremental push
    old_state = load_state(yaml_path)
    to_create, to_update, to_delete, unchanged = compute_diff(yaml_entries, old_state)

    # Verify unchanged elements still exist on server (stale state detection)
    if unchanged:
        server_ids = {el.get('id') for el in client.get_elements()}
        stale = [yid for yid in unchanged
                 if old_state["mappings"][yid]["excalidraw_id"] not in server_ids]
        if stale:
            print(f"  Stale state detected ({len(stale)} elements missing from server), falling back to full push")
            return push(yaml_path, client, clear=True)

    # Delete removed + modified elements
    for yid, eid in to_delete:
        try:
            client.delete_element(eid)
        except Exception:
            pass  # Already deleted or doesn't exist

    for yid, entry, h in to_update:
        eid = old_state["mappings"][yid]["excalidraw_id"]
        try:
            client.delete_element(eid)
        except Exception:
            pass

    # Create new + modified elements
    to_batch = []
    batch_ids = []
    for yid, entry, h in to_create + to_update:
        to_batch.append(skeletons[yid])
        batch_ids.append((yid, h))

    created = []
    if to_batch:
        created = client.create_elements(to_batch)

    # Build new state
    new_mappings = {}
    # Keep unchanged
    for yid in unchanged:
        new_mappings[yid] = old_state["mappings"][yid]
    # Add newly created
    for i, (yid, h) in enumerate(batch_ids):
        new_mappings[yid] = {
            "excalidraw_id": created[i].get("id", "") if i < len(created) else "",
            "hash": h,
        }

    state = {"version": 1, "mappings": new_mappings}
    save_state(yaml_path, state)

    # Summary
    print(f"Pushed {yaml_path}")
    if to_create:
        print(f"  Created: {len(to_create)} ({', '.join(yid for yid, _, _ in to_create)})")
    if to_update:
        print(f"  Updated: {len(to_update)} ({', '.join(yid for yid, _, _ in to_update)})")
    if to_delete:
        print(f"  Deleted: {len(to_delete)} ({', '.join(yid for yid, _ in to_delete)})")
    if unchanged:
        print(f"  Unchanged: {len(unchanged)}")
