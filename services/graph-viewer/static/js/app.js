let cy = null;
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const thresholdInput = document.getElementById('threshold');
const layoutSelect = document.getElementById('layoutSelect');
const errorDiv = document.getElementById('error');
const statsDiv = document.getElementById('stats');
const legendDiv = document.getElementById('legend');

fileInput.addEventListener('change', () => {
    uploadBtn.disabled = !fileInput.files.length;
    hideError();
});

uploadBtn.addEventListener('click', loadGraph);
layoutSelect.addEventListener('change', applyLayout);

thresholdInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && fileInput.files.length) {
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
    const file = fileInput.files[0];
    const threshold = parseFloat(thresholdInput.value);

    if (!file) {
        showError('Please select a file');
        return;
    }

    hideError();
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Loading...';

    try {
        const formData = new FormData();
        formData.append('file', file);
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
        updateStats(data.stats);
        layoutSelect.disabled = false;
        legendDiv.style.display = 'block';

    } catch (error) {
        showError(error.message);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Load Graph';
    }
}

function renderGraph(elements) {
    const container = document.getElementById('cy');
    container.innerHTML = '';

    // Calculate likelihood range for width mapping
    const edges = elements.filter(el => el.data.source && el.data.target);
    const likelihoods = edges.map(e => e.data.likelihood);
    const minLikelihood = Math.min(...likelihoods);
    const maxLikelihood = Math.max(...likelihoods);

    // Width mapping constants
    const MIN_WIDTH = 1.5;
    const MAX_WIDTH = 10;

    // Function to map likelihood to width
    const mapWidth = (likelihood) => {
        if (maxLikelihood === minLikelihood) {
            return (MIN_WIDTH + MAX_WIDTH) / 2;
        }
        const normalized = (likelihood - minLikelihood) / (maxLikelihood - minLikelihood);
        return MIN_WIDTH + normalized * (MAX_WIDTH - MIN_WIDTH);
    };

    cy = cytoscape({
        container: container,
        elements: elements,
        style: [
            {
                selector: 'node',
                style: {
                    'background-color': '#58a6ff',
                    'label': 'data(label)',
                    'color': '#c9d1d9',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '12px',
                    'font-weight': '600',
                    'text-outline-color': '#0d1117',
                    'text-outline-width': 3,
                    'width': 60,
                    'height': 60,
                    'border-width': 3,
                    'border-color': '#1f6feb',
                    'border-opacity': 0.8
                }
            },
            {
                selector: 'node.hover',
                style: {
                    'background-color': '#79c0ff',
                    'border-color': '#79c0ff',
                    'border-width': 4,
                    'border-opacity': 1
                }
            },
            {
                selector: 'node:selected',
                style: {
                    'background-color': '#56d364',
                    'border-color': '#3fb950',
                    'border-width': 5,
                    'border-opacity': 1
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': (ele) => mapWidth(ele.data('likelihood')),
                    'line-color': '#58a6ff',
                    'target-arrow-color': '#58a6ff',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier',
                    'arrow-scale': (ele) => 1 + mapWidth(ele.data('likelihood')) / MAX_WIDTH * 0.8,
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
                    'line-color': '#79c0ff',
                    'target-arrow-color': '#79c0ff',
                    'width': (ele) => mapWidth(ele.data('likelihood')) * 1.5,
                    'opacity': 1,
                    'z-index': 999
                }
            },
            {
                selector: 'edge.highlighted',
                style: {
                    'line-color': '#79c0ff',
                    'target-arrow-color': '#79c0ff',
                    'opacity': 1,
                    'z-index': 998
                }
            },
            {
                selector: 'edge:selected',
                style: {
                    'line-color': '#56d364',
                    'target-arrow-color': '#56d364',
                    'width': (ele) => mapWidth(ele.data('likelihood')) * 1.8,
                    'opacity': 1,
                    'z-index': 999
                }
            },
            {
                selector: 'node.dimmed',
                style: {
                    'opacity': 0.3
                }
            },
            {
                selector: 'edge.dimmed',
                style: {
                    'opacity': 0.2
                }
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

    // Add click handler for nodes and edges
    cy.on('tap', 'node', function(evt) {
        const node = evt.target;
        console.log('Node clicked:', node.data());
    });

    cy.on('tap', 'edge', function(evt) {
        const edge = evt.target;
        console.log('Edge clicked:', edge.data());
    });

    // Node hover effects
    cy.on('mouseover', 'node', function(evt) {
        const node = evt.target;
        const connectedEdges = node.connectedEdges();
        const connectedNodes = connectedEdges.connectedNodes();

        // Dim all elements
        cy.elements().addClass('dimmed');

        // Highlight hovered node and connected elements
        node.removeClass('dimmed').addClass('hover');
        connectedEdges.removeClass('dimmed').addClass('highlighted');
        connectedNodes.removeClass('dimmed');
    });

    cy.on('mouseout', 'node', function(evt) {
        cy.elements().removeClass('dimmed hover highlighted');
    });

    // Edge hover effects
    cy.on('mouseover', 'edge', function(evt) {
        const edge = evt.target;
        edge.addClass('hover');
    });

    cy.on('mouseout', 'edge', function(evt) {
        const edge = evt.target;
        edge.removeClass('hover');
    });
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

    const layout = cy.layout(layoutOptions);
    layout.run();
}
