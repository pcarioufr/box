# The Box

An agentic toolbox for Product Managers, designed to work with Claude Code.

It combines:
- **Skills** - Natural language interfaces for common PM tasks (analytics, document sync, PRD iteration)
- **CLI tools** - Direct access to Datadog, Snowflake, Jira, Confluence, and Google Docs
- **Knowledge bases** - Curated context that keeps Claude grounded in your domain
- **Self-maintaining** - The toolbox improves itself as you use it

The tools run locally via `./box.sh`, with some commands optionally using a Docker container for isolation.

> **Note:** This repo is public, but the `knowledge/` and `data/` directories are gitignored - they contain proprietary context specific to my work.


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

The `knowledge/` directory contains curated knowledge bases for skills:

## Product Analytics (`knowledge/pa/`)

Knowledge base for the unified `/pa` skill covering all product analytics data sources:
- `rum.md` - Datadog RUM query patterns, filters, facets, and aggregation examples
- `snowflake.md` - Semantic model defining core business entities, metrics, and data mappings
- `jira.md` - Custom field mappings and JQL patterns for Jira projects
- `notebooks.md` - Reference for creating Datadog notebooks using standard API format

## General (`knowledge/general.md`)

Domain knowledge about the business context:
- Company information and organizational structure
- Product area context and terminology
- Competitive landscape
- Business metrics and KPIs
- Industry-specific concepts

This file helps Claude understand the broader context when working on tasks, ensuring responses are grounded in the specific domain being worked on.

These knowledge bases ensure consistency across queries and enable rapid answers to recurring questions.


# Claude Skills

When using Claude Code, skills provide the best interface to the underlying libraries:

- `/sync` - Sync external documents (Google Docs, Confluence) to local markdown. Handles URLs or refresh commands.
- `/pa` - Product Analytics: query user behavior (Datadog RUM), business metrics (Snowflake), and qualitative feedback (Jira). Intelligently routes to the right data source(s) based on your question.
- `/prd` - Iterate on Product Requirement Documents using Opus model for deep content analysis and refinement.

Skills handle context, output organization, and best practices automatically.


# Libraries

The `libs/` directory contains the underlying CLI tools accessible via `./box.sh`:

- **Google** (`./box.sh google`) - Sync Google Docs to local markdown via browser-based Apps Script
- **Confluence** (`./box.sh confluence`) - Sync Confluence pages to local markdown, plus markdown cleaning
- **Jira** (`./box.sh jira`) - Fetch Jira tickets with custom fields and ADF-to-text conversion
- **Snowflake** (`./box.sh snowflake`) - Execute SQL queries with INCLUDE directives and template variables
- **Datadog** (`./box.sh datadog`) - Query and aggregate RUM data, fetch session timelines, create/update notebooks for Product Analytics
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

