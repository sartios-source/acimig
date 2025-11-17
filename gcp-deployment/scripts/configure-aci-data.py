#!/usr/bin/env python3
"""
Configure ACI Test Data
Validates and enriches mock ACI data for comprehensive testing
"""

import json
import sys
import argparse
from typing import Dict, List, Any
from datetime import datetime


def validate_topology(data: Dict) -> List[str]:
    """Validate topology data"""
    errors = []

    # Check fabric
    if 'fabric' not in data:
        errors.append("Missing 'fabric' key")

    # Check topology
    if 'topology' in data:
        topo = data['topology']

        # Validate spines
        if 'spines' not in topo or len(topo['spines']) < 2:
            errors.append("Need at least 2 spine switches")

        # Validate leafs
        if 'leafs' not in topo or len(topo['leafs']) < 2:
            errors.append("Need at least 2 leaf switches")

        # Validate FEX
        if 'fex' in topo:
            for fex in topo['fex']:
                if 'parent_leaf' not in fex:
                    errors.append(f"FEX {fex.get('id')} missing parent_leaf")

    # Check tenants
    if 'tenants' not in data or len(data['tenants']) == 0:
        errors.append("Need at least 1 tenant")

    return errors


def analyze_test_scenarios(data: Dict) -> Dict[str, Any]:
    """Analyze data for test scenarios"""
    analysis = {
        'timestamp': datetime.utcnow().isoformat(),
        'topology_summary': {},
        'test_scenarios': {},
        'recommendations': []
    }

    # Topology summary
    if 'topology' in data:
        topo = data['topology']
        analysis['topology_summary'] = {
            'spines': len(topo.get('spines', [])),
            'leafs': len(topo.get('leafs', [])),
            'fex': len(topo.get('fex', []))
        }

    # Analyze EPG distribution
    epg_device_map = {}
    total_epgs = 0
    total_paths = 0

    for tenant in data.get('tenants', []):
        for ap in tenant.get('application_profiles', []):
            for epg in ap.get('epgs', []):
                total_epgs += 1
                epg_name = f"{tenant['name']}/{ap['name']}/{epg['name']}"

                devices = set()
                fex_count = 0
                leaf_count = 0

                for path in epg.get('paths', []):
                    total_paths += 1
                    if 'fex' in path:
                        devices.add(f"FEX-{path['fex']}")
                        fex_count += 1
                    else:
                        devices.add(f"Leaf-{path['leaf']}")
                        leaf_count += 1

                epg_device_map[epg_name] = {
                    'devices': list(devices),
                    'device_count': len(devices),
                    'fex_count': fex_count,
                    'leaf_count': leaf_count,
                    'total_paths': len(epg.get('paths', []))
                }

    analysis['epg_distribution'] = epg_device_map
    analysis['statistics'] = {
        'total_tenants': len(data.get('tenants', [])),
        'total_epgs': total_epgs,
        'total_paths': total_paths
    }

    # Identify test scenarios
    scenarios = {}

    # High coupling scenarios (EPG on multiple devices)
    high_coupling = [
        epg for epg, info in epg_device_map.items()
        if info['device_count'] > 1
    ]
    scenarios['high_coupling'] = {
        'count': len(high_coupling),
        'epgs': high_coupling[:5]  # Top 5
    }

    # FEX-heavy scenarios
    fex_heavy = [
        epg for epg, info in epg_device_map.items()
        if info['fex_count'] > 0
    ]
    scenarios['fex_usage'] = {
        'count': len(fex_heavy),
        'epgs': fex_heavy[:5]
    }

    # Multi-path scenarios
    multi_path = [
        epg for epg, info in epg_device_map.items()
        if info['total_paths'] >= 3
    ]
    scenarios['multi_path'] = {
        'count': len(multi_path),
        'epgs': multi_path[:5]
    }

    analysis['test_scenarios'] = scenarios

    # Generate recommendations
    if len(high_coupling) > 0:
        analysis['recommendations'].append({
            'type': 'coupling_analysis',
            'message': f'{len(high_coupling)} EPGs span multiple devices - good for testing coupling detection'
        })

    if len(fex_heavy) > 0:
        analysis['recommendations'].append({
            'type': 'fex_consolidation',
            'message': f'{len(fex_heavy)} EPGs use FEX - good for testing FEX consolidation'
        })

    return analysis


def export_for_migrator(data: Dict, output_file: str):
    """Export data in format for ACI Migrator"""
    print(f"Exporting data to {output_file}...")

    # Create migrator-compatible format
    migrator_data = {
        'fabric': {
            'name': data['fabric']['name'],
            'version': data['fabric']['apic_version'],
            'import_timestamp': datetime.utcnow().isoformat()
        },
        'devices': [],
        'epg_mappings': []
    }

    # Export devices
    for leaf in data['topology']['leafs']:
        migrator_data['devices'].append({
            'device_id': str(leaf['id']),
            'device_name': leaf['name'],
            'device_type': 'leaf',
            'model': leaf['model']
        })

    for fex in data['topology']['fex']:
        migrator_data['devices'].append({
            'device_id': fex['id'],
            'device_name': fex['name'],
            'device_type': 'fex',
            'model': fex['model'],
            'parent_leaf': str(fex['parent_leaf'])
        })

    # Export EPG mappings
    for tenant in data['tenants']:
        for ap in tenant['application_profiles']:
            for epg in ap['epgs']:
                devices = set()
                vlans = set()

                for path in epg['paths']:
                    if 'fex' in path:
                        devices.add(path['fex'])
                    else:
                        devices.add(str(path['leaf']))
                    vlans.add(str(path['vlan']))

                migrator_data['epg_mappings'].append({
                    'tenant': tenant['name'],
                    'application_profile': ap['name'],
                    'epg': epg['name'],
                    'vlans': sorted(list(vlans)),
                    'devices': sorted(list(devices)),
                    'total_paths': len(epg['paths'])
                })

    # Write to file
    with open(output_file, 'w') as f:
        json.dump(migrator_data, f, indent=2)

    print(f"Exported {len(migrator_data['devices'])} devices and {len(migrator_data['epg_mappings'])} EPG mappings")


def main():
    parser = argparse.ArgumentParser(description='Configure and validate ACI test data')
    parser.add_argument('--input', required=True, help='Input topology JSON file')
    parser.add_argument('--analyze', action='store_true', help='Analyze test scenarios')
    parser.add_argument('--export', help='Export for ACI Migrator (output file)')
    parser.add_argument('--output', help='Output analysis to JSON file')

    args = parser.parse_args()

    # Load input data
    try:
        with open(args.input, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading input file: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate
    print("Validating topology...")
    errors = validate_topology(data)

    if errors:
        print("\nValidation errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print("Validation passed!")

    # Analyze
    if args.analyze or args.output:
        print("\nAnalyzing test scenarios...")
        analysis = analyze_test_scenarios(data)

        print(f"\nTopology Summary:")
        for key, value in analysis['topology_summary'].items():
            print(f"  {key}: {value}")

        print(f"\nStatistics:")
        for key, value in analysis['statistics'].items():
            print(f"  {key}: {value}")

        print(f"\nTest Scenarios:")
        for scenario, info in analysis['test_scenarios'].items():
            print(f"  {scenario}: {info['count']} EPGs")

        print(f"\nRecommendations:")
        for rec in analysis['recommendations']:
            print(f"  - [{rec['type']}] {rec['message']}")

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(analysis, f, indent=2)
            print(f"\nAnalysis saved to {args.output}")

    # Export
    if args.export:
        export_for_migrator(data, args.export)

    print("\nConfiguration complete!")


if __name__ == '__main__':
    main()
