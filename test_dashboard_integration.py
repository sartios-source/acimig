#!/usr/bin/env python3
"""
Test dashboard integration with real data to ensure visualization works.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import app
from analysis import fabric_manager, engine

def test_dashboard_with_data():
    """Test dashboard rendering with actual fabric data."""
    print("="*70)
    print("TESTING DASHBOARD INTEGRATION")
    print("="*70)

    # Create test client
    client = app.test_client()
    app.config['TESTING'] = True

    # Initialize fabric manager
    fm = fabric_manager.FabricManager('fabrics')

    # Check if test fabric exists
    fabrics = fm.list_fabrics()
    test_fabric = None

    for f in fabrics:
        if f['name'] == 'test_fabric':
            test_fabric = f
            break

    if not test_fabric:
        print("\nNo test_fabric found. Creating one with sample data...")
        try:
            fm.create_fabric('test_fabric')

            # Load sample data
            sample_file = Path('data/samples/sample_aci.json')
            if sample_file.exists():
                with open(sample_file, 'r') as f:
                    objects = json.load(f)

                fm.add_dataset('test_fabric', {
                    'type': 'aci_json',
                    'name': 'sample_aci.json',
                    'objects': objects,
                    'path': str(sample_file)
                })
                print(f"   Created test_fabric with {len(objects)} objects")
            else:
                print(f"   ERROR: Sample file not found: {sample_file}")
                return False
        except Exception as e:
            print(f"   ERROR creating test fabric: {e}")
            return False

    print("\n1. Testing with fabric: test_fabric")

    # Set session to use test fabric
    with client.session_transaction() as sess:
        sess['current_fabric'] = 'test_fabric'
        sess['mode'] = 'offboard'

    tests = []

    # Test visualize page
    print("\n2. Testing visualize page with data...")
    try:
        response = client.get('/visualize')
        status = 'PASS' if response.status_code == 200 else 'FAIL'
        error = None if status == 'PASS' else f'Status code: {response.status_code}'

        # Check if required elements are in response
        if status == 'PASS':
            html = response.data.decode('utf-8')

            checks = [
                ('Chart.js CDN', 'chart.js' in html.lower()),
                ('D3.js CDN', 'd3js.org' in html or 'd3.v7' in html),
                ('Dashboard tabs', 'dashboard-tabs' in html or 'tab' in html.lower()),
                ('Dashboards JS', 'dashboards.js' in html),
                ('Visualization data', 'viz-data' in html or 'vizData' in html),
            ]

            for check_name, check_result in checks:
                check_status = 'PASS' if check_result else 'FAIL'
                tests.append({
                    'name': f'Visualize - {check_name}',
                    'status': check_status
                })
                symbol = '[OK]' if check_result else '[FAIL]'
                print(f"   {symbol} {check_name}")

                if not check_result and status == 'PASS':
                    status = 'WARN'
                    error = f'Missing: {check_name}'

    except Exception as e:
        status = 'FAIL'
        error = str(e)
        print(f"   [FAIL] Exception: {e}")

    tests.append({
        'name': 'Visualize page rendering',
        'status': status,
        'error': error
    })

    # Test analyze page
    print("\n3. Testing analyze page with data...")
    try:
        response = client.get('/analyze')
        status = 'PASS' if response.status_code == 200 else 'FAIL'
        error = None if status == 'PASS' else f'Status code: {response.status_code}'

        if status == 'PASS':
            html = response.data.decode('utf-8')

            checks = [
                ('Upload JS', 'upload.js' in html),
                ('Drop zone', 'drop-zone' in html or 'drag' in html.lower()),
                ('Dataset list', 'dataset' in html.lower()),
            ]

            for check_name, check_result in checks:
                check_status = 'PASS' if check_result else 'FAIL'
                tests.append({
                    'name': f'Analyze - {check_name}',
                    'status': check_status
                })
                symbol = '[OK]' if check_result else '[FAIL]'
                print(f"   {symbol} {check_name}")

    except Exception as e:
        status = 'FAIL'
        error = str(e)
        print(f"   [FAIL] Exception: {e}")

    tests.append({
        'name': 'Analyze page rendering',
        'status': status,
        'error': error
    })

    # Test API endpoint
    print("\n4. Testing analysis API endpoint...")
    try:
        response = client.get('/api/analysis/port_utilization')
        status = 'PASS' if response.status_code == 200 else 'FAIL'

        if status == 'PASS':
            try:
                data = json.loads(response.data)
                has_data = isinstance(data, (dict, list))
                api_status = 'PASS' if has_data else 'WARN'
                print(f"   [OK] API returned valid JSON")
            except:
                api_status = 'FAIL'
                print(f"   [FAIL] API returned invalid JSON")
        else:
            api_status = 'FAIL'
            print(f"   [FAIL] Status code: {response.status_code}")

        tests.append({
            'name': 'API analysis endpoint',
            'status': api_status
        })

    except Exception as e:
        tests.append({
            'name': 'API analysis endpoint',
            'status': 'FAIL',
            'error': str(e)
        })
        print(f"   [FAIL] Exception: {e}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    passed = sum(1 for t in tests if t['status'] == 'PASS')
    warned = sum(1 for t in tests if t['status'] == 'WARN')
    failed = sum(1 for t in tests if t['status'] == 'FAIL')

    print(f"\nTotal tests: {len(tests)}")
    print(f"  PASSED: {passed}")
    print(f"  WARNED: {warned}")
    print(f"  FAILED: {failed}")

    if failed > 0:
        print("\nFAILURES:")
        for t in tests:
            if t['status'] == 'FAIL':
                error_msg = t.get('error', 'Unknown error')
                print(f"  - {t['name']}: {error_msg}")

    print("\n" + "="*70)

    if failed == 0:
        print("RESULT: DASHBOARD INTEGRATION TESTS PASSED!")
        return True
    else:
        print("RESULT: SOME DASHBOARD TESTS FAILED")
        return False

if __name__ == '__main__':
    success = test_dashboard_with_data()
    sys.exit(0 if success else 1)
