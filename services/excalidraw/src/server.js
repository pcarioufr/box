/**
 * Excalidraw Canvas Server
 *
 * 1. Serves the custom React frontend with Excalidraw
 * 2. REST API for element manipulation (CRUD + batch)
 * 3. WebSocket for real-time sync between browser and API clients
 *
 * Stateless — all elements live in memory only.
 * Persistence is handled externally via YAML push (libs/excalidraw/push.py).
 */

const express = require('express');
const { WebSocketServer } = require('ws');
const { v4: uuidv4 } = require('uuid');
const http = require('http');
const path = require('path');

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

// ============ Helpers ============

// In-memory element store
const elements = new Map();

// Assign ID and timestamps to a new element
function initElement(element) {
  if (!element.id) {
    element.id = uuidv4().replace(/-/g, '').substring(0, 20);
  }
  const now = new Date().toISOString();
  element.createdAt = element.createdAt || now;
  element.updatedAt = now;
  element.version = 1;
  return element;
}

// Broadcast to all WebSocket clients, optionally excluding one
function broadcast(message, excludeWs = null) {
  const data = JSON.stringify(message);
  wss.clients.forEach(client => {
    if (client.readyState === 1 && client !== excludeWs) {
      client.send(data);
    }
  });
}

// ============ Init ============

app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, '../public')));

// ============ REST API ============

app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    elements_count: elements.size,
    websocket_clients: wss.clients.size
  });
});

app.get('/api/elements', (req, res) => {
  const all = Array.from(elements.values());
  res.json({ success: true, elements: all, count: all.length });
});

app.post('/api/elements', (req, res) => {
  const element = initElement(req.body);
  elements.set(element.id, element);
  broadcast({ type: 'element_created', element });
  res.json({ success: true, element });
});

app.post('/api/elements/batch', (req, res) => {
  const { elements: input } = req.body;
  if (!Array.isArray(input)) {
    return res.status(400).json({ success: false, error: 'elements must be an array' });
  }
  const created = input.map(el => {
    const element = initElement(el);
    elements.set(element.id, element);
    return element;
  });
  broadcast({ type: 'elements_batch_created', elements: created });
  res.json({ success: true, elements: created, count: created.length });
});

app.put('/api/elements/:id', (req, res) => {
  const { id } = req.params;
  const existing = elements.get(id);
  if (!existing) {
    return res.status(404).json({ success: false, error: `Element ${id} not found` });
  }
  const updated = {
    ...existing,
    ...req.body,
    id,
    updatedAt: new Date().toISOString(),
    version: (existing.version || 1) + 1
  };
  elements.set(id, updated);
  broadcast({ type: 'element_updated', element: updated });
  res.json({ success: true, element: updated });
});

app.delete('/api/elements/:id', (req, res) => {
  const { id } = req.params;
  if (!elements.has(id)) {
    return res.status(404).json({ success: false, error: `Element ${id} not found` });
  }
  elements.delete(id);
  broadcast({ type: 'element_deleted', elementId: id });
  res.json({ success: true });
});

app.delete('/api/elements', (req, res) => {
  const count = elements.size;
  elements.clear();
  broadcast({ type: 'clear' });
  res.json({ success: true, message: `Cleared ${count} elements` });
});

app.post('/api/refresh', (req, res) => {
  broadcast({ type: 'refresh' });
  res.json({ success: true });
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../public/index.html'));
});

// ============ WebSocket ============

wss.on('connection', (ws) => {
  console.log('WebSocket client connected');

  // Send current state to new client
  ws.send(JSON.stringify({
    type: 'initial_elements',
    elements: Array.from(elements.values())
  }));

  ws.on('close', () => console.log('WebSocket client disconnected'));
});

// ============ Start ============

const PORT = process.env.PORT || 3000;
server.listen(PORT, '0.0.0.0', () => {
  console.log(`Excalidraw Canvas Server running on port ${PORT}`);
  console.log(`  UI: http://localhost:${PORT}  |  API: /api/elements`);
});
