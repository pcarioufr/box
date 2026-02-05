# Project Context

This project contains utilities and data exports from Datadog's internal systems.

## Available Skills

- `/sync` - Sync external documents (Google Docs, Confluence) to local markdown. Handles URLs or refresh commands.
- `/pa` - Product Analytics: query user behavior (Datadog RUM), business metrics (Snowflake), and qualitative feedback (Jira). Intelligently routes to the right data source(s) based on your question.
- `/prd` - Iterate on Product Requirement Documents using Opus model for deep content analysis and refinement
- `/box` - Run commands in The Box Docker container

## Document Sync

Confluence and Google Docs are managed through a unified sync system via `data/sync.yaml`.

### Sync Modes

| Command | Behavior |
|---------|----------|
| `/sync <google-url>` | If URL in config, update that file. Otherwise, add to config + sync. |
| `/sync <confluence-url>` | If URL in config, update that file. Otherwise, add to config + download. |
| `/sync refresh` | Sync all entries (Google + Confluence). |
| `/sync refresh google` | Sync only Google entries. |
| `/sync refresh confluence` | Sync only Confluence entries. |

### Output Locations

- Google Docs → `data/_google/{slugified-title}.md`
- Confluence → `data/_confluence/{name}.md`

### CLI Commands

```bash
# Google Docs
./box.sh google list                            # List all Google entries
./box.sh google add <url>                       # Add Google Doc (name from doc title)
./box.sh google remove <doc-id>                 # Remove by ID (or partial ID)
./box.sh google refresh                         # Sync all Google entries

# Confluence
./box.sh confluence list                        # List all Confluence entries
./box.sh confluence add <url> --name <n>        # Add Confluence page
./box.sh confluence remove <name>               # Remove by name
./box.sh confluence download <url> --name <n>   # Download without adding to sync
./box.sh confluence clean <file> -o <out>       # Clean markdown tags
```

### sync.yaml Format

```yaml
google:
  # Google entries only need the doc ID - filename derived from doc title
  - id: "1abc123..."
  - id: "1xyz789..."

confluence:
  - url: "https://datadoghq.atlassian.net/wiki/spaces/X/pages/123/..."
    name: "architecture-overview"
```

## Working Folders

All data work is organized in date-based working folders under `data/`:

```
data/YYYY-MM-DD_short-description/
├── master.md              # Summary of findings
├── datadog/               # RUM outputs
├── snowflake/             # Snowflake outputs
├── jira/                  # Jira outputs
└── ...
```

For detailed working folder conventions (naming, when to create vs continue, master.md requirements), see the `/pa` skill documentation.

## Directory Structure

- `services/` - Service definitions (containers, workers, servers)
  - `services/ubuntu/` - Ubuntu service (build, home, opt, .env, box.sh)
  - `services/compose.yml` - Docker Compose orchestration file
- `libs/` - Shared code libraries (Python, etc.)
  - `libs/jira/` - Jira API tools (ticket fetching, ADF conversion)
  - `libs/datadog/` - Datadog API tools (RUM queries)
  - `libs/sync/` - Document sync management (Google Docs, Confluence, markdown cleaning)
- `data/` - Working folders organized by date (see Working Folders section above)
  - `data/sync.yaml` - Sync configuration for Google Docs and Confluence
  - `data/_google/` - Default output for synced Google Docs
  - `data/_confluence/` - Default output for synced Confluence pages
- `knowledge/` - Curated knowledge bases for skills
  - `knowledge/general.md` - Domain knowledge about the company, business, product area, competition, etc.
  - `knowledge/pa/` - Product Analytics knowledge (RUM patterns, Snowflake model, Jira fields, notebooks)
- `.claude/skills/` - Custom Claude skills with utilities and scripts
- `box.sh` - Main CLI entry point
