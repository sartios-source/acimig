#!/usr/bin/env python3
"""
Test script to verify all 16 analysis engine methods work correctly.
"""

import sys
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from analysis import engine

def load_sample_data():
    """Load sample data for testing."""
    sample_file = Path('data/samples/sample_large_scale.json')
    if not sample_file.exists():
        print(f"ERROR: Sample file not found: {sample_file}")
        return None

    with open(sample_file, 'r') as f:
        objects = json.load(f)

    return {
        'datasets': [{
            'type': 'aci_json',
            'name': 'sample_large_scale.json',
            'objects': objects
        }]
    }

def test_analysis_methods():
    """Test all 16 analysis methods."""
    print("="*70)
    print("TESTING ACI ANALYSIS ENGINE")
    print("="*70)

    # Load sample data
    print("\n1. Loading sample data...")
    fabric_data = load_sample_data()
    if not fabric_data:
        return False

    print(f"   Loaded {len(fabric_data['datasets'][0]['objects'])} objects")

    # Initialize analyzer
    print("\n2. Initializing analyzer...")
    try:
        analyzer = engine.ACIAnalyzer(fabric_data)
        print("   Analyzer initialized successfully")
    except Exception as e:
        print(f"   ERROR: Failed to initialize analyzer: {e}")
        return False

    # Test each method
    methods = [
        ('analyze_port_utilization', 'Port Utilization Statistics'),
        ('analyze_leaf_fex_mapping', 'Leaf-to-FEX Mapping'),
        ('analyze_rack_grouping', 'Rack-Level Grouping'),
        ('analyze_bd_epg_mapping', 'BD/EPG/VRF Mapping'),
        ('analyze_vlan_distribution', 'VLAN Distribution'),
        ('analyze_epg_complexity', 'EPG Complexity Scoring'),
        ('analyze_vpc_symmetry', 'vPC Symmetry'),
        ('analyze_pdom', 'Physical Domain Analysis'),
        ('analyze_migration_flags', 'Migration Flags'),
        ('analyze_contract_scope', 'Contract Scope'),
        ('analyze_vlan_spread', 'Multi-EPG VLAN Spread'),
        ('analyze_cmdb_correlation', 'CMDB Correlation'),
        ('analyze_coupling_issues', 'Coupling Issues'),
        ('analyze_migration_waves', 'Migration Waves'),
        ('analyze_vlan_sharing_detailed', 'VLAN Sharing'),
        ('get_visualization_data', 'Visualization Data'),
    ]

    print(f"\n3. Testing {len(methods)} analysis methods...\n")

    results = []
    for method_name, description in methods:
        try:
            method = getattr(analyzer, method_name)
            result = method()
            status = "PASS"
            error = None

            # Basic validation
            if result is None:
                status = "WARN"
                error = "Returned None"
            elif isinstance(result, dict) and len(result) == 0:
                status = "WARN"
                error = "Returned empty dict"
            elif isinstance(result, list) and len(result) == 0:
                status = "WARN"
                error = "Returned empty list"

        except Exception as e:
            status = "FAIL"
            error = str(e)
            result = None

        results.append({
            'method': method_name,
            'description': description,
            'status': status,
            'error': error
        })

        # Print result
        status_symbol = {
            'PASS': '[OK]',
            'WARN': '[WARN]',
            'FAIL': '[FAIL]'
        }[status]

        print(f"   {status_symbol} {description:.<50} {status}")
        if error:
            print(f"        Error: {error}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    passed = sum(1 for r in results if r['status'] == 'PASS')
    warned = sum(1 for r in results if r['status'] == 'WARN')
    failed = sum(1 for r in results if r['status'] == 'FAIL')

    print(f"\nTotal methods tested: {len(methods)}")
    print(f"  PASSED: {passed}")
    print(f"  WARNED: {warned}")
    print(f"  FAILED: {failed}")

    if failed > 0:
        print("\nFAILURES:")
        for r in results:
            if r['status'] == 'FAIL':
                print(f"  - {r['description']}: {r['error']}")

    if warned > 0:
        print("\nWARNINGS:")
        for r in results:
            if r['status'] == 'WARN':
                print(f"  - {r['description']}: {r['error']}")

    print("\n" + "="*70)

    if failed == 0:
        print("RESULT: ALL TESTS PASSED!")
        return True
    else:
        print("RESULT: SOME TESTS FAILED")
        return False

if __name__ == '__main__':
    success = test_analysis_methods()
    sys.exit(0 if success else 1)
