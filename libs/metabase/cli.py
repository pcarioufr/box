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
import re
import sys
import os
import logging
import urllib.error
from pathlib import Path

import yaml

from .dashboard import Dashboard
from .question import Question
from .utils import get_metabase_config, get_state_dir, load_env, api_request

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
            debug=args.debug,
            question_filter=args.questions if hasattr(args, 'questions') and args.questions else None
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
# Validate Command
# =============================================================================

def dashboard_validate(args):
    """Validate dashboard YAML/SQL files for common issues before pushing."""
    directory = Path(args.dir)
    errors = []
    warnings = []

    # --- Check dashboard.yaml exists ---
    dashboard_yaml_path = directory / "dashboard.yaml"
    if not dashboard_yaml_path.exists():
        errors.append(f"Missing dashboard.yaml in {directory}")
        _print_validation_results(errors, warnings)
        return 1

    with open(dashboard_yaml_path, 'r', encoding='utf-8') as f:
        dashboard_def = yaml.safe_load(f)

    if not dashboard_def or "dashboard" not in dashboard_def:
        errors.append("dashboard.yaml: missing top-level 'dashboard' key")
        _print_validation_results(errors, warnings)
        return 1

    dashboard = dashboard_def["dashboard"]

    # --- Collect all question files referenced by cards ---
    question_files = []
    tabs = dashboard.get("tabs", [])
    flat_cards = dashboard.get("cards", [])

    for tab_idx, tab in enumerate(tabs):
        tab_name = tab.get("name", f"tab {tab_idx}")
        for card_idx, card in enumerate(tab.get("cards", [])):
            if "question_file" in card:
                question_files.append((card["question_file"], f"tab '{tab_name}', card {card_idx}"))
            elif "virtual_card" not in card:
                errors.append(f"tab '{tab_name}', card {card_idx}: missing 'question_file' or 'virtual_card'")

            # Check parameter_mappings reference valid dashboard parameters
            if "parameter_mappings" in card:
                param_ids = {p.get("id") for p in dashboard.get("parameters", [])}
                for mapping in card["parameter_mappings"]:
                    pid = mapping.get("parameter_id")
                    if pid and param_ids and pid not in param_ids:
                        errors.append(
                            f"tab '{tab_name}', card {card_idx}: parameter_mapping references "
                            f"'{pid}' but dashboard only has parameters: {', '.join(sorted(param_ids))}"
                        )

    for card_idx, card in enumerate(flat_cards):
        if "question_file" in card:
            question_files.append((card["question_file"], f"card {card_idx}"))

    # --- Check dashboard parameters ---
    for param in dashboard.get("parameters", []):
        ptype = param.get("type", "")
        default = param.get("default")
        if ptype.startswith("number/") and default is not None and not isinstance(default, list):
            warnings.append(
                f"dashboard parameter '{param.get('id', '?')}': "
                f"type is '{ptype}' but default is scalar ({default}), should be a list like [{default}]"
            )

    # --- Validate each question file ---
    for qfile, location in question_files:
        qpath = directory / qfile
        if not qpath.exists():
            errors.append(f"{location}: question file not found: {qfile}")
            continue

        with open(qpath, 'r', encoding='utf-8') as f:
            qdef = yaml.safe_load(f)

        if not qdef or "question" not in qdef:
            errors.append(f"{qfile}: missing top-level 'question' key")
            continue

        question = qdef["question"]

        # Check SQL file exists
        sql_ref = question.get("sql")
        if not sql_ref:
            errors.append(f"{qfile}: missing 'sql' field")
            continue
        if not sql_ref.endswith('.sql'):
            errors.append(f"{qfile}: sql must reference a .sql file, got: {sql_ref}")
            continue

        sql_path = qpath.parent / sql_ref
        if not sql_path.exists():
            errors.append(f"{qfile}: SQL file not found: {sql_ref}")
            continue

        sql_content = sql_path.read_text()

        # --- SQL gotcha checks ---
        _check_sql_gotchas(sql_content, sql_ref, question, errors, warnings)

    # --- Print results ---
    _print_validation_results(errors, warnings)
    return 1 if errors else 0


def _check_sql_gotchas(sql: str, filename: str, question_yaml: dict, errors: list, warnings: list):
    """Check SQL content for known Metabase/Snowflake gotchas."""

    # 1. Single-escaped regex (backslash-d, backslash-w, etc. without double escape)
    #    Look for \d, \w, \s, \b that are NOT preceded by another backslash
    single_escape = re.findall(r'(?<!\\)\\[dwsbDWSB]\+?', sql)
    if single_escape:
        # Filter out double-escaped ones (already correct)
        truly_single = [m for m in single_escape if not any(
            sql[max(0, sql.index(m)-1)] == '\\' for _ in [None]
        )]
        if truly_single:
            warnings.append(
                f"{filename}: possible single-escaped regex pattern(s): {', '.join(set(truly_single))}. "
                f"Use double backslash (e.g. \\\\d+) — Metabase JSON serialization consumes one layer."
            )

    # 2. TRY_TO_TIMESTAMP or TO_TIMESTAMP with numeric argument
    numeric_ts = re.findall(
        r'(?:TRY_TO_TIMESTAMP|TO_TIMESTAMP)\s*\(\s*(?:TRY_TO_NUMBER|FLOOR|CEIL|ROUND|[A-Z_]+::(?:NUMBER|INTEGER|INT|FLOAT))',
        sql, re.IGNORECASE
    )
    if numeric_ts:
        warnings.append(
            f"{filename}: numeric argument to TRY_TO_TIMESTAMP/TO_TIMESTAMP detected. "
            f"Metabase's JDBC driver rejects this — use DATEADD from epoch instead. "
            f"See model.md 'Snowflake SQL Gotchas' section 2."
        )

    # 3. Template variables without matching YAML parameters
    template_vars = set(re.findall(r'\{\{([^#}][^}]*)\}\}', sql))
    template_vars = {v.strip() for v in template_vars}
    yaml_params = set(question_yaml.get('parameters', {}).keys())
    untyped = template_vars - yaml_params
    if untyped:
        warnings.append(
            f"{filename}: template variable(s) {', '.join(sorted(untyped))} found in SQL "
            f"but not declared in question YAML parameters — they'll default to type 'text'."
        )


def _print_validation_results(errors: list, warnings: list):
    """Print validation results."""
    if not errors and not warnings:
        print("✅ All checks passed")
        return

    for w in warnings:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"❌ {e}")

    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    else:
        print(f"\n0 errors, {len(warnings)} warning(s) — safe to push")


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


def question_move(args):
    """Move a question to a different collection, optionally renaming it."""
    try:
        config = get_metabase_config()

        # Fetch current question to get its name
        url = f"{config['url']}/api/card/{args.question_id}"
        existing = api_request(url, config['api_key'])
        current_name = existing.get("name", f"Question {args.question_id}")
        current_collection = existing.get("collection_id")
        new_name = args.name if args.name else current_name

        # Build minimal payload: just collection_id and name (required by Metabase PUT)
        payload = {
            "name": new_name,
            "collection_id": args.parent,
        }

        put_url = f"{config['url']}/api/card/{args.question_id}"
        api_request(put_url, config['api_key'], method="PUT", data=payload)

        rename_note = f' → "{new_name}"' if new_name != current_name else ""
        print(f"✅ Question {args.question_id}{rename_note}: collection {current_collection} → {args.parent}")
        print(f"   {config['url']}/question/{args.question_id}")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def question_orphans(args):
    """List questions in a collection that are not used by a given dashboard."""
    try:
        config = get_metabase_config()

        # Load state file to get active question IDs
        state_path = Path(args.dashboard_dir) / ".state.yaml"
        if not state_path.exists():
            logger.error(f"No .state.yaml found in {args.dashboard_dir}")
            return 1

        with open(state_path, 'r') as f:
            state = yaml.safe_load(f)

        active_ids = set(int(k) for k in state.get("questions", {}).keys())

        # Fetch all questions in the collection
        url = f"{config['url']}/api/collection/{args.collection}/items?models=card&limit=200"
        response = api_request(url, config['api_key'])
        items = response.get("data", [])

        orphans = [q for q in items if q.get("id") not in active_ids]
        active = [q for q in items if q.get("id") in active_ids]

        print(f"Collection {args.collection}: {len(items)} questions total")
        print(f"  ✅ {len(active)} in use by dashboard {state['dashboard']['id']}")
        print(f"  🗑  {len(orphans)} orphaned\n")

        if orphans:
            print("Orphaned questions (not in dashboard):")
            for q in sorted(orphans, key=lambda x: x.get("id", 0)):
                print(f"  [{q['id']}] {q['name']}")
            print(f"\nTo move all orphans to collection {args.target}:")
            for q in orphans:
                print(f"  ./box.sh metabase question move {q['id']} --parent {args.target}")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


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
    push_parser.add_argument(
        "--question",
        action="append",
        dest="questions",
        metavar="FILE",
        help="Only push this question file (relative to --dir). Repeat to push multiple. Dashboard definition is always pushed."
    )
    push_parser.set_defaults(func=dashboard_push)
    
    # Dashboard validate
    validate_parser = dashboard_subparsers.add_parser(
        'validate',
        help='Validate dashboard YAML/SQL for common issues before pushing'
    )
    validate_parser.add_argument("--dir", type=str, required=True, help="Dashboard directory to validate")
    validate_parser.set_defaults(func=dashboard_validate)

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
        help='Question operations (move, orphans, format)'
    )
    question_subparsers = question_parser.add_subparsers(dest='subcommand', help='Question subcommands')

    # Question move
    move_parser = question_subparsers.add_parser(
        'move',
        parents=[common_parser],
        help='Move a question to a different collection'
    )
    move_parser.add_argument('question_id', type=int, help='Question ID to move')
    move_parser.add_argument('--parent', type=int, required=True, help='Target collection ID')
    move_parser.add_argument('--name', type=str, default=None, help='Optional new name for the question')
    move_parser.set_defaults(func=question_move)

    # Question orphans
    orphans_parser = question_subparsers.add_parser(
        'orphans',
        parents=[common_parser],
        help='List questions in a collection not used by a dashboard'
    )
    orphans_parser.add_argument('--collection', type=int, required=True, help='Collection ID to audit')
    orphans_parser.add_argument('--dashboard-dir', type=str, required=True, help='Dashboard directory (contains .state.yaml)')
    orphans_parser.add_argument('--target', type=int, default=None, help='Target collection ID for move suggestions')
    orphans_parser.set_defaults(func=question_orphans)

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
