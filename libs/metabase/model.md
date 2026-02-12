# Metabase Object Model & File Formats

**Purpose**: This document defines the YAML file formats for Metabase dashboards and questions (cards).

**Audience**: AI agents and developers working with the Metabase client library.

**Last Updated**: 2025-12-15

---

## Table of Contents

1. [Overview](#overview)
2. [State Files (Terraform-like Workflow)](#state-files-terraform-like-workflow)
3. [Dashboard YAML Format](#dashboard-yaml-format)
4. [Question (Card) YAML Format](#question-card-yaml-format)
5. [Visualization Examples](#visualization-examples)
6. [Object Relationships](#object-relationships)
7. [Field Reference](#field-reference)

---

## Overview

### Format Philosophy

The Metabase client uses YAML format that mirrors the UI hierarchy: **Dashboard → Tabs → Card Placements → Questions**

**Benefits:**
- ✅ Hierarchical structure matches UI
- ✅ Human and AI readable
- ✅ Version control friendly (clear diffs)
- ✅ Supports inline comments
- ✅ No ID cross-references in nested structures

### Key Terminology

| Term | Description | Notes |
|------|-------------|-------|
| **Dashboard** | Container for visualizations organized in tabs | Top-level object |
| **Tab** | Organizes card placements within a dashboard | Optional, dashboards can be flat |
| **Card Placement** | Reference to a question on a dashboard (position + mappings) | The "where" |
| **Question** | Saved query with visualization settings | The "what" (also called "card" in Metabase API) |
| **Virtual Card** | Inline text/heading without a saved question | No question_id, content is inline |
| **Parameter** | Dashboard-level filter that maps to question parameters | Global filters |

### YAML vs JSON

- **YAML files** (`*.yaml`): Human/AI editable format for version control
- **JSON format**: Metabase API format (automatic conversion by library)
- **SQL files** (`*-query.sql`): Separate files for SQL queries

---

## State Files (Terraform-like Workflow)

### Purpose

For **locally-managed dashboards** (e.g., in investigations), a `.state.yaml` file tracks the mapping between local files and Metabase resources without renaming files or directories. This enables a Terraform-like workflow where:
- **Resource files** (dashboard.yaml, question YAMLs, SQL files) describe the **desired state** (WHAT you want)
- **State file** (`.state.yaml`) tracks the **actual state** (WHERE it lives in Metabase)
- Files remain unchanged after creation (no IDs embedded, no renaming)

### State File Format

```yaml
# .state.yaml - Maps Metabase IDs to local files (ID as primary key)
meta:
  last_synced: 2025-12-20T10:30:00Z # ISO timestamp of last sync
  database_id: 43                    # Database ID (shared by all questions)

dashboard:
  file: dashboard.yaml              # Local filename (unchanged)
  id: 89603                         # Metabase dashboard ID (ONLY in state YAML)
  collection_id: 20309              # Parent collection (deployment detail)

questions:
  # Dict mapping: Metabase ID → file info
  135801:                           # Metabase question ID (primary key)
    file: cohort-comparison.yaml    # Local filename (relative to dashboard directory)
  
  135802:
    file: conversion-rates.yaml
```

**With subdirectories (organized questions):**
```yaml
meta:
  last_synced: 2025-12-20T10:30:00Z
  database_id: 43

questions:
  135801:
    file: 01-overview/cohort-comparison.yaml
  135802:
    file: 01-overview/conversion-rates.yaml
  135803:
    file: 02-analysis/deep-dive.yaml
```

### Directory Structure

**Before `dashboard push` (new dashboard):**
```
dashboards/conversion-analysis/
  ├── dashboard.yaml                    # References questions by filename
  ├── 01-overview/
  │   ├── cohort-comparison.yaml        # No ID
  │   ├── cohort-comparison-query.sql
  │   ├── conversion-rates.yaml
  │   └── conversion-rates-query.sql
  └── 02-analysis/
      ├── deep-dive.yaml
      └── deep-dive-query.sql
```

**After `dashboard push` (creates in Metabase):**
```
dashboards/conversion-analysis/         # ✅ Directory name unchanged
  ├── dashboard.yaml                    # ✅ Unchanged (still uses question_file)
  ├── 01-overview/
  │   ├── cohort-comparison.yaml        # ✅ Unchanged (no id)
  │   ├── cohort-comparison-query.sql
  │   ├── conversion-rates.yaml         # ✅ Unchanged (no id)
  │   └── conversion-rates-query.sql
  ├── 02-analysis/
  │   ├── deep-dive.yaml                # ✅ Unchanged (no id)
  │   └── deep-dive-query.sql
  └── .state.yaml                       # ✅ NEW - maps paths to IDs
```

### How It Works

**Dashboard YAML references questions by file path:**
```yaml
dashboard:
  name: "Conversion Analysis"
  tabs:
    - name: "Overview"
      position: 0
      cards:
        # Reference by relative file path (from dashboard directory)
        - position: {row: 0, col: 0, size_x: 24, size_y: 10}
          question_file: 01-overview/cohort-comparison.yaml
        
        - position: {row: 10, col: 0, size_x: 24, size_y: 8}
          question_file: 01-overview/conversion-rates.yaml
```

**State YAML maps IDs to file paths:**
```yaml
meta:
  last_synced: 2025-12-20T10:30:00Z
  database_id: 43

dashboard:
  file: dashboard.yaml
  id: 89603
  collection_id: 20309
  
questions:
  135801:                                    # ← Metabase ID is the key (primary)
    file: 01-overview/cohort-comparison.yaml # ← File path (relative to dashboard dir)
  135802:
    file: 01-overview/conversion-rates.yaml
```

**Translation during `dashboard push`:**
1. Tool reads `question_file: 01-overview/cohort-comparison.yaml`
2. Builds reverse index: finds ID where `questions[ID].file == "01-overview/cohort-comparison.yaml"`
3. Sends to Metabase API: `card_id: 135801`

**Important**: Question paths in dashboard YAML must match the `file` field in state YAML exactly (relative to dashboard directory).

### Workflow Behavior

**During `dashboard push` (new dashboard - no `.state.yaml` exists):**
1. Check if `.state.yaml` exists → **abort if found** (dashboard already created)
2. Read dashboard YAML → extract `question_file` references
3. Create questions from question YAML files → get IDs
4. Write filename→ID mappings to state YAML
5. Translate `question_file` → `card_id` in memory using state mappings
6. Create dashboard with translated `card_id` references
7. Write dashboard ID and `collection_id` to state YAML
8. **All YAML files remain unchanged** (no IDs added, no renaming)

**During `dashboard push` (existing dashboard - `.state.yaml` exists):**
1. Read dashboard ID and question mappings from `.state.yaml`
2. Update questions via `PUT /api/card/{id}`
3. Update dashboard content via `PUT /api/dashboard/{id}`
4. Update `.state.yaml` with any new mappings

**Safety checks:**
- If `.state.yaml` exists for new dashboard, `dashboard push` fails (prevents duplication)
- If `dashboard.id` exists in YAML for new dashboard, `dashboard push` fails
- If `collection_id` found in dashboard YAML, it's ignored with a warning (use `--parent` flag)
- Failed questions are logged but don't stop dashboard creation

**During `dashboard pull`:**
1. Downloads dashboard YAML (without IDs in content)
2. Downloads all questions automatically (without IDs in content)
3. Organizes questions into tab-based subdirectories
4. Generates `.state.yaml` with all mappings
5. Files are clean and immediately reusable for `push`

### Benefits

- **Single source of truth** - IDs only in state YAML (not duplicated in resource files)
- **No renaming** - Dashboard YAML, question YAML files, and directories keep original names
- **Git-friendly** - Dashboard and question YAML files never change after creation (clean history)
- **Predictable** - File paths never change, resource files describe desired state without IDs
- **True Terraform model** - Resource files = WHAT you want, state YAML = WHERE it lives
- **No drift risk** - Can't have ID mismatches between files and state
- **Reusable** - Downloaded files from `pull` can be immediately used for `push` (round-trip compatible)
- **Extensible** - State YAML enables future features:
  - `--sync` - Update only changed resources
  - `--plan` - Show what would change (like Terraform)
  - Drift detection between local and remote

### State YAML vs ID Prefixes

**Locally-managed dashboards** (investigations, `runs/` directory):
- ✅ Use `.state.yaml` to track IDs
- ✅ Dashboard and question YAML files have NO IDs
- ✅ Files keep original names (no ID prefixes)
- ✅ Terraform-like workflow: state tracks reality
- ✅ Command: `dashboard push --dir <directory> --parent <id> --database <id>`

**Remotely-managed dashboards** (knowledge base, `knowledge/` directory):
- ✅ Use ID prefixes in filenames (`89603-dashboard.yaml`)
- ✅ IDs embedded in YAML files
- ✅ No `.state.yaml` needed (IDs visible in filenames/content)
- ✅ Synced FROM Metabase with `dashboard pull`
- ✅ Authoritative source is Metabase, not local files

This distinction clarifies intent and workflow:
- **Local** = you own it, manage with state YAML (IDs separate from content)
- **Remote** = Metabase owns it, sync with ID prefixes (IDs part of identity)

### Design Decisions

**1. Checksums for drift detection?**

**Decision: NO** - Checksums are overkill for v1. Keep state YAML simple. Without checksums, updates are explicit (user runs `dashboard push` to push changes).

**2. Failed question creation?**

**Decision: Partial creation allowed** - Failed questions are logged and tracked:

```yaml
questions:
  cohort-comparison.yaml:
    id: 135801
    last_synced: 2025-12-20T10:30:05Z
  
  conversion-rates.yaml:
    status: failed
    error: "SQL file not found: conversion-rates-query.sql"
    # No id or last_synced for failed questions
```

Dashboard creation proceeds even with failed questions. Cards referencing failed questions are omitted.

**3. Array or dict for questions?**

**Decision: DICT (keyed by filename/path)** - Enables O(1) lookups when translating `question_file` → `card_id`.

**4. Creation metadata?**

**Decision: NO** - State YAML tracks sync state only, not creation metadata (`created_at`, `created_by`).

**5. Hidden or visible?**

**Decision: HIDDEN (`.state.yaml`)** - It's an implementation detail for the Metabase CLI. Users work with dashboard and question YAML files; state file is internal bookkeeping.

---

## Dashboard YAML Format

### Structure

```yaml
dashboard:
  # === METADATA ===
  id: <integer>                    # Dashboard ID (null for new dashboards)
  name: <string>                   # Dashboard name
  width: "full"|"fixed"            # Layout width
  description: <string>            # Optional description
  
  # === GLOBAL FILTERS ===
  parameters:                      # Dashboard-level filters (array)
    - id: <string>                 # Parameter ID (e.g., "9c811c10")
      name: <string>               # Display name
      type: <string>               # Type: "string/=", "date/range", etc.
      slug: <string>               # URL-friendly name
      default: <any>               # Optional default value
  
  # === TABS ===
  tabs:                            # Optional tab organization (array)
    - name: <string>               # Tab display name
      position: <integer>          # Display order (0-indexed)
      cards:                       # Card placements in this tab (array)
        # See card placement format below
```

### Card Placement Format

Two types of card placements exist:

#### 1. Regular Card Placement (references a saved question)

```yaml
- position:                        # Grid position (REQUIRED - must be nested object)
    row: <integer>                 # Row position (0-indexed)
    col: <integer>                 # Column position (0-indexed, max 24)
    size_x: <integer>              # Width in grid units (max 24)
    size_y: <integer>              # Height in grid units
  card_id: <integer>               # Metabase question ID (direct reference)
  parameter_mappings:              # Optional parameter mappings (array)
    - parameter_id: <string>       # Dashboard parameter ID
      target: <string|array>       # Mapping target (simple or complex format)
```

**Important Notes:**
- **Position must be a nested object** - Common mistake is to use flat format (row/col at card level)
- Field is `card_id` (direct reference), or legacy `card.question_id` (nested format)
- All position fields (row, col, size_x, size_y) are required

**Common Error:**
```yaml
# ❌ WRONG - Flat format (will fail with helpful error)
cards:
  - card_id: 135814
    row: 0
    col: 0
    size_x: 18
    size_y: 8

# ✅ CORRECT - Nested position object
cards:
  - position:
      row: 0
      col: 0
      size_x: 18
      size_y: 8
    card_id: 135814
```

#### 2. Virtual Card Placement (inline text/heading)

```yaml
- position:
    row: <integer>
    col: <integer>
    size_x: <integer>
    size_y: <integer>
  virtual_card:                    # Inline content (no saved question)
    display: "text"|"heading"      # Display type
    text: <string>                 # Content (supports markdown)
    text_align: "left"|"center"|"right"  # Optional alignment
```

### Complete Example

```yaml
dashboard:
  id: 75122
  name: "[Onboarding] Signups & Trials"
  width: full
  description: "Tracks user signups and trial conversions"
  
  parameters:
    - id: "9c811c10"
      name: "Signup Type"
      type: "string/="
      slug: "signup_type"
    
    - id: "a7f23b89"
      name: "Date Range"
      type: "date/range"
      slug: "date_range"
      default: "past30days"
  
  tabs:
    - name: "Overview"
      position: 0
      cards:
        # Section header (virtual card)
        - position:
            row: 0
            col: 0
            size_x: 24
            size_y: 2
          virtual_card:
            display: heading
            text: "Signup Funnel"
        
        # Chart referencing saved question with parameter mappings
        - position:
            row: 2
            col: 0
            size_x: 12
            size_y: 8
          card:
            question_id: 101647  # Weekly Signups by Type
          parameter_mappings:
            - parameter_id: "9c811c10"  # Signup Type
              target: signup_type        # Simple format for template variables
            - parameter_id: "a7f23b89"   # Date Range
              target: date_range
        
        # Another chart
        - position:
            row: 2
            col: 12
            size_x: 12
            size_y: 8
          card:
            question_id: 132314
    
    - name: "Details"
      position: 1
      cards:
        - position:
            row: 0
            col: 0
            size_x: 24
            size_y: 12
          card:
            question_id: 124411
```

**Note**: When downloading dashboards, parameter names are automatically added as comments to `parameter_id` fields for better readability.

---

## Question (Card) YAML Format

### Structure

```yaml
question:                          # Root key for question definition
  # === METADATA ===
  id: <integer>|null               # Question ID (null for new questions)
  url: <string>                    # Metabase URL (generated on get, not needed for push)
  name: <string>                   # Question name
  description: <string>            # Optional description
  
  # === QUERY ===
  sql: <string>                    # SQL file path (required, relative to YAML file)
  
  # === QUERY PARAMETERS ===
  parameters:                      # Template tags in SQL (object)
    <param_name>:                  # Parameter name (matches {{param_name}} in SQL)
      type: <string>               # Parameter type: "date/range", "string/=", "number/=", etc.
      display_name: <string>       # Display name in UI
      default: <any>               # Optional default value
  
  # === VISUALIZATION ===
  display: <string>                # Visualization type (required)
  visualization_settings:          # Display settings (object, varies by type)
    # See visualization examples below
```

**Note**: `database_id` is NOT in the YAML file (it's a deployment detail, passed via `--database` CLI flag and stored in `.state.yaml`).

### SQL File Path

**Critical**: The `sql` field must be a **relative path** from the YAML file's location.

**Examples:**
- YAML at `01-overview/my-query.yaml` (in dashboard directory)
- SQL reference: `sql: my-query-query.sql`
- Actual SQL file: `01-overview/my-query-query.sql` (same directory as YAML)

**NOT supported**: Inline SQL (must be in separate `.sql` file)

### Parameters (Template Tags)

Parameters enable dynamic SQL queries with filters.

#### How It Works

**On `push` (YAML → Metabase)**:
- Template tags are **automatically extracted** from your SQL query
- Any `{{variable_name}}` in the SQL becomes a template tag with `type: text`
- INCLUDE directives like `{{#123-alias}}` become template tags with `type: card`
- Each tag gets a unique UUID and proper metadata

**On `pull` (Metabase → YAML)**:
- Template tags are **not saved** in the YAML (they're derived from SQL)
- Parameters (with types, defaults, etc.) are saved separately in Metabase
- Parameters are shown in the Metabase UI but linked to template tags internally

#### Example

**SQL File** (`query.sql`):
```sql
WITH base_data AS (
    SELECT * 
    FROM {{#131569-base-query}} o
    WHERE 1=1
      [[ AND o.signup_date >= {{date_range}} ]]
      [[ AND o.signup_type = {{signup_type}} ]]
)
SELECT * FROM base_data;
```

**What Happens on `push`**:
```json
{
  "template-tags": {
    "#131569-base-query": {
      "id": "uuid-1",
      "name": "#131569-base-query",
      "display-name": "#131569-base-query",
      "type": "card",
      "card-id": 131569
    },
    "date_range": {
      "id": "uuid-2",
      "name": "date_range",
      "display-name": "Date Range",
      "type": "text"
    },
    "signup_type": {
      "id": "uuid-3",
      "name": "signup_type",
      "display-name": "Signup Type",
      "type": "text"
    }
  }
}
```

**Important Notes**:
- ✅ `{{variable_name}}` → extracted as template tag with `type: text`
- ✅ `{{#card-id-alias}}` → extracted as template tag with `type: card` and `card-id`
- 🔄 Display names are auto-generated from snake_case (e.g., `date_range` → "Date Range")
- 🔧 After pushing, configure parameter types/defaults in Metabase UI if needed

---

## Visualization Examples

### 1. Table Visualization

**Use case**: Display tabular data with custom formatting

```yaml
question:
  id: 132314
  name: "Product Metrics Table"
  sql: product_metrics_table-query.sql
  display: table
  visualization_settings:
    # Column visibility
    table.columns:
      - name: "PRODUCT"
        enabled: true
      - name: "AVG_M3_REVENUE"
        enabled: true
    
    # Column formatting
    column_settings:
      AVG_M3_REVENUE:                # SQL column name
        column_title: "AVG $ M3"     # Custom header
        prefix: "$ "                  # Value prefix
        decimals: 0                   # Decimal places
        number_separators: ", "       # Thousands separator
        show_mini_bar: true          # Inline bar chart
      
      NET_RETENTION_RATIO:
        decimals: 2
        suffix: " x"
        show_mini_bar: true
      
      ADOPTION_PCT:
        column_title: "M3 # Adoption"
        scale: 100                    # Convert 0.75 → 75
        suffix: "%"
        show_mini_bar: true
```

### 2. Stacked Bar Chart (Vertical)

**Use case**: Show categorical breakdowns over time

```yaml
question:
  id: 101647
  name: "Weekly Signups by Signup Type"
  sql: weekly_signups_stacked-query.sql
  display: bar
  visualization_settings:
    # Stacking mode
    stackable.stack_type: stacked    # "stacked" (absolute) or "normalized" (100%)
    
    # Axes - IMPORTANT: Include BOTH the X-axis and the grouping column
    graph.dimensions:
      - "SIGNUP_WEEK"                # X-axis (time)
      - "SIGNUP_TYPE"                # Grouping column (creates series)
    graph.metrics:
      - "SIGNUP_COUNT"               # Y-axis
    
    # X-axis scale
    graph.x_axis.scale: timeseries   # "timeseries" for dates, "ordinal" for categories
    
    # Value labels
    graph.show_values: true          # Show numbers on bars
    graph.label_value_frequency: fit # "fit" or "all"
    
    # Series configuration (MUST be null for automatic grouping)
    graph.series_order_dimension: null
    graph.series_order: null
    
    # Series colors (dictionary keyed by series name)
    series_settings:
      "Self Serve":                  # Series name as key (from SIGNUP_TYPE column)
        color: "#51528D"
      "Sales Assisted":
        color: "#999AC4"
```

**Critical Notes**:
- For grouped charts, `graph.dimensions` must include **both** the X-axis column AND the grouping column
- The second dimension creates the series (one series per unique value)
- `graph.series_order_dimension` and `graph.series_order` must be `null` for automatic grouping
- Use `series_settings` (dict) for colors, **not** `graph.series_order` (array)
- Series names in `series_settings` must exactly match the values from your grouping column

### 3. Horizontal Bar Chart

**Use case**: Compare categories (non-time dimension)

```yaml
question:
  id: 132315
  name: "Revenue Behavior by Product"
  sql: revenue_by_product_horizontal-query.sql
  display: row                       # "row" = horizontal bars
  visualization_settings:
    stackable.stack_type: stacked
    
    graph.dimensions:
      - "PRODUCT"
    graph.metrics:
      - "ADOPTION_REVENUE"
      - "EXPANSION_REVENUE"
      - "FLAT_REVENUE"
      - "CONTRACTION_REVENUE"
      - "CHURN_REVENUE"
    
    # Hide Y-axis
    graph.y_axis.axis_enabled: false
    
    # Show values on segments
    graph.show_values: true
    
    # Custom colors per metric
    series_settings:
      "Adoption":
        color: "#88BF4D"
      "Expansion":
        color: "#A989C5"
      "Flat":
        color: "#EF8C8C"
```

### 4. Line Chart (Timeseries)

**Use case**: Track trends over time

```yaml
question:
  id: 132539
  name: "Signups Over Time by Experiment"
  sql: daily_active_users_line-query.sql
  display: line
  visualization_settings:
    graph.dimensions:
      - "SIGNUP_WEEK"
    graph.metrics:
      - "SIGNUP_COUNT"
    
    # X-axis
    graph.x_axis.scale: timeseries
    
    # Y-axis
    graph.y_axis.scale: linear       # "linear", "log", "pow"
    graph.y_axis.min: 0
    graph.y_axis.labels_enabled: true
    
    # Line styling
    series_settings:
      "Experiment A":
        color: "#509EE3"
        line.marker_enabled: true    # Show dots on line
        line.size: "M"               # "S", "M", "L"
        line.interpolate: linear     # "linear", "step"
```

### 5. Normalized Stacked Bar (100%)

**Use case**: Show percentage distribution over time

```yaml
question:
  id: 124411
  name: "Product Distribution Over Time (100%)"
  sql: feature_adoption_normalized-query.sql
  display: bar
  visualization_settings:
    stackable.stack_type: normalized # Shows percentages, not absolute values
    
    # Both dimensions: X-axis + grouping column
    graph.dimensions:
      - "BILLING_PERIOD"             # X-axis
      - "PRODUCT_NAME"               # Grouping column (creates series)
    graph.metrics:
      - "PRODUCT_COUNT"
    
    graph.show_values: true
    graph.x_axis.scale: timeseries
    
    # Series configuration (must be null)
    graph.series_order_dimension: null
    graph.series_order: null
    
    # Series colors (dictionary by series name)
    series_settings:
      "Product A":
        color: "#88BF4D"
      "Product B":
        color: "#A989C5"
      "Product C":
        color: "#EF8C8C"
      "Product D":
        color: "#F9CF48"
```

### 6. Combo Chart (Bar + Line, Dual Axis)

**Use case**: Compare metrics with different units/scales

```yaml
question:
  id: 132231
  name: "Signups with Time-to-Value Metrics"
  sql: monthly_revenue_combo-query.sql
  display: combo                     # Mixed chart type
  visualization_settings:
    graph.dimensions:
      - "SIGNUP_WEEK"
    graph.metrics:
      - "SIGNUP_COUNT"
      - "P50_HOURS_TO_VALUE"
      - "P80_HOURS_TO_VALUE"
    
    # Dual Y-axis (auto-split by unit)
    graph.y_axis.auto_split: true
    
    # Per-series configuration
    series_settings:
      "SIGNUP_COUNT":
        display: bar                 # This metric as bar
        axis: left                   # Left Y-axis
        color: "#509EE3"
      
      "P50_HOURS_TO_VALUE":
        display: line                # This metric as line
        axis: right                  # Right Y-axis
        color: "#88BF4D"
        line.marker_enabled: true
        line.interpolate: linear
      
      "P80_HOURS_TO_VALUE":
        display: line
        axis: right
        color: "#EF8C8C"
    
    # Column formatting (different suffix per metric)
    column_settings:
      P50_HOURS_TO_VALUE:
        suffix: "h"
      P80_HOURS_TO_VALUE:
        suffix: "h"
```

### 7. Area Chart

**Use case**: Show cumulative or stacked trends

```yaml
question:
  id: 95919
  name: "User Activity Distribution"
  sql: cumulative_conversions_area-query.sql
  display: area
  visualization_settings:
    stackable.stack_type: normalized # 100% stacked area
    
    graph.dimensions:
      - "ACTIVITY_WEEK"
    graph.metrics:
      - "USER_COUNT"
    
    # Tooltip customization
    graph.tooltip_columns:
      - "TOTAL_USERS"
    
    # Column formatting
    column_settings:
      USER_COUNT:
        number_style: percent
        decimals: 1
        scale: 100
```

---

## Object Relationships

### Hierarchy Diagram

```
Dashboard (top-level container)
├── parameters[] ────────────────> Dashboard Parameters (global filters)
│   └── Parameter
│       ├── id
│       ├── name
│       ├── type
│       └── slug
│
├── tabs[] ─────────────────────> Tabs (optional organization)
│   └── Tab
│       ├── name
│       ├── position
│       └── cards[] ───────────> Card Placements (references)
│
└── cards[] (if no tabs) ───────> Card Placements (flat list)
    └── Card Placement
        ├── position
        │   ├── row
        │   ├── col
        │   ├── size_x
        │   └── size_y
        │
        ├── card
        │   └── question_id ───────> Question (saved query)
        │                               ├── id
        │                               ├── name
        │                               ├── sql
        │                               ├── database_id
        │                               ├── display
        │                               └── visualization_settings
        │
        ├── virtual_card (alternative to card)
        │   ├── display
        │   └── text
        │
        └── parameter_mappings[]
            ├── parameter_id ──────> Dashboard Parameter
            └── target
```

### Key Relationships

| Parent | Child | Relationship | Cardinality |
|--------|-------|--------------|-------------|
| Dashboard | Tab | Organizes cards | 0..* (optional) |
| Dashboard | Parameter | Global filters | 0..* |
| Tab | Card Placement | Positioned cards | 0..* |
| Dashboard | Card Placement | Positioned cards (if no tabs) | 0..* |
| Card Placement | Question | References saved query | 0..1 (or virtual_card) |
| Card Placement | Parameter Mapping | Maps dashboard filters | 0..* |

### Important Concepts

**Card Placement vs Question:**
- **Card Placement**: Where a question appears on the dashboard (position + mappings)
- **Question**: The actual saved query with visualization (what data + how to display)
- One question can have multiple placements (reused across dashboards)

**Virtual Cards:**
- Card placements with no `question_id`
- Content stored inline in `virtual_card` field
- Used for text, headings, section dividers
- Not saved as separate questions

**Tabs:**
- Optional organizational feature
- Each card placement can reference a tab
- If no tabs exist, cards are in a flat list under `dashboard.cards`

---

## Field Reference

### Dashboard Fields

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | integer | For updates | Dashboard ID | `75122` |
| `name` | string | Yes | Dashboard name | `"Sales Dashboard"` |
| `width` | string | No | Layout width | `"full"`, `"fixed"` |
| `description` | string | No | Dashboard description | `"Q4 metrics"` |
| `parameters` | array | No | Dashboard-level filters | See Parameter Fields |
| `tabs` | array | No | Tab definitions | See Tab Fields |
| `cards` | array | Conditional | Card placements (if no tabs) | See Card Placement Fields |

### Tab Fields

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `name` | string | Yes | Tab display name | `"Overview"` |
| `position` | integer | Yes | Display order (0-indexed) | `0`, `1`, `2` |
| `cards` | array | No | Card placements in tab | See Card Placement Fields |

### Card Placement Fields

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `position` | object | Yes | Grid position | `{row: 0, col: 0, size_x: 12, size_y: 8}` |
| `card` | object | Conditional | Reference to question | `{question_id: 124411}` |
| `virtual_card` | object | Conditional | Inline content | `{display: "heading", text: "Title"}` |
| `parameter_mappings` | array | No | Dashboard filter mappings | See Parameter Mapping Fields |

**Note**: Either `card` or `virtual_card` must be present, not both.

### Parameter Mapping Fields

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `parameter_id` | string | Yes | Dashboard parameter ID | `"9c811c10"` |
| `target` | string or array | Yes | Mapping target (see below) | `signup_type` or `["dimension", ["field", 42]]` |

#### Parameter Mapping Target Formats

**Simple format (recommended for template variables):**
```yaml
parameter_mappings:
  - parameter_id: "9c811c10"  # Signup Type
    target: signup_type        # Maps to {{signup_type}} in SQL
```

**Note**: The comment after `parameter_id` is automatically added when downloading dashboards to show the parameter's display name.

**Complex format (for dimensions, fields, etc.):**
```yaml
parameter_mappings:
  - parameter_id: "def456"  # Product Category
    target: ["dimension", ["field", 42]]  # Maps to a specific field
```

The simple string format is automatically converted to Metabase's internal format: `["variable", ["template-tag", "signup_type"]]`. Use the simple format whenever possible for better readability!

### Question Fields

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | integer/null | For updates | Question ID | `124411`, `null` |
| `name` | string | Yes | Question name | `"Weekly Signups"` |
| `description` | string | No | Question description | `"Tracks signups by week"` |
| `sql` | string | Yes | SQL file path (relative to YAML) | `"weekly-signups-query.sql"` |
| `parameters` | object | No | Query parameters (template tags) | See Parameter Definition |
| `display` | string | Yes | Visualization type | `"bar"`, `"line"`, `"table"` |
| `visualization_settings` | object | No | Display settings | See Visualization Settings |

**Note**: `database_id` is NOT a field in question YAML (it's a deployment detail, provided via `--database` CLI flag and stored in `.state.yaml`).

### Parameter Definition (Template Tags)

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `type` | string | Yes | Parameter type | `"date/range"`, `"string/="`, `"number/="` |
| `display_name` | string | Yes | Display name in UI | `"Date Range"` |
| `default` | any | No | Default value | `"past30days"`, `null` |

### Visualization Settings

**Common Properties** (apply to most chart types):

| Property | Type | Description | Values |
|----------|------|-------------|--------|
| `graph.dimensions` | array | X-axis fields | `["SIGNUP_WEEK"]` |
| `graph.metrics` | array | Y-axis fields | `["SIGNUP_COUNT"]` |
| `graph.show_values` | boolean | Show value labels | `true`, `false` |
| `stackable.stack_type` | string/null | Stacking mode | `"stacked"`, `"normalized"`, `null` |
| `graph.x_axis.scale` | string | X-axis scale | `"timeseries"`, `"ordinal"` |
| `graph.y_axis.scale` | string | Y-axis scale | `"linear"`, `"log"`, `"pow"` |
| `graph.y_axis.min` | number/null | Y-axis minimum | `0`, `null` |
| `graph.y_axis.auto_split` | boolean | Dual axes | `true`, `false` |

**Series Configuration**:

| Property | Type | Description | Values |
|----------|------|-------------|--------|
| `graph.series_order_dimension` | string/null | Grouping dimension | Set to `null` for automatic grouping |
| `graph.series_order` | array/null | Manual series order | Array of `{key, name, color, enabled}` or `null` |
| `series_settings` | object | Per-series styling | Keys are series names |
| `series_settings[].display` | string | Chart type for series | `"bar"`, `"line"`, `"area"` |
| `series_settings[].axis` | string | Which Y-axis | `"left"`, `"right"` |
| `series_settings[].color` | string | Series color | `"#509EE3"` (hex code) |
| `series_settings[].line.marker_enabled` | boolean | Show line markers | `true`, `false` |
| `series_settings[].line.size` | string | Line thickness | `"S"`, `"M"`, `"L"` |
| `series_settings[].line.interpolate` | string | Line style | `"linear"`, `"step"` |

**Important**: For grouped/stacked charts:
- Include **both** X-axis and grouping columns in `graph.dimensions: [X_COLUMN, GROUP_COLUMN]`
- Set `graph.series_order_dimension: null` and `graph.series_order: null`
- Use `series_settings` (dict) for per-series colors, keyed by series name

**Column Formatting** (for tables and axis labels):

| Property | Type | Description | Values |
|----------|------|-------------|--------|
| `column_settings` | object | Per-column formatting | Keys are SQL column names |
| `column_settings[].column_title` | string | Custom header | `"AVG $ M3"` |
| `column_settings[].prefix` | string | Value prefix | `"$ "`, `"€ "` |
| `column_settings[].suffix` | string | Value suffix | `" %"`, `" x"` |
| `column_settings[].decimals` | integer | Decimal places | `0`, `1`, `2` |
| `column_settings[].scale` | number | Multiply values | `100` (for percentages) |
| `column_settings[].number_separators` | string | Thousands separator | `", "`, `" "` |
| `column_settings[].show_mini_bar` | boolean | Inline bar chart | `true`, `false` |

**Table-Specific**:

| Property | Type | Description | Values |
|----------|------|-------------|--------|
| `table.columns` | array | Column visibility | Array of `{name, enabled}` |

### Dashboard Parameter Fields

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | string | Yes | Parameter ID | `"9c811c10"` |
| `name` | string | Yes | Display name | `"Signup Type"` |
| `type` | string | Yes | Parameter type | `"string/="`, `"date/range"` |
| `slug` | string | Yes | URL-friendly name | `"signup_type"` |
| `default` | any | No | Default value | `"past30days"`, `null` |

---

## YAML ↔ JSON Conversion

The library automatically handles **bidirectional** conversion between human-readable YAML and Metabase's JSON API format.

### Column Settings Conversion

**YAML (what you write and read)**:
```yaml
column_settings:
  AVG_M3_REVENUE:
    prefix: "$ "
    decimals: 0
  SIGNUP_WEEK:
    date_style: YYYY/M/D
```

**JSON (Metabase API format)**:
```json
{
  "column_settings": {
    "[\"name\",\"AVG_M3_REVENUE\"]": {
      "prefix": "$ ",
      "decimals": 0
    },
    "[\"name\",\"SIGNUP_WEEK\"]": {
      "date_style": "YYYY/M/D"
    }
  }
}
```

### Tooltip Columns Conversion

**YAML (what you write and read)**:
```yaml
graph.tooltip_columns:
  - TOTAL_USERS
  - SIGNUP_COUNT
```

**JSON (Metabase API format)**:
```json
{
  "graph.tooltip_columns": [
    ["name", "TOTAL_USERS"],
    ["name", "SIGNUP_COUNT"]
  ]
}
```

### When Conversion Happens

- **YAML → JSON**: Automatically during `dashboard push` operations (for questions and dashboard)
- **JSON → YAML**: Automatically during `dashboard pull` operations
- **Result**: You only work with clean, readable YAML files ✨

**Note**: The same conversion applies to `series_settings` (for colors) and other visualization settings.

---

## Common Patterns for AI Agents

### Pattern 1: Creating a New Dashboard

```yaml
dashboard:
  name: "My New Dashboard"
  width: full
  tabs:
    - name: "Main"
      position: 0
      cards:
        - position: {row: 0, col: 0, size_x: 24, size_y: 2}
          virtual_card:
            display: heading
            text: "Dashboard Title"
```

**Note**: Omit `id` field when creating new dashboards. The `push` command will generate `.state.yaml` with the assigned ID.

### Pattern 2: Creating a New Question

```yaml
question:
  name: "Weekly Revenue"
  sql: weekly-revenue-query.sql
  display: bar
  visualization_settings:
    graph.dimensions: ["WEEK"]
    graph.metrics: ["REVENUE"]
```

**Note**: Omit `id` and `database_id` fields when creating new questions. The `id` will be assigned by Metabase during `dashboard push`, and `database_id` is passed via `--database` CLI flag and stored in `.state.yaml`.

### Pattern 3: Referencing a Question in a Dashboard

```yaml
- position: {row: 2, col: 0, size_x: 12, size_y: 8}
  card:
    question_id: 124411  # Reference existing question
  parameter_mappings:
    - parameter_id: "date_filter"  # Date Range
      target: date_range            # Simple format - maps to {{date_range}} in question SQL
```

### Pattern 4: Adding a Text Card

```yaml
- position: {row: 0, col: 0, size_x: 24, size_y: 2}
  virtual_card:
    display: heading
    text: "Section Title"
    text_align: center
```

---

## Snowflake SQL Gotchas (Metabase Context)

SQL queries run through Metabase's Snowflake JDBC driver, which behaves slightly differently from the Snowflake CLI or SnowSQL. These are hard-won lessons from debugging silent failures and cryptic errors.

### 1. Double-escape regex patterns

Metabase sends SQL to Snowflake via JSON. A single backslash in your `.sql` file (e.g. `\d+`) gets consumed by JSON serialization and arrives as `d+` at Snowflake — **silently matching nothing**.

```sql
-- ❌ BAD: single escape — silently returns empty results
WHERE path RLIKE '/monitors/\d+'

-- ✅ GOOD: double escape — arrives as \d+ at Snowflake
WHERE path RLIKE '/monitors/\\d+'
```

This applies to `RLIKE`, `REGEXP_SUBSTR`, `REGEXP_REPLACE`, and any regex function. The Snowflake CLI also handles `\\d` correctly (it just becomes `\d` in the Python string), so double escapes work in both contexts.

### 2. No numeric types in TRY_TO_TIMESTAMP / TO_TIMESTAMP

Metabase's Snowflake driver rejects `TRY_TO_TIMESTAMP` (and `TO_TIMESTAMP`) with numeric arguments — even `INTEGER`:

```sql
-- ❌ Fails in Metabase: "TRY_CAST cannot be used with NUMBER(38,6) and TIMESTAMP_NTZ(6)"
SELECT TRY_TO_TIMESTAMP(TRY_TO_NUMBER(val) / 1000)

-- ❌ Also fails: "TRY_CAST cannot be used with NUMBER(38,0) and TIMESTAMP_NTZ(3)"
SELECT TRY_TO_TIMESTAMP(TRY_TO_NUMBER(val)::INTEGER, 3)

-- ✅ GOOD: use DATEADD from the Unix epoch instead
SELECT DATEADD('s', FLOOR(TRY_TO_NUMBER(val) / 1000), '1970-01-01'::TIMESTAMP_NTZ)

-- ✅ With millisecond precision:
SELECT DATEADD('ms', TRY_TO_NUMBER(val) % 1000,
       DATEADD('s', FLOOR(TRY_TO_NUMBER(val) / 1000), '1970-01-01'::TIMESTAMP_NTZ))
```

`TRY_TO_TIMESTAMP(string)` is fine — only numeric inputs trigger the JDBC driver issue.

### 3. Template tag types matter for filtering

Metabase template tags default to `type: "text"`, which sends the parameter value as a string. For numeric filters (like org_id), this can cause silent type mismatches or empty results.

```yaml
# ❌ BAD: default type is "text" — org_id sent as string '2' instead of number 2
parameters:
  org_id:
    display_name: "Org ID"

# ✅ GOOD: explicit number type
parameters:
  org_id:
    type: "number/="
    display_name: "Org ID"
```

### 4. Parameter mappings need card_id

Dashboard parameter mappings must include the `card_id` of the dashcard they belong to. Without it, the parameter filter appears in the UI but doesn't flow to questions — Metabase shows "You'll need to pick a value for 'X' before this query can run."

This is handled automatically by `dashboard.py` during push, but if you're debugging parameter issues, check that each `parameter_mappings` entry has a `card_id` field in the API payload.

### 5. Parameter defaults must be arrays

For `number/=` type parameters, the default value must be an array, not a scalar:

```yaml
# ❌ BAD
parameters:
  - id: "org_id_filter"
    type: "number/="
    default: 2

# ✅ GOOD
parameters:
  - id: "org_id_filter"
    type: "number/="
    default: [2]
```
