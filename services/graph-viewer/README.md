# Graph Viewer

Interactive web application for visualizing graphs with customizable node and edge properties.

## Overview

Upload graph data as CSV files and explore relationships interactively. Supports node sizing, coloring, per-edge directionality, and filterable properties.

## Features

- **Two-file format**: Separate nodes CSV (optional) and edges CSV for full control over visual properties
- **Node properties**: Size, color, and label per node
- **Edge properties**: Weight (controls thickness), color, label, and per-edge directed/undirected
- **Filterable properties**: Any `prop_*` column on nodes becomes a multi-select filter in the UI
- **Label behavior**: Labels hidden by default; shown on hover, toggled on/off by clicking a node
- **Threshold filtering**: Filter edges by minimum weight
- **Multiple layouts**: Hierarchical (DAG), Circle, Grid, Concentric, Breadth First, Force Directed
- **Interactive**: Pan, zoom, hover to highlight neighborhoods, click for persistent labels

## Usage

### Starting the Service

```bash
docker compose -f services/compose.yml up graph-viewer
```

Available at: **http://localhost:5001**

### Stopping

```bash
docker compose -f services/compose.yml down graph-viewer
```

## Data Format

### Edges CSV (required)

| Column | Required | Description |
|--------|----------|-------------|
| `source` | yes | Source node ID |
| `target` | yes | Target node ID |
| `weight` | no | Numeric weight (controls edge thickness). Default: 1.0 |
| `label` | no | Edge label text. Default: weight value |
| `color` | no | Hex color (e.g., `#58a6ff`). Default: blue |
| `directed` | no | `true` for arrow, `false` for undirected. Default: `true` |

```csv
source,target,weight,label,directed
monitor-a,monitor-b,3.5,3.5× co=2 Δ50m,true
monitor-c,monitor-d,1.2,1.2× co=4 Δ12m,false
```

### Nodes CSV (optional)

If omitted, nodes are auto-created from edge endpoints with default styling.

| Column | Required | Description |
|--------|----------|-------------|
| `id` | yes | Must match source/target values in edges CSV |
| `label` | no | Display name. Default: id |
| `size` | no | Numeric value (auto-normalized to visual range). Default: uniform |
| `color` | no | Hex color (e.g., `#0a3069`). Default: blue |
| `prop_*` | no | Filterable property (see below) |

```csv
id,label,size,color,prop_service
monitor-a,My Monitor A,2.5,#b3d9ff,service-x
monitor-b,My Monitor B,0.8,#0a3069,service-x service-y
```

### Filterable Properties (`prop_*`)

Any column in the nodes CSV prefixed with `prop_` becomes a multi-select filter in the UI.

- The filter name is derived from the column name (e.g., `prop_service` becomes "service")
- **Multi-valued**: Use space-separated values for nodes that belong to multiple categories (e.g., `service-a service-b`)
- A node matches a filter if **any** of its values are in the selected set
- When no values are selected (or "All" is selected), all nodes are shown
- Edges are hidden when either endpoint is hidden

### Legacy Format

For backward compatibility, a single CSV with positional columns also works:
- Column 1: source, Column 2: target, Column 3: weight, Column 4 (optional): label

## Workflow

1. Open http://localhost:5001
2. Select an edges CSV (and optionally a nodes CSV)
3. Adjust "Min weight" to filter low-weight edges
4. Click "Load Graph"
5. Use filters (if `prop_*` columns exist) to isolate subsets
6. Hover nodes to see labels and highlight neighborhoods
7. Click nodes to pin their labels on the graph
8. Change layout as needed

## API

### POST /api/upload

**Form parameters:**
- `edges`: Edges CSV file (required)
- `nodes`: Nodes CSV file (optional)
- `threshold`: Minimum edge weight (default: 0)

**Response:**
```json
{
  "elements": [
    {"data": {"id": "mon-a", "label": "Monitor A", "size": 2.5, "color": "#b3d9ff", "prop_service": "svc-x"}},
    {"data": {"id": "mon-a->mon-b", "source": "mon-a", "target": "mon-b", "weight": 3.5, "label": "3.5×", "directed": true}}
  ],
  "filters": {
    "prop_service": {"name": "service", "values": ["svc-x", "svc-y", "svc-z"]}
  },
  "stats": {
    "total_edges": 100,
    "filtered_edges": 42,
    "nodes": 15,
    "threshold": 0
  }
}
```

## Technology Stack

- **Backend**: Python Flask
- **Visualization**: Cytoscape.js
- **Layouts**: Dagre (hierarchical layout)
- **Data Processing**: Pandas

## Port

- **Container Port**: 5000
- **Host Port**: 5001

## Development

```bash
docker compose -f services/compose.yml build graph-viewer
docker compose -f services/compose.yml up graph-viewer
```
