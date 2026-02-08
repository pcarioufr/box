# Excalidraw Canvas Server

A custom Excalidraw service with a REST API and real-time WebSocket sync. The server is **stateless** — all elements live in memory only. Persistence is handled externally via declarative YAML diagrams pushed through the CLI.

## Architecture

```
Browser (Excalidraw UI)  <──WebSocket──>  Express Server  <──REST API──>  Claude / CLI
                                               │
                                          In-memory Map
                                         (no disk storage)
```

- **Frontend**: Custom React app using `@excalidraw/excalidraw`, built with Vite at container startup
- **Backend**: Stateless Express.js server with REST API and WebSocket
- **Persistence**: YAML files + `.state.json` managed by the CLI (`libs/excalidraw/push.py`)

## REST API

All endpoints at `http://localhost:3000`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/elements` | Get all elements |
| `POST` | `/api/elements/batch` | Create multiple elements |
| `PUT` | `/api/elements/:id` | Update an element |
| `DELETE` | `/api/elements/:id` | Delete an element |
| `DELETE` | `/api/elements` | Clear all elements |
| `POST` | `/api/refresh` | Force all clients to refresh |

### Element format

Elements are provided as **skeletons** (minimal properties, expanded by Excalidraw):

```json
{
  "type": "rectangle",
  "x": 100, "y": 100,
  "width": 200, "height": 100,
  "label": { "text": "My Label" }
}
```

Supported types: `rectangle`, `ellipse`, `diamond`, `text`, `arrow`, `line`.

The `label` property is syntactic sugar — Excalidraw expands it into a shape + bound text element with `containerId`/`boundElements` references.

## Real-time sync

API changes broadcast via WebSocket to all connected browsers. The frontend is **receive-only** — it renders updates from the API but does not send user edits back to the server.

## YAML Push Workflow

Diagrams are authored as declarative YAML and pushed to the canvas via CLI:

```bash
./box.sh draw api push diagram.yaml         # Incremental push
./box.sh draw api push diagram.yaml --clear  # Full clear + recreate
```

See `libs/excalidraw/push.py` for the YAML spec and push algorithm.

### Stale state handling

The push CLI tracks YAML-to-Excalidraw ID mappings in a `.state.json` file next to the YAML. If the server restarts (losing in-memory elements), the CLI detects stale state and automatically falls back to a full push.

## Running

```bash
./box.sh draw           # Start container + open browser
./box.sh draw stop      # Stop container
```

The container auto-starts when API commands are run (`./box.sh draw api ...`).

## File structure

```
services/excalidraw/
├── Dockerfile              # Node + frontend build at startup
├── package.json            # Server dependencies (express, ws, uuid)
├── src/
│   └── server.js           # Stateless Express server, REST API, WebSocket
└── frontend/
    ├── package.json        # Frontend dependencies (@excalidraw/excalidraw, react, vite)
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.tsx        # React entry point
        └── App.tsx         # Excalidraw component (receive-only WebSocket)
```
