# Libraries Directory

Core libraries for data queries, external integrations, and content sync.

## Overview

This repository uses a **unified runner pattern**: All libraries are accessed through `./box.sh`, which handles virtual environment activation and routing.

```bash
./box.sh <library> [subcommand] [options]
```

## Library Catalog

### Google Library (`google/`)

**Purpose**: Sync Google Docs to local markdown

```bash
./box.sh google list                    # List all Google Doc entries
./box.sh google add "<url>"             # Add a Google Doc to sync
./box.sh google remove "<doc-id>"       # Remove by ID (full or partial)
./box.sh google refresh                 # Sync all via browser
```

**Features**:
- Browser-based sync via Apps Script webhook
- Automatic filename from doc title
- Output: `data/_google/{slugified-title}.md`

---

### Confluence Library (`confluence/`)

**Purpose**: Sync Confluence pages to local markdown

```bash
./box.sh confluence list                           # List all entries
./box.sh confluence add "<url>" --name page-name   # Add a page
./box.sh confluence remove page-name               # Remove by name
./box.sh confluence refresh                        # Show entries to sync
./box.sh confluence download "<url>" --name name   # Download via REST API
./box.sh confluence clean input.md -o cleaned.md   # Clean markdown
```

**Features**:
- Direct REST API download for pages AND blog posts
- Confluence markdown cleaning (removes custom XML-like tags)
- Output: `data/_confluence/{name}.md`

---

### Jira Library (`jira/`)

**Purpose**: Fetch Jira tickets via REST API v3

```bash
# Fetch tickets with mandatory fields
./box.sh jira fetch FRMNTS --max-results 100 --output tickets.json

# Fetch with custom fields and clean output
./box.sh jira fetch FRMNTS \
  --custom-fields customfield_10711 customfield_10713 \
  --clean \
  --working-folder 2026-02-05_analysis \
  --output tickets.json
```

**Features**:
- REST API v3 with pagination
- Custom field support
- ADF (Atlassian Document Format) to plain text conversion with `--clean`
- Working folder organization

---

### Datadog Library (`datadog/`)

**Purpose**: Query RUM (Real User Monitoring) data and create/update notebooks for Product Analytics

#### Query Individual Events

```bash
./box.sh datadog rum query "@type:view" --from-time 1h --limit 100 --output views.json
```

#### Aggregate Data (Top N & Time Series)

```bash
# Top 10 organizations by page view count
./box.sh datadog rum aggregate "@type:view @session.type:user" \
  --from-time 7d \
  --group-by @usr.org_id @usr.org_name \
  --limit 10 \
  --output top_orgs.json

# Daily evolution of page views
./box.sh datadog rum aggregate "@type:view @session.type:user" \
  --from-time 30d \
  --interval 1d \
  --output daily_views.json
```

#### Create and Update Notebooks

```bash
# Create notebook (auto-updates file with ID)
./box.sh datadog notebook create notebook.json

# Update existing notebook
./box.sh datadog notebook update notebook.json
```

**Features**:
- Query and aggregate RUM events
- Multiple aggregation types (count, cardinality, avg, sum, percentiles)
- Time series with configurable intervals
- Create/update notebooks using standard Datadog API format
- Bidirectional workflow: edit JSON locally, push to Datadog
- Working folder organization

**Notebook Documentation**: [knowledge/datadog-notebooks.md](../knowledge/datadog-notebooks.md)

---

### Snowflake Library (`snowflake/`)

**Purpose**: Execute SQL queries with preprocessing (INCLUDE directives, template variables)

```bash
./box.sh snowflake query.sql --format json
./box.sh snowflake query.sql --var-name value --limit 100
```

**Features**:
- INCLUDE directives for reusable query components
- Metabase-compatible template variables (`{{variable}}`, `[[ optional ]]`)
- Multiple output formats (CSV, JSON, Markdown)
- Auto-save results with `--working-folder`

**Documentation**: [libs/snowflake/README.md](./snowflake/README.md)

---

### Excalidraw Library (`excalidraw/`)

**Purpose**: CLI and API client for the Excalidraw Canvas Server. Diagrams are authored as declarative YAML and pushed to a stateless in-memory server.

```bash
./box.sh draw api push diagram.yaml         # Push YAML diagram (incremental)
./box.sh draw api push diagram.yaml --clear  # Full clear + recreate
./box.sh draw api query                      # List elements on canvas
./box.sh draw api query -f json              # Raw JSON output
./box.sh draw api health                     # Check server status
./box.sh draw api clear                      # Clear all elements
```

**YAML format**:
```yaml
shapes:
  - id: auth
    type: rectangle
    pos: [100, 100, 200x100]
    label: "Auth Service"
    color: {bg: "#a5d8ff"}
texts:
  - text: "Title"
    pos: [200, 30]
connectors:
  - type: arrow
    from: auth
    to: db
```

**Features**:
- Declarative YAML diagrams with incremental push via `.state.json` tracking
- Stale state detection (auto-fallback to full push after server restart)
- Arrow geometry computed from shape positions (center-to-center, edge-clipped)
- Real-time sync to browser via WebSocket

**Documentation**: [services/excalidraw/README.md](../services/excalidraw/README.md)

---

### Common Library (`common/`)

**Purpose**: Shared utilities used by multiple libraries

- `config.py` - Sync configuration management (`data/sync.yaml`)

This is an internal library, not called directly via CLI.

---

## Architecture

### Unified Runner Pattern

All libraries follow the same pattern:

1. **`./box.sh`** - Entry point that activates venv and routes commands
2. **Library modules** - Python packages with CLI interfaces (`__main__.py`)
3. **Shared venv** - Single virtual environment (`.venv`) for all dependencies

**Example**: `./box.sh snowflake query.sql` → activates venv → calls `python -m libs.snowflake query query.sql`

### Directory Structure

```
libs/
├── __init__.py
├── README.md              # This file
├── common/                # Shared utilities
│   └── config.py          # sync.yaml management
├── google/                # Google Docs sync
│   ├── __main__.py        # CLI entry point
│   ├── sync-gdocs.gs      # Apps Script for doc conversion
│   └── webhook-setup.md   # Setup instructions
├── confluence/            # Confluence sync
│   ├── __main__.py        # CLI entry point
│   ├── api.py             # Direct REST API client
│   ├── sync.py            # Sync helpers
│   └── clean.py           # Markdown cleaner
├── jira/                  # Jira ticket fetching
│   ├── __main__.py        # CLI entry point
│   └── fetch_tickets.py   # Jira REST API v3
├── datadog/               # RUM query tools
│   ├── __main__.py        # CLI entry point
│   ├── query_rum.py       # Individual event queries
│   ├── aggregate_rum.py   # Aggregation queries
│   └── create_notebook.py # Notebook create/update
└── snowflake/             # SQL query execution
    ├── __main__.py
    ├── cli.py             # CLI routing
    ├── query.py           # Query execution logic
    └── README.md          # Detailed documentation
```

## Setup

### First-Time Setup

**Environment Variables** (`.env`):
- Copy `env.example` to `.env` and fill in your credentials
- See [`env.example`](../env.example) for all available variables

```bash
./box.sh --setup
```

This command:
- Checks Python 3.11+ is installed
- Creates shared virtual environment at `.venv`
- Installs all dependencies from `requirements.txt`
- Configures Snowflake connection file (`~/.snowflake/connections.toml`) from `.env`
