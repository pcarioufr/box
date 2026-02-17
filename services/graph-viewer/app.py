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
    Accept CSV data with columns: source, target, weight
    Return filtered graph data in Cytoscape.js format
    """
    try:
        threshold = float(request.form.get('threshold', 10.0))

        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400

        # Read CSV data
        content = file.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(content))

        # Validate columns
        if len(df.columns) < 3:
            return jsonify({'error': 'CSV must have at least 3 columns: source, target, likelihood'}), 400

        # Use first 3 columns regardless of names
        df.columns = ['source', 'target', 'likelihood'] + list(df.columns[3:])

        # Filter by threshold
        df_filtered = df[df['likelihood'] >= threshold]

        # Build Cytoscape.js data structure
        nodes = set()
        edges = []

        for _, row in df_filtered.iterrows():
            source = str(row['source'])
            target = str(row['target'])
            likelihood = float(row['likelihood'])

            nodes.add(source)
            nodes.add(target)

            edges.append({
                'data': {
                    'id': f"{source}-{target}",
                    'source': source,
                    'target': target,
                    'likelihood': likelihood,
                    'label': f"{likelihood:.1f}%"
                }
            })

        # Convert nodes to Cytoscape format
        node_elements = [{'data': {'id': node, 'label': node}} for node in sorted(nodes)]

        return jsonify({
            'elements': node_elements + edges,
            'stats': {
                'total_edges': len(df),
                'filtered_edges': len(edges),
                'nodes': len(nodes),
                'threshold': threshold
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
