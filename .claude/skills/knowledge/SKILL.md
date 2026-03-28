---
name: knowledge
description: Maintain the project knowledge base. Owns _knowledge/ folder conventions, file templates, and organic maintenance rules. Invoke explicitly to review and update knowledge, or follow its rules organically during conversations.
---

# Knowledge Base Skill

## Structure

Every project directory under `data/` can have a `_knowledge/` folder containing curated, durable understanding. Cross-cutting reference lives in `data/_knowledge/`.

```
data/
├── _knowledge/              # cross-cutting reference
│   ├── general.md           # about Pierre, Datadog context, leadership org chart
│   ├── slack.md             # general Slack channels + leadership IDs
│   ├── snowflake/           # core business entities (org, revenue, product, user, team)
│   ├── datadog/             # data model in Datadog account (RUM, Logs)
│   ├── dev/                 # codebase & dev environment (dd-source, web-ui)
│   └── jira.md
├── detection/
│   ├── _knowledge/          # initiative-specific
│   │   ├── overview.md      # architecture, strategy, org charts, stakeholders
│   │   ├── slack.md         # detection channels + people
│   │   ├── jira.md          # APPAI, MNTS, FRMNTS projects + custom fields
│   │   ├── snowflake/       # monitors, incidents, SLOs, notebooks, Watchdog
│   │   └── dev/             # detection-relevant code areas, web-ui pages
│   └── ...
├── management/
│   ├── _knowledge/
│   └── ...
└── explorations/            # no _knowledge/ — use master.md
```

A topic can be a single file or a folder — let context decide which is appropriate. Start with a file, split into a folder when it grows.

## What belongs in `_knowledge/`

- Curated understanding: architecture, mental models, decisions and their rationale
- Distilled insights from explorations or pulled documents
- Stakeholder context, team structure, recurring themes
- Tool-specific reference (schemas, field mappings, query patterns)
- Development reference: codebase structure, relevant code areas, dev environment setup — stored in `dev/` subdirectories

## What does NOT belong in `_knowledge/`

- Raw data outputs — stay in their project folder
- Pulled documents verbatim — only distilled insights from them belong
- Conversation-scoped plans or task lists
- Ephemeral status ("blocked on X") — use auto-memory instead

## File templates

Every `_knowledge/` file starts with `Last updated: YYYY-MM-DD` and stays under 200 lines. Split by topic when a file grows.

### Initiative overview (`overview.md`)

```markdown
# {Initiative} — Knowledge

Last updated: YYYY-MM-DD

## What it is

One paragraph: what this initiative is, who owns it, why it matters.

## Architecture / Mental model

The current understanding of how things fit together.

## Key decisions

Decisions and their rationale. Update in-place when decisions change — don't append.

## Key references

Pointers to pulled docs or external resources (not the content itself).
```

### Slack reference (`slack.md`)

```markdown
# Slack Reference

Last updated: YYYY-MM-DD

## Channels

| Channel | ID | When to use |
|---|---|---|
| `#channel-name` | `C0...` | ... |

## People

| Name | Slack ID | Role |
|---|---|---|
| ... | `D0...` | ... |
```

### Tool reference (e.g. `snowflake/model.md`)

```markdown
# {Tool} — {Topic}

Last updated: YYYY-MM-DD

## Tables / Fields / Patterns

Curated reference for querying. Keep aligned with actual schema.
```

## Organic maintenance rules

During any conversation, follow these rules without needing explicit invocation:

### Tier 1 — Update silently, mention in one line
- Factual corrections: stale dates, renamed concepts, outdated links
- Adding a missing `Last updated` date after editing

### Tier 2 — Propose the change, update after confirmation
- New insight distilled from an exploration or document pull
- Adding a new section or substantial content to an existing file
- Updating strategic framing (architecture, mental model)

### Tier 3 — Ask first
- Creating a new `_knowledge/` folder or file
- Structural reorganization (splitting, merging, renaming files)
- Removing content

## Explicit invocation (`/knowledge`)

When invoked directly, perform a review pass:

1. List all `_knowledge/` folders and their files with last-updated dates
2. Flag files that are likely stale (>30 days since last update, or conflicting with recent conversation context)
3. Propose specific updates, creations, or cleanups
4. Execute after user confirmation
