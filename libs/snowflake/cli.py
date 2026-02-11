#!/usr/bin/env python3
"""
CLI entry point for Snowflake query execution.

This module provides a unified command-line interface for Snowflake operations.
Supports 'query' and 'discover' commands.

Usage:
    python -m libs.snowflake query <sql-file> [options]
    python -m libs.snowflake discover <subcommand> [options]
    python -m libs.snowflake <sql-file> [options]  # query is implied
"""

import sys
from . import query as query_module
from . import discover as discover_module


def print_help():
    """Print main help message."""
    help_text = """
snowflake - Execute Snowflake queries and explore schemas

Usage:
  snowflake query <sql-file> [options]           - Execute SQL query from file
  snowflake query --sql "SELECT ..." [options]   - Execute inline SQL query
  snowflake discover <subcommand> [options]      - Explore schemas, tables, columns
  snowflake <sql-file> [options]                 - Execute SQL query (query is implied)

Commands:
  query       Execute SQL queries from files or inline
  discover    Explore database schemas and tables

Query Options:
  --sql <query>              Pass SQL query inline (no file needed). Output defaults to tmp/output.csv
  --working-folder <folder>  Working folder name (e.g., "2026-02-03_analysis"). Saves to data/{folder}/snowflake/{output}
  --output <path>            Specify output filename or directory (default: output.csv next to SQL file)
  --limit <N>                Limit results to N rows
  --var-<name> <value>       Set Metabase template variable (e.g., --var-signup_method standard)
  --debug                    Show detailed debug information including SQL content

Discover Subcommands:
  tables <pattern>           Find tables matching pattern
  columns --table <name>     Show columns and top values
  preview --table <name>     Quick data preview
  schemas                    List accessible databases/schemas

Examples:
  # Execute a query with default CSV output
  snowflake query analysis.sql

  # Execute inline SQL
  snowflake query --sql "SELECT COUNT(*) FROM REPORTING.GENERAL.DIM_MONITOR"

  # Find tables with "monitor" in the name
  snowflake discover tables monitor

  # Get column details for a specific table
  snowflake discover columns --table REPORTING.GENERAL.DIM_MONITOR

  # Preview data from a table
  snowflake discover preview --table REPORTING.GENERAL.DIM_ORG --limit 5

  # List all accessible schemas
  snowflake discover schemas

  # Execute with template variables
  snowflake query analysis.sql --var-signup_method standard --var-datacenter us1

Template Variables:
  Queries can use Metabase-style template variables:

  Optional filters (removed if variable not provided):
    [[ AND column = {{variable}} ]]

  Required variables (error if not provided):
    WHERE column = {{variable}}

  Use --var-<name> to provide values for local execution.

For more details:
  snowflake query --help
  snowflake discover --help
"""
    print(help_text)


def main():
    """Main CLI entry point."""
    
    # If no arguments or help requested, show help
    if len(sys.argv) == 1 or sys.argv[1] in ['-h', '--help', 'help']:
        print_help()
        sys.exit(0)
    
    # Get the first argument
    first_arg = sys.argv[1]
    
    # Route based on command
    if first_arg == 'query':
        # Remove 'query' from argv and call query.main()
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        query_module.main()

    elif first_arg == 'discover':
        # Remove 'discover' from argv and call discover.main()
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        discover_module.main()

    # If first arg is --sql, treat as implicit 'query' command with inline SQL
    elif first_arg == '--sql':
        query_module.main()

    # If first arg looks like a file path (not a known command), assume it's a query
    elif first_arg.endswith('.sql') or first_arg.startswith('.') or first_arg.startswith('/') or '/' in first_arg:
        # Treat as implicit 'query' command
        query_module.main()

    else:
        print(f"Error: Unknown command or invalid file path '{first_arg}'", file=sys.stderr)
        print("", file=sys.stderr)
        print("Expected either:", file=sys.stderr)
        print("  - 'query' command: snowflake query <sql-file> [options]", file=sys.stderr)
        print("  - 'discover' command: snowflake discover <subcommand> [options]", file=sys.stderr)
        print("  - SQL file path: snowflake <sql-file> [options]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Use --help for more information.", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

