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


def generate_group_id(group_yaml_id):
    """Generate stable Excalidraw groupId from YAML group id."""
    return hashlib.sha256(group_yaml_id.encode()).hexdigest()[:16]


def compute_hash(entry, group_info=None):
    """Hash a YAML entry for change detection.

    Args:
        entry: The YAML entry dict
        group_info: Optional (group_yaml_id, offset_x, offset_y, excalidraw_group_id) tuple if element belongs to a group
    """
    # Include group information in hash so moving a group triggers updates
    hash_data = entry.copy()
    if group_info:
        hash_data['_group_'] = {
            'id': group_info[0],
            'x': group_info[1],
            'y': group_info[2]
        }

    canonical = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def validate_yaml(data):
    """Validate YAML structure and return all entries with IDs, plus groups.

    Supports hierarchical format where shapes can contain groups with nested shapes.
    """
    shapes_raw = data.get('shapes', [])
    connectors = data.get('connectors', [])

    # Collect all shapes (including nested ones from groups) and build group_map
    shapes = []  # All shapes (flattened, includes texts)
    shape_ids = set()
    group_map = {}  # element_id -> (group_yaml_id, group_offset_x, group_offset_y, excalidraw_group_id)

    text_counter = 0  # For auto-generating text IDs

    def process_element(elem, group_context=None):
        """Process a shape element, which could be a regular shape, text, or group."""
        nonlocal text_counter

        elem_type = elem.get('type')

        if elem_type == 'group':
            # Process group and its nested shapes
            if group_context is not None:
                raise ValueError(f"Nested groups are not allowed (found group inside group)")

            if 'id' not in elem:
                raise ValueError(f"Group missing 'id': {elem}")
            if 'pos' not in elem:
                raise ValueError(f"Group '{elem['id']}' missing 'pos'")
            if 'shapes' not in elem:
                raise ValueError(f"Group '{elem['id']}' missing 'shapes' array")

            group_id = elem['id']
            gx, gy = int(elem['pos'][0]), int(elem['pos'][1])
            excalidraw_group_id = generate_group_id(group_id)

            # Get group's z-index (if any)
            group_z = elem.get('z', 0)

            # Process nested shapes within group
            for nested in elem['shapes']:
                # Inherit group's z-index if nested element doesn't have its own
                if 'z' not in nested:
                    nested['z'] = group_z
                process_element(nested, group_context=(group_id, gx, gy, excalidraw_group_id))

        else:
            # Regular shape or text
            if 'type' not in elem:
                raise ValueError(f"Element missing 'type': {elem}")

            # Auto-generate ID for text elements if missing
            if elem_type == 'text' and 'id' not in elem:
                elem['id'] = f"_text_{text_counter}"
                text_counter += 1

            if 'id' not in elem:
                raise ValueError(f"Shape missing 'id': {elem}")

            elem_id = elem['id']

            if elem_id in shape_ids:
                raise ValueError(f"Duplicate element ID: '{elem_id}'")

            # Validate required fields
            if elem_type == 'text':
                if 'text' not in elem:
                    raise ValueError(f"Text element '{elem_id}' missing 'text' field")

            if 'pos' not in elem:
                raise ValueError(f"Element '{elem_id}' missing 'pos'")

            shape_ids.add(elem_id)
            shapes.append(elem)

            # If this element is inside a group, add to group_map
            if group_context is not None:
                if elem_id in group_map:
                    raise ValueError(f"Element '{elem_id}' belongs to multiple groups")
                group_map[elem_id] = group_context

    # Process all top-level shapes
    for elem in shapes_raw:
        process_element(elem)

    # Validate connectors
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

    return shapes, connectors, group_map


# ============ Skeleton Conversion ============

def shape_to_skeleton(shape, group_map=None):
    """Convert a YAML shape to an Excalidraw skeleton element."""
    x, y, w, h = parse_pos(shape['pos'])

    # Apply group offset and groupIds if element belongs to a group
    excalidraw_group_id = None
    if group_map and shape['id'] in group_map:
        _, gx, gy, excalidraw_group_id = group_map[shape['id']]
        x += gx
        y += gy

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

    # Add Excalidraw native groupIds
    if excalidraw_group_id:
        skeleton["groupIds"] = [excalidraw_group_id]

    if shape.get("label"):
        label = {"text": shape["label"]}
        label["fontSize"] = shape.get("fontSize", LABEL_DEFAULTS["fontSize"])
        label["fontFamily"] = resolve_font_family(shape.get("fontFamily", LABEL_DEFAULTS["fontFamily"]))
        skeleton["label"] = label

    return skeleton


def text_to_skeleton(text_entry, group_map=None):
    """Convert a YAML text to an Excalidraw skeleton element."""
    x, y, _, _ = parse_pos(text_entry['pos'])

    # Apply group offset and groupIds if element belongs to a group
    excalidraw_group_id = None
    if group_map and text_entry['id'] in group_map:
        _, gx, gy, excalidraw_group_id = group_map[text_entry['id']]
        x += gx
        y += gy

    color = text_entry.get('color', {})

    skeleton = {
        "type": "text",
        "x": x, "y": y,
        "text": text_entry["text"],
        "fontSize": text_entry.get("fontSize", TEXT_DEFAULTS["fontSize"]),
        "fontFamily": resolve_font_family(text_entry.get("fontFamily", TEXT_DEFAULTS["fontFamily"])),
        "strokeColor": color.get("stroke", "#1e1e1e"),
    }

    # Add Excalidraw native groupIds
    if excalidraw_group_id:
        skeleton["groupIds"] = [excalidraw_group_id]

    return skeleton


def connector_to_skeleton(connector, shapes_lookup, group_map=None):
    """Convert a YAML connector to an Excalidraw skeleton element."""
    from_shape = shapes_lookup[connector["from"]]
    to_shape = shapes_lookup[connector["to"]]
    geom = compute_arrow(from_shape, to_shape, group_map)
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


def compute_arrow(from_shape, to_shape, group_map=None):
    """Compute arrow geometry between two shapes (center-to-center, edge-clipped)."""
    fx, fy, fw, fh = parse_pos(from_shape['pos'])
    tx, ty, tw, th = parse_pos(to_shape['pos'])

    # Apply group offsets
    if group_map and from_shape['id'] in group_map:
        _, gx, gy, _ = group_map[from_shape['id']]  # Unpack 4 elements now
        fx += gx
        fy += gy

    if group_map and to_shape['id'] in group_map:
        _, gx, gy, _ = group_map[to_shape['id']]  # Unpack 4 elements now
        tx += gx
        ty += gy

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

def compute_diff(yaml_entries, old_state, group_map):
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
        group_info = group_map.get(yaml_id)
        h = compute_hash(entry, group_info)

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

    shapes, connectors, group_map = validate_yaml(data)

    # Build shapes lookup for connector resolution
    shapes_lookup = {s['id']: s for s in shapes}

    # Sort shapes by z-index (lower z first, higher z drawn on top)
    # Elements without z-index default to 0
    # Stable sort preserves YAML order within same z-index
    def get_z_index(shape):
        return shape.get('z', 0)

    shapes_sorted = sorted(enumerate(shapes), key=lambda x: (get_z_index(x[1]), x[0]))

    # Collect all YAML entries with their IDs (in z-index order)
    yaml_entries = {}
    skeletons = {}  # yaml_id -> skeleton element

    for _, s in shapes_sorted:
        yaml_entries[s['id']] = s
        # Use appropriate skeleton function based on type
        if s['type'] == 'text':
            skeletons[s['id']] = text_to_skeleton(s, group_map)
        else:
            skeletons[s['id']] = shape_to_skeleton(s, group_map)

    # Connectors always drawn on top (after all shapes)
    for c in connectors:
        yaml_entries[c['id']] = c
        skeletons[c['id']] = connector_to_skeleton(c, shapes_lookup, group_map)

    if clear:
        # Full clear + recreate
        client.clear()
        # Create elements in z-index order (maintained by yaml_entries ordering)
        yaml_ids = list(yaml_entries.keys())
        all_skeletons = [skeletons[yid] for yid in yaml_ids]
        created = client.create_elements(all_skeletons)

        # Build fresh state
        state = {"version": 1, "mappings": {}}
        for i, yid in enumerate(yaml_ids):
            group_info = group_map.get(yid)
            state["mappings"][yid] = {
                "excalidraw_id": created[i].get("id", ""),
                "hash": compute_hash(yaml_entries[yid], group_info),
            }
        save_state(yaml_path, state)

        print(f"Pushed {yaml_path} (clear mode)")
        print(f"  Created: {len(yaml_entries)}")
        if group_map:
            group_ids = set(g[0] for g in group_map.values())
            print(f"  Groups: {len(group_ids)} ({', '.join(sorted(group_ids))})")
        return

    # Incremental push
    old_state = load_state(yaml_path)
    to_create, to_update, to_delete, unchanged = compute_diff(yaml_entries, old_state, group_map)

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
    if group_map:
        group_ids = set(g[0] for g in group_map.values())
        print(f"  Groups: {len(group_ids)} ({', '.join(sorted(group_ids))})")
