#!/usr/bin/env python3
"""Excalidraw CLI - Tools for interacting with the Excalidraw Canvas Server.

This CLI provides tools for:
- Pushing declarative YAML diagrams to the canvas
- Querying elements on the canvas (debug)
- Health check and canvas clearing
"""

import argparse
import json
import sys


def cmd_health(args):
    """Check canvas server health."""
    from libs.excalidraw.api import get_client

    client = get_client(args.url)
    try:
        health = client.health()
        print(f"Status: {health.get('status', 'unknown')}")
        print(f"Elements: {health.get('elements_count', 0)}")
        print(f"WebSocket clients: {health.get('websocket_clients', 0)}")
    except Exception as e:
        print(f"Error: Cannot connect to canvas server at {args.url}", file=sys.stderr)
        print(f"       Make sure to run: ./box.sh draw", file=sys.stderr)
        sys.exit(1)


def cmd_query(args):
    """Query elements on the canvas."""
    from libs.excalidraw.api import get_client

    client = get_client(args.url)
    elements = client.get_elements()

    if args.format == 'json':
        print(json.dumps(elements, indent=2))
    else:
        if not elements:
            print("Canvas is empty")
        else:
            print(f"Found {len(elements)} elements:\n")
            for el in elements:
                el_type = el.get('type', 'unknown')
                el_id = el.get('id', 'N/A')[:12]
                x, y = el.get('x', 0), el.get('y', 0)
                text = el.get('text', '')
                if text:
                    print(f"  [{el_type}] {el_id}  ({x}, {y})  \"{text[:30]}...\"" if len(text) > 30 else f"  [{el_type}] {el_id}  ({x}, {y})  \"{text}\"")
                else:
                    print(f"  [{el_type}] {el_id}  ({x}, {y})")


def cmd_push(args):
    """Push a YAML diagram spec to the canvas."""
    from libs.excalidraw.api import get_client
    from libs.excalidraw.push import push

    client = get_client(args.url)
    try:
        push(args.file, client, clear=args.clear)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_clear(args):
    """Clear all elements from the canvas."""
    from libs.excalidraw.api import get_client

    client = get_client(args.url)
    count = client.clear()
    print(f"Cleared {count} elements from canvas")


def cmd_yaml(args):
    """Print YAML format reference."""
    print("""YAML Diagram Format Reference
=============================

Hierarchical format where structure reflects nesting. A diagram has two sections:
shapes (everything visual) and connectors (arrows/lines between shapes).

STRUCTURE
---------
  shapes:       # Contains shapes, texts, AND groups
    - ...       # Standalone elements (absolute positions)
    - ...       # Groups with nested elements (relative positions)

  connectors:   # Arrows and lines between shapes
    - ...

═══════════════════════════════════════════════════════════════════════════

SHAPES - Regular Elements
--------------------------
  - id: my-shape              # Required. Stable ID for updates & connectors
    type: rectangle           # Required. rectangle | ellipse | diamond | text
    pos: [100, 200, 300x150]  # Required. [x, y, WIDTHxHEIGHT] for shapes
                              #           [x, y] for text (no dimensions)
    label: "My Label"         # Optional. Text bound inside shape
    text: "My Text"           # Required for type: text. Text content
    color:                    # Optional
      bg: "#a5d8ff"           #   Background (default: transparent)
      stroke: "#1e1e1e"       #   Border/text color (default: #1e1e1e)
    style:                    # Optional. Override defaults
      fillStyle: solid        #   solid | hachure | cross-hatch (default: solid)
      strokeWidth: 2          #   1 | 2 | 4 (default: 2)
      strokeStyle: solid      #   solid | dashed | dotted (default: solid)
      roughness: 1            #   0 (architect) | 1 (artist) | 2 (cartoonist)
      opacity: 100            #   0-100 (default: 100)
    fontSize: 16              # Optional. Label: 16 (default), Text: 20 (default)
    fontFamily: Virgil        # Optional. Virgil | Helvetica | Cascadia
    z: 0                      # Optional. Z-index for layering (default: 0)
                              #   Lower values drawn first (bottom), higher values on top
                              #   For groups: members inherit group's z-index (unless overridden)

═══════════════════════════════════════════════════════════════════════════

SHAPES - Groups (Hierarchical Nesting)
---------------------------------------
  - type: group               # type: group identifies this as a group
    id: monitor1              # Required. Group ID (used for change tracking)
    pos: [100, 30]            # Required. Group origin (ABSOLUTE position)
    shapes:                   # Required. Nested shapes/texts (RELATIVE positions)
      - id: m1_ok             # Nested shape
        type: rectangle
        pos: [0, 0, 100x24]   # Relative to group position [100, 30]
        color: {bg: "#b2f2bb"}

      - id: m1_label          # Nested text
        type: text
        text: "Monitor 1"
        pos: [-80, 4]         # Relative to group position [100, 30]

GROUPS: Key Concepts
--------------------
  • Groups create native Excalidraw groups (selectable/movable as unit in UI)
  • Nested positions are relative to group origin
  • Change group pos → all members move together
  • Only ONE level of nesting (groups can't contain groups)
  • Members can be shapes OR texts (both use same 'shapes' array)

═══════════════════════════════════════════════════════════════════════════

CONNECTORS
----------
  - from: shape-a             # Required. Source shape ID
    to: shape-b               # Required. Target shape ID
    id: my-arrow              # Optional. Auto-generated as "{from}-to-{to}"
    type: arrow               # Optional. arrow | line (default: arrow)
    label: "connects"         # Optional. Label on the connector
    endArrowhead: arrow       # Optional. arrow | bar | dot | triangle | none
    startArrowhead: null      # Optional. Same options (default: none)
    color:                    # Optional
      stroke: "#1e1e1e"       #   Line color (default: #1e1e1e)
    style:                    # Optional
      strokeWidth: 2          #   1 | 2 | 4 (default: 2)
      strokeStyle: solid      #   solid | dashed | dotted (default: solid)

CONNECTORS: Notes
-----------------
  • Reference shape IDs regardless of nesting (works across groups)
  • Auto-routes from shape center to shape center (edge-clipped)

═══════════════════════════════════════════════════════════════════════════

COLORS (Common Examples)
-------------------------
  Light blue:  "#a5d8ff"    Red:     "#ffc9c9"    Green:   "#b2f2bb"
  Yellow:      "#ffec99"    Purple:  "#d0bfff"    Orange:  "#ffd8a8"
  Gray:        "#dee2e6"    Pink:    "#fcc2d7"    Cyan:    "#99e9f2"
  White:       "#ffffff"    Black:   "#1e1e1e"    Transparent: "transparent"

═══════════════════════════════════════════════════════════════════════════

COMPLETE EXAMPLE
----------------
shapes:
  # Standalone shape (absolute position)
  - id: api
    type: rectangle
    pos: [100, 100, 200x80]
    label: "API Gateway"
    color: {bg: "#a5d8ff"}

  # Standalone text (absolute position)
  - id: title
    type: text
    text: "System Architecture"
    pos: [250, 20]
    fontSize: 28

  # Group with nested shapes (hierarchical)
  - type: group
    id: backend
    pos: [400, 100]
    shapes:
      - id: db
        type: rectangle
        pos: [0, 0, 200x80]      # Renders at [400, 100]
        label: "Database"
        color: {bg: "#b2f2bb"}

      - id: cache
        type: rectangle
        pos: [0, 100, 200x80]    # Renders at [400, 200]
        label: "Cache"
        color: {bg: "#ffec99"}

      - id: backend_label
        type: text
        text: "Backend Cluster"
        pos: [60, -30]           # Renders at [460, 70]
        fontSize: 14

connectors:
  - from: api
    to: db
    label: "queries"
    style: {strokeStyle: dashed}

  - from: api
    to: cache
    type: line

═══════════════════════════════════════════════════════════════════════════

Z-INDEX & LAYERING
------------------
  • Elements are drawn in z-index order: lower values first (bottom), higher on top
  • Default z-index: 0 (if not specified)
  • Elements with same z-index preserve YAML order
  • Connectors always drawn on top of all shapes
  • Groups: Members inherit the group's z-index (unless they specify their own)
    - All members of a group render at the same z-level
    - This includes both shapes AND text elements within the group
    - Use groups to keep related elements (shape + label) at the same z-level

  • Example - Standalone elements:
      - id: background
        type: rectangle
        pos: [0, 0, 500x500]
        color: {bg: "#f0f0f0"}
        z: -1              # Behind everything

      - id: content
        type: rectangle
        pos: [50, 50, 200x200]
        # z: 0 (default)   # Normal layer

      - id: overlay
        type: rectangle
        pos: [100, 100, 100x100]
        z: 10              # On top

  • Example - Groups with z-index (shape + text at same z-level):
      - type: group
        id: card
        pos: [100, 100]
        z: 5               # Entire group at z=5
        shapes:
          - id: card_bg
            type: rectangle
            pos: [0, 0, 200x100]
            color: {bg: "#a5d8ff"}
            # Inherits z=5 from group

          - id: card_label
            type: text
            text: "Card Label"
            pos: [50, 40]
            # Inherits z=5 from group (renders with rectangle, not on top)

═══════════════════════════════════════════════════════════════════════════

STATE TRACKING & INCREMENTAL UPDATES
-------------------------------------
  • Push creates .state.json next to YAML (tracks element hashes & IDs)
  • Only changed elements are re-pushed (efficient incremental updates)
  • Moving a group updates all members (positions include group offset in hash)
  • Use --clear for full recreate (deletes everything, starts fresh)
  • Stale state auto-detected if server restarts (falls back to full push)

═══════════════════════════════════════════════════════════════════════════

WORKFLOW
--------
  1. Write .yaml diagram (shapes, connectors)
  2. ./box.sh draw api push diagram.yaml
  3. View in browser: http://localhost:3000
  4. Edit YAML, push again (only changed elements update)
  5. Changes appear instantly in browser

  Push after EVERY meaningful change (not in batches) so user can see
  diagram evolve in real-time and course-correct early.""")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='excalidraw',
        description='Excalidraw Canvas Server CLI',
        epilog='For detailed help: excalidraw <command> --help'
    )
    parser.add_argument(
        '--url',
        default='http://localhost:3000',
        help='Canvas server URL (default: http://localhost:3000)'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Health command
    health_parser = subparsers.add_parser('health', help='Check canvas server health')
    health_parser.set_defaults(func=cmd_health)

    # Query command
    query_parser = subparsers.add_parser('query', help='Query elements on the canvas')
    query_parser.add_argument(
        '--format', '-f',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    query_parser.set_defaults(func=cmd_query)

    # Push command
    push_parser = subparsers.add_parser(
        'push',
        help='Push a YAML diagram spec to the canvas',
        description='Push a declarative YAML diagram to the Excalidraw canvas. '
                    'Supports incremental updates via .state.json tracking.',
    )
    push_parser.add_argument('file', help='Path to .yaml diagram file')
    push_parser.add_argument('--clear', action='store_true',
                             help='Clear canvas before pushing (full recreate)')
    push_parser.set_defaults(func=cmd_push)

    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear all elements from the canvas')
    clear_parser.set_defaults(func=cmd_clear)

    # YAML format reference
    yaml_parser = subparsers.add_parser(
        'yaml',
        help='Print YAML diagram format reference (all options and examples)',
    )
    yaml_parser.set_defaults(func=cmd_yaml)

    # Parse and execute
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
