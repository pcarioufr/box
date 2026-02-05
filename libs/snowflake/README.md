# Snowflake Library

Utilities for executing Snowflake queries in the onboarding-analytics repository.

## Architecture

This library uses a **pythonic CLI architecture** with a single entry point:

### Module Structure

```
libs/snowflake/
├── __init__.py      # Package exports (functions + cli_main)
├── __main__.py      # Makes package executable with `python -m libs.snowflake`
├── cli.py           # Unified CLI entry point and command routing
└── query.py         # Query execution logic with template variable support
```

### Usage

The library can be used in three ways:

1. **Via shell wrapper (recommended for users):**
   ```bash
   ./box.sh snowflake query analysis.sql --format json
   ./box.sh snowflake analysis.sql --limit 100  # 'query' is implied
   ```

2. **As a Python module:**
   ```bash
   python -m libs.snowflake query analysis.sql --output ./results/
   python -m libs.snowflake analysis.sql --debug
   ```

3. **Programmatically:**
   ```python
   from libs.snowflake import connect, execute_query, load_query
   
   conn = connect()
   query = load_query("analysis.sql")
   columns, rows = execute_query(conn, query)
   ```

### Why This Design?

**Single Source of Truth:**
- All command logic, argument parsing, and help text live in Python modules
- The `box.sh` wrapper is now just 4 lines: `python -m libs.snowflake "$@"`
- Documentation, validation, and error handling are centralized

**Maintainability:**
- No duplication between bash and Python
- Easier to test (Python unit tests vs. bash scripts)
- Type hints and docstrings for better IDE support

**Reusability:**
- Functions can be imported and used programmatically
- CLI can be extended without touching `box.sh`
- Same pattern used across all libs (investigation, datadog, etc.)

---

## Features

### Template System

This CLI provides two types of templating features:

**Metabase-Compatible (portable):**
- `{{variable}}` - Required variables
- `[[ AND col = {{variable}} ]]` - Optional filters
- `{{#template-name}}` - Reference other queries/CTEs
- Works in both Metabase and this CLI

**CLI-Specific (how templates are defined):**
- `-- INCLUDE: path/to/file.sql AS {{#name}}` - Define template mappings
- In Metabase: Templates map to saved query names automatically
- In this CLI: You explicitly define mappings via INCLUDE directives

### Key Capabilities

- ✅ Execute SQL files with multiple output formats (CSV, JSON, Markdown)
- ✅ Metabase template variable substitution
- ✅ SQL file composition via INCLUDE directives
- ✅ Row limiting for quick previews
- ✅ Automatic connection management via TOML config
- ✅ Debug mode for troubleshooting

---

## Commands

### `query` - Execute SQL Query

Execute a SQL query from a file and save results to an output file.

**Usage:**
```bash
./box.sh snowflake query <sql-file> [options]
./box.sh snowflake <sql-file> [options]  # 'query' is implied
```

**Options:**
- `--output <path>` - Specify output filename or directory (default: `output.<format>` next to SQL file)
- `--format <fmt>` - Output format: `csv`, `json`, `md` (default: `csv`)
- `--limit <N>` - Limit results to N rows
- `--var-<name> <value>` - Set Metabase template variable
- `--debug` - Show detailed debug information including SQL content

**Examples:**
```bash
# Execute a query with default CSV output
./box.sh snowflake query analysis.sql

# Execute with custom output location and format
./box.sh snowflake query analysis.sql --output ./results/ --format json

# Execute with row limit
./box.sh snowflake query analysis.sql --limit 100

# Execute with template variables
./box.sh snowflake query analysis.sql --var-signup_method standard --var-datacenter us1

# Implicit query command (shorter)
./box.sh snowflake analysis.sql --format md --debug
```

**What it does:**
1. Loads SQL query from file
2. Preprocesses query to handle `INCLUDE` directives and template variables
3. Connects to Snowflake using `~/.snowflake/connections.toml`
4. Executes query (with optional `LIMIT`)
5. Saves results to output file in specified format
6. Displays preview of first 5 rows

**Output Formats:**
- **CSV** - Standard comma-separated values
- **JSON** - Array of objects with column names as keys
- **MD** - Markdown table format

---

## Template Variables

Queries support **Metabase-compatible template variable syntax** for dynamic filtering and parameterization:

### Optional Filters

These sections are removed if the variable is not provided:

```sql
SELECT *
FROM table
WHERE   
    1=1
    -- Metabase Template variables (optional filters)
    [[ AND o.signup_type = {{signup_type}} ]]
    [[ AND o.paid_billing_plan_org = {{paid_billing_plan_org}} ]]
```

**Usage:**
```bash
# Without variables - the [[ ]] sections are removed
./box.sh snowflake query.sql

# With variables - values are substituted
./box.sh snowflake query.sql --var-signup_method standard --var-datacenter us1
```

### Required Variables

These variables must be provided or an error occurs:

```sql
SELECT *
FROM table
WHERE org_id = {{org_id}}  -- Required!
```

**Usage:**
```bash
# This will error - org_id is required
./box.sh snowflake query.sql

# This works - org_id provided
./box.sh snowflake query.sql --var-org_id 12345
```

### Variable Syntax Summary

| Syntax | Type | Metabase Compatible? | Description |
|--------|------|---------------------|-------------|
| `{{variable}}` | Required Variable | ✅ Yes | Required variable (error if not provided) |
| `[[ AND col = {{variable}} ]]` | Optional Filter | ✅ Yes | Optional filter (removed if not provided) |
| `{{#template-name}}` | Query Reference | ✅ Yes | References another query/CTE |
| `-- INCLUDE: ... AS {{#name}}` | Template Definition | ❌ CLI-only | Defines what `{{#name}}` maps to (file path) |

**Notes:**
- Variables can be strings, numbers, or dates
- Variable names must be alphanumeric with underscores
- **Metabase compatibility**: `{{#...}}` references work in both, but Metabase infers mappings from saved query names while this CLI uses explicit `INCLUDE` directives

---

## INCLUDE Directives

Queries can include content from other SQL files as named templates using `INCLUDE` directives.

**Metabase Compatibility:**
- The `{{#template-name}}` syntax for referencing queries is **Metabase-compatible**
- In Metabase: Query references map to saved query names automatically
- In this CLI: You explicitly define mappings using `-- INCLUDE:` directives (**CLI-specific**)

This allows you to write queries that work in Metabase while maintaining file-based query composition in this CLI.

### Basic Syntax

```sql
-- INCLUDE: path/to/file.sql AS {{#template-name}}
```

### Named Includes (Recommended)

Include SQL as a named template and reference it in your query:

```sql
-- ==============================================================================
-- Example: Customer Analysis with Reusable Base Query
-- ==============================================================================

-- INCLUDE: knowledge/questions/_core/131569-legit-signup-orgs.sql AS {{#legit-orgs}}

SELECT
    o.org_id,
    o.signup_method,
    o.datacenter,
    o.signup_type,
    o.paid_billing_plan_org,
    o.signup_timestamp
FROM {{#legit-orgs}} o
WHERE o.signup_timestamp >= DATEADD('month', -3, CURRENT_DATE())
    [[ AND o.signup_type = {{signup_type}} ]]
    [[ AND o.paid_billing_plan_org = {{paid_billing_plan_org}} ]]
ORDER BY o.signup_timestamp DESC
```

**How it works:**
1. `-- INCLUDE: ... AS {{#legit-orgs}}` - Loads the SQL file and names it `legit-orgs`
2. `FROM {{#legit-orgs}} o` - References the included SQL as a CTE/subquery
3. The included SQL is injected inline as if it were a CTE

### Inline Includes (Legacy)

Simple inclusion without naming:

```sql
-- INCLUDE: ../common/date_ranges.sql

SELECT *
FROM my_table
WHERE date_range = 'Q4_2024'
```

The included file's content is injected directly at the include location.

### Path Resolution

- **Relative paths**: Resolved relative to the SQL file's directory
- **Recursive includes**: Included files can themselves include other files
- **No circular dependencies**: The CLI detects and prevents infinite loops

### Use Cases

**1. Reusable Base Queries:**
```sql
-- Base query in knowledge/base/active_customers.sql
SELECT org_id, org_name, tier
FROM customers
WHERE is_active = TRUE

-- Use in multiple analyses
-- INCLUDE: knowledge/base/active_customers.sql AS {{#active-customers}}
SELECT tier, COUNT(*) as customer_count
FROM {{#active-customers}}
GROUP BY tier
```

**2. Common Filters:**
```sql
-- Filters in knowledge/filters/paid_orgs.sql
org.billing_plan IN ('enterprise', 'pro')
AND org.is_test = FALSE

-- Use in queries
SELECT *
FROM organizations org
WHERE -- INCLUDE: knowledge/filters/paid_orgs.sql
```

**3. Shared CTEs:**
```sql
-- CTE in knowledge/cte/date_ranges.sql
WITH date_ranges AS (
  SELECT
    DATE_TRUNC('month', CURRENT_DATE()) as current_month,
    DATE_TRUNC('month', DATEADD('month', -1, CURRENT_DATE())) as prior_month
)

-- Use in analysis
-- INCLUDE: knowledge/cte/date_ranges.sql
SELECT * FROM date_ranges
```

### Best Practices

**✅ DO:**
- Use named includes (`AS {{#name}}`) for clarity and flexibility
- Store reusable queries in a `knowledge/` directory structure
- Document what each included file provides
- Use includes to avoid copy-pasting common query logic

**❌ DON'T:**
- Create circular include dependencies
- Use includes for tiny snippets (just inline them)
- Include files with side effects (like `CREATE TABLE`)

### Example Structure

```
queries/
├── knowledge/
│   ├── base/
│   │   ├── active_customers.sql      # Base customer query
│   │   └── legit_signups.sql         # Clean signup data
│   ├── filters/
│   │   ├── paid_orgs.sql             # Common org filters
│   │   └── test_exclusions.sql       # Test data exclusions
│   └── cte/
│       ├── date_ranges.sql           # Reusable date logic
│       └── cohorts.sql               # Customer cohort definitions
└── analysis/
    ├── customer_growth.sql           # Uses INCLUDE for base queries
    └── revenue_trends.sql            # Composes multiple includes
```

### Template Variables in Includes

Included files can also use template variables:

```sql
-- In knowledge/base/filtered_customers.sql
SELECT * FROM customers
WHERE 1=1
  [[ AND signup_method = {{signup_method}} ]]

-- In main query
-- INCLUDE: knowledge/base/filtered_customers.sql AS {{#customers}}
SELECT COUNT(*) FROM {{#customers}}
```

Variables are substituted **after** all includes are resolved.

---

## Connection Configuration

Snowflake connection details are read from `~/.snowflake/connections.toml`:

```toml
[default]
account = "your_account"
user = "your_username"
password = "your_password"
warehouse = "COMPUTE_WH"
database = "ANALYTICS_DB"
schema = "PUBLIC"
role = "ANALYST"
```

**Security Notes:**
- Never commit connection files to git
- Use environment variables or secure credential storage in production
- Consider using SSO/OAuth for enhanced security

---

## Output File Resolution

The `--output` option intelligently determines where to save results:

### Auto-detection (no `--output` specified)

1. **Investigation step directory** - If SQL file is in a step folder: `runs/.../01-step/output.csv`
2. **Same directory as SQL file** - Otherwise: `path/to/query/output.csv`

### Explicit output path

```bash
# Directory - saves as results.csv in that directory
./box.sh snowflake query.sql --output ./my_results/

# Filename - saves to that specific file
./box.sh snowflake query.sql --output ./analysis_results.csv

# Relative to SQL file
./box.sh snowflake query.sql --output ../shared/results.csv
```

---

## Programmatic Usage

Import and use functions directly in Python code:

```python
from pathlib import Path
from libs.snowflake import connect, execute_query, load_query, preprocess_query, save_as_csv

# Load and preprocess query
sql_file = Path("analysis.sql")
query = load_query(sql_file)
variables = {"signup_method": "standard"}
preprocessed = preprocess_query(query, sql_file.parent, variables)

# Execute query
conn = connect()
try:
    columns, rows = execute_query(conn, preprocessed, limit=1000)
    
    # Save results
    save_as_csv(Path("output.csv"), columns, rows)
    
    # Or process in memory
    for row in rows:
        print(dict(zip(columns, row)))
finally:
    conn.close()
```

**Available Functions:**
- `connect()` - Connect to Snowflake using default config
- `execute_query(conn, query, limit=None)` - Execute query and return results
- `load_query(path)` - Load SQL from file
- `preprocess_query(query, base_dir, variables)` - Handle INCLUDEs and variables
- `save_as_csv(path, columns, rows)` - Save results as CSV
- `save_as_json(path, columns, rows)` - Save results as JSON
- `save_as_markdown(path, columns, rows)` - Save results as Markdown table

---

## Debug Mode

Enable detailed logging with `--debug`:

```bash
./box.sh snowflake query.sql --debug
```

**Shows:**
- Resolved file paths
- Connection details (database, warehouse, role)
- Preprocessed SQL query (after INCLUDE and variable substitution)
- Query execution time
- Column count and names
- Row count
- Output file location
- Full stack traces on errors

**Useful for:**
- Troubleshooting variable substitution issues
- Verifying INCLUDE directive resolution
- Debugging query errors
- Understanding query execution flow

---

## Future Commands

Planned additions:
- `./box.sh snowflake test <sql-file>` - Dry-run query validation without execution
- `./box.sh snowflake explain <sql-file>` - Show query execution plan
- `./box.sh snowflake schema <table>` - Show table schema
- `./box.sh snowflake validate` - Validate connection configuration

---

## Migration Notes

**Before (bash routing):**
```bash
# In box.sh - 7 lines of bash routing logic
snowflake)
    SNOWFLAKE_DIR="$LIBS_DIR/snowflake"
    SNOWFLAKE_SCRIPT="$SNOWFLAKE_DIR/query.py"
    "$SHARED_VENV/bin/python" "$SNOWFLAKE_SCRIPT" "$@"
    exit $?
    ;;
```

**After (pythonic CLI):**
```bash
# In box.sh - 4 lines, single source of truth
snowflake)
    "$SHARED_VENV/bin/python" -m libs.snowflake "$@"
    exit $?
    ;;
```

**Benefits:**
- All documentation in Python (not duplicated in bash)
- Easier to extend with new commands
- Better IDE support with type hints
- Can be imported and used programmatically
- Consistent pattern across all libs

See `libs/CLI_PATTERN.md` for implementation details.

