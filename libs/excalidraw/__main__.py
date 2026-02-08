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

A YAML diagram has three top-level sections: shapes, texts, connectors.
All sections are optional.

SHAPES
------
  - id: my-shape              # Required. Stable ID for incremental updates
    type: rectangle            # Required. rectangle | ellipse | diamond
    pos: [100, 200, 300x150]   # Required. [x, y, WIDTHxHEIGHT]
    label: "My Label"          # Optional. Bound text inside the shape
    color:                     # Optional
      bg: "#a5d8ff"            #   Background fill color (default: transparent)
      stroke: "#1e1e1e"        #   Border color (default: #1e1e1e)
    style:                     # Optional. Override shape defaults
      fillStyle: solid         #   solid | hachure | cross-hatch (default: solid)
      strokeWidth: 2           #   1 | 2 | 4 (default: 2)
      strokeStyle: solid       #   solid | dashed | dotted (default: solid)
      roughness: 1             #   0 (architect) | 1 (artist) | 2 (cartoonist) (default: 1)
      opacity: 100             #   0-100 (default: 100)
    fontSize: 16               # Optional. Label font size (default: 16)
    fontFamily: Virgil          # Optional. Virgil | Helvetica | Cascadia (default: Virgil)

TEXTS
-----
  - id: title                  # Optional. Auto-generated if omitted
    text: "Architecture"       # Required. Text content
    pos: [200, 30]             # Required. [x, y]
    color:                     # Optional
      stroke: "#1e1e1e"        #   Text color (default: #1e1e1e)
    fontSize: 20               # Optional (default: 20)
    fontFamily: Virgil          # Optional. Virgil | Helvetica | Cascadia (default: Virgil)

CONNECTORS
----------
  - from: shape-a              # Required. Source shape ID
    to: shape-b                # Required. Target shape ID
    id: my-arrow               # Optional. Auto-generated as "{from}-to-{to}"
    type: arrow                # Optional. arrow | line (default: arrow)
    label: "connects"          # Optional. Label on the connector
    endArrowhead: arrow        # Optional. arrow | bar | dot | triangle | none (default: arrow)
    startArrowhead: null       # Optional. Same options (default: none)
    color:                     # Optional
      stroke: "#1e1e1e"        #   Line color (default: #1e1e1e)
    style:                     # Optional
      strokeWidth: 2           #   1 | 2 | 4 (default: 2)
      strokeStyle: solid       #   solid | dashed | dotted (default: solid)

COLORS (common examples)
------
  Light blue:  "#a5d8ff"    Red:     "#ffc9c9"    Green:   "#b2f2bb"
  Yellow:      "#ffec99"    Purple:  "#d0bfff"    Orange:  "#ffd8a8"
  Gray:        "#dee2e6"    Pink:    "#fcc2d7"    Cyan:    "#99e9f2"
  White:       "#ffffff"    Black:   "#1e1e1e"

EXAMPLE
-------
  shapes:
    - id: api
      type: rectangle
      pos: [100, 100, 200x80]
      label: "API Gateway"
      color: {bg: "#a5d8ff"}

    - id: db
      type: rectangle
      pos: [400, 100, 200x80]
      label: "Database"
      color: {bg: "#b2f2bb"}
      style: {strokeStyle: dashed}

  texts:
    - text: "System Architecture"
      pos: [250, 20]
      fontSize: 28

  connectors:
    - from: api
      to: db
      label: "queries"
      style: {strokeStyle: dashed}

STATE TRACKING
--------------
  Push creates a .state.json next to the YAML file for incremental updates.
  Only changed elements are re-pushed. Use --clear for a full recreate.
  If the server restarts, stale state is auto-detected and triggers a full push.""")


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
