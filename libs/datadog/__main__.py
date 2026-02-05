#!/usr/bin/env python3
"""Datadog CLI - Tools for querying RUM data and creating notebooks.

This CLI provides tools for:
- RUM: Querying Real User Monitoring data using Datadog API
- Notebooks: Creating Datadog notebooks for publishing analytics results
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


def cmd_rum_query(args):
    """Query RUM data using Datadog API."""
    from libs.datadog.query_rum import query_rum_data

    query_rum_data(
        query=args.query,
        from_time=args.from_time,
        to_time=args.to_time,
        limit=args.limit,
        output_file=args.output,
        format=args.format,
        working_folder=args.working_folder
    )


def cmd_rum_aggregate(args):
    """Aggregate RUM data using Datadog API."""
    from libs.datadog.aggregate_rum import aggregate_rum_data

    aggregate_rum_data(
        query=args.query,
        from_time=args.from_time,
        to_time=args.to_time,
        group_by=args.group_by,
        compute_metric=args.metric,
        compute_aggregation=args.aggregation,
        timeseries_interval=args.interval,
        sort_order=args.sort,
        limit=args.limit,
        output_file=args.output,
        working_folder=args.working_folder
    )


def cmd_notebook_create(args):
    """Create a Datadog notebook."""
    from libs.datadog.create_notebook import create_notebook_from_json
    import json
    import sys

    # Read notebook definition from file or stdin
    source_file = args.notebook_file
    if args.notebook_file == '-':
        notebook_json = sys.stdin.read()
        source_file = None
    else:
        with open(args.notebook_file, 'r') as f:
            notebook_json = f.read()

    # Parse JSON
    try:
        notebook_def = json.loads(notebook_json)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in notebook file: {e}", file=sys.stderr)
        sys.exit(1)

    notebook_url = create_notebook_from_json(
        notebook_def=notebook_def,
        source_file=source_file,
        update_source=not args.no_update_file
    )

    # Print URL for easy access
    print(f"\nNotebook created: {notebook_url}")


def cmd_notebook_update(args):
    """Update a Datadog notebook."""
    from libs.datadog.create_notebook import update_notebook_from_json
    import json
    import sys

    # Read notebook definition from file or stdin
    source_file = args.notebook_file
    if args.notebook_file == '-':
        notebook_json = sys.stdin.read()
        source_file = None
    else:
        with open(args.notebook_file, 'r') as f:
            notebook_json = f.read()

    # Parse JSON
    try:
        notebook_def = json.loads(notebook_json)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in notebook file: {e}", file=sys.stderr)
        sys.exit(1)

    notebook_url = update_notebook_from_json(
        notebook_def=notebook_def,
        source_file=source_file
    )

    # Print URL for easy access
    print(f"\nNotebook updated: {notebook_url}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='datadog',
        description='Datadog CLI - Tools for querying RUM data and creating notebooks',
        epilog='For detailed help: datadog rum --help | datadog notebook --help'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # ===== RUM COMMANDS =====
    rum_parser = subparsers.add_parser('rum', help='RUM (Real User Monitoring) commands')
    rum_subparsers = rum_parser.add_subparsers(dest='rum_command', help='RUM subcommands')

    # RUM query command
    rum_query_parser = rum_subparsers.add_parser(
        'query',
        help='Query RUM data using Datadog API',
        description='''Query Real User Monitoring data from Datadog.

ENVIRONMENT VARIABLES REQUIRED:
  DD_API_KEY         Datadog API key
  DD_APP_KEY         Datadog Application key
  DD_SITE            Datadog site (default: datadoghq.com)

QUERY SYNTAX:
  Use Datadog query syntax for filtering RUM events.
  Examples:
    - "@view.name:*checkout*"
    - "@type:action @action.type:click"
    - "service:web-app @view.url_path:/products"

TIME RANGES:
  Specify times as:
    - Relative: "1h", "24h", "7d", "30d"
    - ISO format: "2025-01-01T00:00:00Z"
    - Unix timestamp: "1704067200"

EXAMPLES:
  # Query all RUM views in the last hour
  datadog rum query "@type:view" --from-time 1h --limit 100

  # Query checkout actions in a specific time range
  datadog rum query "@view.name:*checkout* @type:action" \\
    --from-time "2025-01-01T00:00:00Z" \\
    --to-time "2025-01-02T00:00:00Z" \\
    --limit 500 \\
    --output checkout_actions.json

  # Export to CSV for analysis
  datadog rum query "@type:error" \\
    --from-time 24h \\
    --format csv \\
    --output errors.csv
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    rum_query_parser.add_argument('query', help='RUM query string (Datadog query syntax)')
    rum_query_parser.add_argument(
        '--from-time',
        required=True,
        help='Start time (relative: "1h"/"24h"/"7d", ISO: "2025-01-01T00:00:00Z", or Unix timestamp)'
    )
    rum_query_parser.add_argument(
        '--to-time',
        help='End time (default: now). Same formats as --from-time'
    )
    rum_query_parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of results to return (default: 100, max: 1000)'
    )
    rum_query_parser.add_argument(
        '--working-folder',
        metavar='FOLDER',
        help='Working folder name (e.g., "2026-02-03_analysis"). Saves to data/{folder}/datadog/{output}'
    )
    rum_query_parser.add_argument(
        '--output', '-o',
        metavar='FILENAME',
        help='Output filename (e.g., "results.json"). Default: rum_query_TIMESTAMP.json'
    )
    rum_query_parser.add_argument(
        '--format',
        choices=['json', 'csv'],
        default='json',
        help='Output format (default: json)'
    )
    rum_query_parser.set_defaults(func=cmd_rum_query)

    # RUM aggregate command
    rum_aggregate_parser = rum_subparsers.add_parser(
        'aggregate',
        help='Aggregate RUM data for top N and time series analysis',
        description='''Aggregate Real User Monitoring data from Datadog for analytics.

ENVIRONMENT VARIABLES REQUIRED:
  DD_API_KEY         Datadog API key
  DD_APP_KEY         Datadog Application key
  DD_SITE            Datadog site (default: datadoghq.com)

AGGREGATION TYPES:
  Top N Analysis:  Group by facets to get top organizations, countries, pages, etc.
  Time Series:     Use --interval to analyze evolution over time

QUERY SYNTAX:
  Same as RUM query - use Datadog query syntax for filtering RUM events.

EXAMPLES:
  # Top 10 organizations by view count
  datadog rum aggregate "@type:view @session.type:user" \\
    --from-time 7d \\
    --group-by @usr.org_id @usr.org_name \\
    --limit 10

  # Time evolution of checkout page views (hourly)
  datadog rum aggregate "@type:view @view.name:*checkout* @session.type:user" \\
    --from-time 24h \\
    --interval 1h

  # Top 10 countries by average session duration
  datadog rum aggregate "@type:session @session.type:user" \\
    --from-time 30d \\
    --group-by @geo.country \\
    --metric @session.time_spent \\
    --aggregation avg \\
    --limit 10

  # Combined: Top orgs over time (daily buckets)
  datadog rum aggregate "@type:view @session.type:user" \\
    --from-time 30d \\
    --group-by @usr.org_name \\
    --interval 1d \\
    --limit 5
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    rum_aggregate_parser.add_argument('query', help='RUM query string (Datadog query syntax)')
    rum_aggregate_parser.add_argument(
        '--from-time',
        required=True,
        help='Start time (relative: "1h"/"24h"/"7d", ISO: "2025-01-01T00:00:00Z", or Unix timestamp)'
    )
    rum_aggregate_parser.add_argument(
        '--to-time',
        help='End time (default: now). Same formats as --from-time'
    )
    rum_aggregate_parser.add_argument(
        '--group-by',
        nargs='+',
        metavar='FACET',
        help='Facets to group by (e.g., @usr.org_id @usr.org_name @geo.country)'
    )
    rum_aggregate_parser.add_argument(
        '--metric',
        default='count',
        help='Metric to compute (default: "count" for event count, or field like "@view.time_spent")'
    )
    rum_aggregate_parser.add_argument(
        '--aggregation',
        choices=['count', 'cardinality', 'sum', 'avg', 'min', 'max', 'pc75', 'pc90', 'pc95', 'pc98', 'pc99'],
        default='count',
        help='Aggregation function (default: count, use cardinality for unique counts)'
    )
    rum_aggregate_parser.add_argument(
        '--interval',
        help='Time series interval (e.g., "1h", "1d", "5m") - enables time evolution analysis'
    )
    rum_aggregate_parser.add_argument(
        '--sort',
        choices=['desc', 'asc', 'none'],
        default='desc',
        help='Sort order: desc (top N, default), asc (bottom N), none (lexicographic)'
    )
    rum_aggregate_parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum number of groups to return (default: 10)'
    )
    rum_aggregate_parser.add_argument(
        '--working-folder',
        metavar='FOLDER',
        help='Working folder name (e.g., "2026-02-03_analysis"). Saves to data/{folder}/datadog/{output}'
    )
    rum_aggregate_parser.add_argument(
        '--output', '-o',
        metavar='FILENAME',
        help='Output filename (e.g., "results.json"). Default: rum_aggregate_TIMESTAMP.json'
    )
    rum_aggregate_parser.set_defaults(func=cmd_rum_aggregate)

    # ===== NOTEBOOK COMMANDS =====
    notebook_parser = subparsers.add_parser('notebook', help='Notebook commands')
    notebook_subparsers = notebook_parser.add_subparsers(dest='notebook_command', help='Notebook subcommands')

    # Notebook create command
    notebook_create_parser = notebook_subparsers.add_parser(
        'create',
        help='Create a Datadog notebook from JSON definition',
        description='''Create a Datadog notebook using the standard Datadog API format.

ENVIRONMENT VARIABLES REQUIRED:
  DD_API_KEY         Datadog API key
  DD_APP_KEY         Datadog Application key
  DD_SITE            Datadog site (default: datadoghq.com)

NOTEBOOK FORMAT:
  Uses the standard Datadog Notebooks API format.
  See: https://docs.datadoghq.com/api/latest/notebooks/#create-a-notebook
  See: knowledge/datadog-notebooks.md for examples and reference

EXAMPLES:
  # Create notebook from JSON file
  datadog notebook create notebook.json

  # Create notebook from stdin
  cat notebook.json | datadog notebook create -

The notebook ID is automatically written back to the source file after creation.

For complete examples, see: knowledge/datadog-notebooks.md
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    notebook_create_parser.add_argument(
        'notebook_file',
        help='Notebook JSON file (use "-" for stdin)'
    )
    notebook_create_parser.add_argument(
        '--no-update-file',
        action='store_true',
        help="Don't update the source file with the notebook ID after creation"
    )
    notebook_create_parser.set_defaults(func=cmd_notebook_create)

    # Notebook update command
    notebook_update_parser = notebook_subparsers.add_parser(
        'update',
        help='Update an existing Datadog notebook from JSON definition',
        description='''Update an existing Datadog notebook using the standard Datadog API format.

The notebook JSON must include the notebook ID (data.id) from the create response.

ENVIRONMENT VARIABLES REQUIRED:
  DD_API_KEY         Datadog API key
  DD_APP_KEY         Datadog Application key
  DD_SITE            Datadog site (default: datadoghq.com)

WORKFLOW:
  1. Create notebook: datadog notebook create notebook.json
     → notebook.json is updated with the notebook ID

  2. Edit notebook.json (change cells, title, etc.)

  3. Update notebook: datadog notebook update notebook.json
     → Changes are pushed to Datadog

EXAMPLES:
  # Update notebook from file
  datadog notebook update notebook.json

  # Update notebook from stdin
  cat notebook.json | datadog notebook update -

For complete examples, see: knowledge/datadog-notebooks.md
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    notebook_update_parser.add_argument(
        'notebook_file',
        help='Notebook JSON file with ID (use "-" for stdin)'
    )
    notebook_update_parser.set_defaults(func=cmd_notebook_update)

    # Parse and execute
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Handle subcommands
    if args.command == 'rum' and not hasattr(args, 'func'):
        rum_parser.print_help()
        sys.exit(1)

    if args.command == 'notebook' and not hasattr(args, 'func'):
        notebook_parser.print_help()
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
