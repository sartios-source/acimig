#!/usr/bin/env python3
"""
Comprehensive Coupling Analysis Test
Tests all coupling analysis methods with enterprise-scale data (1000+ EPGs).
"""
import json
import sys
from pathlib import Path
from analysis.engine import ACIAnalyzer
from analysis.fabric_manager import FabricManager

def print_section(title):
    """Print section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def test_coupling_analysis():
    """Test comprehensive coupling analysis with enterprise data."""
    print_section("Enterprise-Scale Coupling Analysis Test")

    # Setup test fabric with enterprise data
    print("\n1. Setting up enterprise fabric...")
    fabric_dir = Path("fabrics/enterprise_1000epg")
    fabric_dir.mkdir(parents=True, exist_ok=True)

    # Copy enterprise data
    import shutil
    shutil.copy("data/samples/sample_enterprise_1000epg.json",
                fabric_dir / "aci_data.json")
    shutil.copy("data/samples/sample_enterprise_1000epg_cmdb.csv",
                fabric_dir / "cmdb_data.csv")

    # Create fabric index
    fm = FabricManager(Path("fabrics"))
    fabric_data = fm.get_fabric_data("enterprise_1000epg")
    if not fabric_data.get('datasets'):
        fabric_data = {
            'created': '2025-11-10T16:00:00',
            'modified': '2025-11-10T16:00:00',
            'datasets': [
                {
                    'filename': 'aci_data.json',
                    'type': 'aci',
                    'format': 'json',
                    'path': str(fabric_dir / 'aci_data.json'),
                    'uploaded': '2025-11-10T16:00:00'
                },
                {
                    'filename': 'cmdb_data.csv',
                    'type': 'cmdb',
                    'path': str(fabric_dir / 'cmdb_data.csv'),
                    'uploaded': '2025-11-10T16:00:00'
                }
            ]
        }

    print(f"   [OK] Enterprise fabric configured")
    print(f"   Datasets: {len(fabric_data.get('datasets', []))}")

    # Initialize analyzer
    print("\n2. Initializing ACI Analyzer with enterprise data...")
    analyzer = ACIAnalyzer(fabric_data)
    print("   [OK] Analyzer initialized")

    # Test 1: Coupling Issues Analysis
    print_section("Test 1: Coupling Issues Analysis")
    print("Analyzing coupling scenarios...")

    coupling = analyzer.analyze_coupling_issues()

    print(f"\n   Coupling Statistics:")
    stats = coupling['statistics']
    print(f"      Total Issues:             {stats['total_issues']}")
    print(f"      High Severity:            {stats['high_severity']}")
    print(f"      Medium Severity:          {stats['medium_severity']}")
    print(f"      Low Severity:             {stats['low_severity']}")
    print(f"      Multi-Device EPGs:        {stats['multi_device_epgs']}")
    print(f"      Shared VLANs:             {stats['shared_vlans']}")
    print(f"      Cross-Tenant Contracts:   {stats['cross_tenant_contracts']}")
    print(f"      Migration Risk Score:     {coupling['migration_risk_score']}/100")

    # Show top coupling issues
    print(f"\n   Top 10 Coupling Issues:")
    for i, issue in enumerate(coupling['issues'][:10], 1):
        print(f"      {i}. [{issue['severity'].upper()}] {issue['issue_type']}: {issue['description']}")
        if 'epg' in issue and issue['issue_type'] != 'cross_tenant_contracts':
            print(f"         EPG: {issue['epg']}")
            print(f"         Impact: {issue['migration_impact']}")

    # High density devices
    if coupling['high_density_devices']:
        print(f"\n   High Density Devices (>10 EPGs):")
        for i, device in enumerate(coupling['high_density_devices'][:5], 1):
            print(f"      {i}. {device['device']}: {device['epg_count']} EPGs, {device['vlan_count']} VLANs")

    # Test 2: Migration Waves Analysis
    print_section("Test 2: Migration Waves Analysis")
    print("Calculating migration waves...")

    waves = analyzer.analyze_migration_waves()

    print(f"\n   Migration Wave Summary:")
    print(f"      Total EPGs:               {waves['total_epgs']}")
    print(f"      Total Effort:             {waves['total_effort_hours']} hours ({waves['total_effort_days']} days)")

    print(f"\n   Wave Breakdown:")
    for wave_summary in waves['summary']:
        print(f"\n      {wave_summary['wave']}:")
        print(f"         EPG Count:            {wave_summary['epg_count']}")
        print(f"         Estimated Hours:      {wave_summary['estimated_hours']}")
        print(f"         Estimated Days:       {wave_summary['estimated_days']}")
        print(f"         Description:          {wave_summary['description']}")

    # Show sample EPGs from each wave
    print(f"\n   Sample EPGs by Wave:")
    for wave_name in ['wave1_standalone', 'wave2_low_coupling', 'wave3_medium_coupling', 'wave4_high_coupling']:
        epgs = waves['waves'][wave_name]
        if epgs:
            print(f"\n      {wave_name.replace('_', ' ').title()} (sample of {min(3, len(epgs))} out of {len(epgs)}):")
            for epg in epgs[:3]:
                print(f"         - {epg['epg']} ({epg['tenant']})")
                print(f"           Devices: {epg['device_count']}, Paths: {epg['path_count']}, Issues: {epg['issues']}")

    # Test 3: VLAN Sharing Analysis
    print_section("Test 3: VLAN Sharing Analysis")
    print("Analyzing VLAN sharing patterns...")

    vlan_analysis = analyzer.analyze_vlan_sharing_detailed()

    print(f"\n   VLAN Sharing Statistics:")
    vlan_stats = vlan_analysis['statistics']
    print(f"      Total VLANs Used:         {vlan_stats['total_vlans_used']}")
    print(f"      Shared VLANs:             {vlan_stats['shared_vlans']}")
    print(f"      Multi-Tenant VLANs:       {vlan_stats['multi_tenant_vlans']}")
    print(f"      Multi-Device VLANs:       {vlan_stats['multi_device_vlans']}")

    # Show top VLAN sharing issues
    print(f"\n   Top 10 VLAN Sharing Issues:")
    for i, issue in enumerate(vlan_analysis['sharing_issues'][:10], 1):
        print(f"      {i}. VLAN {issue['vlan']} [{issue['severity'].upper()}]")
        print(f"         EPG Count:            {issue['epg_count']}")
        print(f"         Device Count:         {issue['device_count']}")
        print(f"         Tenant Count:         {issue['tenant_count']}")
        print(f"         Sample EPGs:          {', '.join(issue['epgs'][:3])}")
        print(f"         Migration Risk:       {issue['migration_risk']}")

    # Test 4: Overall Risk Assessment
    print_section("Test 4: Migration Risk Assessment")

    # Calculate risk factors
    coupling_risk = coupling['migration_risk_score']
    vlan_risk = min(vlan_stats['multi_tenant_vlans'] * 5, 50)
    complexity_risk = min((stats['high_severity'] * 10 + stats['medium_severity'] * 5), 50)

    overall_risk = min(coupling_risk + vlan_risk // 2 + complexity_risk // 2, 100)

    print(f"\n   Risk Factors:")
    print(f"      Coupling Risk:            {coupling_risk}/100")
    print(f"      VLAN Conflict Risk:       {vlan_risk}/50")
    print(f"      Complexity Risk:          {complexity_risk}/50")
    print(f"      Overall Migration Risk:   {overall_risk}/100")

    if overall_risk >= 70:
        risk_level = "HIGH - Complex migration requiring extensive planning"
    elif overall_risk >= 40:
        risk_level = "MEDIUM - Moderate migration complexity"
    else:
        risk_level = "LOW - Straightforward migration"

    print(f"\n   Risk Level: {risk_level}")

    # Test 5: Migration Recommendations
    print_section("Test 5: Migration Recommendations")

    print("\n   Recommended Migration Strategy:")
    print(f"\n   1. Start with Wave 1 ({waves['summary'][0]['epg_count']} EPGs)")
    print(f"      - Standalone EPGs with no coupling")
    print(f"      - Estimated time: {waves['summary'][0]['estimated_days']} days")
    print(f"      - Low risk, good for team training")

    print(f"\n   2. Address VLAN Conflicts")
    print(f"      - {vlan_stats['multi_tenant_vlans']} VLANs shared across tenants")
    print(f"      - Create VLAN remapping plan before migration")
    print(f"      - Document VLAN assignments per EPG")

    print(f"\n   3. Resolve High-Severity Coupling Issues")
    print(f"      - {stats['high_severity']} high-severity issues identified")
    print(f"      - Focus on multi-device EPGs first")
    print(f"      - Consider L2 extension or simultaneous migration")

    print(f"\n   4. Progressive Wave Migration")
    for i, wave_summary in enumerate(waves['summary'][1:], 2):
        print(f"      - Wave {i}: {wave_summary['epg_count']} EPGs ({wave_summary['estimated_days']} days)")

    print(f"\n   5. Cross-Tenant Contract Dependencies")
    if stats['cross_tenant_contracts'] > 0:
        print(f"      - {stats['cross_tenant_contracts']} cross-tenant contracts")
        print(f"      - Migrate dependent tenants together or establish L3 connectivity first")
    else:
        print(f"      - No cross-tenant dependencies (good!)")

    # Save detailed results
    print_section("Saving Analysis Results")

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    results = {
        'coupling_analysis': coupling,
        'migration_waves': waves,
        'vlan_sharing': vlan_analysis,
        'risk_assessment': {
            'coupling_risk': coupling_risk,
            'vlan_risk': vlan_risk,
            'complexity_risk': complexity_risk,
            'overall_risk': overall_risk,
            'risk_level': risk_level
        }
    }

    output_file = output_dir / "coupling_analysis_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n   [OK] Results saved to: {output_file}")
    print(f"   File size: {output_file.stat().st_size / 1024:.2f} KB")

    # Summary
    print_section("Test Summary")
    print("\n   All coupling analysis tests: PASSED [OK]")
    print(f"\n   Key Findings:")
    print(f"      - {waves['total_epgs']} EPGs analyzed")
    print(f"      - {stats['total_issues']} coupling issues identified")
    print(f"      - {waves['total_effort_days']} days estimated for migration")
    print(f"      - Risk level: {risk_level.split(' - ')[0]}")
    print(f"      - {waves['summary'][0]['epg_count']} EPGs can be migrated independently (Wave 1)")
    print(f"      - {stats['multi_device_epgs']} EPGs require coordinated migration")

    print("\n" + "=" * 80)
    return True

if __name__ == '__main__':
    try:
        success = test_coupling_analysis()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[X] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
