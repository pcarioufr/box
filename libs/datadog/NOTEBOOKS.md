# Datadog Notebooks - Standard API Format Reference

This document provides examples and reference for creating Datadog notebooks using the standard Datadog API format.

## Overview

Notebooks are created using the **standard Datadog Notebooks API format**:
- Official API documentation: https://docs.datadoghq.com/api/latest/notebooks/
- No custom abstractions - what you write is what gets sent to the API
- Full access to all Datadog notebook features

## Command Usage

### Create Notebook

```bash
# Create notebook from file
./box.sh datadog notebook create notebook.json

# The file is automatically updated with the notebook ID:
# Before: {"data": {"type": "notebooks", "attributes": {...}}}
# After:  {"data": {"id": 13856789, "type": "notebooks", "attributes": {...}}}

# Create from stdin (won't update source)
cat notebook.json | ./box.sh datadog notebook create -

# Save metadata
./box.sh datadog notebook create notebook.json \
  --working-folder 2026-02-05_analysis \
  --output notebook_metadata.json

# Don't update source file with ID
./box.sh datadog notebook create notebook.json --no-update-file
```

### Update Notebook

```bash
# Update existing notebook (requires ID in JSON)
./box.sh datadog notebook update notebook.json

# Update from stdin
cat notebook.json | ./box.sh datadog notebook update -

# Save update metadata
./box.sh datadog notebook update notebook.json \
  --working-folder 2026-02-05_analysis \
  --output notebook_update_metadata.json
```

### Workflow

```bash
# 1. Create notebook
./box.sh datadog notebook create notebook.json
# → notebook.json is updated with ID

# 2. Edit notebook.json (add cells, change content, etc.)
vim notebook.json

# 3. Push changes to Datadog
./box.sh datadog notebook update notebook.json
# → Updates the existing notebook

# 4. Repeat steps 2-3 as needed
```

---

## Notebook Structure

A notebook definition has this structure:

```json
{
  "data": {
    "type": "notebooks",
    "attributes": {
      "name": "Notebook Title",
      "cells": [
        // Array of cell objects (markdown, widgets, etc.)
      ],
      "time": {
        // Time range for the notebook
      },
      "status": "published",  // Optional: "published" or "draft"
      "metadata": {}          // Optional: custom metadata
    }
  }
}
```

---

## Cell Types

### Markdown Cell

Display text, headings, lists, code blocks:

```json
{
  "type": "notebook_cells",
  "attributes": {
    "definition": {
      "type": "markdown",
      "text": "# Analysis Title\n\n## Overview\n\nMarkdown content here..."
    }
  }
}
```

### Toplist Widget Cell

Show top N results:

```json
{
  "type": "notebook_cells",
  "attributes": {
    "definition": {
      "type": "toplist",
      "title": "Top Organizations by Active Users",
      "requests": [{
        "queries": [{
          "data_source": "rum",
          "name": "query1",
          "search": {
            "query": "@type:view @session.type:user @view.name:*dashboard*"
          },
          "compute": {
            "aggregation": "cardinality",
            "metric": "@usr.id"
          },
          "group_by": [{
            "facet": "@usr.org_name",
            "limit": 10,
            "sort": {
              "aggregation": "cardinality",
              "metric": "@usr.id",
              "order": "desc"
            }
          }]
        }],
        "formulas": [{"formula": "query1"}],
        "response_format": "scalar"
      }]
    }
  }
}
```

### Timeseries Widget Cell

Show data over time:

```json
{
  "type": "notebook_cells",
  "attributes": {
    "definition": {
      "type": "timeseries",
      "title": "Dashboard Views Over Time",
      "requests": [{
        "queries": [{
          "data_source": "rum",
          "name": "query1",
          "search": {
            "query": "@type:view @view.name:*dashboard*"
          },
          "compute": {
            "aggregation": "count",
            "interval": 86400000
          }
        }],
        "formulas": [{"formula": "query1"}],
        "response_format": "timeseries",
        "display_type": "line"
      }]
    }
  }
}
```

---

## Time Ranges

Specify the time range for the entire notebook:

```json
{
  "time": {
    "live_span": "1w"
  }
}
```

Available live spans:
- `"5m"`, `"10m"`, `"15m"`, `"30m"` - Minutes
- `"1h"`, `"4h"` - Hours
- `"1d"`, `"2d"` - Days
- `"1w"` - Week
- `"1mo"`, `"3mo"`, `"6mo"` - Months
- `"1y"` - Year

---

## Complete Examples

### Example 1: Simple Markdown Notebook

```json
{
  "data": {
    "type": "notebooks",
    "attributes": {
      "name": "Weekly Status Update",
      "cells": [
        {
          "type": "notebook_cells",
          "attributes": {
            "definition": {
              "type": "markdown",
              "text": "# Weekly Status\n\n## Highlights\n\n- Feature X shipped\n- Bug fixes deployed\n\n## Next Week\n\n- Start feature Y"
            }
          }
        }
      ],
      "time": {
        "live_span": "1w"
      }
    }
  }
}
```

### Example 2: Notebook with Toplist

```json
{
  "data": {
    "type": "notebooks",
    "attributes": {
      "name": "Dashboard Adoption Analysis",
      "cells": [
        {
          "type": "notebook_cells",
          "attributes": {
            "definition": {
              "type": "markdown",
              "text": "# Dashboard Adoption\n\n## Overview\n\nAnalysis of dashboard usage across customer organizations."
            }
          }
        },
        {
          "type": "notebook_cells",
          "attributes": {
            "definition": {
              "type": "toplist",
              "title": "Top 10 Organizations by Active Users",
              "requests": [{
                "queries": [{
                  "data_source": "rum",
                  "name": "query1",
                  "search": {
                    "query": "@type:view @session.type:user @view.name:*dashboard* @usr.is_datadog_employee:false"
                  },
                  "compute": {
                    "aggregation": "cardinality",
                    "metric": "@usr.id"
                  },
                  "group_by": [{
                    "facet": "@usr.org_name",
                    "limit": 10,
                    "sort": {
                      "aggregation": "cardinality",
                      "metric": "@usr.id",
                      "order": "desc"
                    }
                  }]
                }],
                "formulas": [{"formula": "query1"}],
                "response_format": "scalar"
              }]
            }
          }
        }
      ],
      "time": {
        "live_span": "1mo"
      }
    }
  }
}
```

### Example 3: Notebook with Multiple Widgets

```json
{
  "data": {
    "type": "notebooks",
    "attributes": {
      "name": "Product Analytics - January 2026",
      "cells": [
        {
          "type": "notebook_cells",
          "attributes": {
            "definition": {
              "type": "markdown",
              "text": "# Product Analytics Report\n\n## Executive Summary\n\nDashboard adoption increased 15% month-over-month."
            }
          }
        },
        {
          "type": "notebook_cells",
          "attributes": {
            "definition": {
              "type": "toplist",
              "title": "Top Organizations by Active Users",
              "requests": [{
                "queries": [{
                  "data_source": "rum",
                  "name": "query1",
                  "search": {
                    "query": "@type:view @session.type:user @view.name:*dashboard*"
                  },
                  "compute": {
                    "aggregation": "cardinality",
                    "metric": "@usr.id"
                  },
                  "group_by": [{
                    "facet": "@usr.org_name",
                    "limit": 10,
                    "sort": {
                      "aggregation": "cardinality",
                      "metric": "@usr.id",
                      "order": "desc"
                    }
                  }]
                }],
                "formulas": [{"formula": "query1"}],
                "response_format": "scalar"
              }]
            }
          }
        },
        {
          "type": "notebook_cells",
          "attributes": {
            "definition": {
              "type": "timeseries",
              "title": "Daily Dashboard Views",
              "requests": [{
                "queries": [{
                  "data_source": "rum",
                  "name": "query1",
                  "search": {
                    "query": "@type:view @view.name:*dashboard*"
                  },
                  "compute": {
                    "aggregation": "count",
                    "interval": 86400000
                  }
                }],
                "formulas": [{"formula": "query1"}],
                "response_format": "timeseries",
                "display_type": "line"
              }]
            }
          }
        },
        {
          "type": "notebook_cells",
          "attributes": {
            "definition": {
              "type": "markdown",
              "text": "## Recommendations\n\n1. Expand dashboard templates\n2. Improve onboarding\n3. Monitor EMEA adoption"
            }
          }
        }
      ],
      "time": {
        "live_span": "1mo"
      },
      "status": "published"
    }
  }
}
```

---

## Query Aggregations

RUM queries support these aggregations:

| Aggregation | Description | Requires Metric |
|------------|-------------|-----------------|
| `count` | Count events | No |
| `cardinality` | Count unique values | Yes |
| `sum` | Sum values | Yes |
| `avg` | Average values | Yes |
| `min` | Minimum value | Yes |
| `max` | Maximum value | Yes |
| `median` | Median value | Yes |
| `pc75` | 75th percentile | Yes |
| `pc90` | 90th percentile | Yes |
| `pc95` | 95th percentile | Yes |
| `pc98` | 98th percentile | Yes |
| `pc99` | 99th percentile | Yes |

---

## Time Intervals for Timeseries

Intervals are specified in milliseconds:

| Interval | Milliseconds | Use Case |
|----------|-------------|----------|
| 1 minute | `60000` | Real-time monitoring |
| 5 minutes | `300000` | Short-term trends |
| 10 minutes | `600000` | Hourly patterns |
| 15 minutes | `900000` | Hourly patterns |
| 30 minutes | `1800000` | Hourly patterns |
| 1 hour | `3600000` | Daily patterns |
| 4 hours | `14400000` | Weekly patterns |
| 1 day | `86400000` | Monthly trends |

---

## Common RUM Queries

**All views:**
```
@type:view @session.type:user
```

**Dashboard views (excluding Datadog employees):**
```
@type:view @view.name:*dashboard* @session.type:user @usr.is_datadog_employee:false
```

**Errors:**
```
@type:error @session.type:user
```

**Actions (clicks, etc.):**
```
@type:action @session.type:user
```

**Sessions:**
```
@type:session @session.type:user
```

---

## Workflow: From Analysis to Notebook

### Step 1: Run RUM Queries for Analysis

Use `./box.sh datadog rum aggregate` to analyze data and understand patterns:

```bash
# Explore top organizations
./box.sh datadog rum aggregate \
  "@type:view @view.name:*dashboard* @session.type:user" \
  --from-time 30d \
  --group-by @usr.org_name \
  --metric @usr.id \
  --aggregation cardinality \
  --limit 10 \
  --working-folder 2026-02-05_analysis \
  --output exploration_top_orgs.json
```

This gives you data to analyze and inform your notebook content.

### Step 2: Create Notebook JSON

Based on your analysis, create a notebook JSON file with:
- Markdown cells for context and insights
- Widget cells that replicate your key queries

Save as `data/2026-02-05_analysis/notebook.json`

### Step 3: Create the Notebook

```bash
./box.sh datadog notebook create \
  data/2026-02-05_analysis/notebook.json \
  --working-folder 2026-02-05_analysis \
  --output notebook_metadata.json
```

---

## Tips

1. **Start simple** - Create notebooks with just markdown first
2. **Use Datadog UI** - Build widgets in Datadog UI, then inspect the JSON
3. **Copy from dashboards** - Export dashboard JSON and adapt widget definitions
4. **Test queries first** - Use `rum aggregate` CLI to verify queries work
5. **Version control** - Keep notebook JSON in git for reproducibility

---

## API Reference

For complete API documentation:
- **Notebooks API**: https://docs.datadoghq.com/api/latest/notebooks/
- **Widget definitions**: https://docs.datadoghq.com/dashboards/widgets/
- **RUM queries**: https://docs.datadoghq.com/real_user_monitoring/explorer/search_syntax/
