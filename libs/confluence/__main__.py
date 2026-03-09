#!/usr/bin/env python3
"""Confluence CLI - Pull and clean Confluence pages.

Commands:
- pull: Download a page or blog post as markdown via REST API
- clean: Clean Confluence markdown by removing custom tags
"""

import argparse
import sys
import os

from libs.confluence.api import pull_content, detect_content_type
from libs.confluence.sync import suggest_name_from_url


# --- CLI Commands ---

def cmd_pull(args):
    """Pull Confluence content as markdown."""
    from pathlib import Path

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
