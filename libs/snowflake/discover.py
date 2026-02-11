#!/usr/bin/env python3
"""
Snowflake Discovery Tools

Utilities for exploring Snowflake schemas, tables, and columns without
writing complex metadata queries.

Usage:
  ./discover.py tables <pattern>              - Find tables matching pattern
  ./discover.py columns --table <name>        - Show columns and top values
  ./discover.py preview --table <name>        - Quick data preview
  ./discover.py schemas                       - List accessible databases/schemas

Examples:
  ./discover.py tables "service catalog"
  ./discover.py columns --table REPORTING.GENERAL.DIM_MONITOR
  ./discover.py preview --table REPORTING.GENERAL.DIM_ORG --limit 10
  ./discover.py schemas
"""

import sys
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import snowflake.connector # pyright: ignore[reportMissingImports]
import tomllib  # pyright: ignore[reportMissingImports]


# Color functions
def error(msg: str):
    """Print error message in red."""
    print(f"\033[0;31m{msg}\033[0m", file=sys.stderr)


def warning(msg: str):
    """Print warning message in yellow."""
    print(f"\033[1;33m{msg}\033[0m")


def success(msg: str):
    """Print success message in green."""
    print(f"\033[0;32m{msg}\033[0m")


def info(msg: str):
    """Print info message"""
    print(f"{msg}")


def dim(msg: str):
    """Print dimmed message"""
    print(f"\033[2m{msg}\033[0m")


def connect():
    """Connect to Snowflake using default connection from ~/.snowflake/connections.toml"""
    config_path = Path.home() / '.snowflake' / 'connections.toml'

    if not config_path.exists():
        raise FileNotFoundError(
            f"Snowflake connection config not found at {config_path}\n"
            f"Please create this file with your connection details."
        )

    with open(config_path, 'rb') as f:
        config = tomllib.load(f)

    if 'default' not in config:
        raise ValueError(
            f"No 'default' connection found in {config_path}\n"
            f"Please ensure your config has a [default] section."
        )

    default_conn = config['default']

    return snowflake.connector.connect(
        account=default_conn['account'],
        user=default_conn['user'],
        authenticator=default_conn['authenticator'],
        database=default_conn.get('database'),
        warehouse=default_conn.get('warehouse'),
        role=default_conn.get('role')
    )


@dataclass
class TableInfo:
    """Information about a table"""
    database: str
    schema: str
    name: str
    row_count: Optional[int]
    bytes: Optional[int]
    last_altered: Optional[str]

    @property
    def full_name(self) -> str:
        return f"{self.database}.{self.schema}.{self.name}"

    def format_size(self) -> str:
        """Format bytes as human-readable size"""
        if self.bytes is None:
            return "unknown"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if self.bytes < 1024.0:
                return f"{self.bytes:.1f} {unit}"
            self.bytes /= 1024.0
        return f"{self.bytes:.1f} PB"


@dataclass
class ColumnInfo:
    """Information about a column"""
    name: str
    type: str
    nullable: bool
    default: Optional[str]
    comment: Optional[str]


def discover_tables(conn, pattern: str, limit: int = 50) -> List[TableInfo]:
    """
    Find tables matching a pattern across accessible schemas.

    Uses SHOW TABLES and INFORMATION_SCHEMA queries with graceful permission handling.
    """
    cursor = conn.cursor()
    tables = []

    # Normalize pattern for SQL LIKE
    sql_pattern = f"%{pattern}%"

    info(f"Searching for tables matching '{pattern}'...")
    dim("(Checking REPORTING database)")

    try:
        # Try to query information_schema for detailed info
        query = f"""
        SELECT
            TABLE_CATALOG as database_name,
            TABLE_SCHEMA as schema_name,
            TABLE_NAME as table_name,
            ROW_COUNT,
            BYTES,
            LAST_ALTERED
        FROM REPORTING.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME ILIKE '{sql_pattern}'
            AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY LAST_ALTERED DESC
        LIMIT {limit}
        """

        cursor.execute(query)
        results = cursor.fetchall()

        for row in results:
            tables.append(TableInfo(
                database=row[0],
                schema=row[1],
                name=row[2],
                row_count=row[3],
                bytes=row[4],
                last_altered=row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else None
            ))

    except snowflake.connector.errors.ProgrammingError as e:
        # Permission error or schema doesn't exist - try alternative approach
        warning(f"Limited access to INFORMATION_SCHEMA: {e}")
        dim("Trying alternative SHOW TABLES approach...")

        # Try SHOW TABLES approach for each schema
        for schema in ['BILLING', 'GENERAL', 'SALES', 'MARKETING', 'ENGINEERING']:
            try:
                cursor.execute(f"SHOW TABLES LIKE '{sql_pattern}' IN REPORTING.{schema}")
                results = cursor.fetchall()

                for row in results:
                    # SHOW TABLES returns: created_on, name, database_name, schema_name, kind, ...
                    tables.append(TableInfo(
                        database=row[2],
                        schema=row[3],
                        name=row[1],
                        row_count=None,
                        bytes=row[5] if len(row) > 5 else None,
                        last_altered=None
                    ))
            except Exception:
                # Schema not accessible, skip silently
                pass

    cursor.close()
    return tables[:limit]


def discover_columns(conn, table_name: str, show_samples: bool = True) -> tuple[List[ColumnInfo], Dict[str, Any]]:
    """
    Get column information and statistics for a table.

    Returns:
        (columns, stats) where stats is a dict with column-level statistics
    """
    cursor = conn.cursor()

    # Parse table name (support full or partial names)
    parts = table_name.split('.')
    if len(parts) == 3:
        database, schema, table = parts
    elif len(parts) == 2:
        database = 'REPORTING'
        schema, table = parts
    elif len(parts) == 1:
        # Try to find the table across schemas
        error(f"Ambiguous table name '{table_name}'. Please specify schema: SCHEMA.TABLE or DATABASE.SCHEMA.TABLE")
        return [], {}
    else:
        error(f"Invalid table name format: {table_name}")
        return [], {}

    full_table = f"{database}.{schema}.{table}"

    info(f"Analyzing table: {full_table}")

    # Get column information from INFORMATION_SCHEMA
    columns = []
    try:
        query = f"""
        SELECT
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            COMMENT
        FROM {database}.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_CATALOG = '{database}'
            AND TABLE_SCHEMA = '{schema}'
            AND TABLE_NAME = '{table}'
        ORDER BY ORDINAL_POSITION
        """

        cursor.execute(query)
        results = cursor.fetchall()

        for row in results:
            columns.append(ColumnInfo(
                name=row[0],
                type=row[1],
                nullable=row[2] == 'YES',
                default=row[3],
                comment=row[4]
            ))
    except Exception as e:
        error(f"Failed to get column information: {e}")
        cursor.close()
        return [], {}

    # Get statistics for each column
    stats = {}
    if show_samples and columns:
        dim("Computing column statistics...")

        # Build stats query
        stat_parts = []
        for col in columns:
            col_name = col.name
            # Count non-nulls, count distinct, sample values
            stat_parts.append(f"""
                COUNT({col_name}) as "{col_name}__count",
                COUNT(DISTINCT {col_name}) as "{col_name}__distinct",
                SUM(CASE WHEN {col_name} IS NULL THEN 1 ELSE 0 END) as "{col_name}__nulls"
            """)

        stats_query = f"""
        SELECT
            COUNT(*) as total_rows,
            {', '.join(stat_parts)}
        FROM {full_table}
        """

        try:
            cursor.execute(stats_query)
            result = cursor.fetchone()

            if result:
                total_rows = result[0]
                idx = 1
                for col in columns:
                    count = result[idx]
                    distinct = result[idx + 1]
                    nulls = result[idx + 2]

                    stats[col.name] = {
                        'count': count,
                        'distinct': distinct,
                        'nulls': nulls,
                        'null_pct': (nulls / total_rows * 100) if total_rows > 0 else 0
                    }
                    idx += 3

                stats['_total_rows'] = total_rows
        except Exception as e:
            warning(f"Failed to compute statistics: {e}")

    # Get sample values for each column
    if show_samples and columns:
        dim("Fetching sample values...")

        for col in columns:
            col_name = col.name
            try:
                # Get top 5 most common values
                sample_query = f"""
                SELECT {col_name}, COUNT(*) as freq
                FROM {full_table}
                WHERE {col_name} IS NOT NULL
                GROUP BY {col_name}
                ORDER BY freq DESC
                LIMIT 5
                """

                cursor.execute(sample_query)
                samples = cursor.fetchall()

                if col_name in stats:
                    stats[col_name]['samples'] = [
                        {'value': row[0], 'count': row[1]} for row in samples
                    ]
            except Exception:
                # Some columns might not support GROUP BY (e.g., VARIANT, ARRAY)
                pass

    cursor.close()
    return columns, stats


def preview_table(conn, table_name: str, limit: int = 10) -> tuple[List[str], List[tuple]]:
    """
    Get a quick preview of table data.

    Returns:
        (column_names, rows)
    """
    cursor = conn.cursor()

    # Parse table name
    parts = table_name.split('.')
    if len(parts) == 3:
        full_table = table_name
    elif len(parts) == 2:
        full_table = f"REPORTING.{table_name}"
    else:
        error(f"Invalid table name format: {table_name}")
        return [], []

    info(f"Preview: {full_table} (first {limit} rows)")

    try:
        cursor.execute(f"SELECT * FROM {full_table} LIMIT {limit}")
        results = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]

        cursor.close()
        return col_names, results
    except Exception as e:
        error(f"Failed to preview table: {e}")
        cursor.close()
        return [], []


def list_schemas(conn) -> Dict[str, List[str]]:
    """
    List accessible databases and their schemas.

    Returns:
        Dict mapping database names to lists of schema names
    """
    cursor = conn.cursor()
    result = {}

    info("Listing accessible databases and schemas...")

    try:
        # Get databases
        cursor.execute("SHOW DATABASES")
        databases = [row[1] for row in cursor.fetchall()]

        for db in databases:
            try:
                cursor.execute(f"SHOW SCHEMAS IN {db}")
                schemas = [row[1] for row in cursor.fetchall()]
                result[db] = schemas
            except Exception:
                # Database not accessible
                pass
    except Exception as e:
        error(f"Failed to list schemas: {e}")

    cursor.close()
    return result


def print_tables(tables: List[TableInfo]):
    """Print table discovery results in a formatted table"""
    if not tables:
        warning("No tables found matching the pattern")
        return

    success(f"\nFound {len(tables)} table(s):")
    print()

    # Calculate column widths
    max_name_len = max(len(t.full_name) for t in tables)
    max_name_len = max(max_name_len, 40)  # Minimum width

    # Header
    header = f"{'TABLE':<{max_name_len}}  {'ROWS':>12}  {'SIZE':>10}  {'LAST MODIFIED':<19}"
    print(header)
    print("=" * len(header))

    # Rows
    for table in tables:
        row_count_str = f"{table.row_count:,}" if table.row_count is not None else "unknown"
        size_str = table.format_size()
        last_modified = table.last_altered or "unknown"

        print(f"{table.full_name:<{max_name_len}}  {row_count_str:>12}  {size_str:>10}  {last_modified:<19}")

    print()


def print_columns(columns: List[ColumnInfo], stats: Dict[str, Any]):
    """Print column information with statistics"""
    if not columns:
        warning("No columns found")
        return

    total_rows = stats.get('_total_rows', 0)

    success(f"\nFound {len(columns)} column(s):")
    if total_rows:
        info(f"Total rows: {total_rows:,}")
    print()

    # Print each column
    for col in columns:
        col_stats = stats.get(col.name, {})

        # Column header
        nullable_str = "nullable" if col.nullable else "NOT NULL"
        print(f"📋 {col.name}")
        print(f"   Type: {col.type}  |  {nullable_str}")

        # Statistics
        if col_stats:
            distinct = col_stats.get('distinct', 0)
            null_pct = col_stats.get('null_pct', 0)

            print(f"   Distinct: {distinct:,}  |  Nulls: {null_pct:.1f}%")

            # Sample values
            samples = col_stats.get('samples', [])
            if samples:
                print(f"   Top values:")
                for sample in samples[:3]:
                    value = str(sample['value'])
                    if len(value) > 50:
                        value = value[:47] + "..."
                    count = sample['count']
                    pct = (count / total_rows * 100) if total_rows > 0 else 0
                    print(f"     • {value} ({count:,}, {pct:.1f}%)")

        print()


def print_preview(columns: List[str], rows: List[tuple]):
    """Print table preview in a formatted table"""
    if not rows:
        warning("Table is empty or no data returned")
        return

    success(f"\n{len(rows)} row(s):")
    print()

    # Calculate column widths (max 30 chars per column)
    col_widths = []
    for i, col in enumerate(columns):
        max_width = len(col)
        for row in rows:
            val_str = str(row[i]) if row[i] is not None else "NULL"
            max_width = max(max_width, len(val_str))
        col_widths.append(min(max_width, 30))

    # Header
    header = "  |  ".join(f"{col:<{col_widths[i]}}" for i, col in enumerate(columns))
    print(header)
    print("=" * len(header))

    # Rows
    for row in rows:
        row_str = "  |  ".join(
            f"{str(val):<{col_widths[i]}}" if val is not None else f"{'NULL':<{col_widths[i]}}"
            for i, val in enumerate(row)
        )
        print(row_str)

    print()


def print_schemas(schema_map: Dict[str, List[str]]):
    """Print database and schema listing"""
    if not schema_map:
        warning("No accessible databases found")
        return

    success(f"\nFound {len(schema_map)} database(s):")
    print()

    for db, schemas in sorted(schema_map.items()):
        print(f"📦 {db}")
        for schema in sorted(schemas):
            print(f"   └─ {schema}")
        print()


def print_help():
    """Print help message"""
    help_text = """
snowflake discover - Explore Snowflake schemas, tables, and columns

Usage:
  snowflake discover tables <pattern>          - Find tables matching pattern
  snowflake discover columns --table <name>    - Show columns and top values
  snowflake discover preview --table <name>    - Quick data preview
  snowflake discover schemas                   - List accessible databases/schemas

Options:
  --limit <N>        Limit results (default varies by command)
  --no-samples       Skip sample value computation (columns command)

Examples:
  # Find tables with "monitor" in the name
  snowflake discover tables monitor

  # Get column details for a specific table
  snowflake discover columns --table REPORTING.GENERAL.DIM_MONITOR

  # Preview data from a table
  snowflake discover preview --table REPORTING.GENERAL.DIM_ORG --limit 5

  # List all accessible schemas
  snowflake discover schemas

Table Name Formats:
  - Full: DATABASE.SCHEMA.TABLE
  - Short: SCHEMA.TABLE (assumes REPORTING database)
  - Pattern: "service catalog" (searches across all schemas)
"""
    print(help_text)


def main():
    """Main CLI entry point for discover commands"""

    # Parse arguments
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', 'help']:
        print_help()
        sys.exit(0)

    command = sys.argv[1]

    # Route to subcommands
    if command == 'tables':
        if len(sys.argv) < 3:
            error("Missing required argument: <pattern>")
            print("\nUsage: snowflake discover tables <pattern>")
            sys.exit(1)

        pattern = sys.argv[2]
        limit = 50

        # Parse options
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == '--limit' and i + 1 < len(sys.argv):
                limit = int(sys.argv[i + 1])
                i += 2
            else:
                error(f"Unknown option: {sys.argv[i]}")
                sys.exit(1)

        # Execute
        try:
            conn = connect()
            try:
                tables = discover_tables(conn, pattern, limit)
                print_tables(tables)
            finally:
                conn.close()
        except Exception as e:
            error(f"\nError: {e}")
            sys.exit(1)

    elif command == 'columns':
        # Parse --table argument
        table_name = None
        show_samples = True

        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == '--table' and i + 1 < len(sys.argv):
                table_name = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == '--no-samples':
                show_samples = False
                i += 1
            else:
                error(f"Unknown option: {sys.argv[i]}")
                sys.exit(1)

        if not table_name:
            error("Missing required argument: --table <name>")
            print("\nUsage: snowflake discover columns --table <name>")
            sys.exit(1)

        # Execute
        try:
            conn = connect()
            try:
                columns, stats = discover_columns(conn, table_name, show_samples)
                print_columns(columns, stats)
            finally:
                conn.close()
        except Exception as e:
            error(f"\nError: {e}")
            sys.exit(1)

    elif command == 'preview':
        # Parse --table argument
        table_name = None
        limit = 10

        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == '--table' and i + 1 < len(sys.argv):
                table_name = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == '--limit' and i + 1 < len(sys.argv):
                limit = int(sys.argv[i + 1])
                i += 2
            else:
                error(f"Unknown option: {sys.argv[i]}")
                sys.exit(1)

        if not table_name:
            error("Missing required argument: --table <name>")
            print("\nUsage: snowflake discover preview --table <name>")
            sys.exit(1)

        # Execute
        try:
            conn = connect()
            try:
                columns, rows = preview_table(conn, table_name, limit)
                print_preview(columns, rows)
            finally:
                conn.close()
        except Exception as e:
            error(f"\nError: {e}")
            sys.exit(1)

    elif command == 'schemas':
        # Execute
        try:
            conn = connect()
            try:
                schema_map = list_schemas(conn)
                print_schemas(schema_map)
            finally:
                conn.close()
        except Exception as e:
            error(f"\nError: {e}")
            sys.exit(1)

    else:
        error(f"Unknown discover command: {command}")
        print("\nAvailable commands: tables, columns, preview, schemas")
        print("Use --help for more information")
        sys.exit(1)


if __name__ == '__main__':
    main()
