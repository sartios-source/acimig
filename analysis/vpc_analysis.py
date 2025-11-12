"""
VPC and Port-Channel Analysis Module
Provides comprehensive analysis for VPC domains, port-channels, and dual-homing configurations
to enable complete ACI migration to any target platform.
"""
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import re
import logging

logger = logging.getLogger(__name__)


class VPCAnalyzer:
    """
    Analyzes VPC (Virtual Port Channel) and port-channel configurations
    for complete ACI migration planning.

    Supports:
    - VPC domain identification and pairing
    - Port-channel member interface extraction
    - LACP configuration analysis
    - Dual-homing topology mapping
    - ESI (Ethernet Segment Identifier) candidate identification for EVPN
    - MLAG migration recommendations
    """

    def __init__(self, aci_objects: List[Dict[str, Any]]):
        """
        Initialize VPC analyzer with ACI object data.

        Args:
            aci_objects: List of parsed ACI objects from JSON/XML
        """
        self.aci_objects = aci_objects

        # Categorized objects
        self._vpc_domains = []
        self._port_channels = []
        self._lacp_entities = []
        self._vpc_interfaces = []
        self._fabric_nodes = []
        self._path_attachments = []

        # Lookup dictionaries
        self._vpc_by_id = {}
        self._pc_by_dn = {}
        self._node_by_id = {}

        # Analysis results cache
        self._vpc_pairs = None
        self._dual_homed_servers = None

        self._categorize_objects()

    def _categorize_objects(self):
        """Extract VPC-related objects from ACI data."""
        for obj in self.aci_objects:
            obj_type = obj.get('type')
            attrs = obj.get('attributes', {})

            # VPC domain configuration
            if obj_type == 'vpcDom':
                self._vpc_domains.append(attrs)
                vpc_id = attrs.get('id')
                if vpc_id:
                    self._vpc_by_id[vpc_id] = attrs

            # Port-channel aggregated interfaces
            elif obj_type == 'pcAggrIf':
                self._port_channels.append(attrs)
                dn = attrs.get('dn')
                if dn:
                    self._pc_by_dn[dn] = attrs

            # LACP configuration entities
            elif obj_type == 'lacpEntity':
                self._lacp_entities.append(attrs)

            # VPC interfaces
            elif obj_type == 'vpcIf':
                self._vpc_interfaces.append(attrs)

            # Fabric nodes (for VPC pair identification)
            elif obj_type == 'fabricNode':
                self._fabric_nodes.append(attrs)
                node_id = attrs.get('id')
                if node_id:
                    self._node_by_id[node_id] = attrs

            # Path attachments (for dual-homing detection)
            elif obj_type == 'fvRsPathAtt':
                self._path_attachments.append(attrs)

        logger.info(
            f"VPC Analysis: Found {len(self._vpc_domains)} VPC domains, "
            f"{len(self._port_channels)} port-channels, "
            f"{len(self._vpc_interfaces)} VPC interfaces"
        )

    def analyze_vpc_domains(self) -> Dict[str, Any]:
        """
        Analyze VPC domain configurations and identify leaf pairs.

        Returns:
            Dictionary containing:
            - vpc_domains: List of VPC domains with configuration details
            - vpc_pairs: Leaf switch pairs configured for VPC
            - total_domains: Count of VPC domains
            - recommendations: Migration recommendations
        """
        results = {
            'vpc_domains': [],
            'vpc_pairs': [],
            'total_domains': len(self._vpc_domains),
            'recommendations': []
        }

        # Map VPC domains to leaf pairs
        vpc_pair_map = defaultdict(list)

        for vpc_dom in self._vpc_domains:
            vpc_id = vpc_dom.get('id')
            dn = vpc_dom.get('dn', '')

            # Extract node IDs from DN (e.g., topology/pod-1/node-101/...)
            node_id = self._extract_node_id(dn)

            vpc_info = {
                'id': vpc_id,
                'dn': dn,
                'node_id': node_id,
                'peer_detected': False,
                'config': {
                    'peer_ip': vpc_dom.get('peerIp'),
                    'peer_version': vpc_dom.get('peerVersion'),
                    'virtual_ip': vpc_dom.get('virtualIp'),
                    'status': vpc_dom.get('operSt'),
                    'role': vpc_dom.get('role')
                }
            }

            results['vpc_domains'].append(vpc_info)

            if vpc_id:
                vpc_pair_map[vpc_id].append(vpc_info)

        # Identify VPC pairs (two nodes sharing same VPC domain ID)
        for vpc_id, members in vpc_pair_map.items():
            if len(members) == 2:
                pair = {
                    'vpc_domain_id': vpc_id,
                    'node1': members[0]['node_id'],
                    'node2': members[1]['node_id'],
                    'node1_name': self._get_node_name(members[0]['node_id']),
                    'node2_name': self._get_node_name(members[1]['node_id']),
                    'status': 'active' if members[0]['config']['status'] == 'up' and
                                         members[1]['config']['status'] == 'up' else 'degraded',
                    'virtual_ip': members[0]['config']['virtual_ip'],
                    'migration_ready': True
                }
                results['vpc_pairs'].append(pair)

                # Mark peers as detected
                members[0]['peer_detected'] = True
                members[1]['peer_detected'] = True

            elif len(members) == 1:
                # Single-sided VPC configuration (potential issue)
                results['recommendations'].append({
                    'level': 'warning',
                    'category': 'vpc_configuration',
                    'message': f'VPC domain {vpc_id} has only one member',
                    'details': f'Node {members[0]["node_id"]} configured but peer not found',
                    'impact': 'May indicate misconfiguration or incomplete data collection'
                })

        # Add migration recommendations based on findings
        if results['vpc_pairs']:
            results['recommendations'].append({
                'level': 'info',
                'category': 'evpn_migration',
                'message': f'{len(results["vpc_pairs"])} VPC pairs ready for MLAG/ESI migration',
                'details': 'VPC pairs can be migrated to EVPN ESI (multi-homing) or vendor-specific MLAG',
                'action': 'Generate ESI configurations for dual-homed endpoints'
            })

        return results

    def analyze_port_channels(self) -> Dict[str, Any]:
        """
        Analyze port-channel configurations and member interfaces.

        Returns:
            Dictionary containing:
            - port_channels: List of port-channels with member interfaces
            - vpc_port_channels: Port-channels configured as VPC
            - regular_port_channels: Standard port-channels (non-VPC)
            - total_count: Total port-channel count
            - lacp_analysis: LACP mode distribution
        """
        results = {
            'port_channels': [],
            'vpc_port_channels': [],
            'regular_port_channels': [],
            'total_count': len(self._port_channels),
            'lacp_analysis': {
                'active': 0,
                'passive': 0,
                'on': 0,
                'unknown': 0
            }
        }

        for pc in self._port_channels:
            dn = pc.get('dn', '')
            pc_id = pc.get('id')

            # Extract node and port-channel ID from DN
            node_id = self._extract_node_id(dn)

            # Determine if this is a VPC port-channel
            is_vpc = 'vpc-' in dn.lower() or self._is_vpc_interface(dn)

            # Extract LACP mode
            lacp_mode = self._get_lacp_mode(dn)
            if lacp_mode in results['lacp_analysis']:
                results['lacp_analysis'][lacp_mode] += 1
            else:
                results['lacp_analysis']['unknown'] += 1

            pc_info = {
                'id': pc_id,
                'dn': dn,
                'node_id': node_id,
                'is_vpc': is_vpc,
                'status': pc.get('operSt'),
                'lacp_mode': lacp_mode,
                'speed': pc.get('speed'),
                'member_count': pc.get('activePorts', 0),
                'description': pc.get('descr', ''),
                'usage': pc.get('usage'),
                'migration_type': 'MLAG/ESI' if is_vpc else 'Standard LAG'
            }

            results['port_channels'].append(pc_info)

            if is_vpc:
                results['vpc_port_channels'].append(pc_info)
            else:
                results['regular_port_channels'].append(pc_info)

        return results

    def identify_dual_homed_servers(self) -> Dict[str, Any]:
        """
        Identify servers connected via dual-homing (VPC) for migration planning.

        Returns:
            Dictionary containing:
            - dual_homed_endpoints: List of endpoints with dual connections
            - single_homed_endpoints: List of single-attached endpoints
            - esi_candidates: Endpoints suitable for EVPN ESI migration
            - migration_priority: Prioritized list for migration
        """
        results = {
            'dual_homed_endpoints': [],
            'single_homed_endpoints': [],
            'esi_candidates': [],
            'migration_priority': []
        }

        # Group path attachments by EPG and encapsulation (VLAN)
        endpoint_connections = defaultdict(list)

        for path_att in self._path_attachments:
            tdn = path_att.get('tDn', '')  # Target DN (interface/port-channel)
            encap = path_att.get('encap', '')  # VLAN encapsulation
            epg_dn = self._extract_epg_from_path(path_att.get('dn', ''))

            # Check if this is a port-channel attachment
            is_po = 'aggr-[' in tdn.lower() or 'po' in tdn.lower()
            is_vpc = 'vpc-' in tdn.lower()

            # Extract identifier (server/endpoint identifier)
            endpoint_key = f"{epg_dn}:{encap}"

            endpoint_connections[endpoint_key].append({
                'interface': tdn,
                'is_port_channel': is_po,
                'is_vpc': is_vpc,
                'encap': encap,
                'epg': epg_dn,
                'mode': path_att.get('mode'),
                'state': path_att.get('state')
            })

        # Analyze connection patterns
        for endpoint_key, connections in endpoint_connections.items():
            epg, encap = endpoint_key.split(':', 1)

            # Check if endpoint has multiple connections
            if len(connections) >= 2:
                # Potentially dual-homed
                vpc_connections = [c for c in connections if c['is_vpc']]

                if len(vpc_connections) >= 2:
                    # Dual-homed via VPC (ideal for ESI migration)
                    endpoint_info = {
                        'epg': epg,
                        'vlan': encap,
                        'connection_count': len(connections),
                        'vpc_count': len(vpc_connections),
                        'interfaces': [c['interface'] for c in connections],
                        'redundancy': 'vpc_dual_homed',
                        'esi_ready': True,
                        'migration_complexity': 'low'
                    }
                    results['dual_homed_endpoints'].append(endpoint_info)
                    results['esi_candidates'].append(endpoint_info)
                    results['migration_priority'].append({
                        **endpoint_info,
                        'priority': 1,  # High priority - clean dual-homing
                        'reason': 'VPC dual-homed, direct ESI mapping available'
                    })

                else:
                    # Multiple connections but not VPC (unusual)
                    endpoint_info = {
                        'epg': epg,
                        'vlan': encap,
                        'connection_count': len(connections),
                        'interfaces': [c['interface'] for c in connections],
                        'redundancy': 'multi_attached',
                        'esi_ready': False,
                        'migration_complexity': 'medium'
                    }
                    results['dual_homed_endpoints'].append(endpoint_info)
                    results['migration_priority'].append({
                        **endpoint_info,
                        'priority': 2,  # Medium priority - needs review
                        'reason': 'Multiple attachments, needs manual review'
                    })

            else:
                # Single-homed endpoint
                endpoint_info = {
                    'epg': epg,
                    'vlan': encap,
                    'interface': connections[0]['interface'],
                    'redundancy': 'single_homed',
                    'migration_complexity': 'low'
                }
                results['single_homed_endpoints'].append(endpoint_info)
                results['migration_priority'].append({
                    **endpoint_info,
                    'priority': 3,  # Low priority - simple migration
                    'reason': 'Single-homed, no redundancy requirements'
                })

        # Sort by priority
        results['migration_priority'].sort(key=lambda x: x['priority'])

        return results

    def generate_esi_mapping(self) -> Dict[str, Any]:
        """
        Generate ESI (Ethernet Segment Identifier) recommendations for EVPN migration.

        Returns:
            Dictionary containing:
            - esi_mappings: VPC to ESI mapping recommendations
            - lacp_system_id: Suggested LACP system IDs
            - configuration_template: Sample ESI configuration
        """
        results = {
            'esi_mappings': [],
            'lacp_system_id': [],
            'configuration_template': {}
        }

        # Get VPC pair information
        vpc_analysis = self.analyze_vpc_domains()

        for vpc_pair in vpc_analysis.get('vpc_pairs', []):
            vpc_id = vpc_pair['vpc_domain_id']

            # Generate ESI (format: LACP-based ESI)
            # ESI format: 00:00:00:00:00:00:VV:VV:00:00 (VV:VV = VPC domain ID in hex)
            esi_value = f"00:00:00:00:00:00:{int(vpc_id):04x}:00:00"

            # LACP system ID (use VPC virtual MAC or generate)
            lacp_sys_id = f"00:00:00:00:{int(vpc_id):04x}"

            esi_mapping = {
                'vpc_domain_id': vpc_id,
                'vpc_pair': f"{vpc_pair['node1_name']} <-> {vpc_pair['node2_name']}",
                'recommended_esi': esi_value,
                'lacp_system_id': lacp_sys_id,
                'node1': vpc_pair['node1'],
                'node2': vpc_pair['node2'],
                'virtual_ip': vpc_pair.get('virtual_ip'),
                'migration_notes': [
                    'Configure same ESI on both leaf switches',
                    'Use LACP for port-channel negotiation',
                    'Ensure both leaves are in same EVPN instance',
                    'Configure ESI as all-active (LACP) or single-active'
                ]
            }

            results['esi_mappings'].append(esi_mapping)
            results['lacp_system_id'].append({
                'vpc_id': vpc_id,
                'system_id': lacp_sys_id
            })

        # Generate sample configuration template
        if results['esi_mappings']:
            first_esi = results['esi_mappings'][0]
            results['configuration_template'] = {
                'nx-os': self._generate_nxos_esi_config(first_esi),
                'eos': self._generate_eos_esi_config(first_esi),
                'junos': self._generate_junos_esi_config(first_esi)
            }

        return results

    # Helper methods

    def _extract_node_id(self, dn: str) -> Optional[str]:
        """Extract node ID from distinguished name."""
        match = re.search(r'node-(\d+)', dn)
        return match.group(1) if match else None

    def _extract_epg_from_path(self, dn: str) -> str:
        """Extract EPG DN from path attachment DN."""
        # Path attachment DN format: uni/tn-XXX/ap-YYY/epg-ZZZ/rspathAtt-[...]
        match = re.search(r'(uni/tn-[^/]+/ap-[^/]+/epg-[^/]+)', dn)
        return match.group(1) if match else ''

    def _get_node_name(self, node_id: str) -> str:
        """Get node name from ID."""
        node = self._node_by_id.get(node_id, {})
        return node.get('name', f'node-{node_id}')

    def _is_vpc_interface(self, dn: str) -> bool:
        """Check if interface DN indicates VPC configuration."""
        # Check VPC interface list
        for vpc_if in self._vpc_interfaces:
            if dn in vpc_if.get('dn', ''):
                return True
        return False

    def _get_lacp_mode(self, pc_dn: str) -> str:
        """Determine LACP mode for port-channel."""
        for lacp in self._lacp_entities:
            if pc_dn in lacp.get('dn', ''):
                mode = lacp.get('mode', 'unknown')
                return mode.lower()
        return 'unknown'

    def _generate_nxos_esi_config(self, esi_mapping: Dict[str, Any]) -> str:
        """Generate NX-OS ESI configuration sample."""
        return f"""! NX-OS EVPN ESI Configuration
interface port-channel <id>
  evpn multi-site fabric-tracking
  evpn ethernet-segment {esi_mapping['recommended_esi']}
  lacp system-id {esi_mapping['lacp_system_id']}

! Apply to both VPC peer switches:
! {esi_mapping['vpc_pair']}"""

    def _generate_eos_esi_config(self, esi_mapping: Dict[str, Any]) -> str:
        """Generate Arista EOS ESI configuration sample."""
        return f"""! Arista EOS EVPN ESI Configuration
interface Port-Channel <id>
   evpn ethernet-segment
      identifier {esi_mapping['recommended_esi']}
      route-target import {esi_mapping['lacp_system_id']}
   lacp system-id {esi_mapping['lacp_system_id']}

! Apply to both MLAG peers:
! {esi_mapping['vpc_pair']}"""

    def _generate_junos_esi_config(self, esi_mapping: Dict[str, Any]) -> str:
        """Generate Juniper Junos ESI configuration sample."""
        return f"""/* Junos EVPN ESI Configuration */
interfaces {{
    ae<id> {{
        esi {{
            {esi_mapping['recommended_esi']};
            all-active;
        }}
        aggregated-ether-options {{
            lacp {{
                system-id {esi_mapping['lacp_system_id']};
            }}
        }}
    }}
}}

/* Apply to both MC-LAG peers:
 * {esi_mapping['vpc_pair']}
 */"""

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of VPC/port-channel analysis.

        Returns:
            Summary dictionary with counts and readiness assessment
        """
        vpc_domains = self.analyze_vpc_domains()
        port_channels = self.analyze_port_channels()
        dual_homed = self.identify_dual_homed_servers()
        esi_mapping = self.generate_esi_mapping()

        return {
            'vpc_summary': {
                'total_domains': vpc_domains['total_domains'],
                'active_pairs': len(vpc_domains['vpc_pairs']),
                'migration_ready': len([p for p in vpc_domains['vpc_pairs'] if p.get('migration_ready')])
            },
            'port_channel_summary': {
                'total': port_channels['total_count'],
                'vpc_po': len(port_channels['vpc_port_channels']),
                'regular_po': len(port_channels['regular_port_channels']),
                'lacp_distribution': port_channels['lacp_analysis']
            },
            'endpoint_summary': {
                'dual_homed': len(dual_homed['dual_homed_endpoints']),
                'single_homed': len(dual_homed['single_homed_endpoints']),
                'esi_ready': len(dual_homed['esi_candidates'])
            },
            'esi_summary': {
                'esi_mappings': len(esi_mapping['esi_mappings']),
                'lacp_system_ids': len(esi_mapping['lacp_system_id'])
            },
            'migration_readiness': self._assess_migration_readiness(
                vpc_domains, port_channels, dual_homed
            )
        }

    def _assess_migration_readiness(self, vpc_domains, port_channels, dual_homed) -> Dict[str, Any]:
        """Assess overall migration readiness."""
        score = 0
        max_score = 0
        issues = []

        # VPC pair readiness (40 points)
        max_score += 40
        active_pairs = len([p for p in vpc_domains['vpc_pairs'] if p.get('migration_ready')])
        if active_pairs > 0:
            score += 40
        else:
            issues.append('No active VPC pairs detected')

        # Port-channel configuration (30 points)
        max_score += 30
        if port_channels['total_count'] > 0:
            lacp_ratio = (port_channels['lacp_analysis']['active'] +
                         port_channels['lacp_analysis']['passive']) / port_channels['total_count']
            score += int(30 * lacp_ratio)
            if lacp_ratio < 0.8:
                issues.append(f'Only {int(lacp_ratio*100)}% of port-channels use LACP')
        else:
            issues.append('No port-channels configured')

        # Dual-homed endpoint coverage (30 points)
        max_score += 30
        total_endpoints = len(dual_homed['dual_homed_endpoints']) + len(dual_homed['single_homed_endpoints'])
        if total_endpoints > 0:
            dual_homed_ratio = len(dual_homed['dual_homed_endpoints']) / total_endpoints
            score += int(30 * dual_homed_ratio)

        readiness_pct = int((score / max_score) * 100) if max_score > 0 else 0

        return {
            'score': score,
            'max_score': max_score,
            'percentage': readiness_pct,
            'level': 'high' if readiness_pct >= 80 else 'medium' if readiness_pct >= 50 else 'low',
            'issues': issues,
            'ready_for_migration': readiness_pct >= 70
        }
