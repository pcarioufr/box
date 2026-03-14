#!/usr/bin/env python3
"""Confluence CLI - Pull and clean Confluence pages.

Commands:
- pull: Download a page or blog post as markdown via REST API
- clean: Clean Confluence markdown by removing custom tags
"""

import argparse
import re
import sys
import os
from pathlib import Path

from libs.confluence.api import pull_content, detect_content_type


# --- CLI Commands ---

def cmd_pull(args):
    """Pull Confluence content as markdown."""
    content_type = detect_content_type(args.url)
    print(f"Pulling {content_type}: {args.url}")

    try:
        output_path = pull_content(
            url=args.url,
            output=args.output,
            as_markdown=not args.raw,
        )
        print(f"Saved to {output_path}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def find_confluence_pages(directory: str) -> list[tuple[Path, str]]:
    """Scan directory recursively for .md files with confluence_url in frontmatter.

    Returns list of (file_path, confluence_url) tuples.
    """
    results = []
    for md_file in Path(directory).rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not text.startswith("---"):
            continue
        end = text.find("---", 3)
        if end == -1:
            continue
        frontmatter = text[3:end]
        match = re.search(r'^confluence_url:\s*"?(.+?)"?\s*$', frontmatter, re.MULTILINE)
        if match:
            url = match.group(1).strip()
            results.append((md_file, url))
    return results


def cmd_pull_all(args):
    """Re-pull all Confluence pages found in a directory."""
    directory = args.directory
    if not Path(directory).is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    pages = find_confluence_pages(directory)
    if not pages:
        print(f"No files with confluence_url frontmatter found in {directory}")
        return

    print(f"Found {len(pages)} Confluence page(s) to refresh:")
    for path, url in pages:
        print(f"  {path}")
    print()

    succeeded = 0
    failed = 0
    for path, url in pages:
        print(f"Pulling {path.name}...")
        try:
            pull_content(url=url, output=str(path), as_markdown=True)
            print(f"  Saved to {path}")
            succeeded += 1
        except Exception as e:
            failed += 1
            print(f"  Error: {e}")

    print(f"\nDone: {succeeded} succeeded, {failed} failed")


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
    print(f"Cleaned markdown saved to: {output_path}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='confluence',
        description='Confluence CLI - Pull and clean Confluence pages',
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Pull command
    pull_parser = subparsers.add_parser(
        'pull',
        help='Pull a page or blog post as markdown',
        description='''Pull Confluence content via REST API v2.

Supports both regular pages and blog posts. Output includes YAML
frontmatter with confluence_id for future push support.

Requires ATLASSIAN_EMAIL and ATLASSIAN_TOKEN in .env file.

EXAMPLES:
  confluence pull "https://example.atlassian.net/wiki/spaces/SPACE/pages/123/Title"
  confluence pull "https://example.atlassian.net/wiki/.../pages/123/Title" -o data/project/
  confluence pull "https://example.atlassian.net/wiki/.../pages/123/Title" -o data/project/my-page.md
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    pull_parser.add_argument('url', help='Confluence page or blog post URL')
    pull_parser.add_argument('-o', '--output', default='.', help='Output file path (.md) or directory (default: current dir)')
    pull_parser.add_argument('--raw', action='store_true', help='Save raw storage format instead of markdown')
    pull_parser.set_defaults(func=cmd_pull)

    # Pull-all command
    pull_all_parser = subparsers.add_parser(
        'pull-all',
        help='Re-pull all Confluence pages in a directory',
        description='''Scan a directory recursively for .md files with confluence_url
in their YAML frontmatter, and re-pull each one from Confluence.

Each file is updated in place.

EXAMPLES:
  confluence pull-all data/project/
  confluence pull-all .
''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pull_all_parser.add_argument('directory', help='Directory to scan for Confluence pages')
    pull_all_parser.set_defaults(func=cmd_pull_all)

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
