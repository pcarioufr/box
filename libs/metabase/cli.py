#!/usr/bin/env python3
"""
CLI entry point for Metabase integration.

This module provides a unified command-line interface for Metabase operations:
- dashboard: Pull/push dashboards (handles questions and collections automatically)

Usage:
    python -m libs.metabase [--debug] dashboard <pull|push> [options]
"""

import argparse
import json
import sys
import os
import logging
import urllib.error
from pathlib import Path

from .dashboard import Dashboard
from .utils import get_metabase_config, get_state_dir, load_env

# Configure logger
logger = logging.getLogger(__name__)


# =============================================================================
# Dashboard Command Handlers
# =============================================================================

def dashboard_pull(args):
    """Execute dashboard pull subcommand."""
    try:
        dashboard = Dashboard.pull(
            dashboard_id=args.dashboard_id,
            directory=Path(args.dir),
            debug=args.debug
        )
        return 0
    except ValueError as e:
        logger.error(str(e))
        return 1
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP Error: {e.code} - {e.reason}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def dashboard_push(args):
    """Execute dashboard push subcommand."""
    try:
        dashboard = Dashboard.push(
            directory=Path(args.dir),
            collection_id=args.parent if hasattr(args, 'parent') else None,
            database_id=args.database if hasattr(args, 'database') else None,
            debug=args.debug
        )
        return 0
    except ValueError as e:
        logger.error(str(e))
        return 1
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP {e.code}: {e.reason}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1
    except Exception as e:
        logger.error(f"Failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


# =============================================================================
# CLI Setup and Routing
# =============================================================================

def dashboard_format(args):
    """Show dashboard YAML format help."""
    format_help = """
Dashboard YAML Format
=====================

Basic Structure:
```yaml
dashboard:
  name: "Dashboard Title"
  width: full                    # or "fixed"
  description: "Optional description"
  tabs:
    - name: Overview
      position: 0
      cards:
        # Text card (virtual_card)
        - position: {row: 0, col: 0, size_x: 24, size_y: 2}
          virtual_card:
            display: text
            text: |
              # Section Title
              Description text here
        
        # Chart card (references question file)
        - position: {row: 2, col: 0, size_x: 12, size_y: 8}
          question_file: my-question.yaml  # relative path
```

Key Points:
-----------
• question_file: Path relative to dashboard.yaml
• position: MUST be nested object {row, col, size_x, size_y}
• Grid: 24 columns wide, rows auto-expand
• virtual_card: For text/headings without saved questions
• Tabs are optional (can have flat card list)

Best Practices:
---------------
• Use tabs by theme: Overview, Analysis, Deep Dive
• Add text cards (virtual_card) for context and interpretation
• Reference questions via question_file (not inline definitions)
• One dashboard per investigation

See libs/metabase/model.md for complete reference.
"""
    print(format_help)
    return 0


def question_format(args):
    """Show question YAML format help."""
    format_help = """
Question YAML Format
====================

Basic Structure:
```yaml
question:
  name: "Question Title"
  description: "Optional description"
  display: table                 # or: bar, line, pie, row, area, scalar, etc.
  sql: my-query.sql             # relative path to SQL file
  
  # Optional: Query parameters (for SQL template tags)
  parameters:
    date_range:
      type: date/range
      display_name: "Date Range"
      default: "past30days"
  
  # Optional: Visualization settings
  visualization_settings:
    graph.dimensions: [dimension_col]
    graph.metrics: [metric_col]
```

Common Display Types:
--------------------
• table     - Data table
• bar       - Bar chart
• line      - Line chart
• pie       - Pie chart
• row       - Horizontal bar
• area      - Area chart
• scalar    - Single number
• funnel    - Funnel chart

SQL File:
---------
• Must be separate .sql file (no inline SQL)
• Path relative to question YAML
• Can use template tags: {{parameter_name}}

Best Practices:
---------------
• Test SQL first: ./run.sh snowflake <file>.sql
• Use descriptive names that explain the insight
• Keep SQL queries focused and well-commented

See libs/metabase/model.md for complete reference.
"""
    print(format_help)
    return 0


def setup_dashboard_parser(subparsers, common_parser):
    """Setup dashboard command parsers."""
    dashboard_parser = subparsers.add_parser(
        'dashboard',
        help='Dashboard operations (pull, push, format)'
    )
    dashboard_subparsers = dashboard_parser.add_subparsers(dest='subcommand', help='Dashboard subcommands')
    
    # Dashboard pull
    pull_parser = dashboard_subparsers.add_parser(
        'pull',
        parents=[common_parser],
        help='Pull dashboard from Metabase (download to directory)'
    )
    pull_parser.add_argument("dashboard_id", type=int, help="Dashboard ID to pull")
    pull_parser.add_argument("--dir", type=str, required=True, help="Target directory (will be created if missing)")
    pull_parser.set_defaults(func=dashboard_pull)
    
    # Dashboard push
    # Load env to get default parent collection ID
    load_env()
    default_parent = os.getenv("METABASE_COLLECTION_ID")
    default_parent_int = int(default_parent) if default_parent and default_parent.isdigit() else None

    if default_parent_int:
        parent_help = f"Parent collection ID [env: METABASE_COLLECTION_ID={default_parent_int}]"
    else:
        parent_help = "Parent collection ID [env: METABASE_COLLECTION_ID, required for new dashboards]"

    default_database = os.getenv("METABASE_DATABASE_ID")
    default_database_int = int(default_database) if default_database and default_database.isdigit() else None

    if default_database_int:
        database_help = f"Database ID [env: METABASE_DATABASE_ID={default_database_int}]"
    else:
        database_help = "Database ID [env: METABASE_DATABASE_ID, required for new dashboards]"
    
    push_parser = dashboard_subparsers.add_parser(
        'push',
        parents=[common_parser],
        help='Push dashboard to Metabase (create or update)'
    )
    push_parser.add_argument("--dir", type=str, required=True, help="Dashboard directory (must exist)")
    push_parser.add_argument(
        "--parent",
        type=int,
        default=default_parent_int,
        help=parent_help
    )
    push_parser.add_argument(
        "--database",
        type=int,
        default=default_database_int,
        help=database_help
    )
    push_parser.set_defaults(func=dashboard_push)
    
    # Dashboard format
    format_parser = dashboard_subparsers.add_parser(
        'format',
        help='Show dashboard YAML format help'
    )
    format_parser.set_defaults(func=dashboard_format)


def setup_question_parser(subparsers, common_parser):
    """Setup question command parsers."""
    question_parser = subparsers.add_parser(
        'question',
        help='Question format reference'
    )
    question_subparsers = question_parser.add_subparsers(dest='subcommand', help='Question subcommands')
    
    # Question format
    format_parser = question_subparsers.add_parser(
        'format',
        help='Show question YAML format help'
    )
    format_parser.set_defaults(func=question_format)


def main():
    """Main CLI entry point."""
    # Setup main parser
    parser = argparse.ArgumentParser(
        prog='metabase',
        description='Metabase integration for dashboards',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global options
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    # Common parser for shared arguments (inherited by subcommands)
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    # Setup subcommands
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    setup_dashboard_parser(subparsers, common_parser)
    setup_question_parser(subparsers, common_parser)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Show help if no command specified
    if not args.command:
        parser.print_help()
        return 0
    
    # Configure logging based on debug flag
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(message)s'
    )
    
    # Execute command
    try:
        if hasattr(args, 'func'):
            return args.func(args)
        else:
            # Subcommand parser exists but no subcommand given
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
