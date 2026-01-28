"""
ACI Migrator v2.0 - ACI Migration Analysis Platform.
"""

# DEV_NOTES (Repo Discovery - 2026-01-28)
# - Analysis is computed primarily in analysis/engine.py via ACIAnalyzer methods
#   (e.g., analyze_port_utilization, analyze_vlan_distribution, analyze_epg_complexity,
#   analyze_migration_flags, analyze_leaf_fex_mapping, analyze_device_epg_vlan_mapping).
# - /visualize route in app.py builds viz_data by calling ACIAnalyzer.get_visualization_data()
#   plus explicit analysis methods, then renders templates/visualize.html.
# - Visualize tabs and assets:
#   - VLANs, EPG Complexity, Port Utilization, Migration Readiness tabs are in templates/visualize.html
#   - Charts and tab logic are in static/dashboards.js; styles in static/styles.css
# - JSON ingestion: analysis/parsers.py parses ACI JSON (imdata objects) and CMDB CSV,
#   then ACIAnalyzer._load_data() categorizes objects by ACI class (fvAEPg, fvRsPathAtt,
#   eqptFex, fabricNode, ethpmPhysIf, etc.).
import os
import json
import shutil
import logging
import re
import sys
import subprocess
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from functools import wraps
from typing import Dict, Any

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
from analysis import parsers, engine, fabric_manager, planning, reporting

# Initialize Flask app
app = Flask(__name__)

# Load configuration
config_name = os.environ.get('FLASK_ENV', 'development')
config_class = get_config(config_name)
app.config.from_object(config_class)

# Initialize configuration
config_class.init_app(app)

# Ensure SECRET_KEY reflects any init_app changes (e.g., dev auto-generation)
app.config['SECRET_KEY'] = config_class.SECRET_KEY
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
    app.logger.info(f'ACI Migrator startup - Version {APP_VERSION}')

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

# Initialize caching
from flask_caching import Cache
cache = Cache(app, config={
    'CACHE_TYPE': 'SimpleCache',  # Use simple in-memory cache
    'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutes default timeout
    'CACHE_THRESHOLD': 100  # Max 100 items in cache
})

# Directory structure
BASE_DIR = app.config['BASE_DIR']
DATA_DIR = app.config['DATA_DIR']
FABRICS_DIR = app.config['FABRICS_DIR']
CMDB_DIR = app.config['CMDB_DIR']
OUTPUT_DIR = app.config['OUTPUT_DIR']

# Initialize fabric manager
fm = fabric_manager.FabricManager(FABRICS_DIR)


# Cache helper functions
def get_fabric_cache_key(fabric_name: str, suffix: str = '') -> str:
    """Generate cache key for fabric-specific data."""
    return f"fabric_{fabric_name}_{suffix}"


def invalidate_fabric_cache(fabric_name: str):
    """Invalidate all cache entries for a fabric."""
    keys_to_delete = [
        get_fabric_cache_key(fabric_name, 'analysis_view'),
        get_fabric_cache_key(fabric_name, 'visualization'),
        get_fabric_cache_key(fabric_name, 'planning'),
        get_fabric_cache_key(fabric_name, 'reporting'),
        get_fabric_cache_key(fabric_name, 'analysis'),
        get_fabric_cache_key(fabric_name, 'stats'),
    ]
    for key in keys_to_delete:
        cache.delete(key)
    app.logger.info(f"Invalidated cache for fabric: {fabric_name}")


def ensure_mock_samples():
    """Ensure bundled mock sample data exists for MCP mock imports."""
    sample_path = BASE_DIR / 'data' / 'samples' / 'sample_full_mock.json'
    if sample_path.exists():
        return
    generator = BASE_DIR / 'scripts' / 'generate_full_mock.py'
    if not generator.exists():
        app.logger.warning("Mock sample missing and generator not found: %s", sample_path)
        return
    try:
        subprocess.run(
            [sys.executable, str(generator)],
            cwd=str(BASE_DIR),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        app.logger.info("Generated mock sample data at %s", sample_path)
    except Exception as exc:
        app.logger.warning("Failed to generate mock sample data: %s", exc)


# Template context processor to inject fabrics into all templates
@app.context_processor
def inject_fabrics():
    """Make common values available to all templates."""
    if session.get('ui_mode') != 'new':
        session['ui_mode'] = 'new'
    return {
        'fabrics': fm.list_fabrics(),
        'app_version': APP_VERSION,
        'ui_mode': session.get('ui_mode')
    }


# Error handling decorator
def handle_route_errors(f):
    """Decorator to handle errors in routes with flash messages."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            app.logger.error(f"Validation error in {f.__name__}: {str(e)}")
            flash(f"Validation error: {str(e)}", "error")
            return redirect(url_for('index'))
        except FileNotFoundError as e:
            app.logger.error(f"File not found in {f.__name__}: {str(e)}")
            flash(f"File not found: {str(e)}", "error")
            return redirect(url_for('index'))
        except PermissionError as e:
            app.logger.error(f"Permission denied in {f.__name__}: {str(e)}")
            flash("Permission denied. Please check file permissions.", "error")
            return redirect(url_for('index'))
        except Exception as e:
            app.logger.error(f"Unexpected error in {f.__name__}: {str(e)}", exc_info=True)
            flash("An unexpected error occurred. Please check logs or contact support.", "error")
            return redirect(url_for('index'))
    return decorated_function


def handle_api_errors(f):
    """Decorator to handle errors in API routes with JSON responses."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            app.logger.error(f"Validation error in {f.__name__}: {str(e)}")
            return jsonify({'error': f'Validation error: {str(e)}'}), 400
        except FileNotFoundError as e:
            app.logger.error(f"File not found in {f.__name__}: {str(e)}")
            return jsonify({'error': f'File not found: {str(e)}'}), 404
        except PermissionError as e:
            app.logger.error(f"Permission denied in {f.__name__}: {str(e)}")
            return jsonify({'error': 'Permission denied. Please check file permissions.'}), 403
        except Exception as e:
            app.logger.error(f"Unexpected error in {f.__name__}: {str(e)}", exc_info=True)
            return jsonify({'error': 'An unexpected error occurred. Please check logs or contact support.'}), 500
    return decorated_function


# Security helper functions
def validate_fabric_name(name: str) -> str:
    """Validate fabric name to prevent path traversal and injection attacks."""
    import re
    if not isinstance(name, str):
        raise ValueError("Invalid fabric name. Use only alphanumeric characters, underscore, and hyphen (max 64 chars)")
    name = name.strip()
    if not name:
        raise ValueError("Invalid fabric name. Use only alphanumeric characters, underscore, and hyphen (max 64 chars)")
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', name):
        raise ValueError("Invalid fabric name. Use only alphanumeric characters, underscore, and hyphen (max 64 chars)")
    return name


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


def prepare_report_data(fabric_data: Dict[str, Any], fabric_name: str, mode: str) -> Dict[str, Any]:
    """
    Prepare comprehensive data for PDF/Excel reports.

    Args:
        fabric_data: Raw fabric data
        fabric_name: Name of the fabric
        mode: Migration mode (fixed)

    Returns:
        Formatted report data dictionary
    """
    analyzer = engine.ACIAnalyzer(fabric_data)

    # Basic info
    report_data = {
        'fabric_name': fabric_name,
        'mode': mode,
        'generated_at': datetime.now().isoformat(),
    }

    # Device counts
    devices = fabric_data.get('devices', [])
    leafs = [d for d in devices if d.get('device_type') == 'leaf']
    spines = [d for d in devices if d.get('device_type') == 'spine']
    fexes = [d for d in devices if d.get('device_type') == 'fex']

    report_data.update({
        'total_devices': len(devices),
        'total_leafs': len(leafs),
        'total_spines': len(spines),
        'total_fex': len(fexes),
        'devices': devices,
    })

    # EPG data
    epgs = fabric_data.get('epgs', [])
    report_data.update({
        'total_epgs': len(epgs),
        'epgs': epgs,
    })

    # Logical objects
    report_data.update({
        'total_bridge_domains': len(fabric_data.get('bridge_domains', [])),
        'total_vrfs': len(fabric_data.get('vrfs', [])),
        'total_contracts': len(fabric_data.get('contracts', [])),
        'total_subnets': len(fabric_data.get('subnets', [])),
    })

    # Migration analysis if available
    try:
        # Migration readiness assessment
        assessment = analyzer.generate_complete_migration_assessment()
        report_data['migration_assessment'] = assessment

        # Migration waves
        waves_data = analyzer.analyze_migration_waves()
        report_data['migration_waves'] = waves_data.get('summary', [])

        # Coupling analysis
        coupling = analyzer.analyze_coupling_issues()
        report_data['coupling_analysis'] = coupling

    except Exception as e:
        app.logger.warning(f"Could not generate migration analysis: {e}")
        report_data['migration_assessment'] = {
            'overall_readiness': {'score': 0, 'ready_for_migration': False},
            'component_scores': {}
        }

    # Generate recommendations
    try:
        from analysis.planning import ACIPlanner
        planner = ACIPlanner(fabric_data, mode)
        plan = planner.generate_plan()
        report_data['recommendations'] = plan.get('recommendations', [])
    except Exception as e:
        app.logger.warning(f"Could not generate recommendations: {e}")
        report_data['recommendations'] = []

    return report_data


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
        'app_name': 'ACI Migrator',
        'fabrics_dir_exists': FABRICS_DIR.exists(),
        'output_dir_exists': OUTPUT_DIR.exists()
    })


@app.route('/')
def index():
    """Landing page with mode selection and fabric-specific statistics."""
    mode = 'migration'
    ui_mode = 'new'
    session['ui_mode'] = 'new'
    current_fabric = session.get('current_fabric')
    fabric_stats = None

    if current_fabric:
        fabric_data = fm.get_fabric_data(current_fabric)

        # Initialize stats with defaults
        fabric_stats = {
            'total_datasets': len(fabric_data.get('datasets', [])),
            'total_objects': 0,
            'fex_count': 0,
            'leaf_count': 0,
            'epg_count': 0,
            'bd_count': 0,
            'vrf_count': 0,
            'contract_count': 0,
            'last_upload': 'Never',
            'fabric_created': fabric_data.get('created', 'Unknown'),
        }

        # Get last upload timestamp if datasets exist
        datasets = fabric_data.get('datasets', [])
        if datasets:
            # Sort by upload timestamp and get the most recent
            sorted_datasets = sorted(
                datasets,
                key=lambda x: x.get('uploaded', ''),
                reverse=True
            )
            fabric_stats['last_upload'] = sorted_datasets[0].get('uploaded', 'Unknown')

        # Try to load detailed stats from analyzer if data exists
        try:
            analyzer = engine.ACIAnalyzer(fabric_data)
            analyzer._load_data()

            # Get object counts from analyzer
            fabric_stats['fex_count'] = len(analyzer._fexes)
            fabric_stats['leaf_count'] = len(analyzer._leafs)
            fabric_stats['epg_count'] = len(analyzer._epgs)
            fabric_stats['bd_count'] = len(analyzer._bds)
            fabric_stats['vrf_count'] = len(analyzer._vrfs)
            fabric_stats['contract_count'] = len(analyzer._contracts)
            fabric_stats['total_objects'] = sum([
                fabric_stats['fex_count'],
                fabric_stats['leaf_count'],
                fabric_stats['epg_count'],
                fabric_stats['bd_count'],
                fabric_stats['vrf_count'],
                fabric_stats['contract_count']
            ])

            app.logger.info(f"Calculated stats for fabric {current_fabric}: {fabric_stats['total_objects']} objects")

        except Exception as e:
            app.logger.warning(f"Could not load detailed analyzer stats for {current_fabric}: {e}")
            # Keep default zeros if analyzer fails

    template_name = 'index_new.html'

    return render_template(template_name,
                         mode=mode,
                         ui_mode=ui_mode,
                         current_fabric=current_fabric,
                         fabric_stats=fabric_stats)


@app.route('/ui/select')
def select_ui_mode():
    """Persist the preferred UI mode in the session."""
    requested_mode = request.args.get('mode', '').strip().lower()
    if requested_mode not in {'new'}:
        return jsonify({'error': 'Invalid UI mode'}), 400

    session['ui_mode'] = 'new'
    next_path = request.args.get('next', '/')
    if not next_path.startswith('/'):
        next_path = '/'

    return redirect(next_path)


@app.route('/upload_page')
def upload_page():
    """Upload page - file upload interface."""
    mode = 'migration'
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
    mode = 'migration'
    current_fabric = session.get('current_fabric')

    datasets = []
    unified_data = []
    tenants = []
    vrfs = []
    types = ['FEX', 'Leaf', 'EPG', 'BD', 'VRF', 'Contract', 'Subnet', 'Interface']
    type_counts = {}
    validation_results = None
    cmdb_rows = []
    port_status_data = {
        'rows': [],
        'summary': {
            'total_ports': 0,
            'up_ports': 0,
            'down_ports': 0,
            'unknown_ports': 0,
            'ports_with_epg': 0,
            'epg_paths': 0
        },
        'data_ready': False,
        'missing': []
    }

    if current_fabric:
        fabric_data = fm.get_fabric_data(current_fabric)
        datasets = fabric_data.get('datasets', [])
        cache_key = get_fabric_cache_key(current_fabric, 'analysis_view')
        cached = cache.get(cache_key)
        if cached:
            unified_data = cached.get('unified_data', [])
            tenants = cached.get('tenants', [])
            vrfs = cached.get('vrfs', [])
            type_counts = cached.get('type_counts', {})
            validation_results = cached.get('validation_results')
            port_status_data = cached.get('port_status_data', port_status_data)
            cmdb_rows = cached.get('cmdb_rows', [])
            return render_template('analyze_enhanced.html',
                                  mode=mode,
                                  current_fabric=current_fabric,
                                  datasets=datasets,
                                  validation_results=validation_results,
                                  unified_data=unified_data,
                                  cmdb_rows=cmdb_rows,
                                  port_status_data=port_status_data,
                                  tenants=tenants,
                                  vrfs=vrfs,
                                  types=types,
                                  type_counts=type_counts)

        # Run comprehensive data completeness validation
        try:
            analyzer = engine.ACIAnalyzer(fabric_data)

            # Load data for display
            analyzer._load_data()

            # Data completeness and validation
            validation_results = analyzer.get_data_completeness()

            # CMDB records for dedicated CMDB view
            fex_by_serial = {f.get('ser'): f for f in analyzer._fexes if f.get('ser')}
            leaf_by_serial = {l.get('serial'): l for l in analyzer._leafs if l.get('serial')}
            cmdb_rows = []
            for record in analyzer._cmdb_records:
                serial = record.get('serial_number')
                fex = fex_by_serial.get(serial)
                leaf = leaf_by_serial.get(serial)
                device_type = 'unknown'
                device_id = None
                aci_model = None
                if fex:
                    device_type = 'fex'
                    device_id = fex.get('id')
                    aci_model = fex.get('model')
                elif leaf:
                    device_type = 'leaf'
                    device_id = leaf.get('id')
                    aci_model = leaf.get('model')
                cmdb_rows.append({
                    'serial_number': serial or 'Unknown',
                    'name': record.get('name') or 'Unknown',
                    'model_name': record.get('model') or 'Unknown',
                    'aci_model': aci_model or 'Unknown',
                    'matched': bool(fex or leaf),
                    'flagged': not bool(fex or leaf),
                    'device_type': device_type,
                    'device_id': device_id or 'Unknown',
                    'rack': record.get('rack') or 'Unknown',
                    'building': record.get('building') or 'Unknown',
                    'hall': record.get('hall') or 'Unknown',
                    'site': record.get('site') or 'Unknown',
                    'unit_location': record.get('unitlocation') or 'Unknown'
                })

            # BD lookup by name for VRF resolution
            bd_by_name = {bd.get('name', ''): bd for bd in analyzer._bds if bd.get('name')}

            # Build unified data list with all objects
            # Add FEX devices
            for fex in analyzer._fexes:
                fex_id = fex.get('id', '')
                fex_dn = fex.get('dn', '')
                leaf_id = analyzer._extract_leaf_from_fex_dn(fex_dn) or ''
                unified_data.append({
                    'type': 'FEX',
                    'name': fex.get('name', f"FEX-{fex_id}") if fex_id else fex.get('name', ''),
                    'id': str(fex_id),
                    'tenant': '',
                    'vrf': '',
                    'bd': '',
                    'encap': '',
                    'ip_subnet': '',
                    'model': fex.get('model', ''),
                    'serial': fex.get('ser') or fex.get('serial', ''),
                    'status': fex.get('operSt', 'unknown'),
                    'role': '',
                    'app_profile': '',
                    'scope': '',
                    'node': leaf_id,
                    'speed': ''
                })

            # Add Leaf switches
            for leaf in analyzer._leafs:
                leaf_dn = leaf.get('dn', '')
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
                    'status': leaf.get('operSt', 'unknown'),
                    'role': leaf.get('role', 'leaf'),
                    'app_profile': '',
                    'scope': '',
                    'node': analyzer._extract_node_id_from_dn(leaf_dn) or '',
                    'speed': ''
                })

            # Add EPGs
            for epg in analyzer._epgs:
                epg_dn = epg.get('dn', '')
                epg_tenant = analyzer._extract_tenant_from_dn(epg_dn)
                epg_bd = analyzer._get_bd_name_for_epg(epg)
                epg_vrf = ''
                if epg_bd and epg_bd in bd_by_name:
                    epg_vrf = analyzer._get_vrf_name_for_bd(bd_by_name[epg_bd])
                unified_data.append({
                    'type': 'EPG',
                    'name': epg.get('name', ''),
                    'id': '',
                    'tenant': epg_tenant,
                    'vrf': epg_vrf,
                    'bd': epg_bd,
                    'encap': epg.get('encap', ''),
                    'ip_subnet': '',
                    'model': '',
                    'serial': '',
                    'status': '',
                    'role': '',
                    'app_profile': analyzer._extract_app_profile_from_dn(epg_dn),
                    'scope': '',
                    'node': '',
                    'speed': ''
                })

            # Add Bridge Domains
            for bd in analyzer._bds:
                # Get subnets if available
                bd_dn = bd.get('dn', '')
                subnets_list = [
                    subnet.get('ip')
                    for subnet in analyzer._subnets
                    if bd_dn and bd_dn in subnet.get('dn', '')
                ]
                subnet_str = ', '.join(subnets_list) if subnets_list else ''

                unified_data.append({
                    'type': 'BD',
                    'name': bd.get('name', ''),
                    'id': '',
                    'tenant': analyzer._extract_tenant_from_dn(bd_dn),
                    'vrf': analyzer._get_vrf_name_for_bd(bd),
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
                vrf_dn = vrf.get('dn', '')
                unified_data.append({
                    'type': 'VRF',
                    'name': vrf.get('name', ''),
                    'id': '',
                    'tenant': analyzer._extract_tenant_from_dn(vrf_dn),
                    'vrf': '',
                    'bd': '',
                    'encap': '',
                    'ip_subnet': '',
                    'model': '',
                    'serial': '',
                    'status': '',
                    'role': '',
                    'app_profile': '',
                    'scope': vrf.get('pcEnfPref') or vrf.get('pce_policy', 'enforced'),
                    'node': '',
                    'speed': ''
                })

            # Add Contracts
            for contract in analyzer._contracts:
                contract_dn = contract.get('dn', '')
                unified_data.append({
                    'type': 'Contract',
                    'name': contract.get('name', ''),
                    'id': '',
                    'tenant': analyzer._extract_tenant_from_dn(contract_dn),
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
                subnet_dn = subnet.get('dn', '')
                subnet_bd = analyzer._extract_bd_name_from_dn(subnet_dn)
                subnet_vrf = ''
                if subnet_bd and subnet_bd in bd_by_name:
                    subnet_vrf = analyzer._get_vrf_name_for_bd(bd_by_name[subnet_bd])
                unified_data.append({
                    'type': 'Subnet',
                    'name': '',
                    'id': '',
                    'tenant': analyzer._extract_tenant_from_dn(subnet_dn),
                    'vrf': subnet_vrf,
                    'bd': subnet_bd,
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
                iface_dn = iface.get('dn', '')
                unified_data.append({
                    'type': 'Interface',
                    'name': '',
                    'id': analyzer._extract_interface_id_from_dn(iface_dn) or iface.get('id', ''),
                    'tenant': '',
                    'vrf': '',
                    'bd': '',
                    'encap': '',
                    'ip_subnet': '',
                    'model': '',
                    'serial': '',
                    'status': iface.get('operSt', 'unknown'),
                    'role': iface.get('usage', '') or iface.get('usage', ''),
                    'app_profile': '',
                    'scope': '',
                    'node': analyzer._extract_node_id_from_dn(iface_dn) or '',
                    'speed': iface.get('operSpeed', '') or iface.get('speed', '')
                })

            # Extract unique values for filters
            tenants = sorted(set(item['tenant'] for item in unified_data if item['tenant']))
            vrfs = sorted(set(item['vrf'] for item in unified_data if item['vrf']))

            # Count objects by type
            type_counts = {}
            for obj_type in types:
                type_counts[obj_type] = sum(1 for item in unified_data if item['type'] == obj_type)

            # Build port status spreadsheet data
            port_rows = {}
            for iface in analyzer._interfaces:
                iface_dn = iface.get('dn', '')
                node_id = analyzer._extract_node_id_from_dn(iface_dn) or ''
                iface_id = analyzer._extract_interface_id_from_dn(iface_dn) or iface.get('id', '') or ''
                key = f"{node_id}:{iface_id}"
                port_rows[key] = {
                    'node': node_id,
                    'interface': iface_id,
                    'status': iface.get('operSt', 'unknown'),
                    'admin': iface.get('adminSt', ''),
                    'speed': iface.get('operSpeed', '') or iface.get('speed', ''),
                    'usage': iface.get('usage', ''),
                    'epg_count': 0,
                    'epgs': [],
                    'path_count': 0,
                    'encaps': []
                }

            for path in analyzer._path_attachments:
                tdn = path.get('tDn', '')
                nodes = analyzer._extract_nodes_from_tdn(tdn)
                iface_id = analyzer._extract_interface_id_from_dn(tdn)
                if not iface_id:
                    match = re.search(r'pathep-\[(.*?)\]', tdn)
                    iface_id = match.group(1) if match else ''
                epg_dn = analyzer._extract_epg_from_path_dn(path.get('dn', ''))
                epg_name = epg_dn.split('/epg-')[-1] if epg_dn and '/epg-' in epg_dn else epg_dn
                encap = path.get('encap', '')

                for node_id in nodes or ['']:
                    key = f"{node_id}:{iface_id}"
                    if key not in port_rows:
                        port_rows[key] = {
                            'node': node_id,
                            'interface': iface_id,
                            'status': 'unknown',
                            'admin': '',
                            'speed': '',
                            'usage': '',
                            'epg_count': 0,
                            'epgs': [],
                            'path_count': 0,
                            'encaps': []
                        }
                    if epg_name:
                        if epg_name not in port_rows[key]['epgs']:
                            port_rows[key]['epgs'].append(epg_name)
                        port_rows[key]['epg_count'] = len(port_rows[key]['epgs'])
                    port_rows[key]['path_count'] += 1
                    if encap and encap not in port_rows[key]['encaps']:
                        port_rows[key]['encaps'].append(encap)

            port_status_data['rows'] = list(port_rows.values())
            port_status_data['summary']['total_ports'] = len(port_rows)
            port_status_data['summary']['up_ports'] = sum(1 for r in port_rows.values() if r['status'] == 'up')
            port_status_data['summary']['down_ports'] = sum(1 for r in port_rows.values() if r['status'] == 'down')
            port_status_data['summary']['unknown_ports'] = sum(1 for r in port_rows.values() if r['status'] not in {'up', 'down'})
            port_status_data['summary']['ports_with_epg'] = sum(1 for r in port_rows.values() if r['epg_count'] > 0)
            port_status_data['summary']['epg_paths'] = sum(r['path_count'] for r in port_rows.values())
            port_status_data['data_ready'] = len(analyzer._interfaces) > 0 and len(analyzer._path_attachments) > 0
            if len(analyzer._interfaces) == 0:
                port_status_data['missing'].append('ethpmPhysIf')
            if len(analyzer._path_attachments) == 0:
                port_status_data['missing'].append('fvRsPathAtt')

            cache.set(cache_key, {
                'unified_data': unified_data,
                'tenants': tenants,
                'vrfs': vrfs,
                'type_counts': type_counts,
                'validation_results': validation_results,
                'port_status_data': port_status_data,
                'cmdb_rows': cmdb_rows
            })

        except Exception as e:
            app.logger.error(f"Error during analysis: {str(e)}", exc_info=True)
            unified_data = []

    return render_template('analyze_enhanced.html',
                          mode=mode,
                          current_fabric=current_fabric,
                          datasets=datasets,
                          validation_results=validation_results,
                          unified_data=unified_data,
                          cmdb_rows=cmdb_rows,
                          port_status_data=port_status_data,
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
        fallback_fabric = request.form.get('fabric_name', '').strip()
        if fallback_fabric:
            try:
                fallback_fabric = validate_fabric_name(fallback_fabric)
                if fallback_fabric in [f['name'] for f in fm.list_fabrics()]:
                    current_fabric = fallback_fabric
                    session['current_fabric'] = fallback_fabric
            except ValueError:
                current_fabric = None
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

        # Parse based on file type
        try:
            if file_type == 'aci':
                file_size = file_path.stat().st_size if file_path.exists() else 0
                large_parse_threshold = 50 * 1024 * 1024  # 50MB
                if file_size > large_parse_threshold:
                    fm.add_dataset(current_fabric, {
                        'filename': filename,
                        'type': 'aci',
                        'format': file_ext,
                        'uploaded': datetime.now().isoformat(),
                        'objects': None,
                        'deferred_validation': True,
                        'path': str(file_path)
                    })
                    app.logger.info(
                        f"Deferred parsing for large ACI {file_ext}: {file_size} bytes"
                    )
                    invalidate_fabric_cache(current_fabric)
                    return jsonify({
                        'success': True,
                        'filename': filename,
                        'type': file_type,
                        'message': f'Uploaded {filename}. Validation deferred due to file size.'
                    })

                try:
                    content = read_file_safely(file_path)
                except (FileNotFoundError, PermissionError, ValueError) as e:
                    app.logger.error(f"Error reading file {filename}: {str(e)}")
                    return jsonify({'error': str(e)}), 500

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
                try:
                    content = read_file_safely(file_path)
                except (FileNotFoundError, PermissionError, ValueError) as e:
                    app.logger.error(f"Error reading file {filename}: {str(e)}")
                    return jsonify({'error': str(e)}), 500
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
                try:
                    content = read_file_safely(file_path)
                except (FileNotFoundError, PermissionError, ValueError) as e:
                    app.logger.error(f"Error reading file {filename}: {str(e)}")
                    return jsonify({'error': str(e)}), 500
                parsed_data = parsers.parse_legacy_config(content)
                fm.add_dataset(current_fabric, {
                    'filename': filename,
                    'type': 'legacy',
                    'uploaded': datetime.now().isoformat(),
                    'platform': parsed_data.get('platform', 'unknown'),
                    'path': str(file_path)
                })
                app.logger.info(f"Parsed legacy config: {parsed_data.get('platform')}")

            # Invalidate cache for this fabric since data has changed
            invalidate_fabric_cache(current_fabric)

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


@app.route('/api/mcp/test', methods=['POST'])
@csrf.exempt
def test_mcp_connection():
    """Test connection to MCP server."""
    try:
        data = request.get_json()
        mcp_url = data.get('mcp_url')

        if not mcp_url:
            return jsonify({'error': 'MCP URL required'}), 400

        if mcp_url.strip().lower() == 'mock':
            return jsonify({
                'status': 'healthy',
                'service': 'Mock MCP',
                'version': APP_VERSION,
                'mode': 'mock'
            })

        from mcp_client import test_mcp_connection
        result = test_mcp_connection(mcp_url)

        return jsonify(result)

    except Exception as e:
        app.logger.error(f"MCP connection test failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/mcp/import', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per minute")
def import_from_mcp():
    """Import data from MCP server."""
    try:
        data = request.get_json()
        mcp_url = data.get('mcp_url')
        fabric_name = data.get('fabric_name')

        if not mcp_url or not fabric_name:
            return jsonify({'error': 'MCP URL and fabric name required'}), 400

        # Validate fabric name
        try:
            fabric_name = validate_fabric_name(fabric_name)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        if mcp_url.strip().lower() == 'mock':
            ensure_mock_samples()
            sample_candidates = [
                BASE_DIR / 'data' / 'samples' / 'sample_full_mock.json',
                BASE_DIR / 'data' / 'samples' / 'sample_large_scale.json',
                BASE_DIR / 'data' / 'samples' / 'sample_aci.json',
            ]
            sample_path = next((p for p in sample_candidates if p.exists()), None)
            if not sample_path:
                return jsonify({'error': 'Mock data file not found in data/samples'}), 500

            sample_objects = json.loads(read_file_safely(sample_path))

            # Create fabric directory
            fabric_dir = FABRICS_DIR / fabric_name
            fabric_dir.mkdir(exist_ok=True, parents=True)

            # Remove older mock datasets to avoid stale completeness scores
            fabric_data = fm.get_fabric_data(fabric_name)
            cleaned_datasets = []
            for dataset in fabric_data.get('datasets', []):
                if dataset.get('source') == 'mcp-mock' or str(dataset.get('filename', '')).startswith('mcp_mock_'):
                    path_value = dataset.get('path')
                    if path_value:
                        try:
                            Path(path_value).unlink(missing_ok=True)
                        except Exception:
                            app.logger.warning(f"Failed to delete old mock file: {path_value}")
                    continue
                cleaned_datasets.append(dataset)

            if cleaned_datasets != fabric_data.get('datasets', []):
                fabric_data['datasets'] = cleaned_datasets
                fm.save_fabric_metadata(fabric_name, fabric_data)

            mock_file = fabric_dir / f'mcp_mock_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            mock_file.write_text(json.dumps(sample_objects, indent=2), encoding='utf-8')

            fm.add_dataset(fabric_name, {
                'filename': mock_file.name,
                'type': 'aci_json',
                'format': 'json',
                'uploaded': datetime.now().isoformat(),
                'source': 'mcp-mock',
                'path': str(mock_file)
            })

            session['current_fabric'] = fabric_name
            invalidate_fabric_cache(fabric_name)

            return jsonify({
                'success': True,
                'fabric_name': fabric_name,
                'statistics': {},
                'message': f'Imported bundled sample data via mock MCP ({sample_path.name})'
            })

        from mcp_client import MCPClient, MCPDataValidator

        # Fetch data from MCP server
        client = MCPClient(mcp_url)
        migrator_data = client.get_migrator_data()

        # Validate data
        errors = MCPDataValidator.validate_migrator_data(migrator_data)
        if errors:
            app.logger.error(f"MCP data validation failed: {errors}")
            return jsonify({'error': 'Data validation failed', 'details': errors}), 400

        # Create fabric directory
        fabric_dir = FABRICS_DIR / fabric_name
        fabric_dir.mkdir(exist_ok=True, parents=True)

        # Save MCP data as JSON
        mcp_file = fabric_dir / f'mcp_import_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(mcp_file, 'w') as f:
            json.dump(migrator_data, f, indent=2)

        # Transform MCP data to ACI Migrator internal format
        aci_data = transform_mcp_to_aci_format(migrator_data)
        aci_imdata = build_imdata_from_mcp(migrator_data)

        # Save converted ACI imdata for analysis engine
        aci_file = fabric_dir / f'mcp_import_{datetime.now().strftime("%Y%m%d_%H%M%S")}_aci.json'
        aci_file.write_text(json.dumps({'imdata': aci_imdata}, indent=2), encoding='utf-8')

        # Add to fabric manager
        fm.add_dataset(fabric_name, {
            'filename': mcp_file.name,
            'type': 'mcp_import',
            'uploaded': datetime.now().isoformat(),
            'source': mcp_url,
            'devices': len(migrator_data.get('devices', [])),
            'epgs': len(migrator_data.get('epg_mappings', [])),
            'path': str(mcp_file)
        })

        # Add converted ACI dataset for analysis engine
        fm.add_dataset(fabric_name, {
            'filename': aci_file.name,
            'type': 'aci_json',
            'format': 'json',
            'uploaded': datetime.now().isoformat(),
            'source': f'{mcp_url} (converted)',
            'objects': len(aci_imdata),
            'path': str(aci_file)
        })

        # Set as current fabric
        session['current_fabric'] = fabric_name

        # Invalidate cache
        invalidate_fabric_cache(fabric_name)

        app.logger.info(f"Successfully imported data from MCP server to fabric {fabric_name}")

        return jsonify({
            'success': True,
            'fabric_name': fabric_name,
            'statistics': migrator_data.get('statistics', {}),
            'message': f'Successfully imported data from MCP server'
        })

    except Exception as e:
        app.logger.error(f"MCP import failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def transform_mcp_to_aci_format(mcp_data):
    """Transform MCP data to ACI Migrator internal format."""
    aci_data = {
        'devices': {},
        'epgs': [],
        'vlans': set(),
        'tenants': set()
    }

    # Transform devices
    for device in mcp_data.get('devices', []):
        device_id = device['device_id']
        aci_data['devices'][device_id] = {
            'id': device_id,
            'name': device['device_name'],
            'type': device['device_type'],
            'model': device.get('model', 'Unknown'),
            'parent_leaf': device.get('parent_leaf'),
            'epgs': [],
            'ports': []
        }

    # Transform EPG mappings
    for epg_mapping in mcp_data.get('epg_mappings', []):
        tenant = epg_mapping['tenant']
        ap = epg_mapping.get('application_profile', '')
        epg_name = epg_mapping['epg']
        vlans = epg_mapping.get('vlans', [])
        devices = epg_mapping.get('devices', [])

        aci_data['tenants'].add(tenant)
        for vlan in vlans:
            aci_data['vlans'].add(str(vlan))

        epg_obj = {
            'tenant': tenant,
            'app_profile': ap,
            'name': epg_name,
            'vlans': vlans,
            'devices': devices,
            'paths': epg_mapping.get('paths', []),
            'total_ports': epg_mapping.get('total_ports', 0)
        }

        aci_data['epgs'].append(epg_obj)

        # Link EPG to devices
        for device_id in devices:
            if device_id in aci_data['devices']:
                aci_data['devices'][device_id]['epgs'].append(epg_name)

    # Convert sets to lists for JSON serialization
    aci_data['vlans'] = sorted(list(aci_data['vlans']))
    aci_data['tenants'] = sorted(list(aci_data['tenants']))

    return aci_data


def build_imdata_from_mcp(mcp_data: Dict[str, Any]) -> list:
    """Build a minimal ACI imdata list from MCP migrator data."""
    imdata = []
    device_id_map = {}
    fex_id_map = {}
    next_node_id = 100
    next_fex_id = 2000

    def normalize_id(value: str, fallback: int) -> str:
        match = re.search(r'(\\d+)', str(value))
        return match.group(1) if match else str(fallback)

    # Tenants
    tenants = sorted({epg.get('tenant') for epg in mcp_data.get('epg_mappings', []) if epg.get('tenant')})
    for tenant in tenants:
        imdata.append({
            'type': 'fvTenant',
            'attributes': {
                'dn': f"uni/tn-{tenant}",
                'name': tenant,
                'descr': 'synthetic (MCP import)'
            }
        })

    # Devices
    for device in mcp_data.get('devices', []):
        device_id = device.get('device_id')
        device_type = device.get('device_type')
        device_name = device.get('device_name') or str(device_id)
        model = device.get('model', 'Unknown')

        if device_type in {'leaf', 'spine'}:
            node_id = normalize_id(device_id, next_node_id)
            if node_id == str(next_node_id):
                next_node_id += 1
            device_id_map[device_id] = node_id
            imdata.append({
                'type': 'fabricNode',
                'attributes': {
                    'dn': f"topology/pod-1/node-{node_id}",
                    'id': node_id,
                    'name': device_name,
                    'role': device_type,
                    'model': model,
                    'serial': device.get('serial', ''),
                    'descr': 'synthetic (MCP import)'
                }
            })
        elif device_type == 'fex':
            fex_id = normalize_id(device_id, next_fex_id)
            if fex_id == str(next_fex_id):
                next_fex_id += 1
            fex_id_map[device_id] = fex_id
            imdata.append({
                'type': 'eqptFex',
                'attributes': {
                    'dn': f"topology/pod-1/node-{device.get('parent_leaf', 'unknown')}/sys/extch-{fex_id}",
                    'id': fex_id,
                    'name': device_name,
                    'ser': device.get('serial', device_id),
                    'model': model,
                    'operSt': 'unknown',
                    'descr': 'synthetic (MCP import)'
                }
            })

    # EPGs and path attachments
    for epg_mapping in mcp_data.get('epg_mappings', []):
        tenant = epg_mapping.get('tenant', 'common')
        ap = epg_mapping.get('application_profile', 'app')
        epg_name = epg_mapping.get('epg', 'epg')
        epg_dn = f"uni/tn-{tenant}/ap-{ap}/epg-{epg_name}"

        imdata.append({
            'type': 'fvAEPg',
            'attributes': {
                'dn': epg_dn,
                'name': epg_name,
                'descr': 'synthetic (MCP import)'
            }
        })

        devices = epg_mapping.get('devices', [])
        vlans = epg_mapping.get('vlans', [])
        for device_id in devices:
            node_id = device_id_map.get(device_id)
            fex_id = fex_id_map.get(device_id)
            for vlan in vlans:
                if node_id:
                    tdn = f"topology/pod-1/paths-{node_id}/pathep-[eth1/1]"
                elif fex_id:
                    tdn = f"topology/pod-1/node-unknown/sys/extch-{fex_id}"
                else:
                    tdn = "topology/pod-1/paths-unknown/pathep-[eth1/1]"

                imdata.append({
                    'type': 'fvRsPathAtt',
                    'attributes': {
                        'dn': f"{epg_dn}/rspathAtt-[{tdn}]",
                        'tDn': tdn,
                        'encap': f"vlan-{vlan}",
                        'mode': 'regular',
                        'descr': 'synthetic (MCP import)'
                    }
                })

    return imdata


@app.route('/visualize')
@handle_route_errors
def visualize():
    """Visualization page - interactive dashboards with charts and graphs."""
    mode = 'migration'
    current_fabric = session.get('current_fabric')

    viz_data = {}
    if current_fabric:
        # Try to get from cache first
        cache_key = get_fabric_cache_key(current_fabric, 'visualization')
        viz_data = cache.get(cache_key)

        if viz_data is None:
            # Cache miss - generate data
            fabric_data = fm.get_fabric_data(current_fabric)
            analyzer = engine.ACIAnalyzer(fabric_data)

            # Get base visualization data
            viz_data = analyzer.get_visualization_data()

            # Enrich with analysis data for dashboards
            port_util = analyzer.analyze_port_utilization()
            port_util_quality = analyzer.get_port_utilization_quality()
            vlan_dist = analyzer.analyze_vlan_distribution()
            vlan_coupling = analyzer.analyze_vlan_coupling_index()
            epg_complex = analyzer.analyze_epg_complexity()
            migration_flags = analyzer.analyze_migration_flags()
            migration_units = analyzer.analyze_migration_units()
            vpc_symmetry = analyzer.analyze_vpc_symmetry()
            leaf_fex = analyzer.analyze_leaf_fex_mapping()
            device_mapping = analyzer.analyze_device_epg_vlan_mapping()

            def _trim_device_mapping(mapping, max_devices=500, max_leafs=200, max_fex_per_leaf=20, max_epgs_per_device=50):
                stats = mapping.get('statistics', {})
                total_devices = stats.get('total_devices', 0)
                if total_devices <= max_devices:
                    return mapping
                trimmed = dict(mapping)
                device_map = mapping.get('device_map', {})
                trimmed_devices = {}
                for device_id in list(device_map.keys())[:max_devices]:
                    device_data = dict(device_map[device_id])
                    if isinstance(device_data.get('epgs'), list):
                        device_data['epgs'] = device_data['epgs'][:max_epgs_per_device]
                    trimmed_devices[device_id] = device_data
                trimmed['device_map'] = trimmed_devices
                hierarchy = mapping.get('hierarchy', [])
                trimmed_hierarchy = []
                for leaf in hierarchy[:max_leafs]:
                    leaf_copy = dict(leaf)
                    if isinstance(leaf_copy.get('fex_devices'), list):
                        leaf_copy['fex_devices'] = leaf_copy['fex_devices'][:max_fex_per_leaf]
                        for fex in leaf_copy['fex_devices']:
                            if isinstance(fex.get('epgs'), list):
                                fex['epgs'] = fex['epgs'][:max_epgs_per_device]
                    trimmed_hierarchy.append(leaf_copy)
                trimmed['hierarchy'] = trimmed_hierarchy
                trimmed['statistics'] = dict(stats)
                trimmed['statistics']['truncated'] = True
                trimmed['statistics']['truncated_reason'] = 'device_mapping_limit'
                trimmed['statistics']['total_devices'] = min(total_devices, max_devices)
                return trimmed

            device_mapping = _trim_device_mapping(device_mapping)

            known_util = [p for p in port_util if p.get('utilization_pct') is not None]
            worst_vlan = None
            if vlan_coupling.get('vlans'):
                worst_vlan = max(vlan_coupling['vlans'], key=lambda v: v.get('coupling_score', 0))

            # Add comprehensive statistics
            viz_data['statistics'] = {
                'total_leafs': leaf_fex.get('statistics', {}).get('total_leafs', 0),
                'total_fex': leaf_fex.get('statistics', {}).get('total_fex', 0),
                'avg_utilization': round(
                    sum(p['utilization_pct'] for p in known_util) / len(known_util), 2
                ) if known_util else None,
                'consolidation_candidates': sum(
                    1 for p in port_util if (p.get('consolidation_score') or 0) >= 60
                ),
                'utilization_needs_data': sum(1 for p in port_util if p.get('utilization_pct') is None),
                'total_epgs': len(epg_complex),
                'total_vlans': vlan_dist.get('statistics', {}).get('total_vlans_used', 0),
                'vlan_overlaps': len(vlan_dist.get('overlaps', [])),
                'migration_flags': len(migration_flags),
                'vlan_coupling_high': vlan_coupling.get('statistics', {}).get('high_coupling', 0),
                'worst_vlan_id': worst_vlan.get('vlan_id') if worst_vlan else None,
                'worst_vlan_score': worst_vlan.get('coupling_score') if worst_vlan else None,
                'migration_units': migration_units.get('statistics', {})
            }

            # Add detailed analysis data
            viz_data['port_utilization'] = port_util
            viz_data['port_utilization_quality'] = port_util_quality
            viz_data['vlan_distribution'] = vlan_dist
            viz_data['vlan_coupling'] = vlan_coupling
            viz_data['epg_complexity'] = epg_complex[:20]  # Top 20 for charts
            viz_data['epg_complexity_all'] = epg_complex
            for flag in migration_flags:
                severity = flag.get('severity')
                flag['flagged'] = severity in {'high', 'medium'}
                flag['why'] = flag.get('message', '')
            viz_data['migration_flags'] = migration_flags
            viz_data['migration_units'] = migration_units
            viz_data['vpc_symmetry'] = vpc_symmetry
            viz_data['leaf_fex_mapping'] = leaf_fex
            viz_data['device_mapping'] = device_mapping

            # Store in cache
            cache.set(cache_key, viz_data, timeout=300)
            app.logger.info(f"Generated and cached visualization data for fabric {current_fabric}")

    return render_template('visualize.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         viz_data=viz_data)


@app.route('/plan')
@handle_route_errors
def plan():
    """Planning page - recommendations and what-if scenarios."""
    mode = 'migration'
    current_fabric = session.get('current_fabric')

    plan_data = {}
    if current_fabric:
        cache_key = get_fabric_cache_key(current_fabric, 'planning')
        plan_data = cache.get(cache_key)
        if plan_data is None:
            fabric_data = fm.get_fabric_data(current_fabric)
            planner = planning.ACIPlanner(fabric_data, mode)
            plan_data = planner.generate_plan()
            cache.set(cache_key, plan_data, timeout=300)

    # Get all fabrics for what-if scenarios
    all_fabrics = fm.list_fabrics()

    return render_template('plan.html',
                         mode=mode,
                         current_fabric=current_fabric,
                         plan_data=plan_data,
                         all_fabrics=all_fabrics)


@app.route('/report')
@handle_route_errors
def report():
    """Report generation page - HTML, Markdown, CSV exports."""
    mode = 'migration'
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
@handle_route_errors
def download_report(format):
    """Download report in specified format (markdown, csv, html, json, pdf, excel)."""
    current_fabric = session.get('current_fabric')
    if not current_fabric:
        flash("No fabric selected", "error")
        return redirect(url_for('index'))

    fabric_data = fm.get_fabric_data(current_fabric)
    mode = 'migration'

    # Prepare report data
    report_data = prepare_report_data(fabric_data, current_fabric, mode)

    if format == 'markdown':
        content = reporting.generate_markdown_report(fabric_data, mode)
        filename = f'{current_fabric}_report.md'
        mimetype = 'text/markdown'
        is_binary = False
    elif format == 'csv':
        content = reporting.generate_csv_report(fabric_data, mode)
        filename = f'{current_fabric}_report.csv'
        mimetype = 'text/csv'
        is_binary = False
    elif format == 'html':
        content = reporting.generate_html_report(fabric_data, mode)
        filename = f'{current_fabric}_report.html'
        mimetype = 'text/html'
        is_binary = False
    elif format == 'json':
        content = reporting.generate_json_report(fabric_data, mode)
        filename = f'{current_fabric}_report.json'
        mimetype = 'application/json'
        is_binary = False
    elif format == 'pdf':
        from analysis.export import generate_pdf_report
        content = generate_pdf_report(report_data)
        filename = f'{current_fabric}_report.pdf'
        mimetype = 'application/pdf'
        is_binary = True
    elif format == 'excel':
        from analysis.export import generate_excel_report
        content = generate_excel_report(report_data)
        filename = f'{current_fabric}_report.xlsx'
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        is_binary = True
    else:
        flash(f"Invalid format: {format}", "error")
        return redirect(url_for('report'))

    # Save to output directory
    output_path = OUTPUT_DIR / filename
    if is_binary:
        output_path.write_bytes(content)
    else:
        output_path.write_text(content, encoding='utf-8')

    app.logger.info(f"Generated {format} report for fabric {current_fabric}")
    return send_file(output_path, as_attachment=True, download_name=filename, mimetype=mimetype)


@app.route('/download/offline_collector.py')
def download_offline_collector():
    """Serve the offline collector script."""
    collector_path = BASE_DIR / 'offline_collector.py'
    return send_file(collector_path, as_attachment=True, download_name='offline_collector.py')


@app.route('/help')
def help_page():
    """In-app documentation and ACI object reference."""
    mode = 'migration'
    return render_template('help.html', mode=mode)


# ==================== Advanced Migration Analysis API ====================

@app.route('/api/analyze/vpc/<fabric_id>')
@handle_api_errors
def analyze_vpc(fabric_id):
    """VPC and port-channel configuration analysis for migration."""
    fabric_id = validate_fabric_name(fabric_id)
    fabric_data = fm.get_fabric_data(fabric_id)
    analyzer = engine.ACIAnalyzer(fabric_data)
    results = analyzer.analyze_vpc_configuration()
    return jsonify(results)


@app.route('/api/analyze/contracts/<fabric_id>')
@handle_api_errors
def analyze_contracts(fabric_id):
    """Contract-to-ACL translation analysis."""
    fabric_id = validate_fabric_name(fabric_id)
    fabric_data = fm.get_fabric_data(fabric_id)
    analyzer = engine.ACIAnalyzer(fabric_data)
    results = analyzer.analyze_contract_to_acl_translation()
    return jsonify(results)


@app.route('/api/analyze/l3out/<fabric_id>')
@handle_api_errors
def analyze_l3out(fabric_id):
    """L3Out and external connectivity analysis."""
    fabric_id = validate_fabric_name(fabric_id)
    fabric_data = fm.get_fabric_data(fabric_id)
    analyzer = engine.ACIAnalyzer(fabric_data)
    results = analyzer.analyze_l3out_connectivity()
    return jsonify(results)


@app.route('/api/analyze/vlans/<fabric_id>')
@handle_api_errors
def analyze_vlans(fabric_id):
    """VLAN pool and namespace management analysis."""
    fabric_id = validate_fabric_name(fabric_id)
    fabric_data = fm.get_fabric_data(fabric_id)
    analyzer = engine.ACIAnalyzer(fabric_data)
    results = analyzer.analyze_vlan_pools()
    return jsonify(results)


@app.route('/api/analyze/physical/<fabric_id>')
@handle_api_errors
def analyze_physical(fabric_id):
    """Physical connectivity and interface policy analysis."""
    fabric_id = validate_fabric_name(fabric_id)
    fabric_data = fm.get_fabric_data(fabric_id)
    analyzer = engine.ACIAnalyzer(fabric_data)
    results = analyzer.analyze_physical_connectivity()
    return jsonify(results)


@app.route('/api/migration-assessment/<fabric_id>')
@handle_api_errors
def migration_assessment(fabric_id):
    """Comprehensive migration readiness assessment."""
    fabric_id = validate_fabric_name(fabric_id)
    fabric_data = fm.get_fabric_data(fabric_id)
    analyzer = engine.ACIAnalyzer(fabric_data)
    assessment = analyzer.generate_complete_migration_assessment()
    return jsonify(assessment)


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
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid JSON payload'}), 400
    fabric_name = data.get('name', '').strip()

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
@handle_api_errors
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

    # Check cache first
    cache_key = get_fabric_cache_key(current_fabric, f'analysis_{analysis_type}')
    result = cache.get(cache_key)

    if result is None:
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
        cache.set(cache_key, result, timeout=300)
        app.logger.info(f"Analysis completed and cached: {analysis_type} for fabric {current_fabric}")

    return jsonify(result)


# ==================== Batch Operations API ====================

@app.route('/api/dataset/<filename>', methods=['GET', 'DELETE'])
@csrf.exempt
@limiter.limit("20 per minute")
@handle_api_errors
def dataset_detail(filename):
    """Get or delete a dataset by filename."""
    current_fabric = session.get('current_fabric')
    if not current_fabric:
        return jsonify({'error': 'No fabric selected'}), 400

    fabric_data = fm.get_fabric_data(current_fabric)
    datasets = fabric_data.get('datasets', [])

    dataset = next((d for d in datasets if d.get('filename') == filename), None)
    if not dataset:
        return jsonify({'error': f'Dataset not found: {filename}'}), 404

    if request.method == 'GET':
        return jsonify({'success': True, 'dataset': dataset})

    # DELETE
    file_path = Path(dataset.get('path', ''))
    if file_path.exists():
        file_path.unlink()
        app.logger.info(f"Deleted file: {file_path}")

    datasets.remove(dataset)
    fabric_data['datasets'] = datasets
    fm.save_fabric_metadata(current_fabric, fabric_data)
    invalidate_fabric_cache(current_fabric)

    return jsonify({'success': True, 'message': f'Deleted {filename}'})

@app.route('/api/batch/delete-datasets', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
@handle_api_errors
def batch_delete_datasets():
    """Delete multiple datasets at once."""
    current_fabric = session.get('current_fabric')
    if not current_fabric:
        return jsonify({'error': 'No fabric selected'}), 400

    data = request.get_json()
    dataset_ids = data.get('dataset_ids', [])

    if not dataset_ids or not isinstance(dataset_ids, list):
        return jsonify({'error': 'dataset_ids must be a non-empty list'}), 400

    fabric_data = fm.get_fabric_data(current_fabric)
    datasets = fabric_data.get('datasets', [])

    deleted_count = 0
    errors = []

    for dataset_id in dataset_ids:
        try:
            # Find dataset by filename or index
            dataset_to_delete = None
            for idx, dataset in enumerate(datasets):
                if dataset.get('filename') == dataset_id or str(idx) == str(dataset_id):
                    dataset_to_delete = dataset
                    break

            if dataset_to_delete:
                # Delete file if exists
                file_path = Path(dataset_to_delete.get('path', ''))
                if file_path.exists():
                    file_path.unlink()
                    app.logger.info(f"Deleted file: {file_path}")

                # Remove from datasets list
                datasets.remove(dataset_to_delete)
                deleted_count += 1
            else:
                errors.append(f"Dataset not found: {dataset_id}")

        except Exception as e:
            app.logger.error(f"Error deleting dataset {dataset_id}: {str(e)}")
            errors.append(f"Error deleting {dataset_id}: {str(e)}")

    # Update fabric data
    fabric_data['datasets'] = datasets
    fm.save_fabric_metadata(current_fabric, fabric_data)

    # Invalidate cache
    invalidate_fabric_cache(current_fabric)

    return jsonify({
        'success': True,
        'deleted_count': deleted_count,
        'errors': errors,
        'message': f'Deleted {deleted_count} dataset(s)'
    })


@app.route('/api/batch/compare-fabrics', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per minute")
@handle_api_errors
def batch_compare_fabrics():
    """Compare multiple fabrics side-by-side."""
    data = request.get_json()
    fabric_names = data.get('fabrics', [])

    if not fabric_names or not isinstance(fabric_names, list) or len(fabric_names) < 2:
        return jsonify({'error': 'At least 2 fabric names required'}), 400

    if len(fabric_names) > 5:
        return jsonify({'error': 'Maximum 5 fabrics can be compared at once'}), 400

    comparison = {
        'fabrics': [],
        'summary': {
            'total_fabrics': len(fabric_names),
            'generated': datetime.now().isoformat()
        }
    }

    for fabric_name in fabric_names:
        try:
            fabric_name = validate_fabric_name(fabric_name)
            fabric_data = fm.get_fabric_data(fabric_name)
            analyzer = engine.ACIAnalyzer(fabric_data)
            analyzer._load_data()

            fabric_info = {
                'name': fabric_name,
                'stats': {
                    'leafs': len(analyzer._leafs),
                    'fexes': len(analyzer._fexes),
                    'tenants': len(analyzer._tenants),
                    'vrfs': len(analyzer._vrfs),
                    'bds': len(analyzer._bds),
                    'epgs': len(analyzer._epgs),
                    'contracts': len(analyzer._contracts),
                    'interfaces': len(analyzer._interfaces)
                },
                'datasets': len(fabric_data.get('datasets', []))
            }

            comparison['fabrics'].append(fabric_info)

        except Exception as e:
            app.logger.error(f"Error analyzing fabric {fabric_name}: {str(e)}")
            comparison['fabrics'].append({
                'name': fabric_name,
                'error': str(e)
            })

    return jsonify(comparison)


@app.route('/api/batch/export-reports', methods=['POST'])
@csrf.exempt
@limiter.limit("3 per minute")
@handle_api_errors
def batch_export_reports():
    """Generate reports for multiple fabrics in multiple formats."""
    data = request.get_json()
    fabric_names = data.get('fabrics', [])
    formats = data.get('formats', ['markdown', 'csv'])
    mode = 'migration'

    if not fabric_names or not isinstance(fabric_names, list):
        return jsonify({'error': 'fabric names required'}), 400

    if len(fabric_names) > 10:
        return jsonify({'error': 'Maximum 10 fabrics can be exported at once'}), 400

    # Validate formats
    valid_formats = ['markdown', 'csv', 'html', 'json']
    formats = [f for f in formats if f in valid_formats]
    if not formats:
        formats = ['markdown']

    results = {
        'generated_files': [],
        'errors': [],
        'timestamp': datetime.now().isoformat()
    }

    for fabric_name in fabric_names:
        try:
            fabric_name = validate_fabric_name(fabric_name)
            fabric_data = fm.get_fabric_data(fabric_name)

            for format_type in formats:
                try:
                    # Generate report
                    if format_type == 'markdown':
                        content = reporting.generate_markdown_report(fabric_data, mode)
                        filename = f'{fabric_name}_report.md'
                        mimetype = 'text/markdown'
                    elif format_type == 'csv':
                        content = reporting.generate_csv_report(fabric_data, mode)
                        filename = f'{fabric_name}_report.csv'
                        mimetype = 'text/csv'
                    elif format_type == 'html':
                        content = reporting.generate_html_report(fabric_data, mode)
                        filename = f'{fabric_name}_report.html'
                        mimetype = 'text/html'
                    elif format_type == 'json':
                        content = reporting.generate_json_report(fabric_data, mode)
                        filename = f'{fabric_name}_report.json'
                        mimetype = 'application/json'

                    # Save file
                    output_path = OUTPUT_DIR / filename
                    output_path.write_text(content, encoding='utf-8')

                    results['generated_files'].append({
                        'fabric': fabric_name,
                        'format': format_type,
                        'filename': filename,
                        'path': str(output_path),
                        'size_bytes': output_path.stat().st_size
                    })

                except Exception as e:
                    app.logger.error(f"Error generating {format_type} report for {fabric_name}: {str(e)}")
                    results['errors'].append({
                        'fabric': fabric_name,
                        'format': format_type,
                        'error': str(e)
                    })

        except Exception as e:
            app.logger.error(f"Error processing fabric {fabric_name}: {str(e)}")
            results['errors'].append({
                'fabric': fabric_name,
                'error': str(e)
            })

    return jsonify({
        'success': True,
        'total_files': len(results['generated_files']),
        'total_errors': len(results['errors']),
        'results': results
    })


@app.route('/api/cache/clear', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
@handle_api_errors
def clear_cache():
    """Clear all cache or cache for specific fabric."""
    data = request.get_json() or {}
    fabric_name = data.get('fabric')

    if fabric_name:
        # Clear cache for specific fabric
        fabric_name = validate_fabric_name(fabric_name)
        invalidate_fabric_cache(fabric_name)
        return jsonify({
            'success': True,
            'message': f'Cache cleared for fabric: {fabric_name}'
        })
    else:
        # Clear all cache
        cache.clear()
        return jsonify({
            'success': True,
            'message': 'All cache cleared'
        })


if __name__ == '__main__':
    import socket

    def _is_port_free(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return sock.connect_ex(('127.0.0.1', port)) != 0

    def _pick_port(start_port: int = 5001, max_tries: int = 50) -> int:
        for candidate in range(start_port, start_port + max_tries):
            if _is_port_free(candidate):
                return candidate
        return start_port

    selected_port = _pick_port(5001)
    print("=" * 70)
    print("ACI Migrator - Professional ACI Migration Tool")
    print(f"Version: {APP_VERSION}")
    print("=" * 70)
    print(f"Data directory: {DATA_DIR}")
    print(f"Fabrics directory: {FABRICS_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 70)
    print(f"Access the application at: http://0.0.0.0:{selected_port}")
    print("=" * 70)

    app.run(debug=True, host='0.0.0.0', port=selected_port, threaded=True)
