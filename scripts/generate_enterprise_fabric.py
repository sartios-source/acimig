#!/usr/bin/env python3
"""
Enterprise-Scale ACI Fabric Data Generator
Generates realistic ACI fabric data with complex coupling scenarios for migration analysis.

Features:
- 1000+ EPGs across multiple tenants
- Mixed deployment patterns (FEX-only, leaf-only, FEX+leaf)
- Realistic coupling scenarios (shared VLANs, multi-device EPGs, contract dependencies)
- Enterprise-scale topology (50-200 leafs, 200-800 FEX)
- CMDB correlation data
"""

import json
import random
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set, Tuple

# Configuration
CONFIG = {
    'data_centers': ['NYC-DC1', 'NYC-DC2', 'SFO-DC1', 'CHI-DC1'],
    'leaf_count': 120,           # Enterprise scale
    'fex_per_leaf_range': (2, 8),  # Variable FEX density
    'tenants': [
        {'name': 'Production', 'epg_count': 350, 'app_profiles': 25},
        {'name': 'Development', 'epg_count': 200, 'app_profiles': 15},
        {'name': 'QA', 'epg_count': 150, 'app_profiles': 12},
        {'name': 'Finance', 'epg_count': 100, 'app_profiles': 8},
        {'name': 'HR', 'epg_count': 80, 'app_profiles': 6},
        {'name': 'Engineering', 'epg_count': 70, 'app_profiles': 5},
        {'name': 'Sales', 'epg_count': 50, 'app_profiles': 4},
    ],
    'deployment_patterns': {
        'fex_only': 0.35,      # 35% EPGs on FEX only
        'leaf_only': 0.25,     # 25% EPGs on leaf only
        'fex_and_leaf': 0.30,  # 30% EPGs on both (coupling!)
        'multi_fex': 0.10      # 10% EPGs spanning multiple FEX (high coupling!)
    },
    'coupling_scenarios': {
        'shared_vlans': 0.20,     # 20% chance of VLAN sharing
        'multi_device_epg': 0.25, # 25% chance of EPG on multiple devices
        'cross_tenant_contracts': 0.15  # 15% of contracts cross tenant boundaries
    },
    'vlan_range': (100, 3999),
    'vni_l2_start': 10000,
    'vni_l3_start': 50000,
    'fex_models': [
        {'model': 'N2K-C2348TQ', 'ports': 48},
        {'model': 'N2K-C2248TP-E-1GE', 'ports': 48},
        {'model': 'N2K-C2348UPQ', 'ports': 48},
        {'model': 'N2K-C2232PP', 'ports': 32}
    ],
    'leaf_models': [
        {'model': 'N9K-C9348GC-FXP', 'ports': 48},
        {'model': 'N9K-C93180YC-EX', 'ports': 48},
        {'model': 'N9K-C93180YC-FX', 'ports': 48},
        {'model': 'N9K-C9336C-FX2', 'ports': 36}
    ]
}


class EnterpriseFabricGenerator:
    """Generate enterprise-scale ACI fabric data with realistic coupling scenarios."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.imdata = []
        self.cmdb_records = []

        # Tracking structures
        self.leafs = []
        self.fexes = []
        self.tenants = []
        self.vrfs = []
        self.bds = []
        self.epgs = []
        self.contracts = []
        self.used_vlans = {}  # Track VLAN usage per device
        self.vlan_pool = list(range(*config['vlan_range']))
        random.shuffle(self.vlan_pool)
        self.vlan_idx = 0

    def generate(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Generate complete fabric data."""
        print("Generating Enterprise-Scale ACI Fabric Data...")
        print("=" * 70)

        self._generate_topology()
        self._generate_tenants()
        self._generate_epgs_with_coupling()
        self._generate_contracts()
        self._generate_cmdb()

        self._print_statistics()

        return {'imdata': self.imdata}, self.cmdb_records

    def _generate_topology(self):
        """Generate leaf and FEX topology."""
        print("\n1. Generating Topology...")

        data_centers = self.config['data_centers']
        leafs_per_dc = self.config['leaf_count'] // len(data_centers)

        leaf_id = 101
        fex_id = 101

        for dc in data_centers:
            for i in range(leafs_per_dc):
                # Create leaf
                leaf_model = random.choice(self.config['leaf_models'])
                leaf = {
                    'fabricNode': {
                        'attributes': {
                            'dn': f'topology/pod-1/node-{leaf_id}',
                            'id': str(leaf_id),
                            'name': f'leaf-{dc}-{i+1:03d}',
                            'role': 'leaf',
                            'model': leaf_model['model'],
                            'serial': f'LEAF{leaf_id:05d}SN',
                            'address': f'10.{(leaf_id // 256) % 256}.{leaf_id % 256}.{leaf_id % 256}',
                            'fabricSt': 'active',
                            'operSt': random.choice(['up'] * 95 + ['down'] * 5)  # 95% uptime
                        }
                    }
                }
                self.imdata.append(leaf)
                self.leafs.append({'id': leaf_id, 'name': leaf['fabricNode']['attributes']['name'],
                                 'model': leaf_model['model'], 'ports': leaf_model['ports']})

                # Create FEX for this leaf
                fex_count = random.randint(*self.config['fex_per_leaf_range'])
                for j in range(fex_count):
                    fex_model = random.choice(self.config['fex_models'])
                    fex = {
                        'eqptFex': {
                            'attributes': {
                                'dn': f'topology/pod-1/node-{leaf_id}/sys/fex-{fex_id}',
                                'id': str(fex_id),
                                'model': fex_model['model'],
                                'serial': f'FEX{fex_id:06d}ABC',
                                'operSt': random.choice(['up'] * 90 + ['down'] * 10),  # 90% uptime
                                'descr': f'{dc} FEX {j+1}'
                            }
                        }
                    }
                    self.imdata.append(fex)
                    self.fexes.append({
                        'id': fex_id,
                        'leaf_id': leaf_id,
                        'model': fex_model['model'],
                        'ports': fex_model['ports'],
                        'dc': dc
                    })

                    # Generate interfaces for FEX
                    self._generate_fex_interfaces(fex_id, leaf_id, fex_model['ports'])

                    fex_id += 1

                leaf_id += 1

        print(f"   Generated {len(self.leafs)} leaf switches")
        print(f"   Generated {len(self.fexes)} FEX devices")

    def _generate_fex_interfaces(self, fex_id: int, leaf_id: int, port_count: int):
        """Generate interfaces for a FEX with realistic utilization."""
        utilization = random.uniform(0.10, 0.70)  # 10-70% utilization
        active_ports = int(port_count * utilization)

        for port in range(1, port_count + 1):
            status = 'up' if port <= active_ports else 'down'
            interface = {
                'ethpmPhysIf': {
                    'attributes': {
                        'dn': f'topology/pod-1/node-{leaf_id}/sys/fex-{fex_id}/phys-[eth1/{port}]/phys',
                        'operSt': status,
                        'usage': 'fabric' if port <= 2 else 'epg',
                        'portCap': '1G'
                    }
                }
            }
            self.imdata.append(interface)

    def _generate_tenants(self):
        """Generate tenants with VRFs and BDs."""
        print("\n2. Generating Tenants, VRFs, and Bridge Domains...")

        for tenant_config in self.config['tenants']:
            tenant_name = tenant_config['name']

            # Create tenant
            tenant = {
                'fvTenant': {
                    'attributes': {
                        'dn': f'uni/tn-{tenant_name}',
                        'name': tenant_name,
                        'descr': f'{tenant_name} tenant'
                    }
                }
            }
            self.imdata.append(tenant)
            self.tenants.append(tenant_name)

            # Create VRFs (3-5 per tenant)
            vrf_count = random.randint(3, 5)
            tenant_vrfs = []
            for i in range(vrf_count):
                vrf_name = f'{tenant_name}_VRF{i+1}'
                vrf = {
                    'fvCtx': {
                        'attributes': {
                            'dn': f'uni/tn-{tenant_name}/ctx-{vrf_name}',
                            'name': vrf_name,
                            'pcEnfPref': 'enforced',
                            'descr': f'VRF for {tenant_name}'
                        }
                    }
                }
                self.imdata.append(vrf)
                tenant_vrfs.append(vrf_name)
                self.vrfs.append({'tenant': tenant_name, 'name': vrf_name})

            # Create BDs (8-12 per VRF)
            for vrf_name in tenant_vrfs:
                bd_count = random.randint(8, 12)
                for i in range(bd_count):
                    bd_name = f'{vrf_name}_BD{i+1}'
                    subnet = f'10.{random.randint(0, 255)}.{random.randint(0, 255)}.1/24'

                    bd = {
                        'fvBD': {
                            'attributes': {
                                'dn': f'uni/tn-{tenant_name}/BD-{bd_name}',
                                'name': bd_name,
                                'arpFlood': 'yes',
                                'unicastRoute': 'yes',
                                'descr': f'Bridge Domain for {tenant_name}'
                            }
                        }
                    }
                    self.imdata.append(bd)
                    self.bds.append({
                        'tenant': tenant_name,
                        'vrf': vrf_name,
                        'name': bd_name,
                        'subnet': subnet
                    })

                    # Add subnet
                    subnet_obj = {
                        'fvSubnet': {
                            'attributes': {
                                'dn': f'uni/tn-{tenant_name}/BD-{bd_name}/subnet-[{subnet}]',
                                'ip': subnet,
                                'scope': 'public'
                            }
                        }
                    }
                    self.imdata.append(subnet_obj)

        print(f"   Generated {len(self.tenants)} tenants")
        print(f"   Generated {len(self.vrfs)} VRFs")
        print(f"   Generated {len(self.bds)} Bridge Domains")

    def _generate_epgs_with_coupling(self):
        """Generate EPGs with realistic coupling scenarios."""
        print("\n3. Generating EPGs with Coupling Scenarios...")

        epg_id = 1
        coupling_stats = {
            'fex_only': 0,
            'leaf_only': 0,
            'fex_and_leaf': 0,
            'multi_fex': 0,
            'shared_vlans': 0
        }

        for tenant_config in self.config['tenants']:
            tenant_name = tenant_config['name']
            epg_count = tenant_config['epg_count']
            app_count = tenant_config['app_profiles']

            # Get tenant's BDs
            tenant_bds = [bd for bd in self.bds if bd['tenant'] == tenant_name]

            for app_idx in range(app_count):
                app_name = f'{tenant_name}_APP{app_idx+1}'
                epgs_per_app = epg_count // app_count

                for epg_idx in range(epgs_per_app):
                    epg_name = f'EPG{epg_id:04d}_{app_name}'
                    bd = random.choice(tenant_bds)

                    # Determine deployment pattern
                    pattern = self._choose_deployment_pattern()
                    coupling_stats[pattern] += 1

                    # Generate VLAN and path attachments based on pattern
                    vlans, devices = self._generate_epg_deployment(pattern, epg_name)

                    # Check for VLAN sharing (coupling scenario)
                    if random.random() < self.config['coupling_scenarios']['shared_vlans']:
                        # Reuse an existing VLAN from same device
                        device_id = devices[0] if devices else None
                        if device_id and device_id in self.used_vlans and self.used_vlans[device_id]:
                            vlans[0] = random.choice(list(self.used_vlans[device_id]))
                            coupling_stats['shared_vlans'] += 1

                    # Track VLAN usage
                    for device_id, vlan in zip(devices, vlans):
                        if device_id not in self.used_vlans:
                            self.used_vlans[device_id] = set()
                        self.used_vlans[device_id].add(vlan)

                    # Create EPG
                    epg = {
                        'fvAEPg': {
                            'attributes': {
                                'dn': f'uni/tn-{tenant_name}/ap-{app_name}/epg-{epg_name}',
                                'name': epg_name,
                                'descr': f'{pattern} deployment',
                                'pcEnfPref': 'enforced',
                                'prefGrMemb': 'exclude'
                            }
                        }
                    }
                    self.imdata.append(epg)

                    self.epgs.append({
                        'tenant': tenant_name,
                        'app': app_name,
                        'name': epg_name,
                        'bd': bd['name'],
                        'pattern': pattern,
                        'vlans': vlans,
                        'devices': devices
                    })

                    # Generate path attachments
                    self._generate_path_attachments(tenant_name, app_name, epg_name, devices, vlans)

                    epg_id += 1

        print(f"   Generated {len(self.epgs)} EPGs")
        print(f"\n   Deployment Patterns:")
        for pattern, count in coupling_stats.items():
            pct = (count / len(self.epgs) * 100) if self.epgs else 0
            print(f"      {pattern:20s}: {count:4d} ({pct:5.1f}%)")

    def _choose_deployment_pattern(self) -> str:
        """Choose deployment pattern based on configured probabilities."""
        rand = random.random()
        patterns = self.config['deployment_patterns']

        cumulative = 0
        for pattern, prob in patterns.items():
            cumulative += prob
            if rand <= cumulative:
                return pattern

        return 'fex_only'  # Default

    def _generate_epg_deployment(self, pattern: str, epg_name: str) -> Tuple[List[int], List[str]]:
        """Generate VLAN and device assignments based on deployment pattern."""
        vlans = []
        devices = []

        if pattern == 'fex_only':
            # Single FEX
            fex = random.choice(self.fexes)
            vlan = self._get_next_vlan()
            vlans.append(vlan)
            devices.append(f"fex-{fex['id']}")

        elif pattern == 'leaf_only':
            # Single leaf
            leaf = random.choice(self.leafs)
            vlan = self._get_next_vlan()
            vlans.append(vlan)
            devices.append(f"leaf-{leaf['id']}")

        elif pattern == 'fex_and_leaf':
            # Both FEX and leaf (coupling!)
            fex = random.choice(self.fexes)
            leaf_id = fex['leaf_id']
            vlan = self._get_next_vlan()
            vlans.extend([vlan, vlan])  # Same VLAN on both
            devices.extend([f"fex-{fex['id']}", f"leaf-{leaf_id}"])

        elif pattern == 'multi_fex':
            # Multiple FEX (high coupling!)
            fex_count = random.randint(2, 4)
            # Try to get FEX from same DC for realism
            dc = random.choice(self.config['data_centers'])
            dc_fexes = [f for f in self.fexes if f['dc'] == dc]
            if len(dc_fexes) < fex_count:
                dc_fexes = self.fexes

            selected_fexes = random.sample(dc_fexes, min(fex_count, len(dc_fexes)))
            vlan = self._get_next_vlan()
            for fex in selected_fexes:
                vlans.append(vlan)  # Same VLAN across all FEX
                devices.append(f"fex-{fex['id']}")

        return vlans, devices

    def _get_next_vlan(self) -> int:
        """Get next available VLAN from pool."""
        if self.vlan_idx >= len(self.vlan_pool):
            # Wrap around if we run out
            self.vlan_idx = 0
        vlan = self.vlan_pool[self.vlan_idx]
        self.vlan_idx += 1
        return vlan

    def _generate_path_attachments(self, tenant: str, app: str, epg: str,
                                   devices: List[str], vlans: List[int]):
        """Generate path attachments for EPG."""
        for device, vlan in zip(devices, vlans):
            if device.startswith('fex-'):
                fex_id = device.split('-')[1]
                # Find leaf for this FEX
                fex_info = next((f for f in self.fexes if str(f['id']) == fex_id), None)
                if fex_info:
                    leaf_id = fex_info['leaf_id']
                    path_dn = f'topology/pod-1/paths-{leaf_id}/pathep-[eth{fex_id}/1/1]'
                else:
                    continue
            else:  # leaf
                leaf_id = device.split('-')[1]
                path_dn = f'topology/pod-1/paths-{leaf_id}/pathep-[eth1/1]'

            path_att = {
                'fvRsPathAtt': {
                    'attributes': {
                        'dn': f'uni/tn-{tenant}/ap-{app}/epg-{epg}/rspathAtt-[{path_dn}]',
                        'tDn': path_dn,
                        'encap': f'vlan-{vlan}',
                        'mode': 'regular',
                        'instrImedcy': 'immediate'
                    }
                }
            }
            self.imdata.append(path_att)

    def _generate_contracts(self):
        """Generate contracts including cross-tenant contracts."""
        print("\n4. Generating Contracts...")

        total_contracts = 150
        cross_tenant_count = int(total_contracts *
                                self.config['coupling_scenarios']['cross_tenant_contracts'])

        # Intra-tenant contracts
        for i in range(total_contracts - cross_tenant_count):
            tenant = random.choice(self.tenants)
            contract_name = f'Contract_{tenant}_{i+1}'

            contract = {
                'vzBrCP': {
                    'attributes': {
                        'dn': f'uni/tn-{tenant}/brc-{contract_name}',
                        'name': contract_name,
                        'scope': 'context',
                        'descr': f'Intra-tenant contract for {tenant}'
                    }
                }
            }
            self.imdata.append(contract)
            self.contracts.append({
                'tenant': tenant,
                'name': contract_name,
                'scope': 'context',
                'type': 'intra-tenant'
            })

        # Cross-tenant contracts (coupling!)
        for i in range(cross_tenant_count):
            tenant = random.choice(self.tenants)
            contract_name = f'XTenant_Contract_{i+1}'

            contract = {
                'vzBrCP': {
                    'attributes': {
                        'dn': f'uni/tn-{tenant}/brc-{contract_name}',
                        'name': contract_name,
                        'scope': 'tenant',  # Cross-tenant scope
                        'descr': 'Cross-tenant contract (coupling)'
                    }
                }
            }
            self.imdata.append(contract)
            self.contracts.append({
                'tenant': tenant,
                'name': contract_name,
                'scope': 'tenant',
                'type': 'cross-tenant'
            })

        print(f"   Generated {len(self.contracts)} contracts")
        print(f"      Intra-tenant: {total_contracts - cross_tenant_count}")
        print(f"      Cross-tenant: {cross_tenant_count} (coupling)")

    def _generate_cmdb(self):
        """Generate CMDB correlation data."""
        print("\n5. Generating CMDB Data...")

        # Add all leafs
        for leaf in self.leafs:
            record = {
                'device_name': leaf['name'],
                'serial_number': f'LEAF{leaf["id"]:05d}SN',
                'model': leaf['model'],
                'device_type': 'Leaf Switch',
                'location': leaf['name'].split('-')[1] if '-' in leaf['name'] else 'Unknown',
                'rack': f'R{random.randint(1, 40):02d}',
                'status': 'Active',
                'purchase_date': (datetime.now() - timedelta(days=random.randint(30, 1095))).strftime('%Y-%m-%d')
            }
            self.cmdb_records.append(record)

        # Add all FEX
        for fex in self.fexes:
            record = {
                'device_name': f'FEX-{fex["dc"]}-{fex["id"]}',
                'serial_number': f'FEX{fex["id"]:06d}ABC',
                'model': fex['model'],
                'device_type': 'FEX',
                'location': fex['dc'],
                'rack': f'R{random.randint(1, 40):02d}',
                'status': 'Active',
                'purchase_date': (datetime.now() - timedelta(days=random.randint(30, 1095))).strftime('%Y-%m-%d')
            }
            self.cmdb_records.append(record)

        print(f"   Generated {len(self.cmdb_records)} CMDB records")

    def _print_statistics(self):
        """Print generation statistics."""
        print("\n" + "=" * 70)
        print("Generation Complete - Summary Statistics")
        print("=" * 70)
        print(f"Topology:")
        print(f"  Leaf Switches:        {len(self.leafs)}")
        print(f"  FEX Devices:          {len(self.fexes)}")
        print(f"  Avg FEX per Leaf:     {len(self.fexes) / len(self.leafs):.2f}")
        print(f"\nTenants & Segmentation:")
        print(f"  Tenants:              {len(self.tenants)}")
        print(f"  VRFs:                 {len(self.vrfs)}")
        print(f"  Bridge Domains:       {len(self.bds)}")
        print(f"  EPGs:                 {len(self.epgs)}")
        print(f"\nContracts:")
        print(f"  Total Contracts:      {len(self.contracts)}")
        cross_tenant = sum(1 for c in self.contracts if c['type'] == 'cross-tenant')
        print(f"  Cross-Tenant:         {cross_tenant} ({cross_tenant/len(self.contracts)*100:.1f}%)")
        print(f"\nCoupling Analysis:")

        # Calculate coupling metrics
        fex_only = sum(1 for e in self.epgs if e['pattern'] == 'fex_only')
        leaf_only = sum(1 for e in self.epgs if e['pattern'] == 'leaf_only')
        fex_and_leaf = sum(1 for e in self.epgs if e['pattern'] == 'fex_and_leaf')
        multi_fex = sum(1 for e in self.epgs if e['pattern'] == 'multi_fex')

        coupled_epgs = fex_and_leaf + multi_fex
        print(f"  EPGs with Coupling:   {coupled_epgs} ({coupled_epgs/len(self.epgs)*100:.1f}%)")
        print(f"    FEX+Leaf:           {fex_and_leaf}")
        print(f"    Multi-FEX:          {multi_fex}")
        print(f"  Standalone EPGs:      {fex_only + leaf_only}")

        # VLAN sharing analysis
        shared_vlans = 0
        for device_id, vlans in self.used_vlans.items():
            # Count EPGs using each VLAN
            for vlan in vlans:
                epg_count = sum(1 for e in self.epgs if vlan in e['vlans'] and device_id in
                              [f"fex-{d.split('-')[1]}" if 'fex' in d else f"leaf-{d.split('-')[1]}"
                               for d in e['devices']])
                if epg_count > 1:
                    shared_vlans += 1

        print(f"  Shared VLANs:         {shared_vlans}")
        print(f"\nData Volume:")
        print(f"  Total ACI Objects:    {len(self.imdata)}")
        print(f"  CMDB Records:         {len(self.cmdb_records)}")


def main():
    """Generate enterprise fabric data and save to files."""
    print("Enterprise-Scale ACI Fabric Data Generator")
    print("=" * 70)

    # Create output directory
    output_dir = Path("data/samples")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate data
    generator = EnterpriseFabricGenerator(CONFIG)
    aci_data, cmdb_data = generator.generate()

    # Save ACI data
    aci_file = output_dir / "sample_enterprise_1000epg.json"
    with open(aci_file, 'w') as f:
        json.dump(aci_data, f, indent=2)

    print(f"\nSaved ACI data to: {aci_file}")
    print(f"  File size: {aci_file.stat().st_size / 1024 / 1024:.2f} MB")

    # Save CMDB data
    cmdb_file = output_dir / "sample_enterprise_1000epg_cmdb.csv"
    with open(cmdb_file, 'w', newline='') as f:
        if cmdb_data:
            writer = csv.DictWriter(f, fieldnames=cmdb_data[0].keys())
            writer.writeheader()
            writer.writerows(cmdb_data)

    print(f"Saved CMDB data to: {cmdb_file}")
    print(f"  File size: {cmdb_file.stat().st_size / 1024:.2f} KB")

    print("\n" + "=" * 70)
    print("Generation Complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
