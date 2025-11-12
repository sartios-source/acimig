"""
Physical Connectivity and Interface Policy Analysis Module
Analyzes physical interface configurations, policy groups, profiles,
and connectivity patterns for complete migration planning.
"""
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class PhysicalConnection:
    """Represents a physical interface connection."""
    node_id: str
    interface: str
    speed: str
    admin_state: str
    oper_state: str
    description: str
    policy_group: Optional[str]
    connected_device: Optional[str]


class PhysicalConnectivityAnalyzer:
    """
    Analyzes physical connectivity, interface policies, and cabling.

    Supports:
    - Interface inventory and status
    - Interface policy group mapping
    - LLDP/CDP neighbor discovery
    - Link speed and duplex analysis
    - MTU configuration tracking
    - Interface profile documentation
    - Cabling diagram generation
    - Migration cabling plan
    """

    def __init__(self, aci_objects: List[Dict[str, Any]]):
        """
        Initialize physical connectivity analyzer with ACI object data.

        Args:
            aci_objects: List of parsed ACI objects from JSON/XML
        """
        self.aci_objects = aci_objects

        # Categorized objects
        self._interfaces = []
        self._interface_policy_groups = []
        self._interface_profiles = []
        self._lldp_neighbors = []
        self._cdp_neighbors = []
        self._fabric_nodes = []
        self._fexes = []
        self._path_attachments = []
        self._aeps = []  # Attachable Entity Profiles

        # Lookup dictionaries
        self._node_by_id = {}
        self._interface_by_dn = {}
        self._policy_group_by_dn = {}

        self._categorize_objects()

    def _categorize_objects(self):
        """Extract physical connectivity-related objects from ACI data."""
        for obj in self.aci_objects:
            obj_type = obj.get('type')
            attrs = obj.get('attributes', {})
            dn = attrs.get('dn', '')

            # Physical interfaces
            if obj_type == 'ethpmPhysIf':
                self._interfaces.append(attrs)
                if dn:
                    self._interface_by_dn[dn] = attrs

            # Interface policy groups (access/PC/VPC)
            elif obj_type in ['infraAccPortGrp', 'infraAccBndlGrp']:
                self._interface_policy_groups.append(attrs)
                if dn:
                    self._policy_group_by_dn[dn] = attrs

            # Interface profiles (selector profiles)
            elif obj_type == 'infraAccPortP':
                self._interface_profiles.append(attrs)

            # LLDP neighbors
            elif obj_type == 'lldpAdjEp':
                self._lldp_neighbors.append(attrs)

            # CDP neighbors
            elif obj_type == 'cdpAdjEp':
                self._cdp_neighbors.append(attrs)

            # Fabric nodes
            elif obj_type == 'fabricNode':
                self._fabric_nodes.append(attrs)
                node_id = attrs.get('id')
                if node_id:
                    self._node_by_id[node_id] = attrs

            # FEX devices
            elif obj_type == 'eqptFex':
                self._fexes.append(attrs)

            # Path attachments (for EPG-to-interface mapping)
            elif obj_type == 'fvRsPathAtt':
                self._path_attachments.append(attrs)

            # Attachable Entity Profiles
            elif obj_type == 'infraAttEntityP':
                self._aeps.append(attrs)

        logger.info(
            f"Physical Connectivity Analysis: Found {len(self._interfaces)} interfaces, "
            f"{len(self._interface_policy_groups)} policy groups, "
            f"{len(self._lldp_neighbors)} LLDP neighbors, "
            f"{len(self._cdp_neighbors)} CDP neighbors"
        )

    def analyze_interface_inventory(self) -> Dict[str, Any]:
        """
        Analyze physical interface inventory across the fabric.

        Returns:
            Dictionary containing:
            - interfaces: List of all interfaces with details
            - by_node: Interfaces grouped by node
            - by_speed: Distribution by speed (1G, 10G, 25G, 40G, 100G)
            - by_state: Distribution by operational state
            - total_count: Total interface count
            - utilization: Interface utilization statistics
        """
        results = {
            'interfaces': [],
            'by_node': defaultdict(list),
            'by_speed': defaultdict(int),
            'by_state': {'up': 0, 'down': 0, 'unknown': 0},
            'total_count': len(self._interfaces),
            'utilization': {'used': 0, 'unused': 0, 'utilization_rate': 0}
        }

        for interface in self._interfaces:
            dn = interface.get('dn', '')
            node_id = self._extract_node_id(dn)
            interface_id = self._extract_interface_id(dn)

            # Parse interface attributes
            oper_state = interface.get('operSt', 'unknown')
            admin_state = interface.get('adminSt', 'unknown')
            speed = interface.get('operSpeed', 'unknown')
            mtu = interface.get('operMtu')
            usage = interface.get('usage')

            # Track operational state
            if oper_state == 'up':
                results['by_state']['up'] += 1
                results['utilization']['used'] += 1
            elif oper_state == 'down':
                results['by_state']['down'] += 1
                if usage in ['discovery', 'unused']:
                    results['utilization']['unused'] += 1
                else:
                    results['utilization']['used'] += 1
            else:
                results['by_state']['unknown'] += 1

            # Track speed distribution
            if speed and speed != 'unknown':
                results['by_speed'][speed] += 1

            # Get connected device (via LLDP/CDP)
            neighbor = self._get_neighbor_for_interface(dn)

            # Get policy group
            policy_group = self._get_policy_group_for_interface(dn)

            # Get EPG attachments
            epg_attachments = self._get_epg_attachments_for_interface(dn)

            interface_info = {
                'node_id': node_id,
                'node_name': self._get_node_name(node_id),
                'interface': interface_id,
                'dn': dn,
                'admin_state': admin_state,
                'oper_state': oper_state,
                'speed': speed,
                'mtu': mtu,
                'usage': usage,
                'description': interface.get('descr', ''),
                'policy_group': policy_group,
                'neighbor': neighbor,
                'epg_count': len(epg_attachments),
                'epgs': epg_attachments
            }

            results['interfaces'].append(interface_info)
            results['by_node'][node_id].append(interface_info)

        # Calculate utilization rate
        if results['total_count'] > 0:
            results['utilization']['utilization_rate'] = round(
                (results['utilization']['used'] / results['total_count']) * 100, 2
            )

        # Convert defaultdict to regular dict
        results['by_node'] = dict(results['by_node'])
        results['by_speed'] = dict(results['by_speed'])

        return results

    def analyze_interface_policies(self) -> Dict[str, Any]:
        """
        Analyze interface policy groups and profiles.

        Returns:
            Dictionary containing:
            - policy_groups: List of policy groups with settings
            - profiles: List of interface profiles with port selectors
            - aeps: Attachable Entity Profiles with domain mappings
            - policy_distribution: Count of interfaces per policy
        """
        results = {
            'policy_groups': [],
            'profiles': [],
            'aeps': [],
            'policy_distribution': defaultdict(int)
        }

        # Analyze policy groups
        for policy_group in self._interface_policy_groups:
            dn = policy_group.get('dn', '')
            name = policy_group.get('name')
            lag_type = policy_group.get('lagT', 'not-aggregated')  # link, node (VPC)

            # Get policy references (CDP, LLDP, Link Level, etc.)
            policies = self._get_policies_for_group(dn)

            # Count interfaces using this policy group
            interface_count = self._count_interfaces_with_policy(dn)
            results['policy_distribution'][name] = interface_count

            policy_info = {
                'name': name,
                'dn': dn,
                'lag_type': lag_type,
                'type': 'vpc' if lag_type == 'node' else 'port-channel' if lag_type == 'link' else 'access',
                'policies': policies,
                'interface_count': interface_count
            }

            results['policy_groups'].append(policy_info)

        # Analyze interface profiles
        for profile in self._interface_profiles:
            dn = profile.get('dn', '')
            name = profile.get('name')

            # Get port selectors
            port_selectors = self._get_port_selectors_for_profile(dn)

            profile_info = {
                'name': name,
                'dn': dn,
                'port_selectors': port_selectors,
                'selector_count': len(port_selectors)
            }

            results['profiles'].append(profile_info)

        # Analyze AEPs
        for aep in self._aeps:
            dn = aep.get('dn', '')
            name = aep.get('name')

            # Get domain mappings
            domains = self._get_domains_for_aep(dn)

            aep_info = {
                'name': name,
                'dn': dn,
                'domains': domains,
                'domain_count': len(domains)
            }

            results['aeps'].append(aep_info)

        results['policy_distribution'] = dict(results['policy_distribution'])

        return results

    def discover_network_neighbors(self) -> Dict[str, Any]:
        """
        Discover network neighbors via LLDP and CDP.

        Returns:
            Dictionary containing:
            - lldp_neighbors: List of LLDP-discovered neighbors
            - cdp_neighbors: List of CDP-discovered neighbors
            - topology_map: Connectivity map of discovered devices
            - external_devices: Non-ACI devices connected to fabric
        """
        results = {
            'lldp_neighbors': [],
            'cdp_neighbors': [],
            'topology_map': [],
            'external_devices': []
        }

        # Process LLDP neighbors
        for neighbor in self._lldp_neighbors:
            dn = neighbor.get('dn', '')
            node_id = self._extract_node_id(dn)
            interface_id = self._extract_interface_id(dn)

            neighbor_info = {
                'local_node': node_id,
                'local_interface': interface_id,
                'neighbor_device': neighbor.get('sysName', 'unknown'),
                'neighbor_interface': neighbor.get('portIdV', 'unknown'),
                'neighbor_description': neighbor.get('sysDesc', ''),
                'capabilities': neighbor.get('mgmtPortMac', ''),
                'protocol': 'LLDP'
            }

            results['lldp_neighbors'].append(neighbor_info)

            # Check if external device (non-ACI)
            if not self._is_aci_device(neighbor.get('sysName', '')):
                results['external_devices'].append(neighbor_info)

        # Process CDP neighbors
        for neighbor in self._cdp_neighbors:
            dn = neighbor.get('dn', '')
            node_id = self._extract_node_id(dn)
            interface_id = self._extract_interface_id(dn)

            neighbor_info = {
                'local_node': node_id,
                'local_interface': interface_id,
                'neighbor_device': neighbor.get('devId', 'unknown'),
                'neighbor_interface': neighbor.get('portId', 'unknown'),
                'neighbor_platform': neighbor.get('platId', ''),
                'neighbor_ip': neighbor.get('mgmtIp', ''),
                'protocol': 'CDP'
            }

            results['cdp_neighbors'].append(neighbor_info)

            # Check if external device (non-ACI)
            if not self._is_aci_device(neighbor.get('devId', '')):
                results['external_devices'].append(neighbor_info)

        # Build topology map
        results['topology_map'] = self._build_topology_map(
            results['lldp_neighbors'] + results['cdp_neighbors']
        )

        return results

    def generate_cabling_diagram(self) -> Dict[str, Any]:
        """
        Generate cabling diagram data for visualization.

        Returns:
            Dictionary containing:
            - connections: List of physical connections with endpoints
            - devices: List of devices (nodes, FEXes, external)
            - diagram_format: Data format for visualization tools
        """
        interface_inventory = self.analyze_interface_inventory()
        neighbor_discovery = self.discover_network_neighbors()

        connections = []
        devices = set()

        # Add fabric nodes
        for node in self._fabric_nodes:
            devices.add((node.get('id'), node.get('name'), 'fabric_node'))

        # Add FEXes
        for fex in self._fexes:
            devices.add((fex.get('id'), fex.get('name', f"FEX-{fex.get('id')}"), 'fex'))

        # Process discovered neighbors for connections
        for neighbor in neighbor_discovery['lldp_neighbors'] + neighbor_discovery['cdp_neighbors']:
            local_node = neighbor['local_node']
            local_if = neighbor['local_interface']
            remote_device = neighbor['neighbor_device']
            remote_if = neighbor['neighbor_interface']

            connections.append({
                'source': {
                    'node': local_node,
                    'interface': local_if
                },
                'destination': {
                    'device': remote_device,
                    'interface': remote_if
                },
                'protocol': neighbor['protocol']
            })

            devices.add((remote_device, remote_device, 'external'))

        results = {
            'connections': connections,
            'devices': [{'id': d[0], 'name': d[1], 'type': d[2]} for d in devices],
            'diagram_format': {
                'nodes': [{'id': d[0], 'label': d[1], 'group': d[2]} for d in devices],
                'edges': [
                    {
                        'from': c['source']['node'],
                        'to': c['destination']['device'],
                        'label': f"{c['source']['interface']} -> {c['destination']['interface']}"
                    }
                    for c in connections
                ]
            }
        }

        return results

    def generate_migration_cabling_plan(self) -> Dict[str, Any]:
        """
        Generate cabling plan for migration to target platform.

        Returns:
            Dictionary containing:
            - pre_migration_checklist: Physical tasks before migration
            - cabling_changes: Required cabling changes
            - port_mapping: Old interface to new interface mapping
            - verification_steps: Post-cabling verification
        """
        interface_inventory = self.analyze_interface_inventory()
        neighbor_discovery = self.discover_network_neighbors()

        # Pre-migration checklist
        pre_migration_checklist = [
            {
                'task': 'Document all physical connections',
                'details': f'Document {interface_inventory["utilization"]["used"]} active interfaces',
                'status': 'pending'
            },
            {
                'task': 'Label all cables with source and destination',
                'details': 'Use consistent labeling scheme',
                'status': 'pending'
            },
            {
                'task': 'Photograph patch panel and switch connections',
                'details': 'Take reference photos for rollback',
                'status': 'pending'
            },
            {
                'task': 'Verify spare ports on target switches',
                'details': f'Need {interface_inventory["utilization"]["used"]} ports minimum',
                'status': 'pending'
            }
        ]

        # Identify cabling changes needed
        cabling_changes = []

        # Check for VPC connections that need special handling
        for interface in interface_inventory['interfaces']:
            if interface.get('policy_group') and 'vpc' in interface.get('policy_group', '').lower():
                cabling_changes.append({
                    'type': 'vpc_to_mlag',
                    'source_node': interface['node_name'],
                    'source_interface': interface['interface'],
                    'action': 'Verify dual-homing to MLAG pair on target platform',
                    'priority': 'high'
                })

        # Check for FEX connections
        for fex in self._fexes:
            cabling_changes.append({
                'type': 'fex_migration',
                'fex_id': fex.get('id'),
                'fex_name': fex.get('name', f"FEX-{fex.get('id')}"),
                'action': 'Determine if FEX is supported on target platform or requires replacement',
                'priority': 'critical'
            })

        # Generate port mapping (1:1 mapping by default)
        port_mapping = []
        for interface in interface_inventory['interfaces']:
            if interface['oper_state'] == 'up':
                port_mapping.append({
                    'source': {
                        'node': interface['node_name'],
                        'interface': interface['interface']
                    },
                    'destination': {
                        'node': f"NEW-{interface['node_name']}",
                        'interface': interface['interface']  # Keep same interface numbering
                    },
                    'epg_count': interface['epg_count'],
                    'notes': f"Speed: {interface['speed']}, MTU: {interface.get('mtu', 'default')}"
                })

        # Verification steps
        verification_steps = [
            'Verify physical link status (show interface status)',
            'Verify LLDP/CDP neighbors match expected devices',
            'Test connectivity within each EPG/VLAN',
            'Verify MTU configuration',
            'Test link failover (if dual-homed)',
            'Document any interface errors or drops'
        ]

        return {
            'pre_migration_checklist': pre_migration_checklist,
            'cabling_changes': cabling_changes,
            'port_mapping': port_mapping,
            'verification_steps': verification_steps,
            'summary': {
                'total_interfaces': len(port_mapping),
                'vpc_connections': len([c for c in cabling_changes if c['type'] == 'vpc_to_mlag']),
                'fex_migrations': len([c for c in cabling_changes if c['type'] == 'fex_migration'])
            }
        }

    # Helper methods

    def _extract_node_id(self, dn: str) -> Optional[str]:
        """Extract node ID from DN."""
        match = re.search(r'node-(\d+)', dn)
        return match.group(1) if match else None

    def _extract_interface_id(self, dn: str) -> str:
        """Extract interface ID from DN."""
        # Examples: phys-[eth1/1], aggr-[po1]
        match = re.search(r'phys-\[(.*?)\]', dn)
        if match:
            return match.group(1)
        match = re.search(r'aggr-\[(.*?)\]', dn)
        if match:
            return match.group(1)
        return 'unknown'

    def _get_node_name(self, node_id: str) -> str:
        """Get node name from ID."""
        node = self._node_by_id.get(node_id, {})
        return node.get('name', f'node-{node_id}')

    def _get_neighbor_for_interface(self, interface_dn: str) -> Optional[Dict[str, str]]:
        """Get LLDP/CDP neighbor for an interface."""
        # Check LLDP first
        for neighbor in self._lldp_neighbors:
            neighbor_dn = neighbor.get('dn', '')
            if interface_dn in neighbor_dn:
                return {
                    'device': neighbor.get('sysName', 'unknown'),
                    'interface': neighbor.get('portIdV', 'unknown'),
                    'protocol': 'LLDP'
                }

        # Check CDP
        for neighbor in self._cdp_neighbors:
            neighbor_dn = neighbor.get('dn', '')
            if interface_dn in neighbor_dn:
                return {
                    'device': neighbor.get('devId', 'unknown'),
                    'interface': neighbor.get('portId', 'unknown'),
                    'protocol': 'CDP'
                }

        return None

    def _get_policy_group_for_interface(self, interface_dn: str) -> Optional[str]:
        """Get policy group name for an interface."""
        # This would require mapping through interface selectors and profiles
        # Simplified: return policy group if found in interface path
        for policy_group in self._interface_policy_groups:
            pg_name = policy_group.get('name')
            # Check if interface uses this policy (via path resolution)
            # For now, return None (full implementation would traverse policy hierarchy)
        return None

    def _get_epg_attachments_for_interface(self, interface_dn: str) -> List[str]:
        """Get EPGs attached to an interface."""
        epgs = []
        for path_att in self._path_attachments:
            target_dn = path_att.get('tDn', '')
            if interface_dn in target_dn:
                epg_dn = path_att.get('dn', '').rsplit('/rspathAtt-', 1)[0]
                epg_name = epg_dn.split('/epg-')[-1] if '/epg-' in epg_dn else 'unknown'
                epgs.append(epg_name)
        return list(set(epgs))

    def _get_policies_for_group(self, policy_group_dn: str) -> Dict[str, Any]:
        """Get policy references for a policy group."""
        policies = {}

        # Look for policy relationships (rsHIfPol, rsCdpIfPol, etc.)
        for obj in self.aci_objects:
            attrs = obj.get('attributes', {})
            obj_dn = attrs.get('dn', '')

            if obj_dn.startswith(policy_group_dn):
                obj_type = obj.get('type', '')
                if 'rs' in obj_type.lower() and 'pol' in obj_type.lower():
                    target = attrs.get('tnVzBrCPName') or attrs.get('tDn', 'unknown')
                    policy_type = obj_type.replace('infraRs', '').replace('Pol', '')
                    policies[policy_type] = target

        return policies

    def _count_interfaces_with_policy(self, policy_group_dn: str) -> int:
        """Count interfaces using a specific policy group."""
        # Simplified: would need to traverse selectors and port blocks
        return 0

    def _get_port_selectors_for_profile(self, profile_dn: str) -> List[Dict[str, Any]]:
        """Get port selectors within an interface profile."""
        selectors = []

        for obj in self.aci_objects:
            if obj.get('type') == 'infraHPortS':
                attrs = obj.get('attributes', {})
                selector_dn = attrs.get('dn', '')

                if selector_dn.startswith(profile_dn):
                    selectors.append({
                        'name': attrs.get('name'),
                        'dn': selector_dn,
                        'type': attrs.get('type', 'range')
                    })

        return selectors

    def _get_domains_for_aep(self, aep_dn: str) -> List[Dict[str, str]]:
        """Get domains associated with an AEP."""
        domains = []

        for obj in self.aci_objects:
            if obj.get('type') == 'infraRsDomP':
                attrs = obj.get('attributes', {})
                if attrs.get('dn', '').startswith(aep_dn):
                    domain_dn = attrs.get('tDn', '')
                    domain_type = 'unknown'
                    if 'physDomP' in domain_dn:
                        domain_type = 'physical'
                    elif 'vmmDomP' in domain_dn:
                        domain_type = 'vmm'
                    elif 'l3extDomP' in domain_dn:
                        domain_type = 'l3'

                    domains.append({
                        'type': domain_type,
                        'dn': domain_dn
                    })

        return domains

    def _is_aci_device(self, device_name: str) -> bool:
        """Check if a device is part of the ACI fabric."""
        # Check if device name matches known fabric nodes or FEXes
        for node in self._fabric_nodes:
            if node.get('name') == device_name:
                return True
        for fex in self._fexes:
            if fex.get('name') == device_name:
                return True
        return False

    def _build_topology_map(self, neighbors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build topology map from neighbor discovery data."""
        topology = []

        for neighbor in neighbors:
            topology.append({
                'link': {
                    'source': {
                        'node': neighbor['local_node'],
                        'interface': neighbor['local_interface']
                    },
                    'destination': {
                        'device': neighbor['neighbor_device'],
                        'interface': neighbor['neighbor_interface']
                    }
                },
                'protocol': neighbor['protocol']
            })

        return topology

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of physical connectivity analysis."""
        inventory = self.analyze_interface_inventory()
        policies = self.analyze_interface_policies()
        neighbors = self.discover_network_neighbors()
        migration_plan = self.generate_migration_cabling_plan()

        return {
            'interface_summary': {
                'total': inventory['total_count'],
                'used': inventory['utilization']['used'],
                'unused': inventory['utilization']['unused'],
                'utilization_rate': inventory['utilization']['utilization_rate']
            },
            'policy_summary': {
                'policy_groups': len(policies['policy_groups']),
                'profiles': len(policies['profiles']),
                'aeps': len(policies['aeps'])
            },
            'neighbor_summary': {
                'lldp': len(neighbors['lldp_neighbors']),
                'cdp': len(neighbors['cdp_neighbors']),
                'external_devices': len(neighbors['external_devices'])
            },
            'migration_summary': migration_plan['summary']
        }
