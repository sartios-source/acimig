#!/usr/bin/env python3
"""
Generate Mock ACI Data from Sample Topology
Converts sample-topology.json into APIC API format
"""

import json
import sys
import os
from typing import Dict, List, Any

def generate_fabric_nodes(topology: Dict) -> List[Dict]:
    """Generate fabricNode objects"""
    nodes = []

    # Add APIC
    nodes.append({
        "dn": "topology/pod-1/node-1",
        "id": "1",
        "name": "apic1",
        "role": "controller",
        "model": "APIC-SERVER-M3",
        "serial": "TEP-1-1",
        "address": "10.0.0.1",
        "state": "in-service",
        "fabricSt": "active"
    })

    # Add spines
    for spine in topology['topology']['spines']:
        nodes.append({
            "dn": f"topology/pod-{spine['pod']}/node-{spine['id']}",
            "id": str(spine['id']),
            "name": spine['name'],
            "role": "spine",
            "model": spine['model'],
            "serial": spine['serial'],
            "address": f"10.0.0.{spine['id']}",
            "state": "in-service",
            "fabricSt": "active"
        })

    # Add leafs
    for leaf in topology['topology']['leafs']:
        nodes.append({
            "dn": f"topology/pod-{leaf['pod']}/node-{leaf['id']}",
            "id": str(leaf['id']),
            "name": leaf['name'],
            "role": leaf['role'],
            "model": leaf['model'],
            "serial": leaf['serial'],
            "address": f"10.0.0.{leaf['id']}",
            "state": "in-service",
            "fabricSt": "active"
        })

    return nodes

def generate_tenants(topology: Dict) -> List[Dict]:
    """Generate fvTenant objects"""
    tenants = []

    for tenant in topology['tenants']:
        tenants.append({
            "dn": f"uni/tn-{tenant['name']}",
            "name": tenant['name'],
            "descr": tenant.get('description', ''),
            "ownerKey": "",
            "ownerTag": ""
        })

    # Add common and infra tenants
    tenants.extend([
        {
            "dn": "uni/tn-common",
            "name": "common",
            "descr": "Common tenant",
            "ownerKey": "",
            "ownerTag": ""
        },
        {
            "dn": "uni/tn-infra",
            "name": "infra",
            "descr": "Infrastructure tenant",
            "ownerKey": "",
            "ownerTag": ""
        }
    ])

    return tenants

def generate_vrfs(topology: Dict) -> List[Dict]:
    """Generate fvCtx (VRF) objects"""
    vrfs = []

    for tenant in topology['tenants']:
        for vrf in tenant.get('vrfs', []):
            vrfs.append({
                "dn": f"uni/tn-{tenant['name']}/ctx-{vrf['name']}",
                "name": vrf['name'],
                "descr": vrf.get('description', ''),
                "pcEnfPref": "enforced",
                "bdEnforcedEnable": "no"
            })

    return vrfs

def generate_bridge_domains(topology: Dict) -> List[Dict]:
    """Generate fvBD objects"""
    bds = []

    for tenant in topology['tenants']:
        for bd in tenant.get('bridge_domains', []):
            bds.append({
                "dn": f"uni/tn-{tenant['name']}/BD-{bd['name']}",
                "name": bd['name'],
                "descr": bd.get('description', ''),
                "arpFlood": "yes",
                "unicastRoute": "yes",
                "unkMacUcastAct": "proxy",
                "vmac": "not-applicable"
            })

    return bds

def generate_application_profiles(topology: Dict) -> List[Dict]:
    """Generate fvAp objects"""
    aps = []

    for tenant in topology['tenants']:
        for ap in tenant.get('application_profiles', []):
            aps.append({
                "dn": f"uni/tn-{tenant['name']}/ap-{ap['name']}",
                "name": ap['name'],
                "descr": ap.get('description', ''),
                "prio": "unspecified"
            })

    return aps

def generate_epgs(topology: Dict) -> List[Dict]:
    """Generate fvAEPg objects"""
    epgs = []

    for tenant in topology['tenants']:
        for ap in tenant.get('application_profiles', []):
            for epg in ap.get('epgs', []):
                epgs.append({
                    "dn": f"uni/tn-{tenant['name']}/ap-{ap['name']}/epg-{epg['name']}",
                    "name": epg['name'],
                    "descr": epg.get('description', ''),
                    "prio": "unspecified",
                    "pcEnfPref": "unenforced",
                    "scope": "2195456"
                })

    return epgs

def generate_epg_paths(topology: Dict) -> List[Dict]:
    """Generate fvRsPathAtt objects (EPG to path bindings)"""
    paths = []
    path_id = 1

    for tenant in topology['tenants']:
        for ap in tenant.get('application_profiles', []):
            for epg in ap.get('epgs', []):
                for path in epg.get('paths', []):
                    # Determine path DN based on whether FEX is involved
                    if 'fex' in path:
                        path_dn = f"topology/pod-1/paths-{path['leaf']}/extpaths-{path['fex']}/pathep-[eth{path['port']}]"
                        path_type = "fex"
                    else:
                        path_dn = f"topology/pod-1/paths-{path['leaf']}/pathep-[eth{path['port']}]"
                        path_type = "leaf"

                    paths.append({
                        "dn": f"uni/tn-{tenant['name']}/ap-{ap['name']}/epg-{epg['name']}/rspathAtt-[{path_dn}]",
                        "tDn": path_dn,
                        "encap": f"vlan-{path['vlan']}",
                        "instrImedcy": "immediate",
                        "mode": "regular",
                        "primaryEncap": "unknown",
                        "pathType": path_type,
                        "leafId": str(path['leaf']),
                        "fexId": str(path.get('fex', ''))
                    })
                    path_id += 1

    return paths

def generate_paths(topology: Dict) -> List[Dict]:
    """Generate fabricPathEp objects (physical paths)"""
    paths = []

    # Generate paths for each leaf
    for leaf in topology['topology']['leafs']:
        # Add leaf ports
        for port in range(1, 49):  # 48 ports
            paths.append({
                "dn": f"topology/pod-1/paths-{leaf['id']}/pathep-[eth1/{port}]",
                "name": f"eth1/{port}",
                "pathType": "leaf",
                "nodeId": str(leaf['id']),
                "portId": str(port)
            })

    # Generate FEX paths
    for fex in topology['topology']['fex']:
        for port in range(1, fex['ports'] + 1):
            paths.append({
                "dn": f"topology/pod-1/paths-{fex['parent_leaf']}/extpaths-{fex['id']}/pathep-[eth1/{port}]",
                "name": f"eth1/{port}",
                "pathType": "fex",
                "nodeId": str(fex['parent_leaf']),
                "fexId": fex['id'],
                "portId": str(port)
            })

    return paths

def generate_links(topology: Dict) -> List[Dict]:
    """Generate fabricLink objects"""
    links = []
    link_id = 1

    # Generate spine-to-leaf links
    for spine in topology['topology']['spines']:
        for leaf in topology['topology']['leafs']:
            # Create bidirectional links
            links.append({
                "dn": f"topology/pod-1/link-{link_id}",
                "n1": str(spine['id']),
                "n2": str(leaf['id']),
                "linkType": "fabric"
            })
            link_id += 1

    return links

def generate_contracts(topology: Dict) -> List[Dict]:
    """Generate vzBrCP (contract) objects"""
    contracts = [
        {
            "dn": "uni/tn-production/brc-web-to-app",
            "name": "web-to-app",
            "descr": "Web to App tier contract",
            "scope": "context",
            "prio": "unspecified"
        },
        {
            "dn": "uni/tn-production/brc-app-to-db",
            "name": "app-to-db",
            "descr": "App to DB tier contract",
            "scope": "context",
            "prio": "unspecified"
        }
    ]
    return contracts

def generate_filters(topology: Dict) -> List[Dict]:
    """Generate vzFilter objects"""
    filters = [
        {
            "dn": "uni/tn-production/flt-http",
            "name": "http",
            "descr": "HTTP filter"
        },
        {
            "dn": "uni/tn-production/flt-https",
            "name": "https",
            "descr": "HTTPS filter"
        },
        {
            "dn": "uni/tn-production/flt-sql",
            "name": "sql",
            "descr": "SQL filter"
        }
    ]
    return filters

def generate_l3outs(topology: Dict) -> List[Dict]:
    """Generate l3extOut objects"""
    l3outs = []
    # Can add L3Outs if needed for testing
    return l3outs

def main():
    """Main function to generate mock data"""
    # Load sample topology
    script_dir = os.path.dirname(os.path.abspath(__file__))
    topology_file = os.path.join(script_dir, '..', 'aci-config', 'sample-topology.json')

    try:
        with open(topology_file, 'r') as f:
            topology = json.load(f)
    except FileNotFoundError:
        print(f"Error: {topology_file} not found", file=sys.stderr)
        sys.exit(1)

    # Generate all mock data
    mock_data = {
        "fabric": topology['fabric'],
        "nodes": generate_fabric_nodes(topology),
        "tenants": generate_tenants(topology),
        "vrfs": generate_vrfs(topology),
        "bridge_domains": generate_bridge_domains(topology),
        "application_profiles": generate_application_profiles(topology),
        "epgs": generate_epgs(topology),
        "epg_paths": generate_epg_paths(topology),
        "paths": generate_paths(topology),
        "links": generate_links(topology),
        "contracts": generate_contracts(topology),
        "filters": generate_filters(topology),
        "l3outs": generate_l3outs(topology)
    }

    # Output JSON
    print(json.dumps(mock_data, indent=2))

if __name__ == '__main__':
    main()
