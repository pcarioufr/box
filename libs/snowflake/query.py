#!/Users/pierre.cariou/Code/onboarding-analytics/.venv/bin/python
"""
Snowflake Query Executor

A utility script that executes SQL queries from files and saves results to output files.

Usage:
  ./query.py <path-to-sql-file> [options]
  ./query.py --sql "SELECT ..." [options]

Examples:
  ./query.py ../runs/25-11-21-log-revenue-top10/01-discover-usage-tables/query.sql
  ./query.py ../runs/25-11-22-analysis/01-step/query.sql --output ./
  ./query.py my_analysis.sql --output custom_results.csv
  ./query.py my_query.sql --limit 100
  ./query.py my_query.sql --var-signup_method standard --var-datacenter us1
  ./query.py --sql "SELECT COUNT(*) FROM REPORTING.GENERAL.DIM_MONITOR"
  ./query.py --sql "SELECT * FROM REPORTING.GENERAL.DIM_SLO LIMIT 10" --output results.csv

Options:
  --sql <query>              Pass SQL query inline (no file needed). Output defaults to tmp/output.csv
  --working-folder <folder>  Working folder name (e.g., "2026-02-03_analysis"). Saves to data/{folder}/snowflake/{output}
  --output <path>            Specify output filename or directory (default: output.csv next to SQL file)
  --limit <N>                Limit results to N rows
  --var-<name> <value>       Set Metabase template variable (e.g., --var-signup_method standard)
  --debug                    Show detailed debug information including SQL content
  -h, --help                 Show this help message

Template Variables:
  Queries can use Metabase-style template variables:
  
  Optional filters (removed if variable not provided):
    [[ AND column = {{variable}} ]]
  
  Required variables (error if not provided):
    WHERE column = {{variable}}
  
  Use --var-<name> to provide values for local execution.
"""

import sys
import os
import tomllib  # pyright: ignore[reportMissingImports]
import csv
from pathlib import Path
from typing import Optional, List
import snowflake.connector # pyright: ignore[reportMissingImports]


# Base output directory for Snowflake data
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DEFAULT_SUBDIR = "snowflake"  # Default subdirectory for Snowflake outputs

# Global debug flag
_DEBUG_MODE = False


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


def debug(msg: str):
    """Print debug message in grey (only if debug mode is enabled)."""
    if _DEBUG_MODE:
        print(f"\033[0;90m{msg}\033[0m")





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


def load_query(sql_file: Path) -> str:
    """Load SQL query from file."""
    if not sql_file.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_file}")
    
    return sql_file.read_text()


def parse_includes(query: str, sql_file_dir: Path) -> dict[str, str]:
    """
    Parse INCLUDE directives from SQL file.
    
    Format: -- INCLUDE: path/to/file.sql AS {{#alias-name}}
    
    Paths are resolved relative to the repository root.
    
    Returns:
        Dictionary mapping alias names (e.g., '{{#131569-non-spammy-signup-orgs}}') 
        to their SQL content
    """
    includes = {}
    lines = query.split('\n')
    
    # Find repository root by walking up from sql_file_dir until we find .git
    repo_root = sql_file_dir
    while repo_root.parent != repo_root:
        if (repo_root / '.git').exists():
            break
        repo_root = repo_root.parent
    
    for line in lines:
        line = line.strip()
        if line.startswith('-- INCLUDE:'):
            # Parse: -- INCLUDE: path/to/file.sql AS {{#alias-name}}
            parts = line[11:].strip().split(' AS ')
            if len(parts) != 2:
                warning(f"Invalid INCLUDE syntax: {line}")
                continue
            
            include_path = parts[0].strip()
            alias_name = parts[1].strip()
            
            # Resolve path relative to the repository root
            full_path = (repo_root / include_path).resolve()
            
            if not full_path.exists():
                warning(f"Include file not found: {full_path}")
                continue
            
            # Load the included SQL content
            included_sql = full_path.read_text()
            
            # Remove INCLUDE directives and documentation comments from included SQL
            # (keep only the actual query)
            included_lines = []
            in_query = False
            for inc_line in included_sql.split('\n'):
                stripped = inc_line.strip()
                # Skip INCLUDE directives in included files
                if stripped.startswith('-- INCLUDE:'):
                    continue
                # Start capturing after header comments
                if not in_query and stripped and not stripped.startswith('--'):
                    in_query = True
                if in_query:
                    included_lines.append(inc_line)
            
            cleaned_sql = '\n'.join(included_lines).strip()
            
            # Remove trailing semicolon if present (CTEs don't have semicolons)
            if cleaned_sql.endswith(';'):
                cleaned_sql = cleaned_sql[:-1].rstrip()
            
            includes[alias_name] = cleaned_sql
            debug(f"Loaded include: {alias_name} from {include_path}")
    
    return includes


def substitute_variables(query: str, variables: dict[str, str]) -> str:
    """
    Substitute Metabase template variables in the query.
    
    Handles two patterns:
    1. Optional filters: [[ AND column = {{variable}} ]]
       - If variable is provided: replaces with "AND column = 'value'"
       - If variable is not provided: removes entire [[ ... ]] block
    
    2. Direct variables: {{variable}}
       - If variable is provided: replaces with 'value'
       - If variable is not provided: raises error
    
    Args:
        query: SQL query with Metabase template syntax
        variables: Dictionary of variable names to values
    
    Returns:
        Query with variables substituted or optional blocks removed
    """
    import re
    
    # Pattern 1: Handle optional filter blocks [[ ... {{var}} ... ]]
    # Find all [[ ... ]] blocks
    optional_pattern = r'\[\[(.*?)\]\]'
    
    def replace_optional_block(match):
        block_content = match.group(1)
        
        # Find all {{variable}} references in this block
        var_pattern = r'\{\{(\w+)\}\}'
        variables_in_block = re.findall(var_pattern, block_content)
        
        # If any variable in the block is not provided, remove the entire block
        if not all(var in variables for var in variables_in_block):
            debug(f"Removing optional block (missing variables): {block_content.strip()}")
            return ''
        
        # All variables are provided - substitute them and keep the block
        result = block_content
        for var_name in variables_in_block:
            value = variables[var_name]
            # Quote the value for SQL (escape single quotes)
            escaped_value = value.replace("'", "''")
            quoted_value = f"'{escaped_value}'"
            result = result.replace(f'{{{{{var_name}}}}}', quoted_value)
        
        debug(f"Substituted optional block: {result.strip()}")
        return result
    
    query = re.sub(optional_pattern, replace_optional_block, query, flags=re.DOTALL)
    
    # Pattern 2: Handle remaining direct {{variable}} references (not in [[ ]])
    # These are required variables
    var_pattern = r'\{\{(\w+)\}\}'
    remaining_vars = re.findall(var_pattern, query)
    
    for var_name in remaining_vars:
        # Skip Metabase question references ({{#...}})
        if var_name.startswith('#'):
            continue
            
        if var_name not in variables:
            raise ValueError(
                f"Required variable '{{{{var_name}}}}' not provided. "
                f"Use --var-{var_name} <value> to specify it."
            )
        
        value = variables[var_name]
        escaped_value = value.replace("'", "''")
        quoted_value = f"'{escaped_value}'"
        query = query.replace(f'{{{{{var_name}}}}}', quoted_value)
        debug(f"Substituted variable: {var_name} = {quoted_value}")
    
    return query


def preprocess_query(query: str, sql_file_dir: Path, variables: dict[str, str] = None) -> str:
    """
    Preprocess SQL query to handle INCLUDE directives and variable substitution.
    
    Steps:
    1. Parse INCLUDE directives and wrap as CTEs
    2. Substitute template variables ({{variable}}) with provided values
    3. Remove optional filter blocks [[ ... ]] if variables not provided
    
    This allows queries to use Metabase-compatible syntax while being
    executable locally with a single source of truth.
    
    Args:
        query: SQL query text
        sql_file_dir: Directory containing the SQL file (for resolving includes)
        variables: Dictionary of variable names to values for substitution
    
    Returns:
        Preprocessed query ready for execution
    """
    if variables is None:
        variables = {}
    
    includes = parse_includes(query, sql_file_dir)
    
    if not includes:
        # No includes, but still need to handle template variables
        lines = [line for line in query.split('\n') 
                if not line.strip().startswith('-- INCLUDE:')]
        preprocessed = '\n'.join(lines)
        
        # Substitute variables (handles optional blocks)
        if variables:
            debug(f"Substituting {len(variables)} variable(s): {', '.join(variables.keys())}")
        preprocessed = substitute_variables(preprocessed, variables)
        return preprocessed
    
    # Remove INCLUDE directives from the main query
    main_query_lines = []
    for line in query.split('\n'):
        if not line.strip().startswith('-- INCLUDE:'):
            main_query_lines.append(line)
    main_query = '\n'.join(main_query_lines)
    
    # Build CTEs from includes
    cte_definitions = []
    for alias, sql_content in includes.items():
        # Extract a clean CTE name from the alias
        # {{#131569-non-spammy-signup-orgs}} -> non_spammy_signup_orgs
        cte_name = alias.replace('{{#', '').replace('}}', '').split('-', 1)[-1]
        cte_name = cte_name.replace('-', '_')
        
        cte_definitions.append(f"{cte_name} AS (\n{sql_content}\n)")
        
        # Replace all references to the Metabase alias with the CTE name
        main_query = main_query.replace(alias, cte_name)
    
    # Find the first non-comment, non-empty line to check for WITH
    first_sql_line_idx = -1
    lines = main_query.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('--'):
            first_sql_line_idx = i
            break
    
    # Check if main query already has a WITH clause
    if first_sql_line_idx >= 0:
        first_sql_line = lines[first_sql_line_idx].strip().upper()
        if first_sql_line.startswith('WITH '):
            # Query already has WITH clause - insert our CTEs after "WITH "
            # Find line with WITH and position after "WITH "
            target_line_idx = first_sql_line_idx
            target_line = lines[target_line_idx]
            
            # Find position of WITH in the actual line (preserving whitespace)
            with_pos = target_line.upper().find('WITH ')
            insert_pos_in_line = with_pos + 5  # 5 = len('WITH ')
            
            # Insert our CTEs on a new line after WITH
            ctes = ',\n\n'.join(cte_definitions)
            
            # Reconstruct: everything before target line + modified target line + rest
            before_lines = lines[:target_line_idx]
            after_lines = lines[target_line_idx + 1:]
            
            # Split the WITH line: "WITH existing_cte AS (" -> "WITH " + "existing_cte AS ("
            modified_line = target_line[:insert_pos_in_line] + '\n' + ctes + ',\n\n' + target_line[insert_pos_in_line:]
            
            preprocessed = '\n'.join(before_lines + [modified_line] + after_lines)
            debug(f"Merged {len(includes)} include(s) into existing WITH clause")
        else:
            # Query doesn't have WITH clause - prepend one
            ctes = ',\n\n'.join(cte_definitions)
            preprocessed = f"WITH {ctes}\n\n{main_query}"
            debug(f"Prepended {len(includes)} include(s) as new WITH clause")
    else:
        # No SQL line found (only includes and comments) - prepend WITH clause
        ctes = ',\n\n'.join(cte_definitions)
        preprocessed = f"WITH {ctes}\n\n{main_query}"
        debug(f"Prepended {len(includes)} include(s) as new WITH clause")
    
    # Step 2: Substitute variables (always run to handle optional blocks)
    if variables:
        debug(f"Substituting {len(variables)} variable(s): {', '.join(variables.keys())}")
    preprocessed = substitute_variables(preprocessed, variables)
    
    return preprocessed


def apply_limit_to_query(query: str, limit: int) -> str:
    """
    Append LIMIT clause to SQL query without modifying the original file.
    
    This is more efficient than fetching all results and limiting client-side,
    as Snowflake will only process the requested number of rows.
    """
    # Split into lines to find the actual query (ignoring trailing comments)
    lines = query.split('\n')
    
    # Find the last non-comment, non-empty line
    last_query_line_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        # Skip empty lines and comment-only lines
        if line and not line.startswith('--'):
            last_query_line_idx = i
            break
    
    if last_query_line_idx == -1:
        # No query found, just strip and add limit
        query = query.rstrip().rstrip(';').rstrip()
        return f"{query}\nLIMIT {limit};"
    
    # Get query up to the last actual SQL line
    query_lines = lines[:last_query_line_idx + 1]
    
    # Remove trailing semicolon from the last line if present
    query_lines[-1] = query_lines[-1].rstrip().rstrip(';')
    
    # Reconstruct query and add LIMIT
    query = '\n'.join(query_lines)
    return f"{query}\nLIMIT {limit};"


def execute_query(conn, query: str, limit: Optional[int] = None) -> tuple[List[str], List[tuple]]:
    """
    Execute query and return column names and results.
    
    If limit is provided, appends LIMIT clause to the query for efficiency.
    
    Returns:
        (column_names, rows)
    """
    # Apply LIMIT to query if specified (more efficient than client-side limiting)
    if limit:
        query = apply_limit_to_query(query, limit)
    
    cursor = conn.cursor()
    cursor.execute(query)
    
    # Fetch all results (already limited by query if needed)
    results = cursor.fetchall()
    
    # Get column names
    col_names = [desc[0] for desc in cursor.description]
    
    cursor.close()
    return col_names, results


def save_as_csv(output_path: Path, columns: List[str], rows: List[tuple]):
    """Save results as CSV file."""
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


def detect_output_location(sql_file: Path, variables: Optional[dict] = None) -> Path:
    """
    Detect where to place output file based on SQL file location.

    Default: {stem}[_{var-val}...].csv next to the SQL file.

    Returns:
        Full path to output file
    """
    return sql_file.parent / generate_output_filename(sql_file, variables)


def resolve_output_path(sql_file: Path, output_arg: Optional[str], working_folder: Optional[str] = None, variables: Optional[dict] = None) -> Path:
    """
    Resolve the final output path based on --output argument and SQL file location.

    Args:
        sql_file: Path to SQL file being executed
        output_arg: Value of --output argument (None, filename, or directory path)
        working_folder: Working folder name (e.g., "2026-02-03_analysis")

    Returns:
        Full path to output file (always CSV)
    """

    # If working_folder is specified, use it
    if working_folder:
        # Construct base directory: data/{working_folder}/snowflake/
        output_dir = DATA_DIR / working_folder / DEFAULT_SUBDIR
        output_dir.mkdir(parents=True, exist_ok=True)

        if output_arg:
            # If output_arg is just a filename (no path separators), use it
            if '/' not in output_arg:
                return output_dir / output_arg
            # Otherwise, treat as a path relative to the working folder snowflake directory
            else:
                return (output_dir / output_arg).resolve()
        else:
            # Generate a default filename
            output_filename = generate_output_filename(sql_file, variables)
            return output_dir / output_filename

    # Legacy behavior when no working folder is specified
    if output_arg:
        output_path = Path(output_arg)

        # If it's a directory, generate filename and place in that directory
        if output_path.is_dir() or output_arg.endswith('/'):
            output_dir = output_path.resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir / "results.csv"

        # If it's a filename (no directory separators or has an extension)
        elif '/' not in output_arg or '.' in Path(output_arg).name:
            # If absolute path, use as-is
            if output_path.is_absolute():
                output_path.parent.mkdir(parents=True, exist_ok=True)
                return output_path

            # If relative path with directory components, resolve from SQL file location
            if '/' in output_arg:
                output_path = (sql_file.parent / output_arg).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                return output_path

            # Just a filename - place in detected location
            detected_path = detect_output_location(sql_file)
            return detected_path.parent / output_arg

        # Otherwise, treat as directory
        else:
            output_dir = output_path.resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir / "results.csv"

    # No --output specified, auto-detect
    return detect_output_location(sql_file, variables)


def generate_output_filename(sql_file: Path, variables: Optional[dict] = None) -> str:
    """Generate output filename matching the SQL file name with .csv extension.

    When template variables are provided, appends them as a suffix so that
    multiple runs with different variables don't overwrite each other.
    E.g., monitor-response-rate.sql --var-org_id 2 → monitor-response-rate_org_id-2.csv
    """
    stem = sql_file.stem
    if variables:
        suffix = "_".join(f"{k}-{v}" for k, v in sorted(variables.items()))
        stem = f"{stem}_{suffix}"
    return f"{stem}.csv"


def main():
    global _DEBUG_MODE
    
    # Parse arguments
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print(__doc__)
        sys.exit(0)

    # Check if first arg is --sql (inline query mode)
    inline_sql = None
    sql_file = None

    if sys.argv[1] == '--sql':
        if len(sys.argv) < 3:
            error("--sql requires a query string")
            sys.exit(1)
        inline_sql = sys.argv[2]
        start_idx = 3
    else:
        sql_file_arg = sys.argv[1]
        sql_file = Path(sql_file_arg).resolve()
        debug(f"Resolved SQL file path: {sql_file}")
        start_idx = 2

    # Parse options
    output_arg = None
    limit = None
    debug_mode = False
    working_folder = None
    variables = {}

    i = start_idx
    while i < len(sys.argv):
        if sys.argv[i] == '--working-folder' and i + 1 < len(sys.argv):
            working_folder = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--output' and i + 1 < len(sys.argv):
            output_arg = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--debug':
            debug_mode = True
            _DEBUG_MODE = True  # Set global flag
            i += 1
        elif sys.argv[i].startswith('--var-') and i + 1 < len(sys.argv):
            # Parse variable: --var-name value
            var_name = sys.argv[i][6:]  # Remove '--var-' prefix
            var_value = sys.argv[i + 1]
            variables[var_name] = var_value
            i += 2
        else:
            error(f"Unknown option '{sys.argv[i]}'")
            sys.exit(1)

    debug(f"Parsed options: limit={limit}, output={output_arg}, working_folder={working_folder}, variables={variables}")

    # Resolve output path
    if inline_sql:
        # For inline SQL, default output to tmp/output.csv
        if working_folder:
            output_dir = DATA_DIR / working_folder / DEFAULT_SUBDIR
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / (output_arg or "output.csv")
        elif output_arg:
            output_path = Path(output_arg).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            tmp_dir = DATA_DIR.parent / "tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            output_path = tmp_dir / "output.csv"
    else:
        output_path = resolve_output_path(sql_file, output_arg, working_folder, variables)
    debug(f"Resolved output path: {output_path}")

    # Display execution info
    info(f"\n{'=' * 100}")
    info("SNOWFLAKE QUERY EXECUTOR")
    info('=' * 100)
    if inline_sql:
        info(f"\n📄 SQL: (inline)")
    else:
        info(f"\n📄 SQL File: {sql_file}")
    info(f"💾 Output: {output_path}")
    if limit:
        info(f"🔢 Limit: {limit} rows")
    if variables:
        info(f"🔧 Variables: {', '.join(f'{k}={v}' for k, v in variables.items())}")
    if debug_mode:
        print(f"🐛 Debug: enabled")
    print()

    try:
        # Load query
        if inline_sql:
            query = inline_sql
            debug(f"Using inline SQL ({len(query)} characters)")
        else:
            info("Loading query...")
            query = load_query(sql_file)
            debug(f"Query loaded successfully ({len(query)} characters)")

        # Preprocess query to handle INCLUDE directives and variable substitution
        base_dir = sql_file.parent if sql_file else Path.cwd()
        debug("Preprocessing query (handling INCLUDE directives and variables)...")
        preprocessed_query = preprocess_query(query, base_dir, variables)
        debug(f"Preprocessed query ({len(preprocessed_query)} characters)")
        
        # Show query content only in debug mode
        if debug_mode:
            print(f"\n{'-' * 100}")
            print("PREPROCESSED QUERY:")
            print(f"{'-' * 100}")
            debug(preprocessed_query)
            print(f"{'-' * 100}\n")
        
        # Show if limit will be applied
        if limit:
            warning(f"LIMIT {limit} will be appended to the query")
        
        # Connect to Snowflake
        debug("Connecting to Snowflake...")
        debug("Reading Snowflake configuration from ~/.snowflake/connections.toml")
        conn = connect()
        
        try:
            info("Connected to Snowflake")
            debug(f"Connected to database: {conn.database}, warehouse: {conn.warehouse}")
            
            # Execute query (with LIMIT applied if specified)
            debug("Executing query...")
            if limit:
                debug(f"Appending LIMIT {limit} to query before execution")
            columns, rows = execute_query(conn, preprocessed_query, limit)
            success(f"Query executed successfully - {len(rows)} rows returned")
            debug(f"Column count: {len(columns)}, Columns: {', '.join(columns)}")
            
            # Save results as CSV
            save_as_csv(output_path, columns, rows)
            debug(f"Results saved to {output_path.name}")

            
            # Display preview of first few rows
            if rows:
                print(f"\n📋 Preview (first 5 rows):")
                print("-" * 100)
                header = " | ".join(f"{col:<20}" for col in columns)
                print(header)
                print("-" * 100)
                for row in rows[:5]:
                    row_str = " | ".join(f"{str(val):<20}" if val is not None else f"{'NULL':<20}" for val in row)
                    print(row_str)
                
                if len(rows) > 5:
                    debug(f"... and {len(rows) - 5} more rows (use full output file to see all)")
        
        finally:
            # Always close connection, even if an error occurred
            debug("Closing Snowflake connection")
            conn.close()
        
        
    except Exception as e:
        error(f"\nError: {e}\n")
        debug(f"Error type: {type(e).__name__}")
        if debug_mode:
            import traceback
            debug("Full traceback:")
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

