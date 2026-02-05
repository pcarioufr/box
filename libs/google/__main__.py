#!/usr/bin/env python3
"""Google CLI - Sync Google Docs to local markdown.

Browser-based sync flow:
1. CLI opens webhook URL in browser with doc IDs
2. Browser handles Google auth
3. Apps Script converts docs and writes to Drive folder
4. Google Drive app syncs files locally to data/_google/
"""

import argparse
import sys
import webbrowser
from typing import List, Tuple

from libs.common.config import (
    load_config,
    save_config,
    find_google_entry,
    add_google_entry,
    extract_google_doc_id,
    GOOGLE_OUTPUT_DIR,
)


# Webhook URL for the deployed Apps Script
WEBHOOK_URL = "https://script.google.com/a/macros/datadoghq.com/s/AKfycbwXgybo482_Jafzas8SUDGlyndeSi0k5g7DrG0ZEoK9XYruKdyICzIfK9TOsLIggYkDnA/exec"


def list_entries() -> list:
    """List all Google entries from sync config."""
    config = load_config()
    return config.get("google", [])


def register_doc(url_or_id: str) -> Tuple[dict, bool]:
    """Register a Google Doc in sync config."""
    doc_id = extract_google_doc_id(url_or_id)
    if not doc_id:
        raise ValueError(f"Could not extract Google Doc ID from: {url_or_id}")

    config = load_config()
    existing = find_google_entry(config, doc_id)
    is_new = existing is None

    entry = add_google_entry(config, doc_id)
    save_config(config)

    return entry, is_new


def open_sync_in_browser(doc_ids: List[str]) -> str:
    """Open the sync webhook in browser with doc IDs."""
    url = f"{WEBHOOK_URL}?ids={','.join(doc_ids)}"
    webbrowser.open(url)
    return url


def sync_all() -> List[Tuple[str, str]]:
    """Trigger Google sync via browser."""
    config = load_config()
    entries = config.get("google", [])

    if not entries:
        return []

    doc_ids = [e.get("id") for e in entries if e.get("id")]
    if not doc_ids:
        return []

    open_sync_in_browser(doc_ids)
    return [(doc_id, "Browser opened") for doc_id in doc_ids]


# --- CLI Commands ---

def cmd_list(args):
    """List all Google Doc entries."""
    entries = list_entries()

    if not entries:
        print("No Google Docs configured.")
        print("\nAdd entries with:")
        print("  ./box.sh google add <url>")
        return

    print("Google Docs:")
    print("-" * 60)
    for entry in entries:
        doc_id = entry.get("id", "unknown")
        print(f"  ID: {doc_id[:40]}...")
        print(f"      Output: data/_google/{{slug}}.md")
    print()
    print(f"Total: {len(entries)} doc(s)")


def cmd_add(args):
    """Add a Google Doc to sync config."""
    doc_id = extract_google_doc_id(args.url)
    if not doc_id:
        print(f"Error: Could not extract Google Doc ID from: {args.url}", file=sys.stderr)
        sys.exit(1)

    entry, is_new = register_doc(args.url)

    action = "Added" if is_new else "Already exists"
    print(f"{action}: {entry['id'][:40]}...")
    print(f"  Output: data/_google/{{slug-from-doc-title}}.md")


def cmd_remove(args):
    """Remove a Google Doc from sync config."""
    config = load_config()
    entries = config.get("google", [])

    # Match by ID (can be full ID or partial)
    matching = [e for e in entries if args.identifier in e.get("id", "")]

    if not matching:
        print(f"Error: No entry found with ID containing: {args.identifier}", file=sys.stderr)
        sys.exit(1)

    for entry in matching:
        entries.remove(entry)
        print(f"Removed: {entry['id'][:40]}...")

    config["google"] = entries
    save_config(config)


def cmd_refresh(args):
    """Sync all Google Docs via browser."""
    entries = list_entries()

    if not entries:
        print("No Google Docs to sync.")
        print("Add entries with: ./box.sh google add <url>")
        return

    print(f"Opening browser to sync {len(entries)} Google Doc(s)...")
    print()

    results = sync_all()

    print("Doc IDs being synced:")
    for doc_id, status in results:
        print(f"  - {doc_id[:40]}...")

    print()
    print("Next steps:")
    print("  1. Check browser window for sync status")
    print("  2. Wait for Google Drive to sync files locally")
    print("  3. Files will appear in data/_google/ once Drive syncs")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='google',
        description='Google CLI - Sync Google Docs to local markdown',
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # List command
    list_parser = subparsers.add_parser('list', help='List all Google Doc entries')
    list_parser.set_defaults(func=cmd_list)

    # Add command
    add_parser = subparsers.add_parser('add', help='Add a Google Doc to sync')
    add_parser.add_argument('url', help='Google Doc URL or ID')
    add_parser.set_defaults(func=cmd_add)

    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove a Google Doc from sync')
    remove_parser.add_argument('identifier', help='Doc ID (full or partial)')
    remove_parser.set_defaults(func=cmd_remove)

    # Refresh command
    refresh_parser = subparsers.add_parser('refresh', help='Sync all Google Docs via browser')
    refresh_parser.set_defaults(func=cmd_refresh)

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
