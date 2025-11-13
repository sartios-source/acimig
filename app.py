"""
acimig v1.0 - Professional ACI to EVPN/VXLAN Migration Analysis Tool
Supports both Onboard and EVPN workflows with multi-fabric analysis.
"""
import os
import json
import shutil
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load version from VERSION file
VERSION_FILE = Path(__file__).parent / 'VERSION'
try:
    APP_VERSION = VERSION_FILE.read_text().strip()
except:
    APP_VERSION = '1.0.0'

# Import configuration
from config import get_config

# Import analysis modules
from analysis import parsers, engine, fabric_manager, planning, reporting, evpn_migration

# Initialize Flask app
app = Flask(__name__)

# Load configuration
config_name = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(get_config(config_name))

# Initialize configuration
get_config(config_name).init_app(app)

# Set secret key
app.secret_key = app.config['SECRET_KEY']

# Setup logging
def setup_logging(app):
    """Configure application logging."""
    if not app.debug:
        # File handler for production
        if not app.config['LOG_FILE'].parent.exists():
            app.config['LOG_FILE'].parent.mkdir(parents=True)

        file_handler = RotatingFileHandler(
            app.config['LOG_FILE'],
            maxBytes=app.config['LOG_MAX_BYTES'],
            backupCount=app.config['LOG_BACKUP_COUNT']
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info(f'acimig v{APP_VERSION} startup')

setup_logging(app)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[app.config['API_RATE_LIMIT']],
    storage_uri="memory://"
)

# Directory structure
BASE_DIR = app.config['BASE_DIR']
DATA_DIR = app.config['DATA_DIR']
FABRICS_DIR = app.config['FABRICS_DIR']
CMDB_DIR = app.config['CMDB_DIR']
OUTPUT_DIR = app.config['OUTPUT_DIR']

# Initialize fabric manager
fm = fabric_manager.FabricManager(FABRICS_DIR)


# Template context processor to inject fabrics into all templates
@app.context_processor
def inject_fabrics():
    """Make fabrics list available to all templates for sidebar."""
    return {'fabrics': fm.list_fabrics()}


# Security helper functions
def validate_fabric_name(name: str) -> str:
    """Sanitize fabric name to prevent path traversal and injection attacks."""
    import re
    # Only allow alphanumeric, underscore, and hyphen
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    if not sanitized or len(sanitized) > 64:
        raise ValueError("Invalid fabric name. Use only alphanumeric characters, underscore, and hyphen (max 64 chars)")
    return sanitized


def validate_file_path(file_path: Path, allowed_parent: Path) -> bool:
    """Ensure file path doesn't escape the allowed parent directory."""
    try:
        file_path_resolved = file_path.resolve()
        allowed_parent_resolved = allowed_parent.resolve()
        return str(file_path_resolved).startswith(str(allowed_parent_resolved))
    except Exception:
        return False


def validate_file_upload(file, allowed_extensions: set) -> tuple:
    """
    Validate uploaded file for security.
    Returns: (is_valid, error_message)
    """
    if not file or file.filename == '':
        return False, 'No file selected'

    # Check filename
    filename = secure_filename(file.filename)
    if not filename:
        return False, 'Invalid filename'

    # Check extension
    file_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if file_ext not in allowed_extensions:
        return False, f'File type .{file_ext} not allowed. Allowed types: {", ".join(allowed_extensions)}'

    # Check content type
    allowed_content_types = app.config['ALLOWED_CONTENT_TYPES'].get(file_ext, [])
    if file.content_type and file.content_type not in allowed_content_types:
        app.logger.warning(
            f"Content type mismatch for {filename}: "
            f"expected {allowed_content_types}, got {file.content_type}"
        )

    return True, filename


def read_file_safely(file_path: Path) -> str:
    """Read file content with proper encoding handling."""
    encodings = ['utf-8', 'latin-1', 'cp1252']

    for encoding in encodings:
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")
        except PermissionError:
            raise PermissionError(f"Permission denied: {file_path}")

    raise ValueError(f"Unable to decode file {file_path}. Tried encodings: {encodings}")


# Error handlers
@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large errors."""
    max_size_mb = app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)
    return jsonify({
        'error': f'File too large. Maximum size is {max_size_mb:.0f}MB'
    }), 413


@app.errorhandler(429)
def ratelimit_handler(error):
    """Handle rate limit errors."""
    return jsonify({
        'error': 'Rate limit exceeded. Please try again later.'
    }), 429


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors."""
    app.logger.error(f'Internal error: {error}')
    return jsonify({
        'error': 'An internal error occurred. Please try again or contact support.'
    }), 500


# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': APP_VERSION,
        'app_name': 'acimig',
        'fabrics_dir_exists': FABRICS_DIR.exists(),
        'output_dir_exists': OUTPUT_DIR.exists()
    })


@app.route('/')
def index():
    """Landing page with mode selection and recent fabrics."""
    mode = session.get('mode', 'evpn')
    fabrics = fm.list_fabrics()
    return render_template('index.html', mode=mode, fabrics=fabrics)


@app.route('/set_mode/<mode>')
def set_mode(mode):
    """Toggle between onboard and evpn modes."""
    if mode in ['onboard', 'evpn']:
        session['mode'] = mode
    return redirect(url_for('index'))


@app.route('/upload_page')
def upload_page():
    """Upload page - file upload interface."""
    mode = session.get('mode', 'evpn')
    current_fabric = session.get('current_fabric')

    datasets = []
    if current_fabric:
        fabric_data = fm.get_fabric_data(current_fabric)
        datasets = fabric_data.get('datasets', [])

    return render_template('upload.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         datasets=datasets)


@app.route('/analyze')
def analyze():
    """Analysis page - unified data view with comprehensive filtering."""
    mode = session.get('mode', 'evpn')
    current_fabric = session.get('current_fabric')

    datasets = []
    unified_data = []
    tenants = []
    vrfs = []
    types = ['FEX', 'Leaf', 'EPG', 'BD', 'VRF', 'Contract', 'Subnet', 'Interface']
    type_counts = {}

    if current_fabric:
        fabric_data = fm.get_fabric_data(current_fabric)
        datasets = fabric_data.get('datasets', [])

        # Run comprehensive data completeness validation
        try:
            analyzer = engine.ACIAnalyzer(fabric_data)

            # Load data for display
            analyzer._load_data()

            # Build unified data list with all objects
            # Add FEX devices
            for fex in analyzer._fexes:
                unified_data.append({
                    'type': 'FEX',
                    'name': fex.get('name', ''),
                    'id': str(fex.get('id', '')),
                    'tenant': '',
                    'vrf': '',
                    'bd': '',
                    'encap': '',
                    'ip_subnet': '',
                    'model': fex.get('model', ''),
                    'serial': fex.get('serial', ''),
                    'status': fex.get('status', 'Active'),
                    'role': '',
                    'app_profile': '',
                    'scope': '',
                    'node': '',
                    'speed': ''
                })

            # Add Leaf switches
            for leaf in analyzer._leafs:
                unified_data.append({
                    'type': 'Leaf',
                    'name': leaf.get('name', ''),
                    'id': str(leaf.get('id', '')),
                    'tenant': '',
                    'vrf': '',
                    'bd': '',
                    'encap': '',
                    'ip_subnet': '',
                    'model': leaf.get('model', ''),
                    'serial': leaf.get('serial', ''),
                    'status': leaf.get('status', 'Active'),
                    'role': leaf.get('role', 'Leaf'),
                    'app_profile': '',
                    'scope': '',
                    'node': '',
                    'speed': ''
                })

            # Add EPGs
            for epg in analyzer._epgs:
                unified_data.append({
                    'type': 'EPG',
                    'name': epg.get('name', ''),
                    'id': '',
                    'tenant': epg.get('tenant', ''),
                    'vrf': '',
                    'bd': epg.get('bd', ''),
                    'encap': epg.get('encap', ''),
                    'ip_subnet': '',
                    'model': '',
                    'serial': '',
                    'status': '',
                    'role': '',
                    'app_profile': epg.get('app_profile', ''),
                    'scope': '',
                    'node': '',
                    'speed': ''
                })

            # Add Bridge Domains
            for bd in analyzer._bds:
                # Get subnets if available
                subnets_list = bd.get('subnets', [])
                subnet_str = ', '.join(subnets_list) if subnets_list else ''

                unified_data.append({
                    'type': 'BD',
                    'name': bd.get('name', ''),
                    'id': '',
                    'tenant': bd.get('tenant', ''),
                    'vrf': bd.get('vrf', ''),
                    'bd': '',
                    'encap': '',
                    'ip_subnet': subnet_str,
                    'model': '',
                    'serial': '',
                    'status': '',
                    'role': '',
                    'app_profile': '',
                    'scope': bd.get('l2_unknown', 'proxy'),
                    'node': '',
                    'speed': ''
                })

            # Add VRFs
            for vrf in analyzer._vrfs:
                unified_data.append({
                    'type': 'VRF',
                    'name': vrf.get('name', ''),
                    'id': '',
                    'tenant': vrf.get('tenant', ''),
                    'vrf': '',
                    'bd': '',
                    'encap': '',
                    'ip_subnet': '',
                    'model': '',
                    'serial': '',
                    'status': '',
                    'role': '',
                    'app_profile': '',
                    'scope': vrf.get('pce_policy', 'enforced'),
                    'node': '',
                    'speed': ''
                })

            # Add Contracts
            for contract in analyzer._contracts:
                unified_data.append({
                    'type': 'Contract',
                    'name': contract.get('name', ''),
                    'id': '',
                    'tenant': contract.get('tenant', ''),
                    'vrf': '',
                    'bd': '',
                    'encap': '',
                    'ip_subnet': '',
                    'model': '',
                    'serial': '',
                    'status': '',
                    'role': '',
                    'app_profile': '',
                    'scope': contract.get('scope', 'context'),
                    'node': '',
                    'speed': ''
                })

            # Add Subnets
            for subnet in analyzer._subnets:
                unified_data.append({
                    'type': 'Subnet',
                    'name': '',
                    'id': '',
                    'tenant': subnet.get('tenant', ''),
                    'vrf': '',
                    'bd': subnet.get('bd', ''),
                    'encap': '',
                    'ip_subnet': subnet.get('ip', ''),
                    'model': '',
                    'serial': '',
                    'status': '',
                    'role': '',
                    'app_profile': '',
                    'scope': subnet.get('scope', 'private'),
                    'node': '',
                    'speed': ''
                })

            # Add Interfaces
            for iface in analyzer._interfaces:
                unified_data.append({
                    'type': 'Interface',
                    'name': '',
                    'id': iface.get('id', ''),
                    'tenant': '',
                    'vrf': '',
                    'bd': '',
                    'encap': '',
                    'ip_subnet': '',
                    'model': '',
                    'serial': '',
                    'status': iface.get('oper_state', 'down'),
                    'role': iface.get('usage', ''),
                    'app_profile': '',
                    'scope': '',
                    'node': iface.get('node', ''),
                    'speed': iface.get('speed', '')
                })

            # Extract unique values for filters
            tenants = sorted(set(item['tenant'] for item in unified_data if item['tenant']))
            vrfs = sorted(set(item['vrf'] for item in unified_data if item['vrf']))

            # Count objects by type
            type_counts = {}
            for obj_type in types:
                type_counts[obj_type] = sum(1 for item in unified_data if item['type'] == obj_type)

        except Exception as e:
            app.logger.error(f"Error during analysis: {str(e)}", exc_info=True)
            unified_data = []

    return render_template('analyze.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         datasets=datasets,
                         unified_data=unified_data,
                         tenants=tenants,
                         vrfs=vrfs,
                         types=types,
                         type_counts=type_counts)


@app.route('/upload', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def upload():
    """Handle file uploads - ACI JSON/XML, legacy configs, CMDB CSV."""
    current_fabric = session.get('current_fabric')
    if not current_fabric:
        app.logger.warning("Upload attempted without fabric selection")
        return jsonify({'error': 'No fabric selected'}), 400

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    # Validate file upload
    is_valid, result = validate_file_upload(file, app.config['ALLOWED_EXTENSIONS'])
    if not is_valid:
        app.logger.warning(f"Invalid file upload: {result}")
        return jsonify({'error': result}), 400

    filename = result
    file_ext = filename.rsplit('.', 1)[-1].lower()

    try:
        # Validate fabric name
        try:
            current_fabric = validate_fabric_name(current_fabric)
        except ValueError as e:
            app.logger.error(f"Invalid fabric name: {current_fabric}")
            return jsonify({'error': str(e)}), 400

        # Determine file type
        if file_ext in ['json', 'xml']:
            file_type = 'aci'
        elif file_ext == 'csv':
            file_type = 'cmdb'
        elif file_ext in ['txt', 'cfg', 'conf']:
            file_type = 'legacy'
        else:
            return jsonify({'error': f'Unsupported file type: {file_ext}'}), 400

        # Save file with path traversal protection
        fabric_dir = FABRICS_DIR / current_fabric
        fabric_dir.mkdir(exist_ok=True, parents=True)

        file_path = (fabric_dir / filename).resolve()

        # Verify path doesn't escape fabric directory
        if not validate_file_path(file_path, fabric_dir):
            app.logger.error(f"Path traversal attempt detected: {file_path}")
            return jsonify({'error': 'Invalid file path'}), 400

        # Save file
        file.save(str(file_path))
        app.logger.info(f"File uploaded: {filename} to fabric {current_fabric}")

        # Parse and validate with proper error handling
        try:
            content = read_file_safely(file_path)
        except (FileNotFoundError, PermissionError, ValueError) as e:
            app.logger.error(f"Error reading file {filename}: {str(e)}")
            return jsonify({'error': str(e)}), 500

        # Parse based on file type
        try:
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
                app.logger.info(
                    f"Parsed ACI {file_ext}: {len(parsed_data.get('objects', []))} objects"
                )

            elif file_type == 'cmdb':
                parsed_data = parsers.parse_cmdb_csv(content)
                fm.add_dataset(current_fabric, {
                    'filename': filename,
                    'type': 'cmdb',
                    'uploaded': datetime.now().isoformat(),
                    'records': len(parsed_data),
                    'path': str(file_path)
                })
                app.logger.info(f"Parsed CMDB CSV: {len(parsed_data)} records")

            elif file_type == 'legacy':
                parsed_data = parsers.parse_legacy_config(content)
                fm.add_dataset(current_fabric, {
                    'filename': filename,
                    'type': 'legacy',
                    'uploaded': datetime.now().isoformat(),
                    'platform': parsed_data.get('platform', 'unknown'),
                    'path': str(file_path)
                })
                app.logger.info(f"Parsed legacy config: {parsed_data.get('platform')}")

            return jsonify({
                'success': True,
                'filename': filename,
                'type': file_type,
                'message': f'Successfully uploaded and parsed {filename}'
            })

        except ValueError as e:
            # Parsing error - provide user-friendly message
            app.logger.error(f"Parsing error for {filename}: {str(e)}")
            # Clean up invalid file
            if file_path.exists():
                file_path.unlink()
            return jsonify({'error': f'Parse error: {str(e)}'}), 400

    except Exception as e:
        app.logger.error(f"Unexpected error during upload: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred during upload'}), 500


@app.route('/visualize')
def visualize():
    """Visualization page - interactive dashboards with charts and graphs."""
    mode = session.get('mode', 'evpn')
    current_fabric = session.get('current_fabric')

    viz_data = {}
    if current_fabric:
        try:
            fabric_data = fm.get_fabric_data(current_fabric)
            analyzer = engine.ACIAnalyzer(fabric_data)

            # Get base visualization data
            viz_data = analyzer.get_visualization_data()

            # Enrich with analysis data for dashboards
            port_util = analyzer.analyze_port_utilization()
            vlan_dist = analyzer.analyze_vlan_distribution()
            epg_complex = analyzer.analyze_epg_complexity()
            migration_flags = analyzer.analyze_migration_flags()
            vpc_symmetry = analyzer.analyze_vpc_symmetry()
            leaf_fex = analyzer.analyze_leaf_fex_mapping()
            device_mapping = analyzer.analyze_device_epg_vlan_mapping()

            # Add comprehensive statistics
            viz_data['statistics'] = {
                'total_leafs': leaf_fex.get('statistics', {}).get('total_leafs', 0),
                'total_fex': leaf_fex.get('statistics', {}).get('total_fex', 0),
                'avg_utilization': round(
                    sum(p['utilization_pct'] for p in port_util) / len(port_util), 2
                ) if port_util else 0,
                'consolidation_candidates': sum(
                    1 for p in port_util if p['consolidation_score'] >= 60
                ),
                'total_epgs': len(epg_complex),
                'total_vlans': vlan_dist.get('statistics', {}).get('total_vlans_used', 0),
                'vlan_overlaps': len(vlan_dist.get('overlaps', [])),
                'migration_flags': len(migration_flags)
            }

            # Add detailed analysis data
            viz_data['port_utilization'] = port_util[:50]  # Top 50
            viz_data['vlan_distribution'] = vlan_dist
            viz_data['epg_complexity'] = epg_complex[:20]  # Top 20
            viz_data['migration_flags'] = migration_flags
            viz_data['vpc_symmetry'] = vpc_symmetry
            viz_data['leaf_fex_mapping'] = leaf_fex
            viz_data['device_mapping'] = device_mapping

            app.logger.info(f"Generated visualization data for fabric {current_fabric}")

        except Exception as e:
            app.logger.error(f"Error generating visualization data: {str(e)}", exc_info=True)
            viz_data = {'error': str(e)}

    return render_template('visualize.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         viz_data=viz_data)


@app.route('/plan')
def plan():
    """Planning page - recommendations and what-if scenarios."""
    mode = session.get('mode', 'evpn')
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
    mode = session.get('mode', 'evpn')
    current_fabric = session.get('current_fabric')

    report_data = {}
    if current_fabric:
        fabric_data = fm.get_fabric_data(current_fabric)
        report_data = reporting.generate_report(fabric_data, mode)

    return render_template('report.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         report_data=report_data)


@app.route('/evpn_migration')
def evpn_migration_page():
    """EVPN migration planning and configuration generation."""
    mode = session.get('mode', 'evpn')
    current_fabric = session.get('current_fabric')

    evpn_data = {}
    if current_fabric:
        fabric_data = fm.get_fabric_data(current_fabric)
        analyzer = engine.ACIAnalyzer(fabric_data)
        analyzer._load_data()

        # Get target platform from request or default to nxos
        target_platform = request.args.get('platform', 'nxos')

        # Generate EVPN migration plan
        evpn_data = evpn_migration.generate_evpn_migration_report(
            analyzer._aci_objects,
            target_platform
        )
        evpn_data['target_platform'] = target_platform

    return render_template('evpn_migration.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         evpn_data=evpn_data)


@app.route('/download/evpn_config/<device_role>')
def download_evpn_config(device_role):
    """Download EVPN configuration for specific device role."""
    current_fabric = session.get('current_fabric')
    if not current_fabric:
        return "No fabric selected", 400

    fabric_data = fm.get_fabric_data(current_fabric)
    analyzer = engine.ACIAnalyzer(fabric_data)
    analyzer._load_data()

    target_platform = request.args.get('platform', 'nxos')

    # Generate migration report
    migration_data = evpn_migration.generate_evpn_migration_report(
        analyzer._aci_objects,
        target_platform
    )

    # Get config for device role
    config = migration_data['config_samples'].get(device_role, '')

    # Save to output directory
    filename = f'{current_fabric}_evpn_{device_role}_{target_platform}.cfg'
    output_path = OUTPUT_DIR / filename
    output_path.write_text(config, encoding='utf-8')

    return send_file(output_path, as_attachment=True, download_name=filename, mimetype='text/plain')


@app.route('/download/report/<format>')
def download_report(format):
    """Download report in specified format (markdown, csv, html)."""
    current_fabric = session.get('current_fabric')
    if not current_fabric:
        return "No fabric selected", 400

    fabric_data = fm.get_fabric_data(current_fabric)
    mode = session.get('mode', 'evpn')

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
    mode = session.get('mode', 'evpn')
    return render_template('help.html', mode=mode)


# ==================== Advanced Migration Analysis API ====================

@app.route('/api/analyze/vpc/<fabric_id>')
def analyze_vpc(fabric_id):
    """VPC and port-channel configuration analysis for migration."""
    try:
        fabric_id = validate_fabric_name(fabric_id)
        fabric_data = fm.get_fabric_data(fabric_id)
        analyzer = engine.ACIAnalyzer(fabric_data)
        results = analyzer.analyze_vpc_configuration()
        return jsonify(results)
    except Exception as e:
        app.logger.error(f"VPC analysis failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze/contracts/<fabric_id>')
def analyze_contracts(fabric_id):
    """Contract-to-ACL translation analysis."""
    try:
        fabric_id = validate_fabric_name(fabric_id)
        fabric_data = fm.get_fabric_data(fabric_id)
        analyzer = engine.ACIAnalyzer(fabric_data)
        results = analyzer.analyze_contract_to_acl_translation()
        return jsonify(results)
    except Exception as e:
        app.logger.error(f"Contract analysis failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze/l3out/<fabric_id>')
def analyze_l3out(fabric_id):
    """L3Out and external connectivity analysis."""
    try:
        fabric_id = validate_fabric_name(fabric_id)
        fabric_data = fm.get_fabric_data(fabric_id)
        analyzer = engine.ACIAnalyzer(fabric_data)
        results = analyzer.analyze_l3out_connectivity()
        return jsonify(results)
    except Exception as e:
        app.logger.error(f"L3Out analysis failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze/vlans/<fabric_id>')
def analyze_vlans(fabric_id):
    """VLAN pool and namespace management analysis."""
    try:
        fabric_id = validate_fabric_name(fabric_id)
        fabric_data = fm.get_fabric_data(fabric_id)
        analyzer = engine.ACIAnalyzer(fabric_data)
        results = analyzer.analyze_vlan_pools()
        return jsonify(results)
    except Exception as e:
        app.logger.error(f"VLAN analysis failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze/physical/<fabric_id>')
def analyze_physical(fabric_id):
    """Physical connectivity and interface policy analysis."""
    try:
        fabric_id = validate_fabric_name(fabric_id)
        fabric_data = fm.get_fabric_data(fabric_id)
        analyzer = engine.ACIAnalyzer(fabric_data)
        results = analyzer.analyze_physical_connectivity()
        return jsonify(results)
    except Exception as e:
        app.logger.error(f"Physical connectivity analysis failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/migration-assessment/<fabric_id>')
def migration_assessment(fabric_id):
    """Comprehensive migration readiness assessment."""
    try:
        fabric_id = validate_fabric_name(fabric_id)
        fabric_data = fm.get_fabric_data(fabric_id)
        analyzer = engine.ACIAnalyzer(fabric_data)
        assessment = analyzer.generate_complete_migration_assessment()
        return jsonify(assessment)
    except Exception as e:
        app.logger.error(f"Migration assessment failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# Fabric Management API
@app.route('/fabrics', methods=['GET'])
def list_fabrics():
    """List all fabrics."""
    fabrics = fm.list_fabrics()
    return jsonify(fabrics)


@app.route('/fabrics', methods=['POST'])
@csrf.exempt
def create_fabric():
    """Create a new fabric."""
    data = request.get_json()
    fabric_name = data.get('name')

    if not fabric_name:
        return jsonify({'error': 'Fabric name required'}), 400

    try:
        # Validate and sanitize fabric name
        fabric_name = validate_fabric_name(fabric_name)
        fm.create_fabric(fabric_name)
        session['current_fabric'] = fabric_name
        app.logger.info(f"Created new fabric: {fabric_name}")
        return jsonify({'success': True, 'fabric': fabric_name})
    except ValueError as e:
        app.logger.warning(f"Failed to create fabric: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/fabrics/<fabric_name>', methods=['DELETE'])
@csrf.exempt
def delete_fabric(fabric_name):
    """Delete a fabric."""
    try:
        # Validate fabric name
        fabric_name = validate_fabric_name(fabric_name)
        fm.delete_fabric(fabric_name)
        if session.get('current_fabric') == fabric_name:
            session.pop('current_fabric', None)
        app.logger.info(f"Deleted fabric: {fabric_name}")
        return jsonify({'success': True})
    except ValueError as e:
        app.logger.warning(f"Failed to delete fabric: {str(e)}")
        return jsonify({'error': str(e)}), 404


@app.route('/fabrics/<fabric_name>/select', methods=['POST'])
@csrf.exempt
def select_fabric(fabric_name):
    """Select a fabric as current."""
    try:
        # Validate fabric name
        fabric_name = validate_fabric_name(fabric_name)
        if fabric_name not in [f['name'] for f in fm.list_fabrics()]:
            return jsonify({'error': 'Fabric not found'}), 404

        session['current_fabric'] = fabric_name
        app.logger.info(f"Selected fabric: {fabric_name}")
        return jsonify({'success': True, 'fabric': fabric_name})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/analysis/<analysis_type>')
@limiter.limit("30 per minute")
def get_analysis(analysis_type):
    """Get specific analysis results via API."""
    current_fabric = session.get('current_fabric')
    if not current_fabric:
        return jsonify({'error': 'No fabric selected'}), 400

    # Whitelist of allowed analysis types
    ALLOWED_ANALYSIS_TYPES = {
        'port_utilization', 'leaf_fex_mapping', 'rack_grouping',
        'bd_epg_mapping', 'vlan_distribution', 'epg_complexity',
        'vpc_symmetry', 'pdom_analysis', 'migration_flags',
        'contract_scope', 'vlan_spread', 'cmdb_correlation'
    }

    if analysis_type not in ALLOWED_ANALYSIS_TYPES:
        app.logger.warning(f"Invalid analysis type requested: {analysis_type}")
        return jsonify({'error': 'Unknown analysis type'}), 400

    try:
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

        result = analysis_methods[analysis_type]()
        app.logger.info(f"Analysis completed: {analysis_type} for fabric {current_fabric}")
        return jsonify(result)

    except Exception as e:
        app.logger.error(f"Analysis error ({analysis_type}): {str(e)}", exc_info=True)
        return jsonify({'error': 'Analysis failed. Please check logs.'}), 500


if __name__ == '__main__':
    print("=" * 70)
    print(f"acimig v{APP_VERSION} - Professional ACI Migration Tool")
    print("=" * 70)
    print(f"Data directory: {DATA_DIR}")
    print(f"Fabrics directory: {FABRICS_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 70)
    print("Access the application at: http://127.0.0.1:5000")
    print("=" * 70)

    app.run(debug=True, host='127.0.0.1', port=5000)
