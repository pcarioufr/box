# Metabase Client

Python client for interacting with Metabase dashboards via the Metabase API.

⚠️  **BETA**: This client is under active development. Breaking changes expected.

## Overview

The Metabase client provides a simplified dashboard-centric interface:
- **Pull**: Download dashboards from Metabase to local YAML files (automatically includes all questions)
- **Push**: Create or update dashboards in Metabase (automatically handles questions and collections)

All question and collection operations are handled automatically through dashboard operations, simplifying the workflow for both humans and agents.

**File Format**: Dashboards and cards are stored in a hierarchical YAML format that mirrors the UI structure. See [model.md](./model.md) for complete format documentation.

**Configuration**: Color palettes and other settings are defined in [config.yaml](./config.yaml).

## Configuration

### Color Palettes

The `config.yaml` file defines reusable color palettes that can be referenced in card visualizations. This ensures consistent colors across all dashboards.

**Available palettes:**
- `enum` - 8 colors for categorical data (enum1-enum8)
- `scale` - 7 colors for diverging scales (scale1-scale7)
- `blue-shades`, `green-shades`, `purple-shades`, `orange-shades`, `red-shades`, `yellow-shades`, `pink-shades`, `grey-shades` - 6 shades each (light to dark)

**Usage in card YAML:**

```yaml
visualization_settings:
  series_settings:
    MY_METRIC:
      color: "blue2"  # References blue-shades/blue2 from config.yaml
```

You can also use direct hex codes for custom colors:

```yaml
series_settings:
  MY_METRIC:
    color: "#509EE3"  # Direct hex code
```

See [config.yaml](./config.yaml) for the complete list of available colors.

## File Organization

The Metabase client stores dashboard and card definitions in a structured directory hierarchy.

### Terraform-like Workflow (State Files)

For **locally-managed dashboards** (e.g., investigations), the client uses a `.state.yaml` file to track mappings between local files and Metabase resources:

**Key principles:**
- **Resource files** (dashboard.yaml, questions/*.yaml, SQL files) describe **desired state** (WHAT you want) - NO IDs
- **State file** (`.state.yaml`) tracks **actual state** (WHERE it lives in Metabase) - IDs only here
- Files remain unchanged after creation (no IDs embedded, no renaming)
- `--parent` flag specifies deployment target (not in YAML content)

**Example structure:**
```
my-dashboard/
  ├── dashboard.yaml           # References questions by filename (no IDs)
  ├── questions/
  │   ├── metric1.yaml         # No ID
  │   ├── metric1-query.sql
  │   ├── metric2.yaml         # No ID
  │   └── metric2-query.sql
  └── .state.yaml              # Maps filenames → Metabase IDs
```

**Benefits:**
- ✅ Git-friendly (resource files never change after creation)
- ✅ Reusable (same dashboard YAML for dev/staging/prod with different `--parent`)
- ✅ No drift risk (IDs can't get out of sync between files)
- ✅ Terraform-like: resource files = config, state file = reality

**See [model.md](./model.md#state-files-terraform-like-workflow) for complete specification.**

### Default Output Structure

When using `dashboard pull` (always downloads questions):

```
my-dashboard/
├── dashboard.yaml                           # Dashboard definition
├── .state.yaml                              # State file tracking Metabase IDs
├── 01-overview/                             # Tab 1: Overview
│   ├── 124411-weekly-signups.yaml
│   ├── 124411-weekly-signups-query.sql
│   ├── 101647-signup-funnel.yaml
│   └── 101647-signup-funnel-query.sql
├── 02-intake/                               # Tab 2: Intake
│   ├── 132314-product-table.yaml
│   └── 132314-product-table-query.sql
└── 03-conversion/                           # Tab 3: Conversion
    ├── 95919-user-activity.yaml
    └── 95919-user-activity-query.sql
```

**Note**:
- The dashboard YAML is saved as `dashboard.yaml` at the root
- A `.state.yaml` file tracks Metabase IDs (Terraform-like workflow)
- Questions are organized into flat tab subfolders: `01-{tab-name}/`, `02-{tab-name}/`, etc.
- Each question consists of a `.yaml` file and a `-query.sql` file with matching names
- SQL queries are stored in separate `.sql` files alongside the YAML

### Debug Mode

When using the `--debug` flag, raw JSON responses from the Metabase API are saved alongside YAML files:

```
knowledge/questions/
├── 75122-onboarding-signups/
│   ├── 75122-onboarding-signups.yaml
│   ├── 75122-onboarding-signups.json      # Raw API response (debug)
│   └── 01-overview/
│       ├── 124411-weekly-signups.yaml
│       ├── 124411-weekly-signups-query.sql
│       └── 124411-weekly-signups.json     # Raw API response (debug)
```

**When to use debug mode:**
- Troubleshooting conversion issues
- Inspecting raw Metabase API responses
- Comparing YAML output with JSON source

### Overwrite Protection

When using `get` commands, if a directory or file with the same ID already exists in the output directory, you will be prompted to confirm before overwriting:

```bash
./box.sh metabase dashboard get 75122
# ⚠️  Warning: Found existing directory with ID 75122:
#     - 75122-old-name/ (will be replaced with 75122-new-name/)
# Overwrite? [y/N]:
```

If you confirm, the old directory/file will be deleted and replaced with the new one. This prevents accidental file accumulation when dashboard names change in Metabase.

## Commands

### Global Options

The `--debug` flag is available as a global option for all commands:

```bash
./box.sh metabase --debug dashboard <pull|push> [args...]
```

When enabled, `--debug`:
- Enables verbose logging output
- Shows detailed API request/response information
- Saves raw JSON responses to disk (for pull commands)
- Displays full stack traces on errors

**Examples:**

```bash
# Debug a dashboard pull operation
./box.sh metabase --debug dashboard pull 75122 --dir my-dashboard/

# Debug a dashboard push operation
./box.sh metabase --debug dashboard push --dir my-dashboard/ --parent 20138 --database 43
```

**Note:** The `--debug` flag can also be passed at the command level (after the subcommand) for backward compatibility, but the global syntax is preferred.

### Pull Dashboard

Download a dashboard from Metabase to a local directory (automatically includes all questions):

```bash
./box.sh metabase dashboard pull <dashboard_id> --dir <directory> [options]
```

**Options:**
- `<dashboard_id>` - Dashboard ID to pull (required)
- `--dir <directory>` - Target directory (required, will be created if missing)
- `--debug` - Also save raw JSON files
- `--help` - Show help message

**Examples:**

```bash
# Pull a dashboard to a specific directory
./box.sh metabase dashboard pull 75122 --dir my-dashboard/

# Pull with debug JSON files
./box.sh metabase dashboard pull 75122 --dir my-dashboard/ --debug
```

**What it does:**
1. Checks if a directory with the same ID already exists (prompts for overwrite confirmation)
2. Fetches dashboard definition from `/api/dashboard/{id}`
3. Creates target directory if it doesn't exist
4. Converts to YAML format (user-friendly, hierarchical)
5. Adds parameter name comments to parameter mappings (e.g., `parameter_id: abc123  # Signup Type`)
6. Saves dashboard YAML: `dashboard.yaml`
7. Automatically extracts all card IDs and fetches each question
8. Organizes questions into tab-based subfolders:
   - Each tab gets a subfolder: `{rank:02d}-{tab-slug}/` (e.g., `01-overview/`, `02-intake/`)
   - Questions are saved as flat files: `{card_id}-{slug}.yaml` and `{card_id}-{slug}-query.sql`
   - SQL queries are stored in separate `.sql` files
9. If `--debug`, also saves raw JSON responses

**Output Structure:**
- `{dir}/` - Dashboard folder
  - `dashboard.yaml` - Dashboard definition (YAML)
  - `dashboard.json` - Raw API response (debug only)
  - `.state.yaml` - State file tracking Metabase IDs
  - `{rank:02d}-{tab-slug}/` - Tab folders (flat structure)
    - `{card_id}-{slug}.yaml` - Question definition
    - `{card_id}-{slug}-query.sql` - Question SQL query
    - `{card_id}-{slug}.json` - Raw API response (debug only)

**Parameter Comments**: When downloading dashboards, parameter IDs in parameter mappings are annotated with their display names for readability:
```yaml
parameter_mappings:
  - parameter_id: 9c811c10  # Signup Type
    target: signup_type
  - parameter_id: a7f23b89  # Date Range
    target: date_range
```

**File Format**: See [model.md](./model.md) for complete YAML format documentation.

### Validate Dashboard

Check dashboard YAML/SQL files for common issues before pushing:

```bash
./box.sh metabase dashboard validate --dir <directory>
```

**What it checks:**
- Dashboard structure (missing keys, broken question_file references, missing SQL files)
- Parameter wiring (parameter_mappings reference valid dashboard parameter IDs)
- Parameter defaults (number types should use array format `[2]` not scalar `2`)
- SQL gotchas:
  - Single-escaped regex (`\d+` instead of `\\d+`) — silently matches nothing in Metabase
  - Numeric arguments to `TRY_TO_TIMESTAMP` / `TO_TIMESTAMP` — Metabase JDBC driver rejects these
  - Template variables without YAML parameter declarations — default to type `text`

**Examples:**

```bash
# Validate before pushing
./box.sh metabase dashboard validate --dir my-dashboard/
# ✅ All checks passed

# Fix issues, then push
./box.sh metabase dashboard push --dir my-dashboard/
```

### Push Dashboard

Create or update a dashboard in Metabase from a local directory (automatically handles questions and collections):

```bash
./box.sh metabase dashboard push --dir <directory> [options]
```

**Required:**
- `--dir <directory>` - Dashboard directory containing dashboard.yaml and questions/ (required)

**Options (for new dashboards):**
- `--parent <id>` - Parent collection ID where dashboard will be created (defaults to `METABASE_COLLECTION_ID` from .env, required for new dashboards)
- `--database <id>` - Database ID for questions (defaults to `METABASE_DATABASE_ID` from .env, required for new dashboards)
- `--question <FILE>` - Only push this question file (relative to `--dir`). Can be repeated to push multiple. Dashboard definition is always pushed.
- `--debug` - Enable debug output
- `--help` - Show help message

**Examples:**

```bash
# Create a new dashboard (uses METABASE_COLLECTION_ID and METABASE_DATABASE_ID from .env)
./box.sh metabase dashboard push --dir my-dashboard/

# Create a new dashboard with explicit parent collection and database
./box.sh metabase dashboard push --dir my-dashboard/ --parent 20138 --database 43

# Update an existing dashboard (uses IDs from .state.yaml)
./box.sh metabase dashboard push --dir my-dashboard/

# Update only specific questions (dashboard definition is always pushed)
./box.sh metabase dashboard push --dir my-dashboard/ --question 01-overview/my-question.yaml

# Push with debug mode
./box.sh metabase dashboard push --dir my-dashboard/ --parent 20138 --database 43 --debug
```

**What it does:**

**For new dashboards** (no `.state.yaml` exists):
1. Validates that dashboard.yaml does NOT have a dashboard ID
2. Creates all questions from questions/ directory via `POST /api/card`
3. Translates question file references to card IDs
4. Creates dashboard with cards via `POST /api/dashboard`
5. **Generates `.state.yaml`** with dashboard ID, collection_id, database_id, and question mappings
6. **Source files remain unchanged** (no IDs added, no renaming)

**For existing dashboards** (`.state.yaml` exists):
1. Reads dashboard ID and question mappings from `.state.yaml`
2. Updates questions via `PUT /api/card`
3. Updates dashboard content via `PUT /api/dashboard/{id}`
4. Updates `.state.yaml` with any new mappings

**Important Safety Checks:**
- For new dashboards: If dashboard.yaml has an `id`, the command will **fail** 
- For new dashboards: If `.state.yaml` exists, the command will **fail** (dashboard already created)
- If `collection_id` or `database_id` is in YAML, it's **ignored with warning** (use `--parent` and `--database` flags instead)
- Failed questions are logged but don't stop dashboard creation/update

**Auto-Collection Creation:**
- When creating a new dashboard, a sub-collection is automatically created within the parent collection
- The sub-collection is named after the dashboard
- Example: Dashboard "Product Analytics" → Collection "Product Analytics" created in parent collection
- This keeps dashboards and their questions organized in dedicated collections

**Terraform-like Workflow:**
- **Resource files** (dashboard.yaml, questions/*.yaml, SQL files) describe **desired state** - NO IDs
- **State file** (`.state.yaml`) tracks **actual state** (Metabase IDs) - IDs only here
- Files remain unchanged after creation (no IDs embedded, no renaming)
- Same dashboard YAML can be deployed to dev/staging/prod with different `--parent` and `--database` flags


### Dashboard Format

Show dashboard YAML format help and examples:

```bash
./box.sh metabase dashboard format
```

### Question Format

Show question/card YAML format help and examples:

```bash
./box.sh metabase question format
```

Covers common display types (table, bar, line, pie, row, area, scalar, funnel), SQL file references, parameter definitions, and visualization settings.

## File Format

Dashboards and cards are stored in YAML format for readability and version control.

**Key Features:**
- Hierarchical structure: Dashboard → Tabs → Cards
- Human-readable and editable
- Inline comments and documentation
- SQL can be inline or referenced from files

**Complete documentation**: See [model.md](./model.md) for:
- Dashboard YAML format with examples
- Card (question) YAML format with visualization examples
- Field reference for all object types
- Object relationships and hierarchy
- Comparison with JSON API format

**Quick Example:**
```yaml
dashboard:
  id: 75122
  name: "[Onboarding] Signups & Trials"
  tabs:
    - name: "Overview"
      cards:
        - position: {row: 0, col: 0, size_x: 12, size_y: 8}
          card: {question_id: 124411}
```

## Metabase Object Model

The Metabase client works with several core concepts:
- **Dashboard**: Container for visualizations organized into tabs
- **Tab**: Organizes cards within a dashboard
- **Card**: A saved question/query (what data to show and how)
- **Card Placement**: A reference to a card on a dashboard (where it appears)
- **Virtual Card**: Inline text/heading content (no separate card)
- **Parameter**: Dashboard-level filters that map to card parameters

**Complete documentation**: See [model.md](./model.md) for:
- Object relationships and hierarchy
- Field reference for all types
- ID management when updating
- Detailed examples

### Card (Question)

A card is a saved question/query in Metabase. Cards exist independently and can be reused across multiple dashboards.

**Key aspects:**
- Contains the SQL query and visualization settings
- Can be referenced by multiple dashboard placements
- Supports various visualization types (table, bar, line, combo, etc.)
- Each visualization type has specific settings (stacking, axes, colors, formatting)

**Complete documentation**: See [model.md](./model.md) for:
- Full YAML format specification
- 7 visualization examples (table, bar, line, combo, area, etc.)
- Visualization settings reference
- Parameter definitions

### Dashboard Placement

When a card appears on a dashboard, it's called a "dashboard placement" or "dashcard". This adds positioning and dashboard-specific properties to the card reference.

**Complete documentation**: See [model.md](./model.md) for object relationships and field details.

## Configuration

### Environment Variables

Set in `.env` file (at repo root):

```bash
# Metabase instance URL
METABASE_URL=https://metabase-analytics.us1.prod.dog

# Metabase Database ID (for creating questions)
METABASE_DATABASE_ID=43

# Parent Collection ID (where to create new dashboards)
# This will be used as the default --parent value if not specified in the CLI
# Example: ./box.sh metabase dashboard push --dir <dir> --database <db>
#   (will use METABASE_COLLECTION_ID as default parent)
# Or explicitly: ./box.sh metabase dashboard push --dir <dir> --parent <id> --database <db>
METABASE_COLLECTION_ID=20103

# API key for authentication (required)
METABASE_API_KEY=your-metabase-api-key-here
```

### Getting Your API Key

1. Log in to Metabase
2. Navigate to: Settings → Admin Settings → Settings → Authentication
3. Find "API Keys" section
4. Create a new API key or use an existing one
5. Copy the key to your `.env` file

## Workflow Examples

### Download a Dashboard for Review

```bash
# Pull dashboard and all its questions to a local directory
./box.sh metabase dashboard pull 75122 --dir my-dashboard/

# Review the YAML files
ls my-dashboard/
# dashboard.yaml
# .state.yaml
# 01-overview/
# 02-intake/
# ...
```

### Duplicate a Dashboard

```bash
# 1. Pull the source dashboard
./box.sh metabase dashboard pull 75122 --dir my-dashboard/

# 2. Remove .state.yaml to create a new dashboard
rm my-dashboard/.state.yaml

# 3. Push to create new dashboard (generates new .state.yaml, files unchanged)
./box.sh metabase dashboard push --dir my-dashboard/ --parent 20138 --database 43

# The new dashboard and all its questions are now created with new IDs
```

### Modify and Update a Dashboard

```bash
# 1. Pull dashboard
./box.sh metabase dashboard pull 89021 --dir my-dashboard/

# 2. Edit the YAML files (add/remove cards, change positions, update queries, etc.)
# Edit: my-dashboard/dashboard.yaml
# Edit: my-dashboard/01-overview/124411-weekly-signups-query.sql

# 3. Push changes (uses IDs from .state.yaml to update existing dashboard)
./box.sh metabase dashboard push --dir my-dashboard/
```

### Deploy Dashboard to Different Environment

```bash
# 1. Pull from production
./box.sh metabase dashboard pull 75122 --dir my-dashboard/

# 2. Remove .state.yaml
rm my-dashboard/.state.yaml

# 3. Deploy to staging with different collection and database
./box.sh metabase dashboard push --dir my-dashboard/ --parent 99999 --database 55
```

## Version Control

YAML files are tracked in git to:
- ✅ Document dashboard structure over time
- ✅ Review changes to dashboards via diffs (YAML produces cleaner diffs than JSON)
- ✅ Share dashboard definitions across team
- ✅ Enable reproducibility


## API Reference

This client uses the Metabase API:
- Documentation: https://www.metabase.com/docs/latest/api
- Dashboard GET: `GET /api/dashboard/{id}`
- Dashboard POST: `POST /api/dashboard`
- Dashboard PUT: `PUT /api/dashboard/{id}`
- Card GET: `GET /api/card/{id}`
- Authentication: `X-API-KEY` header

## FAQ

### How do I work with questions and collections?

All question and collection operations are handled automatically through dashboard operations:
- **Pull dashboard**: Automatically downloads all questions
- **Push dashboard**: Automatically creates/updates questions and handles collections

This simplified approach makes the workflow easier for both humans and agents.

### Can I update a dashboard that I just pulled?

**Yes!** The push operation intelligently handles both creation and updates:

```bash
# Pull dashboard
./box.sh metabase dashboard pull 89021 --dir my-dashboard/
# Creates .state.yaml with dashboard ID and question mappings

# Edit files as needed
# ...

# Push changes (detects existing .state.yaml and updates)
./box.sh metabase dashboard push --dir my-dashboard/
```

The `.state.yaml` file tracks which dashboard and questions in Metabase correspond to your local files.

### What is the .state.yaml file?

The `.state.yaml` file is similar to Terraform state - it tracks the mapping between your local files and Metabase resources:

```yaml
meta:
  last_synced: 2025-12-20T10:30:00Z
  database_id: 43

dashboard:
  file: dashboard.yaml
  id: 89021
  collection_id: 20138
  url: https://metabase.../dashboard/89021

questions:
  124411:  # Metabase ID is the primary key
    file: 01-overview/124411-weekly-signups.yaml
  132314:
    file: 02-intake/132314-product-table.yaml
```

**Structure Notes:**
- `meta.database_id`: Database ID for all questions (deployment detail)
- `dashboard.file`: Always `dashboard.yaml` (hardcoded filename)
- `dashboard.url`: Metabase URL for convenience (not used by CLI)
- `questions`: Map of Metabase question ID → file path (relative to dashboard dir)

- **Pull**: Creates `.state.yaml` automatically
- **Push (new)**: Creates `.state.yaml` after successful creation
- **Push (update)**: Uses `.state.yaml` to know which resources to update

### Can I deploy the same dashboard to multiple environments?

**Yes!** Remove the `.state.yaml` file between deployments:

```bash
# Pull from prod
./box.sh metabase dashboard pull 75122 --dir my-dashboard/

# Deploy to staging
rm my-dashboard/.state.yaml
./box.sh metabase dashboard push --dir my-dashboard/ --parent 111 --database 22

# Deploy to prod (different IDs)
rm my-dashboard/.state.yaml  
./box.sh metabase dashboard push --dir my-dashboard/ --parent 222 --database 33
```

Each deployment gets its own `.state.yaml` with environment-specific IDs.

## Troubleshooting

### API Key Not Set

```
❌ Configuration error: METABASE_API_KEY not set
```

**Solution**: Set `METABASE_API_KEY` in your `.env` file (see Configuration section).

### Dashboard Not Found

```
❌ HTTP 404
```

**Solution**: Verify the dashboard ID exists in Metabase. Check the dashboard URL in your browser (e.g., `https://metabase.../dashboard/75122`).

### Authentication Failed

```
❌ HTTP 401
```

**Solution**: Your API key may be invalid or expired. Generate a new API key in Metabase admin settings.

### Missing Tabs Error

```
❌ Content has X dashcards with tab references but 'tabs' field is missing
```

**Solution**: Your content file has dashcards that reference tabs, but the `tabs` field is not included. Add `tabs` to your content JSON:

```bash
# Include tabs in your content file
cat source.json | jq '{dashcards, tabs, parameters}' > content.json
```

### Card Get Failures

When pulling dashboards (which automatically downloads questions), some questions may fail (e.g., `403 Forbidden`). Common reasons:
- **403 Forbidden**: Card is in a personal collection that your API key can't access
- **404 Not Found**: Card no longer exists
- **401 Unauthorized**: API key permissions insufficient

## Development Status

### ✅ Implemented

- Pull dashboards from Metabase as YAML (automatically includes all questions)
- Push dashboards to Metabase (automatically handles question creation/updates)
- Terraform-like state management (`.state.yaml` tracks Metabase IDs)
- Smart create vs. update based on `.state.yaml`
- Selective question push (`--question` filter)
- Pre-push validation (`dashboard validate`)
- Overwrite protection for pull commands
- SQL file separation for questions
- Tab-based organization for questions
- Color palette management for visualizations
- Parameter name comments in YAML output (for readability)
- Dashboard parameters and parameter mappings (template variables)
- Debug mode with raw JSON output
- Format help commands (`dashboard format`, `question format`)

### 🚧 In Progress

- Additional dashboard properties (as discovered)
- Enhanced error messages

### 📋 Planned

- Webhook/change detection
- Dashboard templates

## Contributing

This is an internal library under active development. As new Metabase object properties and relationships are discovered, update:

1. **Model Documentation** (`model.md`) - Document new properties and relationships in the ORM
2. **Put/Post Commands** - Add support for new fields
3. **Examples** - Add usage examples
4. **Tests** - Add test coverage

## See Also

- `dashboard.py` - Dashboard pull/push implementation
- `question.py` - Question operations (used internally by dashboard)
- `collection.py` - Collection operations (used internally by dashboard)
- `cli.py` - CLI entry point
- `model.md` - YAML format documentation
- Metabase API Documentation: https://www.metabase.com/docs/latest/api

