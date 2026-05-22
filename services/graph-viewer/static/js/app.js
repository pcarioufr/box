let cy = null;
const edgesInput = document.getElementById('edgesInput');
const nodesInput = document.getElementById('nodesInput');
const uploadBtn = document.getElementById('uploadBtn');
const thresholdInput = document.getElementById('threshold');
const layoutSelect = document.getElementById('layoutSelect');
const errorDiv = document.getElementById('error');
const statsDiv = document.getElementById('stats');
const detailPanel = document.getElementById('detailPanel');
const detailContent = document.getElementById('detailContent');
const detailEmpty = detailPanel.querySelector('.detail-empty');
const detailName = document.getElementById('detailName');
const detailProps = document.getElementById('detailProps');

edgesInput.addEventListener('change', () => {
    uploadBtn.disabled = !edgesInput.files.length;
    hideError();
});

uploadBtn.addEventListener('click', loadGraph);
layoutSelect.addEventListener('change', applyLayout);

thresholdInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && edgesInput.files.length) {
        loadGraph();
    }
});

function hideError() {
    errorDiv.style.display = 'none';
}

function showError(message) {
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

function updateStats(stats) {
    document.getElementById('statNodes').textContent = stats.nodes;
    document.getElementById('statEdges').textContent = stats.filtered_edges;
    document.getElementById('statTotal').textContent = stats.total_edges;
    statsDiv.style.display = 'flex';
}

async function loadGraph() {
    const edgesFile = edgesInput.files[0];
    const nodesFile = nodesInput.files.length ? nodesInput.files[0] : null;
    const threshold = parseFloat(thresholdInput.value);

    if (!edgesFile) {
        showError('Please select an edges file');
        return;
    }

    hideError();
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Loading...';

    try {
        const formData = new FormData();
        formData.append('edges', edgesFile);
        if (nodesFile) {
            formData.append('nodes', nodesFile);
        }
        formData.append('threshold', threshold);

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load graph');
        }

        renderGraph(data.elements);
        buildFilters(data.filters || {});
        updateStats(data.stats);
        layoutSelect.disabled = false;
        detailPanel.style.display = 'block';

    } catch (error) {
        showError(error.message);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Load Graph';
    }
}

// Default visual constants
const DEFAULT_NODE_COLOR = '#58a6ff';
const DEFAULT_EDGE_COLOR = '#58a6ff';
const MIN_NODE_SIZE = 30;
const MAX_NODE_SIZE = 80;
const MIN_EDGE_WIDTH = 1.5;
const MAX_EDGE_WIDTH = 10;

function renderGraph(elements) {
    const container = document.getElementById('cy');
    container.innerHTML = '';

    const edges = elements.filter(el => el.data.source && el.data.target);
    const nodes = elements.filter(el => !el.data.source);

    // Compute weight range for edge width mapping
    const weights = edges.map(e => e.data.weight || 0);
    const minWeight = Math.min(...weights);
    const maxWeight = Math.max(...weights);

    const mapWidth = (w) => {
        if (maxWeight === minWeight) return (MIN_EDGE_WIDTH + MAX_EDGE_WIDTH) / 2;
        const t = (w - minWeight) / (maxWeight - minWeight);
        return MIN_EDGE_WIDTH + t * (MAX_EDGE_WIDTH - MIN_EDGE_WIDTH);
    };

    // Compute size range for node size mapping
    const sizes = nodes.map(n => n.data.size).filter(s => s != null);
    const minSize = sizes.length ? Math.min(...sizes) : 0;
    const maxSize = sizes.length ? Math.max(...sizes) : 0;
    const hasSizes = sizes.length > 0 && maxSize > minSize;

    const mapNodeSize = (s) => {
        if (!hasSizes || s == null) return (MIN_NODE_SIZE + MAX_NODE_SIZE) / 2;
        const t = (s - minSize) / (maxSize - minSize);
        return MIN_NODE_SIZE + t * (MAX_NODE_SIZE - MIN_NODE_SIZE);
    };

    cy = cytoscape({
        container: container,
        elements: elements,
        style: [
            {
                selector: 'node',
                style: {
                    'background-color': (ele) => ele.data('color') || DEFAULT_NODE_COLOR,
                    'label': '',
                    'color': '#c9d1d9',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '11px',
                    'font-weight': '600',
                    'text-outline-color': '#0d1117',
                    'text-outline-width': 3,
                    'width': (ele) => mapNodeSize(ele.data('size')),
                    'height': (ele) => mapNodeSize(ele.data('size')),
                    'border-width': 2,
                    'border-color': (ele) => ele.data('color') || '#1f6feb',
                    'border-opacity': 0.8,
                    'text-wrap': 'wrap',
                    'text-max-width': '120px',
                }
            },
            {
                selector: 'node.show-label',
                style: {
                    'label': 'data(label)',
                }
            },
            {
                selector: 'node.hover',
                style: {
                    'label': 'data(label)',
                    'border-width': 4,
                    'border-opacity': 1,
                    'z-index': 999,
                }
            },
            {
                selector: 'node:selected',
                style: {
                    'border-color': '#ffffff',
                    'border-width': 5,
                    'border-opacity': 1
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': (ele) => mapWidth(ele.data('weight') || 0),
                    'line-color': (ele) => ele.data('color') || DEFAULT_EDGE_COLOR,
                    'target-arrow-color': (ele) => ele.data('color') || DEFAULT_EDGE_COLOR,
                    'target-arrow-shape': (ele) => ele.data('directed') ? 'triangle' : 'none',
                    'curve-style': 'bezier',
                    'arrow-scale': (ele) => 1 + mapWidth(ele.data('weight') || 0) / MAX_EDGE_WIDTH * 0.8,
                    'label': 'data(label)',
                    'font-size': '10px',
                    'text-rotation': 'autorotate',
                    'text-margin-y': -10,
                    'color': '#8b949e',
                    'text-outline-color': '#0d1117',
                    'text-outline-width': 2,
                    'opacity': 0.7,
                    'line-style': 'solid'
                }
            },
            {
                selector: 'edge.hover',
                style: {
                    'width': (ele) => mapWidth(ele.data('weight') || 0) * 1.5,
                    'opacity': 1,
                    'z-index': 999
                }
            },
            {
                selector: 'edge.highlighted',
                style: {
                    'opacity': 1,
                    'z-index': 998
                }
            },
            {
                selector: 'edge:selected',
                style: {
                    'line-color': '#56d364',
                    'target-arrow-color': '#56d364',
                    'width': (ele) => mapWidth(ele.data('weight') || 0) * 1.8,
                    'opacity': 1,
                    'z-index': 999
                }
            },
            {
                selector: 'node.dimmed',
                style: { 'opacity': 0.3 }
            },
            {
                selector: 'edge.dimmed',
                style: { 'opacity': 0.2 }
            }
        ],
        layout: {
            name: 'dagre',
            rankDir: 'LR',
            nodeSep: 100,
            rankSep: 150
        },
        minZoom: 0.1,
        maxZoom: 3
    });

    let pinnedNode = null;

    // Click: toggle persistent label + pin detail panel
    cy.on('tap', 'node', function(evt) {
        const node = evt.target;
        node.toggleClass('show-label');
        if (node.hasClass('show-label')) {
            pinnedNode = node;
            showDetailPanel(node);
        } else {
            pinnedNode = null;
            hideDetailPanel();
        }
    });
    // Click on background: unpin
    cy.on('tap', function(evt) {
        if (evt.target === cy) {
            if (pinnedNode) {
                pinnedNode.removeClass('show-label');
                pinnedNode = null;
                hideDetailPanel();
            }
        }
    });

    // Node hover: highlight neighbourhood + show detail panel
    cy.on('mouseover', 'node', function(evt) {
        const node = evt.target;
        const connectedEdges = node.connectedEdges();
        const connectedNodes = connectedEdges.connectedNodes();
        cy.elements().addClass('dimmed');
        node.removeClass('dimmed').addClass('hover');
        connectedEdges.removeClass('dimmed').addClass('highlighted');
        connectedNodes.removeClass('dimmed');
        showDetailPanel(node);
    });
    cy.on('mouseout', 'node', function() {
        cy.elements().removeClass('dimmed hover highlighted');
        // If a node is pinned, show its details; otherwise clear
        if (pinnedNode) {
            showDetailPanel(pinnedNode);
        } else {
            hideDetailPanel();
        }
    });

    // Edge hover
    cy.on('mouseover', 'edge', function(evt) {
        evt.target.addClass('hover');
    });
    cy.on('mouseout', 'edge', function(evt) {
        evt.target.removeClass('hover');
    });
}

// --- Filters ---

const filtersDiv = document.getElementById('filters');

function buildFilters(filters) {
    filtersDiv.innerHTML = '';
    const keys = Object.keys(filters);
    if (keys.length === 0) {
        filtersDiv.style.display = 'none';
        return;
    }
    filtersDiv.style.display = 'flex';

    for (const propKey of keys) {
        const { name, values } = filters[propKey];

        const group = document.createElement('div');
        group.className = 'filter-group';

        const label = document.createElement('label');
        label.textContent = name;
        group.appendChild(label);

        const select = document.createElement('select');
        select.multiple = true;
        select.dataset.propKey = propKey;
        select.size = Math.min(values.length + 1, 6);

        // "All" option at top
        const allOpt = document.createElement('option');
        allOpt.value = '__all__';
        allOpt.textContent = `All (${values.length})`;
        allOpt.selected = true;
        select.appendChild(allOpt);

        for (const v of values) {
            const opt = document.createElement('option');
            opt.value = v;
            opt.textContent = v;
            select.appendChild(opt);
        }

        select.addEventListener('change', () => {
            const selected = Array.from(select.selectedOptions).map(o => o.value);
            // If "All" is among the selection, or nothing specific selected, treat as all
            if (selected.includes('__all__')) {
                // Deselect individual values, keep only All
                for (const opt of select.options) {
                    opt.selected = opt.value === '__all__';
                }
            } else if (selected.length === 0) {
                // Nothing selected — revert to All
                select.options[0].selected = true;
            }
            applyFilters();
        });

        group.appendChild(select);
        filtersDiv.appendChild(group);
    }
}

function applyFilters() {
    if (!cy) return;

    // Collect active filter selections
    const activeFilters = {};
    for (const select of filtersDiv.querySelectorAll('select')) {
        const propKey = select.dataset.propKey;
        const selected = Array.from(select.selectedOptions).map(o => o.value);
        if (!selected.includes('__all__') && selected.length > 0) {
            activeFilters[propKey] = new Set(selected);
        }
    }

    const filterKeys = Object.keys(activeFilters);
    if (filterKeys.length === 0) {
        // No filters active — show everything
        cy.elements().removeClass('filtered');
        cy.elements().style('display', 'element');
        return;
    }

    // Hide/show nodes based on filters.
    // Prop values are space-separated (multi-valued). A node matches a filter
    // if ANY of its values are in the selected set.
    cy.nodes().forEach(node => {
        let match = true;
        for (const propKey of filterKeys) {
            const raw = node.data(propKey);
            if (raw == null) { match = false; break; }
            const nodeVals = String(raw).split(/\s+/);
            if (!nodeVals.some(v => activeFilters[propKey].has(v))) {
                match = false;
                break;
            }
        }
        node.style('display', match ? 'element' : 'none');
    });

    // Hide edges where either endpoint is hidden
    cy.edges().forEach(edge => {
        const srcVisible = edge.source().style('display') !== 'none';
        const tgtVisible = edge.target().style('display') !== 'none';
        edge.style('display', (srcVisible && tgtVisible) ? 'element' : 'none');
    });
}

// --- Detail Panel ---

function showDetailPanel(node) {
    const data = node.data();
    detailName.textContent = data.label || data.id;
    detailProps.innerHTML = '';

    // Collect all prop_* keys
    const propKeys = Object.keys(data).filter(k => k.startsWith('prop_'));
    for (const key of propKeys) {
        const displayName = key.replace(/^prop_/, '');
        const value = data[key];
        if (value == null || value === '') continue;

        const row = document.createElement('div');
        row.className = 'detail-prop';

        const keySpan = document.createElement('span');
        keySpan.className = 'detail-prop-key';
        keySpan.textContent = displayName + ':';

        const valSpan = document.createElement('span');
        valSpan.className = 'detail-prop-value';
        valSpan.textContent = String(value).replace(/\s+/g, ', ');

        row.appendChild(keySpan);
        row.appendChild(valSpan);
        detailProps.appendChild(row);
    }

    detailEmpty.style.display = 'none';
    detailContent.style.display = 'block';
}

function hideDetailPanel() {
    detailEmpty.style.display = 'block';
    detailContent.style.display = 'none';
}

function applyLayout() {
    if (!cy) return;

    const layoutName = layoutSelect.value;
    let layoutOptions = { name: layoutName };

    if (layoutName === 'dagre') {
        layoutOptions = {
            name: 'dagre',
            rankDir: 'LR',
            nodeSep: 100,
            rankSep: 150,
            animate: true,
            animationDuration: 500
        };
    } else if (layoutName === 'cose') {
        layoutOptions = {
            name: 'cose',
            animate: true,
            animationDuration: 500,
            nodeRepulsion: 8000,
            idealEdgeLength: 100
        };
    } else if (layoutName === 'breadthfirst') {
        layoutOptions = {
            name: 'breadthfirst',
            directed: true,
            spacingFactor: 1.5,
            animate: true,
            animationDuration: 500
        };
    } else {
        layoutOptions.animate = true;
        layoutOptions.animationDuration = 500;
    }

    cy.layout(layoutOptions).run();
}
