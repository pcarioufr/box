# Project Context

This project contains utilities and data exports from Datadog's internal systems.

## CLI Tools

All tools are accessed via `./box.sh <tool>`. Use `--help` on any command for full usage.

| Tool | Entry point | What it does |
|------|------------|--------------|
| Google Docs | `./box.sh google pull` | Pull Google Doc to local markdown |
| Confluence | `./box.sh confluence pull` | Pull Confluence page to local markdown |
| Excalidraw | `./box.sh excalidraw` | Diagram editor (YAML → canvas) |
| Metabase | `./box.sh metabase dashboard` | Pull/push dashboards as YAML |
| Snowflake | `./box.sh snowflake query` / `discover` | SQL queries and schema exploration |
| Datadog RUM | `./box.sh datadog rum` | Query/aggregate user behavior data |
| Jira | `./box.sh jira fetch` | Fetch tickets with JQL |
| Analysis | `./box.sh analysis` | A/B test comparison, clustering |

### Tips (not in --help)

- **Excalidraw**: Push after every meaningful change — the user watches the canvas live. Never batch edits. Use `./box.sh excalidraw api yaml` for the YAML format reference.
- **Document Pull**: Both Google and Confluence embed source identifiers in YAML frontmatter (`google_id`, `confluence_id`) for traceability.
- **Metabase**: Remove `.state.yaml` before pushing to create a new dashboard (vs updating existing).
- **Snowflake**: Prefer `--sql "SELECT ..."` for throwaway queries. Use double backslashes (`\\d+`) for regex in SQL files — the CLI consumes one escape layer.

## Working Folders

Most work happens in **long-lived project directories** under `data/` (e.g., `data/detection/`). Use the existing project folder when continuing work on an ongoing effort.

For **new, standalone explorations**, create a date-based folder under `data/explorations/`:

```
data/explorations/YYYY-MM-DD_short-description/
├── master.md              # Summary of findings
├── datadog/               # RUM outputs
├── snowflake/             # Snowflake outputs
├── jira/                  # Jira outputs
└── ...
```

For detailed working folder conventions (naming, when to create vs continue, master.md requirements), see the `/exploration` skill documentation.

## Directory Structure

- `services/` - Service definitions (containers, workers, servers)
- `libs/` - Shared code libraries (Python: jira, datadog, google, confluence, metabase)
- `data/` - Working folders and knowledge, organized by project
- `.claude/skills/` - Custom Claude skills
- `box.sh` - Main CLI entry point

## Knowledge Base

Curated domain knowledge lives in `_knowledge/` folders within `data/`. Read these for context before working on a topic.

- `data/_knowledge/` — cross-cutting reference (tool schemas, Slack directory, general domain)
- `data/<project>/_knowledge/` — initiative-specific knowledge (e.g. `data/detection/_knowledge/`)

For curation rules and templates, see the `/knowledge` skill.

