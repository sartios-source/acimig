#!/usr/bin/env python3
"""
Seed a demo fabric with sample ACI/CMDB data for quick UI testing.
"""

from pathlib import Path
from datetime import datetime
import sys

base_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base_dir))

from analysis import parsers, fabric_manager


def main():
    samples_dir = base_dir / "data" / "samples"
    fabrics_dir = base_dir / "fabrics"

    aci_path = samples_dir / "sample_large_scale.json"
    cmdb_path = samples_dir / "sample_large_scale_cmdb.csv"

    if not aci_path.exists() or not cmdb_path.exists():
        raise FileNotFoundError("Sample files not found in data/samples")

    fm = fabric_manager.FabricManager(fabrics_dir)
    fabric_name = "demo_fabric"

    try:
        fm.create_fabric(fabric_name)
        print(f"Created fabric: {fabric_name}")
    except ValueError:
        print(f"Fabric already exists: {fabric_name}")

    now = datetime.now().isoformat()

    aci_content = aci_path.read_text(encoding="utf-8")
    aci_parsed = parsers.parse_aci(aci_content, "json")
    fm.add_dataset(fabric_name, {
        "filename": aci_path.name,
        "type": "aci",
        "format": "json",
        "uploaded": now,
        "objects": len(aci_parsed.get("objects", [])),
        "path": str(aci_path),
    })
    print(f"Added ACI dataset: {aci_path.name}")

    cmdb_content = cmdb_path.read_text(encoding="utf-8")
    cmdb_parsed = parsers.parse_cmdb_csv(cmdb_content)
    fm.add_dataset(fabric_name, {
        "filename": cmdb_path.name,
        "type": "cmdb",
        "uploaded": now,
        "records": len(cmdb_parsed),
        "path": str(cmdb_path),
    })
    print(f"Added CMDB dataset: {cmdb_path.name}")

    print("Done. Select 'demo_fabric' in the UI.")


if __name__ == "__main__":
    main()
