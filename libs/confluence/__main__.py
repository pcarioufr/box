#!/usr/bin/env python3
"""Confluence CLI - Sync and download Confluence pages.

Commands:
- list: List all Confluence entries in sync.yaml
- add: Add a new Confluence page to sync
- remove: Remove a Confluence page from sync
- refresh: Show entries that need syncing (actual sync via MCP)
- download: Download a page or blog post directly via REST API
- clean: Clean Confluence markdown by removing custom tags
"""

import argparse
import sys
import os

from libs.common.config import (
    load_config,
    save_config,
    extract_confluence_page_id,
    get_confluence_output_path,
)
from libs.confluence.sync import (
    list_entries,
    register_page,
    suggest_name_from_url,
    parse_url,
)
from libs.confluence.api import detect_content_type


# --- CLI Commands ---

def cmd_list(args):
    """List all Confluence entries."""
    entries = list_entries()

    if not entries:
        print("No Confluence pages configured.")
        print("\nAdd entries with:")
        print("  ./box.sh confluence add <url> --name <name>")
        return

    print("Confluence Pages:")
    print("-" * 60)
    for entry in entries:
        output_path = get_confluence_output_path(entry["name"])
        exists = "✓" if output_path.exists() else "✗"
        print(f"  [{exists}] {entry['name']}")
        print(f"      URL: {entry['url'][:60]}...")
        print(f"      Output: data/_confluence/{entry['name']}.md")
    print()
    print(f"Total: {len(entries)} page(s)")


def cmd_add(args):
    """Add a Confluence page to sync config."""
    page_id = extract_confluence_page_id(args.url)
    if not page_id:
        print(f"Error: Could not extract page ID from: {args.url}", file=sys.stderr)
        sys.exit(1)

    name = args.name or suggest_name_from_url(args.url)
    entry, is_new = register_page(args.url, name)

    action = "Added" if is_new else "Already exists"
    print(f"{action}: {entry['name']}")
    print(f"  URL: {entry['url']}")
    print(f"  Output: data/_confluence/{entry['name']}.md")


def cmd_remove(args):
    """Remove a Confluence page from sync config."""
    config = load_config()
    entries = config.get("confluence", [])

    matching = [e for e in entries if e.get("name") == args.name]

    if not matching:
        print(f"Error: No entry found with name: {args.name}", file=sys.stderr)
        sys.exit(1)

    for entry in matching:
        entries.remove(entry)
        print(f"Removed: {entry['name']}")

    config["confluence"] = entries
    save_config(config)


def cmd_refresh(args):
    """Show Confluence entries that need syncing."""
    entries = list_entries()

    if not entries:
        print("No Confluence entries to sync.")
        print("Add entries with: ./box.sh confluence add <url> --name <name>")
        return

    if args.name:
        entries = [e for e in entries if e.get("name") == args.name]
        if not entries:
            print(f"Error: No entry found with name: {args.name}", file=sys.stderr)
            sys.exit(1)

    print(f"Confluence entries to sync ({len(entries)}):")
    print()

    for entry in entries:
        output_path = get_confluence_output_path(entry["name"])
        exists = "exists" if output_path.exists() else "missing"
        cloud_id, page_id, _ = parse_url(entry["url"])

        print(f"  {entry['name']} ({exists})")
        print(f"    Cloud ID: {cloud_id}")
        print(f"    Page ID: {page_id}")
        print(f"    Output: data/_confluence/{entry['name']}.md")
        print()

    print("Note: Use '/confluence refresh' in Claude to sync via MCP.")


def cmd_download(args):
    """Download Confluence content via REST API."""
    from libs.confluence.api import download_content

    # Determine name
    name = args.name or suggest_name_from_url(args.url)
    content_type = detect_content_type(args.url)

    print(f"Downloading {content_type}: {args.url}")
    print(f"Output name: {name}")

    try:
        output_path, title = download_content(
            url=args.url,
            name=name,
            as_markdown=not args.raw
        )
        print(f"✓ Downloaded: {title}")
        print(f"  Saved to: {output_path}")

        if args.add_to_sync:
            register_page(args.url, name)
            print(f"  Added to sync.yaml")

    except Exception as e:
        print(f"Error downloading: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_clean(args):
    """Clean Confluence markdown by removing custom tags."""
    from libs.confluence.clean import clean_file

    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)

    output_path = clean_file(
        input_file=args.input_file,
        output_file=args.output,
        in_place=args.in_place
    )
    print(f"✓ Cleaned markdown saved to: {output_path}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='confluence',
        description='Confluence CLI - Sync and download Confluence pages',
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # List command
    list_parser = subparsers.add_parser('list', help='List all Confluence entries')
    list_parser.set_defaults(func=cmd_list)

    # Add command
    add_parser = subparsers.add_parser('add', help='Add a Confluence page to sync')
    add_parser.add_argument('url', help='Confluence page URL')
    add_parser.add_argument('--name', '-n', help='Name for the synced file (without .md)')
    add_parser.set_defaults(func=cmd_add)

    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove a Confluence page from sync')
    remove_parser.add_argument('name', help='Entry name')
    remove_parser.set_defaults(func=cmd_remove)

    # Refresh command
    refresh_parser = subparsers.add_parser('refresh', help='Show entries that need syncing')
    refresh_parser.add_argument('--name', '-n', help='Sync only a specific entry')
    refresh_parser.set_defaults(func=cmd_refresh)

    # Download command
    download_parser = subparsers.add_parser(
        'download',
        help='Download a page or blog post via REST API',
        description='''Download Confluence content directly via REST API.

This command uses the Confluence REST API v2 directly, enabling access to
both regular pages AND blog posts with proper authentication.

Requires ATLASSIAN_EMAIL and ATLASSIAN_TOKEN in .env file.

EXAMPLES:
  confluence download "https://example.atlassian.net/wiki/spaces/SPACE/pages/123/Title" --name my-page
  confluence download "https://example.atlassian.net/wiki/spaces/~/blog/2024/01/01/456/Blog+Title" --name my-blog
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    download_parser.add_argument('url', help='Confluence page or blog post URL')
    download_parser.add_argument('--name', '-n', help='Name for the output file (without .md)')
    download_parser.add_argument('--raw', action='store_true', help='Save raw storage format instead of markdown')
    download_parser.add_argument('--add-to-sync', action='store_true', help='Also add to sync.yaml')
    download_parser.set_defaults(func=cmd_download)

    # Clean command
    clean_parser = subparsers.add_parser(
        'clean',
        help='Clean Confluence markdown by removing custom tags',
        description='''Clean Confluence markdown exports by removing custom tags.

Confluence markdown exports contain custom XML-like tags that need cleanup:
  - <custom data-type="emoji">:emoji:</custom> → :emoji:
  - <custom data-type="smartlink">URL</custom> → [URL](URL)
  - <custom data-type="mention">@Name</custom> → @Name
  - ![](blob:...) → *[Image: broken blob reference removed]*

EXAMPLES:
  confluence clean input.md                    # Creates input.cleaned.md
  confluence clean input.md -o output.md       # Creates output.md
  confluence clean input.md --in-place         # Overwrites input.md
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    clean_parser.add_argument('input_file', help='Input markdown file to clean')
    clean_parser.add_argument('-o', '--output', help='Output filename')
    clean_parser.add_argument('--in-place', action='store_true', help='Overwrite the input file')
    clean_parser.set_defaults(func=cmd_clean)

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
