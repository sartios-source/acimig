"""
ACI to EVPN Migration Engine
Maps ACI constructs to EVPN/VXLAN equivalents and generates migration plans.
"""
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import re


class ACIToEVPNMapper:
    """
    Maps ACI objects to EVPN constructs.

    ACI → EVPN Mapping:
    - fvCtx (VRF) → L3 VNI + VRF
    - fvBD (Bridge Domain) → L2 VNI + VLAN
    - fvAEPg (EPG) → VLAN + access ports
    - vzBrCP (Contract) → ACL/Route-map/Zone-based policy
    - fvTenant → VRF separation or customer isolation
    """

    def __init__(self, aci_objects: List[Dict[str, Any]]):
        self.aci_objects = aci_objects

        # Categorized ACI objects
        self.tenants = []
        self.vrfs = []
        self.bds = []
        self.epgs = []
        self.contracts = []
        self.path_attachments = []
        self.subnets = []

        # EVPN constructs
        self.l3_vnis = {}  # VRF → L3 VNI mapping
        self.l2_vnis = {}  # BD → L2 VNI mapping
        self.vlans = {}    # EPG → VLAN mapping

        # VNI allocation
        self.l3_vni_start = 50000
        self.l2_vni_start = 10000
        self.vlan_start = 100

        self._categorize_objects()

    def _categorize_objects(self):
        """Categorize ACI objects by type."""
        for obj in self.aci_objects:
            obj_type = obj.get('type')
            attrs = obj.get('attributes', {})

            if obj_type == 'fvTenant':
                self.tenants.append(attrs)
            elif obj_type == 'fvCtx':
                self.vrfs.append(attrs)
            elif obj_type == 'fvBD':
                self.bds.append(attrs)
            elif obj_type == 'fvAEPg':
                self.epgs.append(attrs)
            elif obj_type == 'vzBrCP':
                self.contracts.append(attrs)
            elif obj_type == 'fvRsPathAtt':
                self.path_attachments.append(attrs)
            elif obj_type == 'fvSubnet':
                self.subnets.append(attrs)

    def generate_evpn_mapping(self) -> Dict[str, Any]:
        """Generate complete ACI to EVPN mapping."""

        # Allocate L3 VNIs for VRFs
        for idx, vrf in enumerate(self.vrfs):
            vrf_name = vrf.get('name', '')
            vrf_dn = vrf.get('dn', '')
            l3_vni = self.l3_vni_start + idx

            self.l3_vnis[vrf_dn] = {
                'name': vrf_name,
                'l3_vni': l3_vni,
                'rd': f'auto',  # Will be device-specific
                'rt_import': f'{l3_vni}:{l3_vni}',
                'rt_export': f'{l3_vni}:{l3_vni}',
            }

        # Allocate L2 VNIs and VLANs for Bridge Domains
        for idx, bd in enumerate(self.bds):
            bd_name = bd.get('name', '')
            bd_dn = bd.get('dn', '')
            vrf_ref = bd.get('vrf', '')

            l2_vni = self.l2_vni_start + idx
            vlan = self.vlan_start + idx

            # Find associated subnets
            bd_subnets = []
            for subnet in self.subnets:
                if bd_dn in subnet.get('dn', ''):
                    subnet_ip = subnet.get('ip', '')
                    bd_subnets.append({
                        'ip': subnet_ip,
                        'scope': subnet.get('scope', 'private'),
                    })

            self.l2_vnis[bd_dn] = {
                'name': bd_name,
                'l2_vni': l2_vni,
                'vlan': vlan,
                'vrf': vrf_ref,
                'subnets': bd_subnets,
                'arp_suppression': True,  # Best practice for EVPN
            }

        # Map EPGs to VLANs (reuse BD VLANs)
        for epg in self.epgs:
            epg_name = epg.get('name', '')
            epg_dn = epg.get('dn', '')
            bd_ref = epg.get('bd', '')

            # Find the BD DN that matches this BD name
            bd_dn = None
            for dn, bd_data in self.l2_vnis.items():
                if bd_data['name'] == bd_ref:
                    bd_dn = dn
                    break

            if bd_dn:
                self.vlans[epg_dn] = {
                    'name': epg_name,
                    'vlan': self.l2_vnis[bd_dn]['vlan'],
                    'l2_vni': self.l2_vnis[bd_dn]['l2_vni'],
                    'bd': bd_ref,
                }

        return {
            'l3_vnis': self.l3_vnis,
            'l2_vnis': self.l2_vnis,
            'vlans': self.vlans,
        }

    def identify_migration_complexity(self) -> Dict[str, Any]:
        """Identify factors that increase migration complexity."""
        complexity = {
            'score': 0,
            'factors': [],
            'risks': [],
        }

        # Factor 1: Number of tenants (multi-tenancy complexity)
        tenant_count = len(self.tenants)
        if tenant_count > 5:
            complexity['factors'].append(f'High tenant count ({tenant_count})')
            complexity['score'] += 20

        # Factor 2: Contract complexity
        contract_count = len(self.contracts)
        if contract_count > 20:
            complexity['factors'].append(f'Complex contract policy ({contract_count} contracts)')
            complexity['score'] += 30
            complexity['risks'].append('Contracts must be translated to ACLs or zone-based policies')

        # Factor 3: Service graph usage
        service_graphs = [obj for obj in self.aci_objects if obj.get('type') == 'vzRtGraphAtt']
        if service_graphs:
            complexity['factors'].append(f'Service graphs in use ({len(service_graphs)})')
            complexity['score'] += 25
            complexity['risks'].append('L4-7 service insertion requires redesign')

        # Factor 4: L3Out complexity
        l3outs = [obj for obj in self.aci_objects if obj.get('type') == 'l3extInstP']
        if len(l3outs) > 5:
            complexity['factors'].append(f'Multiple L3Outs ({len(l3outs)})')
            complexity['score'] += 15

        # Factor 5: EPG per BD ratio (design complexity)
        bd_count = len(self.bds)
        epg_count = len(self.epgs)
        if bd_count > 0:
            epg_per_bd = epg_count / bd_count
            if epg_per_bd > 3:
                complexity['factors'].append(f'High EPG-to-BD ratio ({epg_per_bd:.1f}:1)')
                complexity['score'] += 10

        # Determine overall complexity level
        if complexity['score'] < 30:
            complexity['level'] = 'low'
        elif complexity['score'] < 60:
            complexity['level'] = 'medium'
        else:
            complexity['level'] = 'high'

        return complexity


class EVPNConfigGenerator:
    """Generate EVPN configuration for various platforms."""

    def __init__(self, mapping: Dict[str, Any], platform: str = 'nxos'):
        self.mapping = mapping
        self.platform = platform.lower()

        self.l3_vnis = mapping.get('l3_vnis', {})
        self.l2_vnis = mapping.get('l2_vnis', {})

    def generate_config(self, device_role: str = 'leaf', device_id: int = 1) -> str:
        """
        Generate EVPN configuration for a device.

        Args:
            device_role: 'leaf', 'spine', or 'border'
            device_id: Device identifier for unique RD/RT generation
        """
        if self.platform == 'nxos':
            return self._generate_nxos_config(device_role, device_id)
        elif self.platform == 'eos':
            return self._generate_eos_config(device_role, device_id)
        elif self.platform == 'junos':
            return self._generate_junos_config(device_role, device_id)
        else:
            return f"# Unsupported platform: {self.platform}"

    def _generate_nxos_config(self, device_role: str, device_id: int) -> str:
        """Generate Cisco NX-OS EVPN configuration."""
        config = []

        # Feature enablement
        config.append("! ========================================")
        config.append("! NX-OS EVPN Configuration")
        config.append("! ========================================")
        config.append("")
        config.append("feature bgp")
        config.append("feature nv overlay")
        config.append("feature vn-segment-vlan-based")
        config.append("")

        if device_role == 'leaf':
            config.append("! NVE Interface")
            config.append("interface nve1")
            config.append("  no shutdown")
            config.append("  source-interface loopback1")
            config.append("  host-reachability protocol bgp")
            config.append("")

            # L3 VNI configuration
            config.append("! L3 VNIs (VRF VNIs)")
            for vrf_dn, vrf_data in self.l3_vnis.items():
                l3_vni = vrf_data['l3_vni']
                config.append(f"  member vni {l3_vni} associate-vrf")
            config.append("")

            # L2 VNI configuration
            config.append("! L2 VNIs")
            for bd_dn, bd_data in self.l2_vnis.items():
                l2_vni = bd_data['l2_vni']
                config.append(f"  member vni {l2_vni}")
                config.append(f"    suppress-arp")
                config.append(f"    ingress-replication protocol bgp")
            config.append("")

            # VLAN to VNI mapping
            config.append("! VLAN to VNI Mapping")
            for bd_dn, bd_data in self.l2_vnis.items():
                vlan = bd_data['vlan']
                l2_vni = bd_data['l2_vni']
                bd_name = bd_data['name']
                config.append(f"vlan {vlan}")
                config.append(f"  name {bd_name}")
                config.append(f"  vn-segment {l2_vni}")
                config.append("")

            # VRF configuration
            config.append("! VRF Configuration")
            for vrf_dn, vrf_data in self.l3_vnis.items():
                vrf_name = vrf_data['name']
                l3_vni = vrf_data['l3_vni']
                rd = f"{device_id}:{l3_vni}"
                rt = vrf_data['rt_import']

                config.append(f"vrf context {vrf_name}")
                config.append(f"  vni {l3_vni}")
                config.append(f"  rd {rd}")
                config.append(f"  address-family ipv4 unicast")
                config.append(f"    route-target import {rt}")
                config.append(f"    route-target export {rt}")
                config.append(f"    route-target import {rt} evpn")
                config.append(f"    route-target export {rt} evpn")
                config.append("")

            # SVI configuration
            config.append("! SVI (Anycast Gateway) Configuration")
            for bd_dn, bd_data in self.l2_vnis.items():
                vlan = bd_data['vlan']
                bd_name = bd_data['name']
                vrf_name = bd_data['vrf']

                config.append(f"interface Vlan{vlan}")
                config.append(f"  description {bd_name}")
                config.append(f"  no shutdown")
                config.append(f"  vrf member {vrf_name}")

                # Add subnet IPs if available
                for subnet in bd_data.get('subnets', []):
                    subnet_ip = subnet['ip']
                    config.append(f"  ip address {subnet_ip}")

                config.append(f"  fabric forwarding mode anycast-gateway")
                config.append("")

            # BGP EVPN configuration
            config.append("! BGP EVPN Configuration")
            config.append("router bgp 65000")
            config.append(f"  router-id 10.0.0.{device_id}")
            config.append("  address-family l2vpn evpn")
            config.append("    advertise-pip")
            config.append("")

            for vrf_dn, vrf_data in self.l3_vnis.items():
                vrf_name = vrf_data['name']
                config.append(f"  vrf {vrf_name}")
                config.append(f"    address-family ipv4 unicast")
                config.append(f"      advertise l2vpn evpn")
                config.append("")

        elif device_role == 'spine':
            config.append("! Spine Configuration (Route Reflector)")
            config.append("router bgp 65000")
            config.append(f"  router-id 10.0.0.{device_id}")
            config.append("  address-family l2vpn evpn")
            config.append("    retain route-target all")
            config.append("  template peer LEAF")
            config.append("    remote-as 65000")
            config.append("    update-source loopback0")
            config.append("    address-family l2vpn evpn")
            config.append("      send-community extended")
            config.append("      route-reflector-client")
            config.append("")

        return "\n".join(config)

    def _generate_eos_config(self, device_role: str, device_id: int) -> str:
        """Generate Arista EOS EVPN configuration."""
        config = []

        config.append("! ========================================")
        config.append("! Arista EOS EVPN Configuration")
        config.append("! ========================================")
        config.append("")

        if device_role == 'leaf':
            # VXLAN interface
            config.append("interface Vxlan1")
            config.append("   vxlan source-interface Loopback1")
            config.append("   vxlan udp-port 4789")

            # L2 VNI mappings
            for bd_dn, bd_data in self.l2_vnis.items():
                vlan = bd_data['vlan']
                l2_vni = bd_data['l2_vni']
                config.append(f"   vxlan vlan {vlan} vni {l2_vni}")

            # L3 VNI mappings
            for vrf_dn, vrf_data in self.l3_vnis.items():
                vrf_name = vrf_data['name']
                l3_vni = vrf_data['l3_vni']
                config.append(f"   vxlan vrf {vrf_name} vni {l3_vni}")
            config.append("")

            # VRF configuration
            for vrf_dn, vrf_data in self.l3_vnis.items():
                vrf_name = vrf_data['name']
                config.append(f"vrf instance {vrf_name}")
                config.append("")

            # VLAN configuration
            for bd_dn, bd_data in self.l2_vnis.items():
                vlan = bd_data['vlan']
                bd_name = bd_data['name']
                config.append(f"vlan {vlan}")
                config.append(f"   name {bd_name}")
                config.append("")

            # SVI configuration
            for bd_dn, bd_data in self.l2_vnis.items():
                vlan = bd_data['vlan']
                vrf_name = bd_data['vrf']

                config.append(f"interface Vlan{vlan}")
                config.append(f"   vrf {vrf_name}")

                for subnet in bd_data.get('subnets', []):
                    subnet_ip = subnet['ip']
                    config.append(f"   ip address virtual {subnet_ip}")
                config.append("")

            # BGP configuration
            config.append("router bgp 65000")
            config.append(f"   router-id 10.0.0.{device_id}")
            config.append("   neighbor SPINES peer group")
            config.append("   neighbor SPINES remote-as 65000")
            config.append("   neighbor SPINES update-source Loopback0")
            config.append("   neighbor SPINES send-community extended")
            config.append("   address-family evpn")
            config.append("      neighbor SPINES activate")
            config.append("")

            for vrf_dn, vrf_data in self.l3_vnis.items():
                vrf_name = vrf_data['name']
                l3_vni = vrf_data['l3_vni']
                rd = f"{device_id}:{l3_vni}"
                rt = vrf_data['rt_import']

                config.append(f"   vrf {vrf_name}")
                config.append(f"      rd {rd}")
                config.append(f"      route-target import evpn {rt}")
                config.append(f"      route-target export evpn {rt}")
                config.append("      redistribute connected")
                config.append("")

        return "\n".join(config)

    def _generate_junos_config(self, device_role: str, device_id: int) -> str:
        """Generate Juniper Junos EVPN configuration (simplified)."""
        config = []

        config.append("/* ======================================== */")
        config.append("/* Juniper Junos EVPN Configuration */")
        config.append("/* ======================================== */")
        config.append("")
        config.append("set protocols evpn encapsulation vxlan")
        config.append("set protocols evpn extended-vni-list all")
        config.append("")

        # VRF configuration
        for vrf_dn, vrf_data in self.l3_vnis.items():
            vrf_name = vrf_data['name']
            l3_vni = vrf_data['l3_vni']

            config.append(f"set routing-instances {vrf_name} instance-type vrf")
            config.append(f"set routing-instances {vrf_name} protocols evpn ip-prefix-routes advertise direct-nexthop")
            config.append(f"set routing-instances {vrf_name} vrf-target target:{l3_vni}:{l3_vni}")
            config.append("")

        return "\n".join(config)


class EVPNMigrationPlanner:
    """Generate step-by-step ACI to EVPN migration plan."""

    def __init__(self, aci_objects: List[Dict[str, Any]], target_platform: str = 'nxos'):
        self.mapper = ACIToEVPNMapper(aci_objects)
        self.target_platform = target_platform
        self.mapping = None
        self.complexity = None

    def generate_migration_plan(self) -> Dict[str, Any]:
        """Generate complete migration plan."""

        # Generate mapping
        self.mapping = self.mapper.generate_evpn_mapping()

        # Assess complexity
        self.complexity = self.mapper.identify_migration_complexity()

        # Generate migration steps
        steps = self._generate_migration_steps()

        # Generate configuration samples
        config_samples = self._generate_config_samples()

        # Generate validation checklist
        validation = self._generate_validation_checklist()

        return {
            'mapping': self.mapping,
            'complexity': self.complexity,
            'steps': steps,
            'config_samples': config_samples,
            'validation': validation,
            'target_platform': self.target_platform,
        }

    def _generate_migration_steps(self) -> List[Dict[str, Any]]:
        """Generate detailed migration steps."""
        steps = [
            {
                'phase': 'Pre-Migration',
                'step': 1,
                'title': 'Document Current ACI Fabric',
                'description': 'Export all ACI configuration and create comprehensive documentation',
                'tasks': [
                    'Export tenant configurations',
                    'Document all EPG-to-port mappings',
                    'Capture current routing tables and endpoints',
                    'Document contract policies',
                    'Identify service graph dependencies',
                ],
                'duration': '1-2 days',
                'risk': 'low',
            },
            {
                'phase': 'Pre-Migration',
                'step': 2,
                'title': 'Design EVPN Fabric Architecture',
                'description': 'Design target EVPN fabric with spine-leaf topology',
                'tasks': [
                    'Define underlay IGP (OSPF/IS-IS)',
                    'Plan BGP AS and route reflector strategy',
                    'Allocate VNI ranges (L2 and L3)',
                    'Design IP addressing (loopbacks, p2p links)',
                    f'Generate {self.target_platform.upper()} configuration templates',
                ],
                'duration': '3-5 days',
                'risk': 'medium',
            },
            {
                'phase': 'Pre-Migration',
                'step': 3,
                'title': 'Build Parallel EVPN Fabric',
                'description': 'Deploy new EVPN fabric in parallel to ACI',
                'tasks': [
                    'Install and cable new switches',
                    'Configure underlay routing (OSPF/IS-IS)',
                    'Configure BGP EVPN overlay',
                    'Validate EVPN control plane',
                    'Test basic L2/L3 connectivity',
                ],
                'duration': '5-10 days',
                'risk': 'low',
            },
            {
                'phase': 'Migration',
                'step': 4,
                'title': 'Migrate Non-Critical Workloads',
                'description': 'Pilot migration with low-risk applications',
                'tasks': [
                    'Select pilot workloads (dev/test)',
                    'Configure VLANs and VNIs on EVPN fabric',
                    'Physically migrate servers or add dual-homing',
                    'Validate connectivity and policy',
                    'Monitor for issues',
                ],
                'duration': '1-2 weeks',
                'risk': 'medium',
            },
            {
                'phase': 'Migration',
                'step': 5,
                'title': 'Translate and Implement Security Policy',
                'description': 'Convert ACI contracts to EVPN policy (ACLs/zone-based)',
                'tasks': [
                    'Map contracts to ACL rules',
                    'Implement zone-based policies if needed',
                    'Configure route-map filtering for inter-VRF',
                    'Test policy enforcement',
                    'Document policy changes',
                ],
                'duration': '2-4 weeks',
                'risk': 'high',
                'warnings': [
                    'ACI contracts have finer granularity than traditional ACLs',
                    'May require application-level changes',
                ],
            },
            {
                'phase': 'Migration',
                'step': 6,
                'title': 'Migrate Production Workloads',
                'description': 'Move production applications in phases',
                'tasks': [
                    'Schedule maintenance windows',
                    'Migrate by application or tenant',
                    'Use dual-homing where possible for rollback',
                    'Validate each application after migration',
                    'Update documentation',
                ],
                'duration': '4-8 weeks',
                'risk': 'high',
                'warnings': [
                    'Requires careful coordination with application teams',
                    'Plan rollback procedures for each phase',
                ],
            },
            {
                'phase': 'Post-Migration',
                'step': 7,
                'title': 'Decommission ACI Fabric',
                'description': 'Remove ACI fabric after successful migration',
                'tasks': [
                    'Verify all workloads migrated',
                    'Keep ACI online for 30+ days as fallback',
                    'Remove ACI connections',
                    'Repurpose or decommission ACI hardware',
                    'Archive ACI configuration',
                ],
                'duration': '1-2 weeks',
                'risk': 'low',
            },
        ]

        return steps

    def _generate_config_samples(self) -> Dict[str, str]:
        """Generate sample EVPN configurations."""
        generator = EVPNConfigGenerator(self.mapping, self.target_platform)

        return {
            'leaf_switch': generator.generate_config('leaf', 1),
            'spine_switch': generator.generate_config('spine', 101),
            'border_leaf': generator.generate_config('leaf', 2),
        }

    def _generate_validation_checklist(self) -> List[Dict[str, Any]]:
        """Generate validation checklist."""
        return [
            {
                'category': 'Underlay Validation',
                'checks': [
                    {'item': 'All p2p links up', 'command': 'show ip interface brief'},
                    {'item': 'OSPF/IS-IS neighbors established', 'command': 'show ip ospf neighbors'},
                    {'item': 'Loopback reachability', 'command': 'ping <remote-loopback>'},
                ],
            },
            {
                'category': 'BGP EVPN Validation',
                'checks': [
                    {'item': 'BGP sessions established', 'command': 'show bgp l2vpn evpn summary'},
                    {'item': 'EVPN routes received', 'command': 'show bgp l2vpn evpn'},
                    {'item': 'VNI status', 'command': 'show nve vni'},
                ],
            },
            {
                'category': 'Data Plane Validation',
                'checks': [
                    {'item': 'MAC learning', 'command': 'show mac address-table'},
                    {'item': 'ARP resolution', 'command': 'show ip arp'},
                    {'item': 'L2 connectivity', 'command': 'ping <remote-host>'},
                    {'item': 'L3 connectivity', 'command': 'ping <remote-subnet>'},
                ],
            },
            {
                'category': 'Policy Validation',
                'checks': [
                    {'item': 'ACL hit counts', 'command': 'show ip access-lists'},
                    {'item': 'Allowed traffic flows', 'command': 'test traffic flows'},
                    {'item': 'Blocked traffic verification', 'command': 'verify deny rules'},
                ],
            },
        ]


def generate_evpn_migration_report(aci_objects: List[Dict[str, Any]], target_platform: str = 'nxos') -> Dict[str, Any]:
    """
    High-level function to generate complete EVPN migration report.

    Args:
        aci_objects: List of ACI objects from parsers
        target_platform: Target EVPN platform ('nxos', 'eos', 'junos')

    Returns:
        Complete migration report with mapping, plan, and configs
    """
    planner = EVPNMigrationPlanner(aci_objects, target_platform)
    return planner.generate_migration_plan()
