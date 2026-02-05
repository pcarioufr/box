#!/usr/bin/env python3
"""Jira CLI - Tools for fetching Jira tickets.

This CLI provides tools for:
- Fetching tickets via REST API v3
- Converting ADF (Atlassian Document Format) to plain text
"""

import argparse
import sys
import logging

# Setup logging
handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[handler],
    force=True
)


def cmd_fetch(args):
    """Fetch Jira tickets using REST API v3."""
    from libs.jira.fetch_tickets import fetch_jira_tickets

    fetch_jira_tickets(
        project=args.project,
        jql=args.jql,
        custom_fields=args.custom_fields,
        max_results=args.max_results,
        output_file=args.output,
        clean_output=args.clean,
        working_folder=args.working_folder
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='jira',
        description='Jira CLI - Fetch and process Jira tickets',
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Fetch command
    fetch_parser = subparsers.add_parser(
        'fetch',
        help='Fetch Jira tickets using REST API v3',
        description='''Fetch Jira tickets from Datadog Jira projects.

MANDATORY FIELDS (always included):
  - Standard: summary, description, created, comment, issuelinks
  - Org fields: customfield_10236 (Org ID), customfield_10237 (Org Name)

COMMON CUSTOM FIELDS (use --custom-fields):
  - customfield_10711: User Story (ADF - rich text)
  - customfield_10713: Current Workaround (ADF - rich text)
  - customfield_19999: Customer Pain Point (ADF - rich text)
  - customfield_19997: Business Impact Context (ADF - rich text)

ENVIRONMENT VARIABLES REQUIRED:
  ATLASSIAN_EMAIL    Your Datadog email address
  ATLASSIAN_TOKEN    Atlassian API token (create at: https://id.atlassian.com/manage-profile/security/api-tokens)

EXAMPLES:
  # Fetch 100 tickets with mandatory fields only
  jira fetch FRMNTS --max-results 100 --output tickets.json

  # Fetch with feature request custom fields and clean output
  jira fetch FRMNTS \\
    --custom-fields customfield_10711 customfield_10713 \\
    --max-results 100 \\
    --clean \\
    --output tickets.json
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    fetch_parser.add_argument('project', help='Jira project key (e.g., FRMNTS)')
    fetch_parser.add_argument('--jql', help='Custom JQL query (default: project = PROJECT ORDER BY created DESC)')
    fetch_parser.add_argument(
        '--custom-fields',
        nargs='+',
        metavar='FIELD',
        help='Additional custom fields to include (e.g., customfield_10711 customfield_10713)'
    )
    fetch_parser.add_argument(
        '--max-results',
        type=int,
        default=100,
        help='Maximum number of results to fetch (default: 100)'
    )
    fetch_parser.add_argument(
        '--working-folder',
        metavar='FOLDER',
        help='Working folder name (e.g., "2026-02-03_analysis"). Saves to data/{folder}/jira/{output}'
    )
    fetch_parser.add_argument(
        '--output', '-o',
        metavar='FILENAME',
        help='Output filename (e.g., "tickets.json", default: tickets.json)'
    )
    fetch_parser.add_argument(
        '--clean',
        action='store_true',
        help='Output clean human-readable format with converted ADF fields and simplified structure'
    )
    fetch_parser.set_defaults(func=cmd_fetch)

    # Parse and execute
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
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
