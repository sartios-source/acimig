#!/usr/bin/env python3
"""
Test script to verify all Flask routes are accessible and return expected responses.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app import app

def test_routes():
    """Test all application routes."""
    print("="*70)
    print("TESTING FLASK ROUTES")
    print("="*70)

    # Create test client
    client = app.test_client()
    app.config['TESTING'] = True

    # Define routes to test
    routes = [
        # GET routes
        ('GET', '/', 200, 'Index/Home'),
        ('GET', '/health', 200, 'Health Check'),
        ('GET', '/analyze', 200, 'Analyze Page'),
        ('GET', '/visualize', 200, 'Visualize Page'),
        ('GET', '/plan', 200, 'Plan Page'),
        ('GET', '/report', 200, 'Report Page'),
        ('GET', '/evpn_migration', 200, 'EVPN Migration Page'),
        ('GET', '/help', 200, 'Help Page'),
        ('GET', '/fabrics', 200, 'List Fabrics API'),
        ('GET', '/set_mode/offboard', 302, 'Set Mode Offboard (redirect)'),
        ('GET', '/set_mode/onboard', 302, 'Set Mode Onboard (redirect)'),
        ('GET', '/set_mode/evpn', 302, 'Set Mode EVPN (redirect)'),

        # Static files
        ('GET', '/static/styles.css', 200, 'CSS File'),
        ('GET', '/static/app.js', 200, 'App JS File'),
        ('GET', '/static/dashboards.js', 200, 'Dashboards JS File'),
        ('GET', '/static/upload.js', 200, 'Upload JS File'),
    ]

    print(f"\nTesting {len(routes)} routes...\n")

    results = []
    for method, route, expected_status, description in routes:
        try:
            if method == 'GET':
                response = client.get(route, follow_redirects=False)
            elif method == 'POST':
                response = client.post(route)
            else:
                response = None
                status = 'SKIP'
                error = f'Unsupported method: {method}'

            if response:
                status_code = response.status_code
                if status_code == expected_status:
                    status = 'PASS'
                    error = None
                else:
                    status = 'FAIL'
                    error = f'Expected {expected_status}, got {status_code}'
        except Exception as e:
            status = 'FAIL'
            error = str(e)
            status_code = None

        results.append({
            'route': route,
            'description': description,
            'status': status,
            'status_code': status_code,
            'expected': expected_status,
            'error': error
        })

        # Print result
        status_symbol = {
            'PASS': '[OK]',
            'FAIL': '[FAIL]',
            'SKIP': '[SKIP]'
        }[status]

        route_display = f"{method} {route}"
        print(f"   {status_symbol} {description:.<40} {route_display}")
        if error:
            print(f"        Error: {error}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    skipped = sum(1 for r in results if r['status'] == 'SKIP')

    print(f"\nTotal routes tested: {len(routes)}")
    print(f"  PASSED: {passed}")
    print(f"  FAILED: {failed}")
    print(f"  SKIPPED: {skipped}")

    if failed > 0:
        print("\nFAILURES:")
        for r in results:
            if r['status'] == 'FAIL':
                print(f"  - {r['description']} ({r['route']}): {r['error']}")

    print("\n" + "="*70)

    if failed == 0:
        print("RESULT: ALL ROUTE TESTS PASSED!")
        return True
    else:
        print("RESULT: SOME ROUTE TESTS FAILED")
        return False

if __name__ == '__main__':
    success = test_routes()
    sys.exit(0 if success else 1)
