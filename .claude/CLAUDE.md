# Project Context

This project contains utilities and data exports from Datadog's internal systems.

## Available Skills

- `/sync` - Sync external documents (Google Docs, Confluence) to local markdown. Handles URLs or refresh commands.
- `/pa` - Product Analytics: query user behavior (Datadog RUM), business metrics (Snowflake), and qualitative feedback (Jira). Intelligently routes to the right data source(s) based on your question.
- `/prd` - Iterate on Product Requirement Documents using Opus model for deep content analysis and refinement
- `/todo` - Manage a personal todo list in `data/todo.md`. Add, complete, triage, and clean up tasks.
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

## Diagrams (Excalidraw)

Create architecture diagrams, low-fidelity designs, and concept sketches using Excalidraw. The server is stateless — diagrams are authored as declarative YAML and pushed to the canvas.

### CLI Commands

```bash
./box.sh draw                                    # Start Excalidraw and open browser (http://localhost:3000)
./box.sh draw stop                               # Stop Excalidraw container
./box.sh draw api push diagram.yaml              # Push YAML diagram (incremental)
./box.sh draw api push diagram.yaml --clear      # Full clear + recreate
./box.sh draw api query                          # List elements on canvas
./box.sh draw api query -f json                  # Raw JSON output
./box.sh draw api health                         # Check server status
./box.sh draw api clear                          # Clear all elements
```

### Workflow

1. **Author**: Write a `.yaml` diagram file (shapes, texts, connectors)
2. **Push**: `./box.sh draw api push diagram.yaml` — elements appear in the browser
3. **Iterate**: Edit the YAML, push again — only changed elements are updated
4. **View**: Open http://localhost:3000 to see the diagram in Excalidraw UI

**Push after every meaningful change.** The user has the canvas open in their browser and can see updates in real-time. Never batch multiple edits into a single push — push each change individually so the user can watch the diagram evolve and course-correct early. This applies to both initial creation (push after first shapes, then connectors, then labels) and iteration (push after each tweak, not all tweaks at once).

### YAML Format

Diagrams use a hierarchical YAML format where structure reflects nesting. Two main sections:
- `shapes` - everything visual (rectangles, ellipses, diamonds, text, groups)
- `connectors` - arrows/lines between shapes

Groups can contain nested shapes with relative positions. Change a group's position to move all members together.

**For complete format documentation with examples:**
```bash
./box.sh draw api yaml
```

### State Tracking

Each YAML file has a sibling `.state.json` that maps YAML IDs to server-assigned Excalidraw IDs. This enables incremental updates. If the server restarts (losing in-memory state), the CLI detects stale mappings and automatically falls back to a full push.

### Output Location

- YAML diagrams → anywhere in `data/` (e.g., `data/diagrams/*.yaml`)
- State files → sibling `.state.json` next to each YAML

## Database (ClickHouse)

Fast open-source column-oriented database for analytical workloads. Ideal for real-time analytics, time-series data, and large-scale data processing.

### CLI Commands

```bash
./box.sh clickhouse start                        # Start ClickHouse server
./box.sh clickhouse stop                         # Stop ClickHouse server
./box.sh clickhouse restart                      # Restart ClickHouse server
./box.sh clickhouse status                       # Check server status
./box.sh clickhouse client                       # Open interactive SQL shell
./box.sh clickhouse query "SELECT version()"     # Execute SQL query
./box.sh clickhouse query -f query.sql           # Execute SQL from file
./box.sh clickhouse logs                         # View server logs
```

### Access

- **HTTP Interface**: http://localhost:8123
- **Web UI**: http://localhost:8123/play (interactive query editor)
- **Native Protocol**: localhost:9000 (for clickhouse-client)
- **Default User**: `default` (no password)

### Workflow

1. **Start**: `./box.sh clickhouse start` — server available in seconds
2. **Create Tables**: Use MergeTree engine for most analytical use cases
3. **Import Data**: Load CSV, Parquet, or query directly from URLs
4. **Query**: Use standard SQL with ClickHouse extensions (ARRAY JOIN, etc.)

### Example: Time-Series Analytics

```sql
-- Create events table
CREATE TABLE events (
    timestamp DateTime,
    event_type String,
    user_id UInt32,
    value Float64
) ENGINE = MergeTree()
ORDER BY (timestamp, event_type);

-- Insert sample data
INSERT INTO events VALUES
    (now(), 'click', 1, 1.5),
    (now(), 'view', 2, 2.3);

-- Aggregate by event type
SELECT
    event_type,
    count() as count,
    avg(value) as avg_value
FROM events
GROUP BY event_type;
```

### Data Persistence

Data is stored in a Docker volume (`clickhouse_data`) and persists across container restarts. To reset:

```bash
./box.sh clickhouse stop
docker volume rm box_clickhouse_data
./box.sh clickhouse start
```

### Output Location

- Data volume: `clickhouse_data` (managed by Docker)
- Query results: Output to stdout or save to `/data` for persistence

**See `services/clickhouse/README.md` for complete documentation.**

## Dashboards (Metabase)

Manage Metabase dashboards using YAML definitions. Dashboards are authored declaratively and pushed to the Metabase server.

### CLI Commands

```bash
./box.sh metabase dashboard pull <id> --dir <dir>           # Pull dashboard + questions to YAML
./box.sh metabase dashboard push --dir <dir>                # Push (create or update)
./box.sh metabase dashboard push --dir <dir> --question <f> # Push specific question(s) only
./box.sh metabase dashboard validate --dir <dir>            # Validate YAML/SQL before pushing
./box.sh metabase dashboard format                          # Show dashboard YAML format help
./box.sh metabase question format                           # Show question YAML format help
```

### Workflow

1. **Pull**: `./box.sh metabase dashboard pull 75122 --dir my-dashboard/` — downloads dashboard + all questions
2. **Edit**: Modify YAML files (SQL queries, visualizations, card positions)
3. **Push**: `./box.sh metabase dashboard push --dir my-dashboard/` — updates dashboard in Metabase

To create a new dashboard: remove `.state.yaml` before pushing with `--parent` and `--database` flags.

### State Tracking

Each dashboard directory has a `.state.yaml` file that maps local files to Metabase IDs. This enables incremental updates and environment promotion (remove state file to deploy same dashboard to different environment).

### Output Location

- Dashboard directories → anywhere in `data/` (e.g., `data/YYYY-MM-DD_investigation/`)
- State files → `.state.yaml` in each dashboard directory
- Question files → organized by tabs within dashboard directory

**See `libs/metabase/README.md` for complete documentation.**

## Analysis (Statistical)

Statistical analysis for CSV data: A/B test comparison and exploratory analysis with clustering.

```bash
# A/B test comparison (entities CSV + metrics YAML → statistical tests)
./box.sh analysis compare --entities experiment.csv --metrics metrics.yaml

# Exploratory analysis (entities CSV → clusters + correlations)
./box.sh analysis analyze --entities customer_data.csv --clusters 4

# Help
./box.sh analysis --help
```

**See `./box.sh analysis --help` for input formats and examples, or `libs/analysis/README.md` for complete documentation.**

## Working Folders

Most work happens in **long-lived project directories** under `data/` (e.g., `data/monitorless-detection/`). Use the existing project folder when continuing work on an ongoing effort.

For **new, standalone explorations**, create a date-based folder under `data/explorations/`:

```
data/explorations/YYYY-MM-DD_short-description/
├── master.md              # Summary of findings
├── datadog/               # RUM outputs
├── snowflake/             # Snowflake outputs
├── jira/                  # Jira outputs
└── ...
```

For detailed working folder conventions (naming, when to create vs continue, master.md requirements), see the `/pa` skill documentation.


## Snowflake

### Discovery

Use `./box.sh snowflake discover` to explore schemas, tables, and columns without writing metadata queries. Supports finding tables by pattern, analyzing column statistics with top values, previewing data, and listing accessible schemas.

See `./box.sh snowflake discover --help` for available commands and options.

### Query Execution

For temporary or discovery queries, prefer inline SQL with `--sql` to avoid creating throwaway files: `./box.sh snowflake query --sql "SELECT ..."`. Use SQL files only for reusable or complex queries.

Use double backslashes (`\\d+`, `\\w+`) for regex in SQL files — both the Snowflake CLI and Metabase consume one escape layer, so `\\d` arrives as `\d` at the Snowflake engine.

## Sibling Directories

Code from external GitHub projects is stored in sibling directories under `../Code/`:

```
../Code/
  acme/             # acme org's internal GitHub repositories
    acme-analytics  # acme analytics Github repository
    acme-core       # acme core Github repository
  beta/             # beta project Github repository 
```

When referencing or reading source code from other repositories, look in `../Code/`.

## Directory Structure

- `services/` - Service definitions (containers, workers, servers)
  - `services/ubuntu/` - Ubuntu service (build, home, opt, .env, box.sh)
  - `services/excalidraw` - Excalidraw diagram editor (official Docker image)
  - `services/graph-viewer` - Interactive directed graph viewer (http://localhost:5001)
  - `services/compose.yml` - Docker Compose orchestration file
- `libs/` - Shared code libraries (Python, etc.)
  - `libs/jira/` - Jira API tools (ticket fetching, ADF conversion)
  - `libs/datadog/` - Datadog API tools (RUM queries)
  - `libs/sync/` - Document sync management (Google Docs, Confluence, markdown cleaning)
  - `libs/metabase/` - Metabase dashboard management (YAML pull/push, state tracking)
- `data/` - Working folders organized by date (see Working Folders section above)
  - `data/sync.yaml` - Sync configuration for Google Docs and Confluence
  - `data/_google/` - Default output for synced Google Docs
  - `data/_confluence/` - Default output for synced Confluence pages
  - `data/diagrams/` - Excalidraw diagrams (.excalidraw files)
- `knowledge/` - Curated knowledge bases for skills
  - `knowledge/general.md` - Domain knowledge about the company, business, product area, competition, etc.
  - `knowledge/pa/` - Product Analytics knowledge (RUM patterns, Snowflake model, Jira fields, notebooks)
- `.claude/skills/` - Custom Claude skills with utilities and scripts
- `box.sh` - Main CLI entry point
- `tmp/` - Temporary files (SQL queries, scratch data). Use `tmp/` (project-local) instead of `/tmp/` for all temporary files so sandbox permissions don't block writes.
