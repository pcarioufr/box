# Graph Viewer

Interactive web application for visualizing directed graphs with weighted edges.

## Overview

This service provides a web interface to upload and visualize graph data. It displays relationships between nodes with edges weighted by a numeric value (e.g., likelihood, frequency, strength).

## Features

- **CSV Upload**: Upload co-visitation data in simple 3-column format
- **Threshold Filtering**: Filter edges by likelihood percentage (default: 10%)
- **Interactive Graph**: Pan, zoom, and click on nodes/edges
- **Multiple Layouts**: Choose from 6 different graph layout algorithms
  - Hierarchical (DAG) - default, left-to-right flow
  - Circle - nodes in a circle
  - Grid - nodes in a grid
  - Concentric - nodes in concentric circles
  - Breadth First - tree-like layout
  - Force Directed - physics-based layout
- **Real-time Stats**: View node and edge counts

## Usage

### Starting the Service

```bash
docker compose -f services/compose.yml up graph-viewer
```

Or start all services:

```bash
docker compose -f services/compose.yml up
```

The service will be available at: **http://localhost:5001**

### Stopping the Service

```bash
docker compose -f services/compose.yml down graph-viewer
```

### Data Format

Upload a CSV file with 3 columns (column names are ignored):
1. **Column 1**: Source node name
2. **Column 2**: Target node name
3. **Column 3**: Edge weight (numeric value, e.g., 0-100)

Example CSV:
```csv
source,target,weight
auth,dashboard,45.5
auth,settings,23.1
dashboard,metrics,67.8
dashboard,logs,34.2
settings,profile,89.3
```

### Workflow

1. Open http://localhost:5001 in your browser
2. Click "Choose File" and select your CSV file
3. Adjust the threshold if needed (default: 10) - edges below this value will be filtered out
4. Click "Load Graph" to visualize
5. Use the Layout dropdown to change the visualization style
6. Interact with the graph:
   - Click and drag to pan
   - Scroll to zoom
   - Click nodes or edges to select them (details logged to console)

## Technology Stack

- **Backend**: Python Flask
- **Visualization**: Cytoscape.js (network graph library)
- **Layouts**: Dagre (hierarchical layout algorithm)
- **Data Processing**: Pandas

## Port

- **Container Port**: 5000
- **Host Port**: 5001 (mapped in docker-compose.yml)

## Development

To rebuild after changes:

```bash
docker compose -f services/compose.yml build graph-viewer
docker compose -f services/compose.yml up graph-viewer
```

## API Endpoint

### POST /api/upload

Upload CSV data and get filtered graph.

**Parameters:**
- `file`: CSV file (multipart/form-data)
- `threshold`: Minimum edge weight (default: 10.0)

**Response:**
```json
{
  "elements": [
    {"data": {"id": "node1", "label": "node1"}},
    {"data": {"id": "node1-node2", "source": "node1", "target": "node2", "likelihood": 45.5, "label": "45.5%"}}
  ],
  "stats": {
    "total_edges": 100,
    "filtered_edges": 42,
    "nodes": 15,
    "threshold": 10.0
  }
}
```
