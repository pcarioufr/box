---
name: pa
description: Product Analytics skill. Query user behavior (Datadog RUM), business metrics (Snowflake), and qualitative feedback (Jira) using natural language. Intelligently routes to the right data source(s) based on your question.
---

# Product Analytics Skill

Combine behavioral data (Datadog RUM), business data (Snowflake), and qualitative data (Jira) to answer product questions.

## Query Routing

Analyze the user's question to determine which data source(s) to use:

| Source | When | Signals |
|--------|------|---------|
| **RUM** | User behavior questions | views, clicks, sessions, adoption, engagement, journeys, time on page |
| **Snowflake** | Business metric questions | revenue, ARR, MRR, contracts, tiers, pricing, customers |
| **Jira** | Customer feedback questions | feature requests, bugs, tickets, pain points |
| **Combined** | Cross-domain correlation | questions spanning multiple domains |

## Query Guardrails

- **RUM**: Always include `@session.type:user @usr.is_datadog_employee:false`
- **Snowflake**: Exclude test orgs: `WHERE o.IS_TEST = FALSE`
- **Jira**: Always use `--clean` for human-readable output
- **RUM aggregates**: Cap at 1,000 buckets — start with aggregates before diving into raw events

## Knowledge Base

Read these **before** writing queries:

- `knowledge/datadog/` — RUM query patterns, facets, filters, data model
- `knowledge/snowflake/` — Tables, metrics, business definitions
- `knowledge/jira/` — Custom field mappings, JQL patterns

## CLI Entry Points

Each source has its own CLI. Use `--help` for full options:

```bash
./box.sh datadog rum query --help
./box.sh datadog rum aggregate --help
./box.sh datadog fetch --help
./box.sh datadog notebook --help
./box.sh snowflake --help
./box.sh jira fetch --help
```

## Working Folders

All output goes in `data/explorations/YYYY-MM-DD_short-description/` with subfolders per source (`datadog/`, `snowflake/`, `jira/`). Use `--working-folder` on CLI commands.

- **New task** → create a new folder (date + 2-4 word kebab-case description)
- **Follow-up** → continue existing folder
- **Uncertain** → ask the user

## master.md

**After every investigation, update `master.md` in the working folder.** Use `.claude/skills/pa/master.md` as template. The task is not complete until master.md reflects the findings.

## Publishing

Only create Datadog notebooks when the user explicitly asks to publish or share.
