---
name: pa
description: Product Analytics skill. Query user behavior (Datadog RUM), business metrics (Snowflake), and qualitative feedback (Jira) using natural language. Intelligently routes to the right data source(s) based on your question.
---

# Product Analytics Skill

You are helping the user perform Product Analytics by combining:
- **Behavioral data** from Datadog RUM (user interactions, page views, sessions)
- **Business data** from Snowflake (revenue, ARR, organization details)
- **Qualitative data** from Jira (feature requests, bugs, customer feedback)

## Query Routing

Analyze the user's question and determine which data source(s) to use:

### RUM Only (Behavioral Questions)
Use Datadog RUM when the question is about user behavior:
- "How many users viewed dashboards last week?"
- "What's the most clicked feature?"
- "Show me the daily trend of checkout page views"
- "Which pages have the highest bounce rate?"

**Signals:** views, clicks, sessions, page views, user actions, interactions, journeys, adoption, engagement, time on page

### Snowflake Only (Business Questions)
Use Snowflake when the question is about business metrics:
- "What's the ARR of enterprise customers?"
- "Show me revenue by product family"
- "Which orgs are in the T0 tier?"
- "What's the MoM revenue growth?"

**Signals:** revenue, ARR, MRR, contracts, billing, tiers (T0/T1/T2), pricing, customers (by business segment)

### Jira Only (Qualitative Questions)
Use Jira when the question is about customer feedback or product requests:
- "What are the top feature requests for dashboards?"
- "Show me recent bugs reported by customers"
- "What pain points do customers mention about alerting?"
- "Get the FRMNTS tickets from last month"

**Signals:** feature requests, bugs, tickets, feedback, pain points, workarounds, customer asks, issues, JIRA/FRMNTS project names

### Combined Analysis
Use multiple sources when correlating data across domains:
- "Which high-ARR orgs are most engaged with dashboards?" → RUM + Snowflake
- "What feature requests came from our top dashboard users?" → RUM + Jira
- "Show bugs reported by T0 customers" → Jira + Snowflake
- "Correlate feature adoption with related feature requests and customer ARR" → All three

**Signals:** Questions that mention metrics from multiple domains, or ask to correlate/enrich/combine data

## CLI Commands

The CLI commands remain separate for each data source:

### Datadog RUM

```bash
# Query RUM events
./box.sh datadog rum query QUERY [options]

# Aggregate RUM data (top N, time series)
./box.sh datadog rum aggregate QUERY [options]

# Detailed help
./box.sh datadog rum query --help
./box.sh datadog rum aggregate --help
```

### Snowflake

```bash
# Execute SQL query
./box.sh snowflake query <sql-file> [options]

# Detailed help
./box.sh snowflake --help
```

### Jira

```bash
# Fetch tickets from a project
./box.sh jira fetch PROJECT [options]

# Common options:
#   --jql "..."           Custom JQL query
#   --max-results N       Limit results (default: 50)
#   --clean               Human-readable output (recommended)
#   --custom-fields       Include additional fields

# Detailed help
./box.sh jira fetch --help
```

**Example:**
```bash
./box.sh jira fetch FRMNTS \
  --jql "project = FRMNTS AND created >= '2025-11-01' ORDER BY created DESC" \
  --max-results 100 \
  --clean \
  --working-folder 2026-02-05_feature-analysis \
  --output tickets.json
```

### Datadog Notebooks (Publishing)

When the user wants to publish or share their analysis:

```bash
# Create a notebook from JSON definition
./box.sh datadog notebook create data/<working-folder>/datadog/notebook.json

# Update an existing notebook
./box.sh datadog notebook update data/<working-folder>/datadog/notebook.json

# Detailed help
./box.sh datadog notebook --help
```

**Important:** Only create notebooks when the user explicitly asks to publish or share their analysis. Do not proactively suggest creating notebooks.

## Working Folders

**All work is organized in date-based working folders** under `data/`:

```
data/YYYY-MM-DD_short-description/
├── master.md              # Overall findings and context
├── datadog/               # RUM query outputs + notebooks
│   ├── *.json             # RUM query results
│   └── notebook.json      # Optional: Datadog notebook definition
├── snowflake/             # Snowflake query outputs
│   └── *.csv, *.sql
└── jira/                  # Jira ticket outputs
    └── *.json
```

### Directory Naming

**Format:** `YYYY-MM-DD_short-description`

- **Date**: Use today's date
- **Description**: Kebab-case, 2-4 words describing the work
  - Good: `dashboard-adoption`, `top-logs-customers`, `feature-analysis`
  - Bad: `analysis`, `query1`, `temp`

### When to Create vs Continue

**Create a new working folder when:**
- Starting a new task or question from the user
- The work is logically distinct from recent work
- User explicitly asks to start fresh

**Continue an existing working folder when:**
- Iterating on recent work from the same date
- User asks follow-up questions on the same topic
- Building on analysis from earlier in the session

**Ask the user when uncertain**, especially:
- In a new Claude session (you don't have full context)
- When the relationship to previous work is ambiguous

### CLI Output Pattern

All CLI commands support `--working-folder` for consistent output organization:

```bash
# RUM outputs → data/{folder}/datadog/
./box.sh datadog rum aggregate "..." \
  --working-folder 2026-02-05_dashboard-adoption \
  --output top_orgs.json

# Snowflake outputs → data/{folder}/snowflake/
./box.sh snowflake query analysis.sql \
  --working-folder 2026-02-05_dashboard-adoption \
  --output org_arr.csv

# Jira outputs → data/{folder}/jira/
./box.sh jira fetch FRMNTS \
  --working-folder 2026-02-05_dashboard-adoption \
  --output tickets.json
```

### Task Completion: master.md

**CRITICAL: After EVERY investigation, you MUST update (or create) `master.md` in the working folder.**

This is not optional. The workflow is:
1. Run queries / gather data
2. Present findings to user
3. **Update `master.md`** ← Do not skip this step

**The task is NOT complete until master.md is created or updated.**

Use the template at `.claude/skills/pa/master.md` as a starting point. It includes:
- Question / Task
- Approach (skills used, data sources, methodology)
- Key Findings (with business context)
- Artifacts (files created)
- Data Quality Notes (caveats, limitations)
- Follow-up Questions

## Knowledge Base

Consult these files before writing queries:

- **RUM patterns:** `knowledge/pa/rum.md` - Common RUM queries, facets, filters
- **Snowflake model:** `knowledge/pa/snowflake.md` - Tables, metrics, business definitions
- **Jira fields:** `knowledge/pa/jira.md` - Custom field mappings, JQL patterns
- **Notebooks:** `knowledge/pa/notebooks.md` - Notebook creation reference

## Workflow

### 1. Understand the Question

Parse the user's question to determine:
- What metric/insight are they looking for?
- Which data source(s) are needed?
- What time range is relevant?

### 2. Create/Identify Working Folder

- New task → Create `data/YYYY-MM-DD_description/`
- Follow-up → Continue existing folder
- Uncertain → Ask the user

### 3. Execute Queries

**For RUM queries:**
1. Consult `knowledge/pa/rum.md` for query patterns
2. Always include customer filters: `@session.type:user @usr.is_datadog_employee:false`
3. Save results to `datadog/` subfolder

**For Snowflake queries:**
1. Consult `knowledge/pa/snowflake.md` for schema and business rules
2. Exclude test orgs: `WHERE o.IS_TEST = FALSE`
3. Save results to `snowflake/` subfolder

**For Jira queries:**
1. Consult `knowledge/pa/jira.md` for field mappings
2. Use `--clean` flag for human-readable output
3. Save results to `jira/` subfolder

**For combined queries:**
1. Run queries in logical order (e.g., get org IDs from RUM first)
2. Use results from one source to filter queries in another
3. Join results and present combined insights

### 4. Present Findings

- Summarize key insights in business terms
- Include relevant caveats (data freshness, sampling, etc.)
- Suggest follow-up questions

### 5. Document in master.md

**CRITICAL:** Update `master.md` with:
- Question asked
- Approach taken
- Key findings
- Artifacts created
- Data quality notes

### 6. Publish (Optional, User-Initiated Only)

If the user asks to publish or share:
1. Create `datadog/notebook.json` in the working folder
2. Use `./box.sh datadog notebook create datadog/notebook.json`
3. Return the notebook URL

## Common Patterns

### Top N Organizations by Feature Usage + ARR

```bash
# Step 1: Get top orgs by usage (RUM)
./box.sh datadog rum aggregate \
  "@type:view @view.name:*dashboard* @session.type:user @usr.is_datadog_employee:false" \
  --from-time 30d \
  --group-by @usr.org_id \
  --metric @usr.id \
  --aggregation cardinality \
  --limit 20 \
  --working-folder 2026-02-05_analysis \
  --output top_orgs_usage.json

# Step 2: Get ARR for those orgs (Snowflake)
./box.sh snowflake query org_arr.sql \
  --working-folder 2026-02-05_analysis \
  --output org_arr.csv

# Step 3: Join and analyze
```

### Feature Requests from Top Users

```bash
# Step 1: Get top orgs by feature usage (RUM)
./box.sh datadog rum aggregate \
  "@type:view @view.name:*dashboard* @session.type:user @usr.is_datadog_employee:false" \
  --from-time 30d \
  --group-by @usr.org_id @usr.org_name \
  --limit 10 \
  --working-folder 2026-02-05_analysis \
  --output top_dashboard_orgs.json

# Step 2: Get feature requests mentioning those orgs (Jira)
./box.sh jira fetch FRMNTS \
  --jql "project = FRMNTS AND 'Org Name' ~ 'OrgNameHere'" \
  --clean \
  --working-folder 2026-02-05_analysis \
  --output org_feature_requests.json

# Step 3: Analyze qualitative feedback from power users
```

### Bugs from High-ARR Customers

```bash
# Step 1: Get T0/T1 customer org IDs (Snowflake)
./box.sh snowflake query high_arr_orgs.sql \
  --working-folder 2026-02-05_analysis \
  --output high_arr_orgs.csv

# Step 2: Get bugs from those orgs (Jira)
# Use org IDs/names to filter JQL
./box.sh jira fetch BUGS \
  --jql "project = BUGS AND 'Org ID' IN (123, 456, 789)" \
  --clean \
  --working-folder 2026-02-05_analysis \
  --output high_arr_bugs.json
```

## Tips

1. **Always filter for customers in RUM:** Include `@session.type:user @usr.is_datadog_employee:false`
2. **Use --clean for Jira:** Converts ADF to readable text automatically
3. **Check the knowledge base first:** Patterns, schemas, and field mappings are documented
4. **Start with aggregates:** Use `rum aggregate` for top N before diving into raw events
5. **Mind the bucket limits:** RUM aggregates cap at 1,000 buckets (see knowledge base)
6. **Document everything:** Update `master.md` after each investigation
7. **Only publish when asked:** Don't proactively create notebooks
8. **Visualize with Excalidraw:** When findings would benefit from a diagram (architecture, data flows, feature maps), use `./box.sh draw api push diagram.yaml` to create visual summaries. See CLAUDE.md for the YAML format.

## Getting Help

```bash
./box.sh datadog --help
./box.sh datadog rum aggregate --help
./box.sh datadog notebook --help
./box.sh snowflake --help
./box.sh jira fetch --help
```
