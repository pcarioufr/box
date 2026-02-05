# Overview

`The Box` is a Ubuntu virtual machine that runs within a docker container.

Since `The Box` runs as a short-lived container, nothing that happens in the box is persisted - apart from its `home` folder. Which makes it a fully controlled and easily distributed working environment.

I personally use it as a dev-tool box (adding scripts that wrap terraform, ssh, etc.) commands. But it's also a convenient way to sandbox ubuntu stuff.


## Prerequisites

### Install Docker

```bash
brew install docker-desktop
```

### Install Node.js (Optional)

Required for MCP servers (like Atlassian MCP) that use the `mcp-remote` proxy.

```bash
brew install node
```


## Hello world!

```bash
$ ./box.sh ubuntu hello -l french
hello.sh::28 | salut la compagnie !
```

## Open a terminal in `The Box`

Alternatively, use the `ubuntu` command with no further argument to open a terminal in the virtual machine.

```bash
$ ./box.sh ubuntu
me@box:~ *$*
```

## Alias `The Box` entry points

Run the `alias` command [on the host] to use `box` as a shortcut for `./box.sh`.

```bash
$ alias box='./box.sh'
$ box ubuntu hello
hello.sh::28 | hello world!
```

This alias persists as long as your terminal window/tab remains open.


# Customise `The Box`

## Bring you own scripts


The box comes with a default configuration in the `services/ubuntu/` directory, which consists of:

* a docker build folder - see [`services/ubuntu/build`](services/ubuntu/build)
* a home folder - see [`services/ubuntu/home`](services/ubuntu/home)
* scripts and utilities - see [`services/ubuntu/opt`](services/ubuntu/opt)
* environment variables to set within the virtual machine - see [`services/ubuntu/.env`](services/ubuntu/.env)

You can customize the ubuntu service by editing files in `services/ubuntu/` or modifying the service definition in [`services/compose.yml`](services/compose.yml).


## Bring you own data

The ubuntu service mounts the `data/` directory to `/data` inside the container - see [`services/compose.yml`](services/compose.yml).

To use a different data directory, update the volume mapping in [`services/compose.yml`](services/compose.yml).


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
- **Datadog** (`./box.sh datadog`) - Query and aggregate RUM data, create/update notebooks for Product Analytics

See [libs/README.md](libs/README.md) for details, or run `./box.sh <command> --help`.

## Setup

```bash
cp env.example .env   # Add your credentials (Atlassian, Datadog, Snowflake)
./box.sh --setup      # Create venv and install dependencies
```

