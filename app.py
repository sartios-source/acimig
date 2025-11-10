"""
ACI Analysis Tool - Flask Application
Supports both Onboard and Offboard workflows with multi-fabric analysis.
"""
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename

# Import analysis modules
from analysis import parsers, engine, fabric_manager, planning, reporting

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload

# Directory structure
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
FABRICS_DIR = BASE_DIR / 'fabrics'
CMDB_DIR = BASE_DIR / 'cmdb'
OUTPUT_DIR = BASE_DIR / 'output'

# Ensure directories exist
for directory in [DATA_DIR, FABRICS_DIR, CMDB_DIR, OUTPUT_DIR]:
    directory.mkdir(exist_ok=True)

# Initialize fabric manager
fm = fabric_manager.FabricManager(FABRICS_DIR)


@app.route('/')
def index():
    """Landing page with mode selection and recent fabrics."""
    mode = session.get('mode', 'offboard')
    fabrics = fm.list_fabrics()
    return render_template('index.html', mode=mode, fabrics=fabrics)


@app.route('/set_mode/<mode>')
def set_mode(mode):
    """Toggle between onboard and offboard modes."""
    if mode in ['onboard', 'offboard']:
        session['mode'] = mode
    return redirect(url_for('index'))


@app.route('/analyze')
def analyze():
    """Analysis page - upload and validate datasets."""
    mode = session.get('mode', 'offboard')
    current_fabric = session.get('current_fabric')

    datasets = []
    validation_results = []

    if current_fabric:
        fabric_data = fm.get_fabric_data(current_fabric)
        datasets = fabric_data.get('datasets', [])

        # Run validation
        analyzer = engine.ACIAnalyzer(fabric_data)
        validation_results = analyzer.validate()

    return render_template('analyze.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         datasets=datasets,
                         validation_results=validation_results)


@app.route('/upload', methods=['POST'])
def upload():
    """Handle file uploads - ACI JSON/XML, legacy configs, CMDB CSV."""
    current_fabric = session.get('current_fabric')
    if not current_fabric:
        return jsonify({'error': 'No fabric selected'}), 400

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[-1].lower()

        # Determine file type
        if file_ext in ['json', 'xml']:
            file_type = 'aci'
        elif file_ext == 'csv':
            file_type = 'cmdb'
        elif file_ext in ['txt', 'cfg', 'conf']:
            file_type = 'legacy'
        else:
            return jsonify({'error': f'Unsupported file type: {file_ext}'}), 400

        # Save file
        fabric_dir = FABRICS_DIR / current_fabric
        fabric_dir.mkdir(exist_ok=True)

        file_path = fabric_dir / filename
        file.save(str(file_path))

        # Parse and validate
        content = file_path.read_text(encoding='utf-8')

        if file_type == 'aci':
            parsed_data = parsers.parse_aci(content, file_ext)
            fm.add_dataset(current_fabric, {
                'filename': filename,
                'type': 'aci',
                'format': file_ext,
                'uploaded': datetime.now().isoformat(),
                'objects': len(parsed_data.get('objects', [])),
                'path': str(file_path)
            })
        elif file_type == 'cmdb':
            parsed_data = parsers.parse_cmdb_csv(content)
            fm.add_dataset(current_fabric, {
                'filename': filename,
                'type': 'cmdb',
                'uploaded': datetime.now().isoformat(),
                'records': len(parsed_data),
                'path': str(file_path)
            })
        elif file_type == 'legacy':
            parsed_data = parsers.parse_legacy_config(content)
            fm.add_dataset(current_fabric, {
                'filename': filename,
                'type': 'legacy',
                'uploaded': datetime.now().isoformat(),
                'platform': parsed_data.get('platform', 'unknown'),
                'path': str(file_path)
            })

        return jsonify({
            'success': True,
            'filename': filename,
            'type': file_type,
            'message': f'Successfully uploaded and parsed {filename}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/visualize')
def visualize():
    """Visualization page - topology, density, rack layouts."""
    mode = session.get('mode', 'offboard')
    current_fabric = session.get('current_fabric')

    viz_data = {}
    if current_fabric:
        fabric_data = fm.get_fabric_data(current_fabric)
        analyzer = engine.ACIAnalyzer(fabric_data)
        viz_data = analyzer.get_visualization_data()

    return render_template('visualize.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         viz_data=viz_data)


@app.route('/plan')
def plan():
    """Planning page - recommendations and what-if scenarios."""
    mode = session.get('mode', 'offboard')
    current_fabric = session.get('current_fabric')

    plan_data = {}
    if current_fabric:
        fabric_data = fm.get_fabric_data(current_fabric)
        planner = planning.ACIPlanner(fabric_data, mode)
        plan_data = planner.generate_plan()

    # Get all fabrics for what-if scenarios
    all_fabrics = fm.list_fabrics()

    return render_template('plan.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         plan_data=plan_data,
                         all_fabrics=all_fabrics)


@app.route('/report')
def report():
    """Report generation page - HTML, Markdown, CSV exports."""
    mode = session.get('mode', 'offboard')
    current_fabric = session.get('current_fabric')

    report_data = {}
    if current_fabric:
        fabric_data = fm.get_fabric_data(current_fabric)
        report_data = reporting.generate_report(fabric_data, mode)

    return render_template('report.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         report_data=report_data)


@app.route('/download/report/<format>')
def download_report(format):
    """Download report in specified format (markdown, csv, html)."""
    current_fabric = session.get('current_fabric')
    if not current_fabric:
        return "No fabric selected", 400

    fabric_data = fm.get_fabric_data(current_fabric)
    mode = session.get('mode', 'offboard')

    if format == 'markdown':
        content = reporting.generate_markdown_report(fabric_data, mode)
        filename = f'{current_fabric}_report.md'
        mimetype = 'text/markdown'
    elif format == 'csv':
        content = reporting.generate_csv_report(fabric_data, mode)
        filename = f'{current_fabric}_report.csv'
        mimetype = 'text/csv'
    elif format == 'html':
        content = reporting.generate_html_report(fabric_data, mode)
        filename = f'{current_fabric}_report.html'
        mimetype = 'text/html'
    else:
        return "Invalid format", 400

    # Save to output directory
    output_path = OUTPUT_DIR / filename
    output_path.write_text(content, encoding='utf-8')

    return send_file(output_path, as_attachment=True, download_name=filename, mimetype=mimetype)


@app.route('/download/offline_collector.py')
def download_offline_collector():
    """Serve the offline collector script."""
    collector_path = BASE_DIR / 'offline_collector.py'
    return send_file(collector_path, as_attachment=True, download_name='offline_collector.py')


@app.route('/help')
def help_page():
    """In-app documentation and ACI object reference."""
    mode = session.get('mode', 'offboard')
    return render_template('help.html', mode=mode)


# Fabric Management API
@app.route('/fabrics', methods=['GET'])
def list_fabrics():
    """List all fabrics."""
    fabrics = fm.list_fabrics()
    return jsonify(fabrics)


@app.route('/fabrics', methods=['POST'])
def create_fabric():
    """Create a new fabric."""
    data = request.get_json()
    fabric_name = data.get('name')

    if not fabric_name:
        return jsonify({'error': 'Fabric name required'}), 400

    try:
        fm.create_fabric(fabric_name)
        session['current_fabric'] = fabric_name
        return jsonify({'success': True, 'fabric': fabric_name})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/fabrics/<fabric_name>', methods=['DELETE'])
def delete_fabric(fabric_name):
    """Delete a fabric."""
    try:
        fm.delete_fabric(fabric_name)
        if session.get('current_fabric') == fabric_name:
            session.pop('current_fabric', None)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@app.route('/fabrics/<fabric_name>/select', methods=['POST'])
def select_fabric(fabric_name):
    """Select a fabric as current."""
    if fabric_name not in [f['name'] for f in fm.list_fabrics()]:
        return jsonify({'error': 'Fabric not found'}), 404

    session['current_fabric'] = fabric_name
    return jsonify({'success': True, 'fabric': fabric_name})


@app.route('/api/analysis/<analysis_type>')
def get_analysis(analysis_type):
    """Get specific analysis results via API."""
    current_fabric = session.get('current_fabric')
    if not current_fabric:
        return jsonify({'error': 'No fabric selected'}), 400

    fabric_data = fm.get_fabric_data(current_fabric)
    analyzer = engine.ACIAnalyzer(fabric_data)

    analysis_methods = {
        'port_utilization': analyzer.analyze_port_utilization,
        'leaf_fex_mapping': analyzer.analyze_leaf_fex_mapping,
        'rack_grouping': analyzer.analyze_rack_grouping,
        'bd_epg_mapping': analyzer.analyze_bd_epg_mapping,
        'vlan_distribution': analyzer.analyze_vlan_distribution,
        'epg_complexity': analyzer.analyze_epg_complexity,
        'vpc_symmetry': analyzer.analyze_vpc_symmetry,
        'pdom_analysis': analyzer.analyze_pdom,
        'migration_flags': analyzer.analyze_migration_flags,
        'contract_scope': analyzer.analyze_contract_scope,
        'vlan_spread': analyzer.analyze_vlan_spread,
        'cmdb_correlation': analyzer.analyze_cmdb_correlation,
    }

    if analysis_type not in analysis_methods:
        return jsonify({'error': 'Unknown analysis type'}), 400

    try:
        result = analysis_methods[analysis_type]()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 70)
    print("ACI Analysis Tool - Starting")
    print("=" * 70)
    print(f"Data directory: {DATA_DIR}")
    print(f"Fabrics directory: {FABRICS_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 70)
    print("Access the application at: http://127.0.0.1:5000")
    print("=" * 70)

    app.run(debug=True, host='127.0.0.1', port=5000)
