# The Box

An agentic toolbox for Product Managers, designed to work with Claude Code.

It combines:
- **Skills** - Natural language interfaces for common PM tasks (e.g., data exploration, knowledge curation)
- **CLI tools** - Direct access to Datadog, Snowflake, Jira, Confluence, and Google Docs
- **Knowledge base** - Curated context that keeps Claude grounded in your domain, maintained organically via the `/knowledge` skill
- **Self-maintaining** - The toolbox improves itself as you use it

The tools run locally via `./box.sh`, with some commands optionally using a Docker container for isolation.

> **Note:** This repo is public, but the `data/` directory is gitignored - it contains proprietary context specific to my work.


## Sibling Directories

Code from external GitHub projects is stored in sibling directories under `../Code/`:

```
../Code/
  acme/             # acme org's internal GitHub repositories
    acme-analytics  # acme analytics Github repository
    acme-core       # acme core Github repository
  beta/             # beta project Github repository 
```

## Setup

```bash
cp env.example .env   # Add your credentials (Atlassian, Datadog, Snowflake)
./box.sh --setup      # Create venv and install dependencies
```

### Prerequisites

- **Python 3.11+**: `brew install python@3.11`
- **Docker**: `brew install docker-desktop`
- **Node.js** (for MCP servers): `brew install node`

> This toolbox has been tested on macOS environments.


# Knowledge Base

Curated knowledge lives in `_knowledge/` folders inside `data/`:

- **`data/_knowledge/`** — cross-cutting reference (tool schemas, Slack directory, general domain context)
- **`data/<project>/_knowledge/`** — initiative-specific knowledge (e.g., `data/detection/_knowledge/`)

The `/knowledge` skill owns the curation rules: file templates, when to update silently vs. ask first, and explicit review passes. Knowledge files are living documents updated in-place — only distilled insights from pulled documents or explorations belong here, not raw outputs.


# Claude Skills

When using Claude Code, skills provide higher-level interfaces to the underlying libraries:

- `/exploration` - Data exploration: query user behavior (Datadog RUM), business metrics (Snowflake), and qualitative feedback (Jira). Intelligently routes to the right data source(s) based on your question. Outputs go in `data/explorations/`.
- `/knowledge` - Knowledge base curation: review, update, and maintain `_knowledge/` folders. Also runs organically during conversations to keep knowledge current.


# MCP Servers

Claude Code also has direct API access via MCP servers, configured in `.claude/settings.json`:

- **Datadog** — search/analyze logs, monitors, dashboards, RUM events, incidents, services
- **Atlassian** — read/write Jira issues and Confluence pages
- **Slack** — search channels, read/send messages, manage canvases
- **Snowflake** — run queries, explore schemas, manage objects


# Libraries

The `libs/` directory contains the underlying CLI tools accessible via `./box.sh`:

- **Google** (`./box.sh google pull`) - Pull Google Docs as local markdown via browser-based Apps Script
- **Confluence** (`./box.sh confluence pull`) - Pull Confluence pages as local markdown via REST API v2
- **Jira** (`./box.sh jira`) - Fetch Jira tickets with custom fields and ADF-to-text conversion
- **Snowflake** (`./box.sh snowflake`) - Execute SQL queries with INCLUDE directives and template variables
- **Datadog** (`./box.sh datadog`) - Query and aggregate RUM data, fetch session timelines, create/update notebooks for Product Analytics
- **Metabase** (`./box.sh metabase`) - Manage Metabase dashboards using YAML definitions with Terraform-like state tracking for pull/push workflows
- **Analysis** (`./box.sh analysis`) - Statistical analysis for CSV data: A/B test comparison and exploratory analysis with clustering
- **Excalidraw** (`./box.sh draw`) - Local diagram editor for architecture diagrams, wireframes, and concept sketches

See [libs/README.md](libs/README.md) for details, or run `./box.sh <command> --help`.


# Services

The `services/` directory contains Docker services orchestrated via `docker-compose`:

- **Excalidraw** - Collaborative canvas with REST API running at http://localhost:3000
  - REST API for programmatic element creation/updates
  - Real-time sync between browser UI and API via WebSocket
  - Persistent state in `data/_excalidraw/elements.json`
  - `./box.sh draw` - Start and open in browser
  - `./box.sh draw new <name>` - Create new diagram file
  - `./box.sh draw list` - List saved diagrams
  - See [services/excalidraw/README.md](services/excalidraw/README.md) for API documentation

- **Graph Viewer** - Interactive directed graph visualizer at http://localhost:5001
  - Upload CSV data (source, target, weight)
  - Filter by weight threshold
  - Multiple graph layouts (DAG, force-directed, circular, etc.)
  - Dark mode interface with dynamic edge width mapping
  - See [services/graph-viewer/README.md](services/graph-viewer/README.md) for details

