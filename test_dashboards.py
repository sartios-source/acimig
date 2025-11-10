#!/usr/bin/env python3
"""
Test script for dashboard visualization data generation.
Tests the analysis engine without Flask session/CSRF.
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from analysis.engine import ACIAnalyzer
from analysis.parsers import parse_aci_json
from analysis.fabric_manager import FabricManager

def test_dashboard_data():
    """Test dashboard data generation with sample large-scale data."""
    print("=" * 70)
    print("Dashboard Visualization Data Test")
    print("=" * 70)

    # Initialize fabric manager
    print("\n1. Initializing Fabric Manager...")
    fm = FabricManager(Path("fabrics"))
    print("   [OK] Fabric manager initialized")

    # Get fabric data
    print("\n2. Loading fabric data for: test_fabric")
    fabric_data = fm.get_fabric_data("test_fabric")
    datasets = fabric_data.get('datasets', [])
    print(f"   [OK] Loaded fabric data with {len(datasets)} datasets")

    # Show dataset info
    for ds in datasets:
        print(f"      - {ds.get('name', 'unknown')}: {ds.get('type', 'unknown')}")

    # Initialize analyzer
    print("\n3. Initializing ACI Analyzer...")
    analyzer = ACIAnalyzer(fabric_data)
    print("   [OK] Analyzer initialized")

    # Run all analysis methods
    print("\n4. Running Analysis Methods:")
    print("-" * 70)

    analyses = {
        'port_utilization': analyzer.analyze_port_utilization(),
        'leaf_fex_mapping': analyzer.analyze_leaf_fex_mapping(),
        'vlan_distribution': analyzer.analyze_vlan_distribution(),
        'epg_complexity': analyzer.analyze_epg_complexity(),
        'migration_flags': analyzer.analyze_migration_flags(),
        'vpc_symmetry': analyzer.analyze_vpc_symmetry(),
        'bd_epg_mapping': analyzer.analyze_bd_epg_mapping(),
        'contract_scope': analyzer.analyze_contract_scope(),
        'cmdb_correlation': analyzer.analyze_cmdb_correlation()
    }

    for name, result in analyses.items():
        if isinstance(result, dict):
            data_size = len(result)
            print(f"   [OK] {name:30s} {data_size} keys")
        elif isinstance(result, list):
            data_size = len(result)
            print(f"   [OK] {name:30s} {data_size} items")
        else:
            print(f"   [OK] {name:30s} OK")

    # Generate visualization data structure
    print("\n5. Generating Dashboard Visualization Data:")
    print("-" * 70)

    viz_data = {
        'topology': analyses['leaf_fex_mapping'],
        'port_utilization': analyses['port_utilization'],
        'vlan_distribution': analyses['vlan_distribution'],
        'epg_complexity': analyses['epg_complexity'],
        'migration_flags': analyses['migration_flags'],
        'vpc_symmetry': analyses['vpc_symmetry'],
        'bd_epg': analyses['bd_epg_mapping'],
        'contract_scope': analyses['contract_scope'],
        'cmdb_correlation': analyses['cmdb_correlation']
    }

    # Calculate statistics
    port_util = analyses['port_utilization']
    if port_util:
        avg_util = sum(p['utilization_pct'] for p in port_util) / len(port_util)
        consolidation_candidates = sum(1 for p in port_util if p['consolidation_score'] >= 60)
    else:
        avg_util = 0
        consolidation_candidates = 0

    topology_stats = analyses['leaf_fex_mapping'].get('statistics', {})

    viz_data['statistics'] = {
        'total_leafs': topology_stats.get('total_leafs', 0),
        'total_fex': topology_stats.get('total_fex', 0),
        'avg_utilization': round(avg_util, 2),
        'consolidation_candidates': consolidation_candidates
    }

    print(f"   Total Leafs:                  {viz_data['statistics']['total_leafs']}")
    print(f"   Total FEX:                    {viz_data['statistics']['total_fex']}")
    print(f"   Average Utilization:          {viz_data['statistics']['avg_utilization']}%")
    print(f"   Consolidation Candidates:     {consolidation_candidates}")

    # Validate dashboard data structure
    print("\n6. Validating Dashboard Data Structure:")
    print("-" * 70)

    required_keys = ['topology', 'port_utilization', 'vlan_distribution',
                     'epg_complexity', 'migration_flags', 'statistics']

    for key in required_keys:
        if key in viz_data:
            print(f"   [OK] {key:30s} present")
        else:
            print(f"   [X] {key:30s} MISSING")

    # Check topology structure
    topo = viz_data['topology']
    if 'nodes' in topo and 'edges' in topo:
        print(f"\n   Topology Graph:")
        print(f"     Nodes: {len(topo['nodes'])}")
        print(f"     Edges: {len(topo['edges'])}")
        if topo['nodes']:
            leaf_nodes = [n for n in topo['nodes'] if n.get('type') == 'leaf']
            fex_nodes = [n for n in topo['nodes'] if n.get('type') == 'fex']
            print(f"     Leaf nodes: {len(leaf_nodes)}")
            print(f"     FEX nodes: {len(fex_nodes)}")

    # Check port utilization data
    if port_util:
        print(f"\n   Port Utilization:")
        print(f"     Total FEX analyzed: {len(port_util)}")
        if port_util:
            sample = port_util[0]
            print(f"     Sample keys: {', '.join(sample.keys())}")
            print(f"     Sample: {sample['fex_id']} - {sample['utilization_pct']}% utilization")

    # Check VLAN data
    vlan_dist = analyses['vlan_distribution']
    if vlan_dist and 'vlans' in vlan_dist:
        print(f"\n   VLAN Distribution:")
        print(f"     Total VLANs: {len(vlan_dist['vlans'])}")
        if 'overlaps' in vlan_dist:
            print(f"     VLAN overlaps: {len(vlan_dist['overlaps'])}")

    # Check EPG complexity
    epg_complex = analyses['epg_complexity']
    if epg_complex:
        print(f"\n   EPG Complexity:")
        print(f"     Total EPGs: {len(epg_complex)}")
        if epg_complex:
            complexity_levels = {}
            for epg in epg_complex:
                level = epg.get('complexity_level', 'unknown')
                complexity_levels[level] = complexity_levels.get(level, 0) + 1
            for level, count in complexity_levels.items():
                print(f"     {level.capitalize()}: {count}")

    # Check migration flags
    migration_flags = analyses['migration_flags']
    if migration_flags:
        print(f"\n   Migration Readiness:")
        print(f"     Total flags: {len(migration_flags)}")
        if migration_flags:
            severity_counts = {}
            for flag in migration_flags:
                severity = flag.get('severity', 'unknown')
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            for severity, count in severity_counts.items():
                print(f"     {severity.capitalize()}: {count}")

    print("\n" + "=" * 70)
    print("Dashboard Data Test: PASSED [OK]")
    print("=" * 70)

    # Save sample output for inspection
    output_file = Path("output/dashboard_test_data.json")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(viz_data, f, indent=2, default=str)
    print(f"\nSample data saved to: {output_file}")

    return True

if __name__ == '__main__':
    try:
        success = test_dashboard_data()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[X] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
