#!/usr/bin/env python3
"""APIC API collector for ACI imdata exports."""
import argparse
import json
import getpass
import requests
from datetime import datetime

DEFAULT_CLASSES = [
    'fabricNode', 'eqptFex', 'fvAEPg', 'fvBD', 'fvCtx', 'fvTenant', 'fvRsPathAtt',
    'fvSubnet', 'ethpmPhysIf', 'physDomP', 'vzBrCP', 'vzSubj', 'vzFilter', 'vzEntry',
    'vzRsSubjFiltAtt', 'fvRsCons', 'fvRsProv', 'vpcDom', 'pcAggrIf', 'lacpEntity',
    'vpcIf', 'l3extOut', 'l3extInstP', 'l3extLNodeP', 'l3extLIfP',
    'l3extRsNodeL3OutAtt', 'l3extSubnet', 'l3extRsEctx', 'bgpPeerP', 'ospfIfP',
    'ipRouteP', 'fvnsVlanInstP', 'fvnsEncapBlk', 'vmmDomP', 'l3extDomP',
    'infraRsVlanNs', 'vmmRsVlanNs', 'l3extRsVlanNs', 'infraAccPortGrp',
    'infraAccBndlGrp', 'infraAccPortP', 'infraHPortS', 'infraRsDomP',
    'infraAttEntityP', 'lldpAdjEp', 'cdpAdjEp', 'fvRsBd', 'fvRsCtx'
]


def login(apic_url: str, username: str, password: str) -> requests.Session:
    session = requests.Session()
    payload = {
        "aaaUser": {
            "attributes": {
                "name": username,
                "pwd": password
            }
        }
    }
    resp = session.post(f"{apic_url}/api/aaaLogin.json", json=payload, timeout=30)
    resp.raise_for_status()
    return session


def collect_class(session: requests.Session, apic_url: str, class_name: str) -> list:
    resp = session.get(f"{apic_url}/api/node/class/{class_name}.json", timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data.get('imdata', [])


def parse_args():
    parser = argparse.ArgumentParser(description="APIC API collector")
    parser.add_argument("--apic-url", required=True, help="APIC base URL (https://apic)")
    parser.add_argument("--username", required=True, help="APIC username")
    parser.add_argument("--password", help="APIC password (prompted if omitted)")
    parser.add_argument("--classes", help="Comma-separated ACI classes to collect")
    parser.add_argument("--output", default="apic_export.json", help="Output JSON path")
    return parser.parse_args()


def main():
    args = parse_args()
    password = args.password or getpass.getpass("APIC password: ")
    classes = DEFAULT_CLASSES
    if args.classes:
        classes = [c.strip() for c in args.classes.split(',') if c.strip()]

    session = login(args.apic_url.rstrip('/'), args.username, password)
    all_imdata = []
    errors = []

    for class_name in classes:
        try:
            imdata = collect_class(session, args.apic_url.rstrip('/'), class_name)
            all_imdata.extend(imdata)
            print(f"Collected {class_name}: {len(imdata)} objects")
        except Exception as exc:
            errors.append(f"{class_name}: {exc}")
            print(f"Failed {class_name}: {exc}")

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "classes": classes,
        "errors": errors,
        "imdata": all_imdata
    }
    with open(args.output, 'w', encoding='utf-8') as handle:
        json.dump(output, handle, indent=2)

    print(f"Saved {len(all_imdata)} objects to {args.output}")
    if errors:
        print("Errors:")
        for err in errors:
            print(f" - {err}")


if __name__ == "__main__":
    raise SystemExit(main())
