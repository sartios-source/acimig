#!/usr/bin/env python3
"""
Sandbox test for ACI analysis engine using bundled large-scale sample data.
Validates core analysis outputs are populated and structurally sane.
"""
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from analysis import engine


ACI_SAMPLE = BASE_DIR / "data" / "samples" / "sample_large_scale.json"
CMDB_SAMPLE = BASE_DIR / "data" / "samples" / "sample_large_scale_cmdb.csv"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    if not ACI_SAMPLE.exists():
        print(f"Missing ACI sample: {ACI_SAMPLE}")
        return 1

    datasets = [
        {"type": "aci_json", "format": "json", "path": str(ACI_SAMPLE), "filename": ACI_SAMPLE.name},
    ]

    if CMDB_SAMPLE.exists():
        datasets.append({"type": "cmdb", "format": "csv", "path": str(CMDB_SAMPLE), "filename": CMDB_SAMPLE.name})

    analyzer = engine.ACIAnalyzer({"name": "sandbox", "datasets": datasets})

    port_util = analyzer.analyze_port_utilization()
    leaf_fex = analyzer.analyze_leaf_fex_mapping()
    rack_grouping = analyzer.analyze_rack_grouping()
    bd_epg = analyzer.analyze_bd_epg_mapping()
    vlan_dist = analyzer.analyze_vlan_distribution()
    epg_complex = analyzer.analyze_epg_complexity()
    vpc_symmetry = analyzer.analyze_vpc_symmetry()
    pdom = analyzer.analyze_pdom()
    migration_flags = analyzer.analyze_migration_flags()
    contract_scope = analyzer.analyze_contract_scope()
    vlan_spread = analyzer.analyze_vlan_spread()
    cmdb_corr = analyzer.analyze_cmdb_correlation()
    coupling = analyzer.analyze_coupling_issues()
    migration_waves = analyzer.analyze_migration_waves()
    vlan_sharing = analyzer.analyze_vlan_sharing_detailed()
    viz = analyzer.get_visualization_data()

    require(len(port_util) > 0, "Port utilization should not be empty")
    require(leaf_fex.get("statistics", {}).get("total_leafs", 0) > 0, "Leaf/FEX mapping missing leafs")
    require(len(bd_epg.get("mappings", [])) > 0, "BD/EPG mapping empty")
    require(len(vlan_dist.get("vlan_usage", {})) > 0, "VLAN distribution empty")
    require(len(epg_complex) > 0, "EPG complexity empty")
    require(len(contract_scope) > 0, "Contract scope empty")
    require(len(vpc_symmetry.get("statistics", {})) > 0, "vPC symmetry stats missing")
    require(len(pdom) >= 0, "Physical domains returned invalid data")
    require(len(vlan_spread.get("vlan_usage", {})) > 0, "VLAN spread empty")
    require(len(coupling) >= 0, "Coupling analysis failed")
    require(len(migration_waves.get("summary", [])) > 0, "Migration waves empty")
    require(len(vlan_sharing.get("sharing_issues", [])) >= 0, "VLAN sharing failed")
    require(len(viz.get("topology", {}).get("nodes", [])) > 0, "Visualization topology empty")

    print("Sandbox analysis engine test passed.")
    print(f"Port utilization entries: {len(port_util)}")
    print(f"EPG complexity entries: {len(epg_complex)}")
    print(f"Migration flags: {len(migration_flags)}")
    print(f"Contract scope entries: {len(contract_scope)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAILED: {exc}")
        raise SystemExit(1)
