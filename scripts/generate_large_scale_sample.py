#!/usr/bin/env python3
"""
Generate Large-Scale ACI Sample Data
Creates realistic ACI fabric with 110 leafs and 316 FEX devices
"""
import json
import random
from datetime import datetime

# Configuration
NUM_LEAFS = 110
NUM_FEX = 316
NUM_TENANTS = 8
NUM_VRFS_PER_TENANT = 2
NUM_BDS_PER_VRF = 5
NUM_EPGS_PER_BD = 3
NUM_CONTRACTS = 50
PORTS_PER_FEX = 48

def generate_fabric():
    """Generate complete ACI fabric data."""

    print(f"Generating ACI fabric data:")
    print(f"  - {NUM_LEAFS} leaf switches")
    print(f"  - {NUM_FEX} FEX devices")
    print(f"  - {NUM_TENANTS} tenants")
    print(f"  - ~{NUM_TENANTS * NUM_VRFS_PER_TENANT * NUM_BDS_PER_VRF} bridge domains")
    print(f"  - ~{NUM_TENANTS * NUM_VRFS_PER_TENANT * NUM_BDS_PER_VRF * NUM_EPGS_PER_BD} EPGs")
    print()

    imdata = []

    # Generate leaf switches (distributed across 2 pods, 5 sites)
    print("Generating leaf switches...")
    pods = [1, 2]
    sites = ['NYC-DC1', 'NYC-DC2', 'SFO-DC1', 'CHI-DC1', 'DAL-DC1']

    leafs_per_site = NUM_LEAFS // len(sites)
    leaf_id = 101

    for site_idx, site in enumerate(sites):
        for i in range(leafs_per_site):
            pod = pods[site_idx % len(pods)]

            leaf = {
                "fabricNode": {
                    "attributes": {
                        "dn": f"topology/pod-{pod}/node-{leaf_id}",
                        "id": str(leaf_id),
                        "name": f"leaf-{site}-{i+1:03d}",
                        "role": "leaf",
                        "model": random.choice([
                            "N9K-C93180YC-EX",
                            "N9K-C93180YC-FX",
                            "N9K-C9336C-FX2",
                            "N9K-C9348GC-FXP"
                        ]),
                        "serial": f"LEAF{leaf_id:05d}SN",
                        "address": f"10.{pod}.{leaf_id // 256}.{leaf_id % 256}",
                        "fabricSt": "active",
                        "operSt": "up"
                    }
                }
            }
            imdata.append(leaf)
            leaf_id += 1

    # Fill remaining leafs
    remaining = NUM_LEAFS - (leafs_per_site * len(sites))
    for i in range(remaining):
        leaf = {
            "fabricNode": {
                "attributes": {
                    "dn": f"topology/pod-1/node-{leaf_id}",
                    "id": str(leaf_id),
                    "name": f"leaf-MISC-{i+1:03d}",
                    "role": "leaf",
                    "model": "N9K-C93180YC-EX",
                    "serial": f"LEAF{leaf_id:05d}SN"
                }
            }
        }
        imdata.append(leaf)
        leaf_id += 1

    # Generate FEX devices (distributed across leafs)
    print(f"Generating {NUM_FEX} FEX devices...")

    # Distribute FEX across leafs (some leafs have more, some have less)
    # Create realistic distribution with some leafs having 0, some having up to 12
    leaf_ids = list(range(101, 101 + NUM_LEAFS))
    fex_distribution = {}

    # Assign FEX to leafs
    fex_assigned = 0
    for leaf in leaf_ids:
        # Random number of FEX per leaf (0-12, weighted towards 2-4)
        if fex_assigned >= NUM_FEX:
            fex_count = 0
        else:
            remaining_fex = NUM_FEX - fex_assigned
            remaining_leafs = len(leaf_ids) - leaf_ids.index(leaf)
            avg_per_leaf = max(1, remaining_fex // remaining_leafs)

            # Some variation
            fex_count = random.randint(
                max(0, avg_per_leaf - 2),
                min(12, avg_per_leaf + 3, remaining_fex)
            )

        fex_distribution[leaf] = fex_count
        fex_assigned += fex_count

    # Generate FEX objects
    fex_id = 101
    fex_serial_id = 1000

    for leaf_id, fex_count in fex_distribution.items():
        for i in range(fex_count):
            pod = 1 if leaf_id < 200 else 2

            fex = {
                "eqptFex": {
                    "attributes": {
                        "dn": f"topology/pod-{pod}/node-{leaf_id}/sys/extch-{fex_id}",
                        "id": str(fex_id),
                        "ser": f"FEX{fex_serial_id:06d}ABC",
                        "model": random.choice([
                            "N2K-C2248TP-E-1GE",
                            "N2K-C2348UPQ",
                            "N2K-C2232PP-10GE",
                            "N2K-C2348TQ"
                        ]),
                        "operSt": random.choice(["up"] * 95 + ["down"] * 5),  # 95% up
                        "descr": f"FEX for leaf {leaf_id}",
                        "vendor": "Cisco Systems, Inc."
                    }
                }
            }
            imdata.append(fex)

            # Add physical interfaces for this FEX (sample a few)
            for port in range(1, min(PORTS_PER_FEX, 10)):  # Only add first 10 ports to keep file size reasonable
                is_connected = random.random() < 0.65  # 65% port utilization

                interface = {
                    "ethpmPhysIf": {
                        "attributes": {
                            "dn": f"topology/pod-{pod}/node-{leaf_id}/sys/phys-[eth{fex_id}/1/{port}]",
                            "id": f"eth{fex_id}/1/{port}",
                            "operSt": "up" if is_connected else "down",
                            "adminSt": "up",
                            "operSpeed": "1G" if is_connected else "unknown"
                        }
                    }
                }
                imdata.append(interface)

            fex_id += 1
            fex_serial_id += 1

    # Generate tenants
    print(f"Generating {NUM_TENANTS} tenants...")
    tenant_names = [
        'Production', 'Development', 'QA', 'Finance',
        'HR', 'Engineering', 'Sales', 'Marketing'
    ][:NUM_TENANTS]

    epg_counter = 0

    for tenant_name in tenant_names:
        # Tenant
        tenant = {
            "fvTenant": {
                "attributes": {
                    "dn": f"uni/tn-{tenant_name}",
                    "name": tenant_name,
                    "descr": f"{tenant_name} tenant"
                }
            }
        }
        imdata.append(tenant)

        # VRFs per tenant
        for vrf_idx in range(NUM_VRFS_PER_TENANT):
            vrf_name = f"{tenant_name}-VRF{vrf_idx+1}"

            vrf = {
                "fvCtx": {
                    "attributes": {
                        "dn": f"uni/tn-{tenant_name}/ctx-{vrf_name}",
                        "name": vrf_name,
                        "pcEnfPref": "enforced"
                    }
                }
            }
            imdata.append(vrf)

            # Application profiles
            app_profile = f"{tenant_name}-APP"

            # Bridge domains per VRF
            for bd_idx in range(NUM_BDS_PER_VRF):
                bd_name = f"{tenant_name}-BD{bd_idx+1}"

                bd = {
                    "fvBD": {
                        "attributes": {
                            "dn": f"uni/tn-{tenant_name}/BD-{bd_name}",
                            "name": bd_name,
                            "vrf": vrf_name,
                            "arpFlood": "no",
                            "unicastRoute": "yes"
                        }
                    }
                }
                imdata.append(bd)

                # Subnet for BD
                subnet_third_octet = (vrf_idx * 50) + bd_idx
                subnet = {
                    "fvSubnet": {
                        "attributes": {
                            "dn": f"uni/tn-{tenant_name}/BD-{bd_name}/subnet-[10.{tenant_names.index(tenant_name)}.{subnet_third_octet}.1/24]",
                            "ip": f"10.{tenant_names.index(tenant_name)}.{subnet_third_octet}.1/24",
                            "scope": "public"
                        }
                    }
                }
                imdata.append(subnet)

                # EPGs per BD
                for epg_idx in range(NUM_EPGS_PER_BD):
                    epg_name = f"{tenant_name}-EPG{epg_idx+1}-{bd_name}"

                    epg = {
                        "fvAEPg": {
                            "attributes": {
                                "dn": f"uni/tn-{tenant_name}/ap-{app_profile}/epg-{epg_name}",
                                "name": epg_name,
                                "bd": bd_name
                            }
                        }
                    }
                    imdata.append(epg)

                    # Create path attachments (EPG to FEX bindings)
                    # Each EPG is attached to 1-3 random FEX devices
                    num_attachments = random.randint(1, 3)
                    selected_fex = random.sample(range(101, 101 + min(50, NUM_FEX)), num_attachments)

                    for fex_node_id in selected_fex:
                        # Find the leaf this FEX is attached to
                        leaf_id = None
                        for lid, fcount in fex_distribution.items():
                            if fcount > 0:
                                leaf_id = lid
                                break

                        if leaf_id:
                            vlan = 100 + (epg_counter % 900)  # VLANs 100-999
                            pod = 1
                            port = random.randint(1, 48)

                            path_att = {
                                "fvRsPathAtt": {
                                    "attributes": {
                                        "dn": f"uni/tn-{tenant_name}/ap-{app_profile}/epg-{epg_name}/rspathAtt-[topology/pod-{pod}/paths-{leaf_id}/extpaths-{fex_node_id}/pathep-[eth1/{port}]]",
                                        "tDn": f"topology/pod-{pod}/paths-{leaf_id}/extpaths-{fex_node_id}/pathep-[eth1/{port}]",
                                        "encap": f"vlan-{vlan}",
                                        "mode": "regular"
                                    }
                                }
                            }
                            imdata.append(path_att)

                    epg_counter += 1

    # Generate contracts
    print(f"Generating {NUM_CONTRACTS} contracts...")
    for contract_idx in range(NUM_CONTRACTS):
        tenant = random.choice(tenant_names)

        contract = {
            "vzBrCP": {
                "attributes": {
                    "dn": f"uni/tn-{tenant}/brc-Contract-{contract_idx+1}",
                    "name": f"Contract-{contract_idx+1}",
                    "scope": random.choice(["context", "tenant", "global"]),
                    "prio": random.choice(["default", "level1", "level2"])
                }
            }
        }
        imdata.append(contract)

    # Generate some L3Outs
    print("Generating L3Outs...")
    for tenant in tenant_names[:3]:  # Only first 3 tenants have L3Outs
        l3out = {
            "l3extOut": {
                "attributes": {
                    "dn": f"uni/tn-{tenant}/out-Internet-L3Out",
                    "name": "Internet-L3Out"
                }
            }
        }
        imdata.append(l3out)

        external_epg = {
            "l3extInstP": {
                "attributes": {
                    "dn": f"uni/tn-{tenant}/out-Internet-L3Out/instP-External-Networks",
                    "name": "External-Networks"
                }
            }
        }
        imdata.append(external_epg)

    print(f"\nGenerated {len(imdata)} total objects")

    return {"imdata": imdata}


def generate_cmdb_data():
    """Generate CMDB CSV data matching the fabric."""

    print("\nGenerating CMDB data...")

    records = []
    records.append("SerialNumber,Rack,Building,Hall,Site,InstallDate,Owner")

    # Leaf serials
    for leaf_id in range(101, 101 + NUM_LEAFS):
        site_idx = (leaf_id - 101) // (NUM_LEAFS // 5)
        sites = ['NYC-DC1', 'NYC-DC2', 'SFO-DC1', 'CHI-DC1', 'DAL-DC1']
        site = sites[min(site_idx, len(sites)-1)]

        rack = f"R{(leaf_id - 101) % 20 + 1:02d}"
        building = site.split('-')[0]
        hall = f"Hall-{((leaf_id - 101) // 20) + 1}"

        records.append(f"LEAF{leaf_id:05d}SN,{rack},{building},{hall},{site},2023-01-15,Network-Ops")

    # FEX serials
    for fex_serial_id in range(1000, 1000 + NUM_FEX):
        site_idx = (fex_serial_id - 1000) // (NUM_FEX // 5)
        sites = ['NYC-DC1', 'NYC-DC2', 'SFO-DC1', 'CHI-DC1', 'DAL-DC1']
        site = sites[min(site_idx, len(sites)-1)]

        rack = f"R{(fex_serial_id - 1000) % 20 + 1:02d}"
        building = site.split('-')[0]
        hall = f"Hall-{((fex_serial_id - 1000) // 20) + 1}"

        records.append(f"FEX{fex_serial_id:06d}ABC,{rack},{building},{hall},{site},2023-03-20,Network-Ops")

    return "\n".join(records)


if __name__ == '__main__':
    print("="*70)
    print("ACI Large-Scale Sample Data Generator")
    print("="*70)
    print()

    # Generate fabric data
    fabric_data = generate_fabric()

    # Save to file
    output_file = '../data/samples/sample_large_scale.json'
    print(f"\nSaving to {output_file}...")

    with open(output_file, 'w') as f:
        json.dump(fabric_data, f, indent=2)

    print(f"[OK] Saved {len(fabric_data['imdata'])} objects")

    # Generate CMDB data
    cmdb_data = generate_cmdb_data()
    cmdb_file = '../data/samples/sample_large_scale_cmdb.csv'

    print(f"\nSaving CMDB to {cmdb_file}...")
    with open(cmdb_file, 'w') as f:
        f.write(cmdb_data)

    print(f"[OK] Saved {cmdb_data.count(chr(10))} CMDB records")

    print()
    print("="*70)
    print("Sample data generated successfully!")
    print("="*70)
    print()
    print("Summary:")
    print(f"  Leafs: {NUM_LEAFS}")
    print(f"  FEX: {NUM_FEX}")
    print(f"  Tenants: {NUM_TENANTS}")
    print(f"  Total objects: {len(fabric_data['imdata'])}")
    print()
    print("You can now upload these files:")
    print(f"  1. {output_file}")
    print(f"  2. {cmdb_file}")
    print()
