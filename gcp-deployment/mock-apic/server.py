#!/usr/bin/env python3
"""
Mock APIC Server for ACI Migrator POC
Simulates Cisco APIC REST API for testing purposes
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import secrets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# In-memory session storage
sessions = {}

# Load mock data
def load_mock_data():
    """Load mock ACI data from JSON file"""
    try:
        with open('/opt/mock-apic/mock_data.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load mock data: {e}")
        return generate_default_data()

def generate_default_data():
    """Generate default mock data if file doesn't exist"""
    return {
        "fabric": {
            "name": "ACI-POC-Fabric",
            "apic_version": "5.2(4e)",
            "fabric_id": 1
        },
        "nodes": [],
        "tenants": [],
        "contracts": [],
        "filters": []
    }

# Global data store
mock_data = load_mock_data()

def generate_token():
    """Generate a session token"""
    return secrets.token_urlsafe(32)

def create_session(username: str):
    """Create a new session"""
    token = generate_token()
    sessions[token] = {
        "username": username,
        "created": datetime.utcnow(),
        "expires": datetime.utcnow() + timedelta(hours=8)
    }
    return token

def validate_session(token: str) -> bool:
    """Validate a session token"""
    if token not in sessions:
        return False

    session = sessions[token]
    if datetime.utcnow() > session["expires"]:
        del sessions[token]
        return False

    return True

def get_token_from_request():
    """Extract token from request"""
    # Check cookie
    token = request.cookies.get('APIC-cookie')
    if token:
        return token

    # Check header
    token = request.headers.get('DevCookie')
    if token:
        return token

    return None

def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()
        if not token or not validate_session(token):
            return jsonify({
                "error": {
                    "code": "401",
                    "text": "Token was invalid"
                }
            }), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Helper functions to format responses like real APIC
def format_class_response(class_name: str, objects: List[Dict]) -> Dict:
    """Format response in APIC class query format"""
    return {
        "totalCount": str(len(objects)),
        "imdata": [
            {class_name: {"attributes": obj}} for obj in objects
        ]
    }

def format_mo_response(class_name: str, obj: Dict) -> Dict:
    """Format response for MO query"""
    return {
        "totalCount": "1",
        "imdata": [
            {class_name: {"attributes": obj}}
        ]
    }

# Authentication endpoints
@app.route('/api/aaaLogin.json', methods=['POST'])
def login():
    """Handle APIC login"""
    try:
        data = request.get_json()

        if not data or 'aaaUser' not in data:
            return jsonify({
                "error": {
                    "code": "400",
                    "text": "Invalid request format"
                }
            }), 400

        username = data['aaaUser']['attributes'].get('name')
        password = data['aaaUser']['attributes'].get('pwd')

        # Simple authentication (admin/C1sco12345 or any user for POC)
        if not username or not password:
            return jsonify({
                "error": {
                    "code": "401",
                    "text": "Username and password required"
                }
            }), 401

        # Create session
        token = create_session(username)

        response = make_response(jsonify({
            "totalCount": "1",
            "imdata": [{
                "aaaLogin": {
                    "attributes": {
                        "token": token,
                        "siteFingerprint": "mock-fingerprint",
                        "refreshTimeoutSeconds": "600",
                        "maximumLifetimeSeconds": "28800",
                        "guiIdleTimeoutSeconds": "1200",
                        "restTimeoutSeconds": "90",
                        "creationTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
                        "firstLoginTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
                        "userName": username,
                        "remoteUser": "false",
                        "version": "5.2(4e)",
                        "buildTime": "2023-01-15T10:00:00.000+00:00"
                    }
                }
            }]
        }))

        # Set cookie
        response.set_cookie(
            'APIC-cookie',
            value=token,
            max_age=28800,
            httponly=True,
            samesite='Lax'
        )

        logger.info(f"User {username} logged in successfully")
        return response

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            "error": {
                "code": "500",
                "text": str(e)
            }
        }), 500

@app.route('/api/aaaRefresh.json', methods=['GET'])
@require_auth
def refresh():
    """Refresh authentication token"""
    token = get_token_from_request()
    session = sessions[token]

    # Extend session
    session['expires'] = datetime.utcnow() + timedelta(hours=8)

    return jsonify({
        "totalCount": "1",
        "imdata": [{
            "aaaLogin": {
                "attributes": {
                    "token": token,
                    "refreshTimeoutSeconds": "600",
                    "maximumLifetimeSeconds": "28800"
                }
            }
        }]
    })

@app.route('/api/aaaLogout.json', methods=['POST'])
def logout():
    """Handle logout"""
    token = get_token_from_request()
    if token and token in sessions:
        del sessions[token]

    return jsonify({
        "totalCount": "0",
        "imdata": []
    })

# Fabric topology queries
@app.route('/api/class/fabricNode.json', methods=['GET'])
@require_auth
def get_fabric_nodes():
    """Get all fabric nodes"""
    nodes = mock_data.get('nodes', [])
    return jsonify(format_class_response('fabricNode', nodes))

@app.route('/api/class/fabricPathEp.json', methods=['GET'])
@require_auth
def get_fabric_paths():
    """Get all fabric paths (interfaces)"""
    paths = mock_data.get('paths', [])
    return jsonify(format_class_response('fabricPathEp', paths))

@app.route('/api/class/fabricLink.json', methods=['GET'])
@require_auth
def get_fabric_links():
    """Get all fabric links"""
    links = mock_data.get('links', [])
    return jsonify(format_class_response('fabricLink', links))

@app.route('/api/class/fvTenant.json', methods=['GET'])
@require_auth
def get_tenants():
    """Get all tenants"""
    tenants = mock_data.get('tenants', [])
    return jsonify(format_class_response('fvTenant', tenants))

@app.route('/api/class/fvAEPg.json', methods=['GET'])
@require_auth
def get_epgs():
    """Get all EPGs"""
    epgs = mock_data.get('epgs', [])
    return jsonify(format_class_response('fvAEPg', epgs))

@app.route('/api/class/fvBD.json', methods=['GET'])
@require_auth
def get_bridge_domains():
    """Get all Bridge Domains"""
    bds = mock_data.get('bridge_domains', [])
    return jsonify(format_class_response('fvBD', bds))

@app.route('/api/class/fvCtx.json', methods=['GET'])
@require_auth
def get_vrfs():
    """Get all VRFs"""
    vrfs = mock_data.get('vrfs', [])
    return jsonify(format_class_response('fvCtx', vrfs))

@app.route('/api/class/fvRsPathAtt.json', methods=['GET'])
@require_auth
def get_epg_paths():
    """Get EPG to path attachments"""
    paths = mock_data.get('epg_paths', [])
    return jsonify(format_class_response('fvRsPathAtt', paths))

@app.route('/api/class/vzBrCP.json', methods=['GET'])
@require_auth
def get_contracts():
    """Get all contracts"""
    contracts = mock_data.get('contracts', [])
    return jsonify(format_class_response('vzBrCP', contracts))

@app.route('/api/class/vzFilter.json', methods=['GET'])
@require_auth
def get_filters():
    """Get all filters"""
    filters = mock_data.get('filters', [])
    return jsonify(format_class_response('vzFilter', filters))

@app.route('/api/class/l3extOut.json', methods=['GET'])
@require_auth
def get_l3outs():
    """Get all L3Outs"""
    l3outs = mock_data.get('l3outs', [])
    return jsonify(format_class_response('l3extOut', l3outs))

@app.route('/api/class/fvAp.json', methods=['GET'])
@require_auth
def get_application_profiles():
    """Get all Application Profiles"""
    aps = mock_data.get('application_profiles', [])
    return jsonify(format_class_response('fvAp', aps))

# Health and status endpoints
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Mock APIC Server",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/api/class/topSystem.json', methods=['GET'])
@require_auth
def get_system_info():
    """Get system information"""
    system_info = [{
        "dn": "topology/pod-1/node-1/sys",
        "address": "10.0.1.10",
        "name": "apic1",
        "role": "controller",
        "state": "in-service",
        "version": mock_data['fabric']['apic_version'],
        "fabricId": str(mock_data['fabric']['fabric_id'])
    }]
    return jsonify(format_class_response('topSystem', system_info))

# Generic class query handler for any other classes
@app.route('/api/class/<class_name>.json', methods=['GET'])
@require_auth
def generic_class_query(class_name):
    """Generic handler for any class queries"""
    logger.info(f"Generic class query: {class_name}")

    # Return empty result for unknown classes
    return jsonify(format_class_response(class_name, []))

# MO query handler
@app.route('/api/mo/<path:dn>.json', methods=['GET'])
@require_auth
def managed_object_query(dn):
    """Query for specific managed object by DN"""
    logger.info(f"MO query: {dn}")

    # Simple implementation - return empty for now
    return jsonify({
        "totalCount": "0",
        "imdata": []
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": {
            "code": "404",
            "text": "Resource not found"
        }
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({
        "error": {
            "code": "500",
            "text": "Internal server error"
        }
    }), 500

if __name__ == '__main__':
    logger.info("Starting Mock APIC Server")
    logger.info("Listening on 0.0.0.0:443 (HTTPS)")

    # For production, use proper SSL certificates
    # For POC, we'll use self-signed cert generated by setup script
    app.run(
        host='0.0.0.0',
        port=443,
        ssl_context=('/opt/mock-apic/cert.pem', '/opt/mock-apic/key.pem'),
        debug=False
    )
