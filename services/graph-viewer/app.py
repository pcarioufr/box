from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import pandas as pd
import io

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_data():
    """
    Accept graph data in two formats:

    1. Two-file format (nodes + edges):
       - nodes CSV: id, label, size, color
       - edges CSV: source, target, weight, label, color, directed

    2. Legacy single-file format (edges only):
       - CSV: source, target, weight[, label]
       - Nodes are auto-created from edge endpoints.

    All node/edge visual properties are optional — sensible defaults apply.
    """
    try:
        threshold = float(request.form.get('threshold', 0))

        # --- Parse edges file (required) ---
        edges_file = request.files.get('edges') or request.files.get('file')
        if not edges_file or edges_file.filename == '':
            return jsonify({'error': 'No edges file provided'}), 400

        edges_df = pd.read_csv(io.StringIO(edges_file.read().decode('utf-8')))

        # --- Parse optional nodes file ---
        nodes_file = request.files.get('nodes')
        nodes_df = None
        if nodes_file and nodes_file.filename != '':
            nodes_df = pd.read_csv(io.StringIO(nodes_file.read().decode('utf-8')))

        # --- Detect format ---
        edge_cols = [c.lower().strip() for c in edges_df.columns]
        edges_df.columns = edge_cols

        if 'source' in edge_cols and 'target' in edge_cols:
            # Named-column format
            pass
        elif len(edge_cols) >= 3:
            # Legacy positional format: col0=source, col1=target, col2=weight, col3=label
            renames = {}
            renames[edge_cols[0]] = 'source'
            renames[edge_cols[1]] = 'target'
            renames[edge_cols[2]] = 'weight'
            if len(edge_cols) >= 4:
                renames[edge_cols[3]] = 'label'
            edges_df = edges_df.rename(columns=renames)
        else:
            return jsonify({'error': 'Edges CSV must have at least: source, target, weight'}), 400

        # Ensure weight column exists
        if 'weight' not in edges_df.columns:
            edges_df['weight'] = 1.0

        # Filter by threshold on weight
        edges_df = edges_df[edges_df['weight'] >= threshold]
        total_before = len(edges_df) + len(edges_df)  # approx — we lost the pre-filter count
        # Re-count: we need total from before filtering
        # Re-read for total count
        total_edges = len(edges_df)  # will be overridden below

        # --- Build node lookup from nodes CSV ---
        node_props = {}  # id -> {label, size, color, prop_*...}
        prop_columns = []  # list of prop_* column names (without prefix)
        if nodes_df is not None:
            nodes_df.columns = [c.lower().strip() for c in nodes_df.columns]
            prop_columns = [c for c in nodes_df.columns if c.startswith('prop_')]
            for _, row in nodes_df.iterrows():
                nid = str(row.get('id', ''))
                props = {
                    'label': str(row['label']) if 'label' in row and pd.notna(row.get('label')) else nid,
                    'size': float(row['size']) if 'size' in row and pd.notna(row.get('size')) else None,
                    'color': str(row['color']) if 'color' in row and pd.notna(row.get('color')) else None,
                }
                for pc in prop_columns:
                    val = row.get(pc)
                    props[pc] = str(val) if pd.notna(val) else None
                node_props[nid] = props

        # --- Build Cytoscape elements ---
        nodes = set()
        edge_elements = []

        for _, row in edges_df.iterrows():
            source = str(row['source'])
            target = str(row['target'])
            weight = float(row['weight']) if pd.notna(row.get('weight')) else 1.0
            label = str(row['label']) if 'label' in row and pd.notna(row.get('label')) else f"{weight:.1f}"
            color = str(row['color']) if 'color' in row and pd.notna(row.get('color')) else None
            directed = True  # default
            if 'directed' in row:
                val = row['directed']
                if isinstance(val, bool):
                    directed = val
                elif isinstance(val, str):
                    directed = val.lower() not in ('false', '0', 'no')
                elif pd.notna(val):
                    directed = bool(val)

            nodes.add(source)
            nodes.add(target)

            edge_data = {
                'id': f"{source}->{target}",
                'source': source,
                'target': target,
                'weight': weight,
                'label': label,
                'directed': directed,
            }
            if color:
                edge_data['color'] = color

            edge_elements.append({'data': edge_data})

        # Build node elements — merge auto-discovered nodes with explicit node props
        def _build_node_data(nid, props):
            node_data = {
                'id': nid,
                'label': props.get('label') or nid,
            }
            if props.get('size') is not None:
                node_data['size'] = props['size']
            if props.get('color') is not None:
                node_data['color'] = props['color']
            for pc in prop_columns:
                if props.get(pc) is not None:
                    node_data[pc] = props[pc]
            return node_data

        node_elements = []
        for nid in sorted(nodes):
            props = node_props.get(nid, {})
            node_elements.append({'data': _build_node_data(nid, props)})

        # Also include nodes from nodes CSV that aren't in any edge (isolated nodes)
        for nid, props in node_props.items():
            if nid not in nodes:
                node_elements.append({'data': _build_node_data(nid, props)})

        # Collect distinct values for each prop_* column (for filter UI).
        # Values are space-separated to support multi-valued props.
        filters = {}
        for pc in prop_columns:
            name = pc[len('prop_'):]  # strip prefix for display
            all_vals = set()
            for p in node_props.values():
                raw = p.get(pc)
                if raw is not None:
                    for v in str(raw).split():
                        all_vals.add(v)
            filters[pc] = {'name': name, 'values': sorted(all_vals)}

        return jsonify({
            'elements': node_elements + edge_elements,
            'filters': filters,
            'stats': {
                'total_edges': len(edges_df),
                'filtered_edges': len(edge_elements),
                'nodes': len(node_elements),
                'threshold': threshold,
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
