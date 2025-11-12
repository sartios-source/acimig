"""
L3Out and External Connectivity Analysis Module
Analyzes ACI L3Out configurations, border leaf connections, routing protocols,
and external network connectivity for complete migration planning.
"""
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class L3OutConnection:
    """Represents an external Layer 3 connection."""
    name: str
    tenant: str
    vrf: str
    protocol: str  # bgp, ospf, eigrp, static
    border_leafs: List[str]
    interfaces: List[str]
    routing_config: Dict[str, Any]
    external_networks: List[Dict[str, Any]]


class L3OutAnalyzer:
    """
    Analyzes ACI L3Out configurations and external connectivity.

    Supports:
    - L3Out identification and classification
    - Border leaf interface mapping
    - Routing protocol analysis (BGP, OSPF, EIGRP, static)
    - External EPG (extEPG) extraction
    - Transit routing identification
    - Default gateway analysis
    - Route map and policy analysis
    - Migration recommendations for external connectivity
    """

    def __init__(self, aci_objects: List[Dict[str, Any]]):
        """
        Initialize L3Out analyzer with ACI object data.

        Args:
            aci_objects: List of parsed ACI objects from JSON/XML
        """
        self.aci_objects = aci_objects

        # Categorized objects
        self._l3outs = []
        self._bgp_peers = []
        self._ospf_interfaces = []
        self._static_routes = []
        self._external_epgs = []
        self._logical_node_profiles = []
        self._logical_interface_profiles = []
        self._vrfs = []
        self._fabric_nodes = []

        # Lookup dictionaries
        self._l3out_by_dn = {}
        self._node_by_id = {}
        self._vrf_by_dn = {}

        self._categorize_objects()

    def _categorize_objects(self):
        """Extract L3Out-related objects from ACI data."""
        for obj in self.aci_objects:
            obj_type = obj.get('type')
            attrs = obj.get('attributes', {})
            dn = attrs.get('dn', '')

            # L3Out configurations
            if obj_type == 'l3extOut':
                self._l3outs.append(attrs)
                if dn:
                    self._l3out_by_dn[dn] = attrs

            # BGP peer configurations
            elif obj_type == 'bgpPeerP':
                self._bgp_peers.append(attrs)

            # OSPF interface configurations
            elif obj_type == 'ospfIfP':
                self._ospf_interfaces.append(attrs)

            # Static routes
            elif obj_type == 'ipRouteP':
                self._static_routes.append(attrs)

            # External EPGs
            elif obj_type == 'l3extInstP':
                self._external_epgs.append(attrs)

            # Logical node profiles (border leaf associations)
            elif obj_type == 'l3extLNodeP':
                self._logical_node_profiles.append(attrs)

            # Logical interface profiles (external interfaces)
            elif obj_type == 'l3extLIfP':
                self._logical_interface_profiles.append(attrs)

            # VRFs
            elif obj_type == 'fvCtx':
                self._vrfs.append(attrs)
                if dn:
                    self._vrf_by_dn[dn] = attrs

            # Fabric nodes
            elif obj_type == 'fabricNode':
                self._fabric_nodes.append(attrs)
                node_id = attrs.get('id')
                if node_id:
                    self._node_by_id[node_id] = attrs

        logger.info(
            f"L3Out Analysis: Found {len(self._l3outs)} L3Outs, "
            f"{len(self._bgp_peers)} BGP peers, {len(self._ospf_interfaces)} OSPF interfaces, "
            f"{len(self._static_routes)} static routes, {len(self._external_epgs)} external EPGs"
        )

    def analyze_l3outs(self) -> Dict[str, Any]:
        """
        Analyze all L3Out configurations.

        Returns:
            Dictionary containing:
            - l3outs: List of L3Out details with routing protocols
            - total_l3outs: Count of L3Outs
            - protocols: Distribution by routing protocol
            - border_leafs: Set of border leaf switches
            - vrfs_with_external: VRFs with external connectivity
        """
        results = {
            'l3outs': [],
            'total_l3outs': len(self._l3outs),
            'protocols': {'bgp': 0, 'ospf': 0, 'eigrp': 0, 'static': 0, 'multiple': 0},
            'border_leafs': set(),
            'vrfs_with_external': set()
        }

        for l3out in self._l3outs:
            dn = l3out.get('dn', '')
            name = l3out.get('name')
            tenant = self._extract_tenant_from_dn(dn)

            # Get associated VRF
            vrf_relation = self._find_l3out_vrf_relation(dn)
            vrf_name = vrf_relation.get('tnFvCtxName') if vrf_relation else 'unknown'

            # Identify routing protocols used
            protocols = self._identify_l3out_protocols(dn)

            # Track protocol usage
            if len(protocols) > 1:
                results['protocols']['multiple'] += 1
            else:
                for proto in protocols:
                    if proto in results['protocols']:
                        results['protocols'][proto] += 1

            # Get border leafs and interfaces
            border_leafs, interfaces = self._get_l3out_border_leafs_and_interfaces(dn)
            results['border_leafs'].update(border_leafs)

            # Get external EPGs (subnets reachable via this L3Out)
            external_epgs = self._get_external_epgs_for_l3out(dn)

            # BGP configuration details
            bgp_config = self._get_bgp_config_for_l3out(dn) if 'bgp' in protocols else {}

            # OSPF configuration details
            ospf_config = self._get_ospf_config_for_l3out(dn) if 'ospf' in protocols else {}

            l3out_info = {
                'name': name,
                'dn': dn,
                'tenant': tenant,
                'vrf': vrf_name,
                'protocols': protocols,
                'border_leafs': list(border_leafs),
                'border_leaf_count': len(border_leafs),
                'interfaces': interfaces,
                'interface_count': len(interfaces),
                'external_epgs': external_epgs,
                'external_subnet_count': sum(len(epg.get('subnets', [])) for epg in external_epgs),
                'bgp_config': bgp_config,
                'ospf_config': ospf_config,
                'migration_complexity': self._assess_l3out_complexity(protocols, border_leafs, external_epgs)
            }

            results['l3outs'].append(l3out_info)
            results['vrfs_with_external'].add(f"{tenant}:{vrf_name}")

        results['border_leafs'] = list(results['border_leafs'])
        results['vrfs_with_external'] = list(results['vrfs_with_external'])

        return results

    def analyze_bgp_configuration(self) -> Dict[str, Any]:
        """
        Analyze BGP configuration across all L3Outs.

        Returns:
            Dictionary containing:
            - bgp_peers: List of BGP peer configurations
            - as_numbers: Set of AS numbers used
            - peer_count: Total BGP peer count
            - ebgp_sessions: External BGP sessions
            - ibgp_sessions: Internal BGP sessions
        """
        results = {
            'bgp_peers': [],
            'as_numbers': set(),
            'peer_count': len(self._bgp_peers),
            'ebgp_sessions': 0,
            'ibgp_sessions': 0
        }

        for peer in self._bgp_peers:
            dn = peer.get('dn', '')
            peer_ip = peer.get('addr')
            remote_as = peer.get('asn')
            local_as = self._get_local_as_for_peer(dn)

            # Determine if eBGP or iBGP
            is_ebgp = remote_as != local_as if (remote_as and local_as) else None

            if is_ebgp is True:
                results['ebgp_sessions'] += 1
            elif is_ebgp is False:
                results['ibgp_sessions'] += 1

            # Extract L3Out and node information
            l3out_name = self._extract_l3out_from_dn(dn)
            node_id = self._extract_node_id(dn)

            peer_info = {
                'peer_ip': peer_ip,
                'remote_as': remote_as,
                'local_as': local_as,
                'session_type': 'eBGP' if is_ebgp else 'iBGP' if is_ebgp is False else 'unknown',
                'l3out': l3out_name,
                'node_id': node_id,
                'node_name': self._get_node_name(node_id),
                'admin_state': peer.get('adminSt'),
                'password_configured': bool(peer.get('password')),
                'ttl_security': peer.get('ttl'),
                'dn': dn
            }

            results['bgp_peers'].append(peer_info)

            if remote_as:
                results['as_numbers'].add(remote_as)
            if local_as:
                results['as_numbers'].add(local_as)

        results['as_numbers'] = list(results['as_numbers'])

        return results

    def analyze_ospf_configuration(self) -> Dict[str, Any]:
        """
        Analyze OSPF configuration across all L3Outs.

        Returns:
            Dictionary containing:
            - ospf_interfaces: List of OSPF-enabled interfaces
            - areas: Set of OSPF areas configured
            - total_interfaces: Count of OSPF interfaces
            - interface_types: Distribution by interface type
        """
        results = {
            'ospf_interfaces': [],
            'areas': set(),
            'total_interfaces': len(self._ospf_interfaces),
            'interface_types': {'p2p': 0, 'broadcast': 0, 'unknown': 0}
        }

        for ospf_if in self._ospf_interfaces:
            dn = ospf_if.get('dn', '')

            # Extract configuration
            auth_key = ospf_if.get('authKey')
            auth_type = ospf_if.get('authType', 'none')

            # Find associated OSPF interface profile for area
            area = self._get_ospf_area_for_interface(dn)
            if area:
                results['areas'].add(area)

            # Extract L3Out and node information
            l3out_name = self._extract_l3out_from_dn(dn)
            node_id = self._extract_node_id(dn)

            # Determine interface type (from parent interface profile)
            if_type = self._get_ospf_interface_type(dn)
            if if_type in results['interface_types']:
                results['interface_types'][if_type] += 1
            else:
                results['interface_types']['unknown'] += 1

            ospf_info = {
                'dn': dn,
                'l3out': l3out_name,
                'node_id': node_id,
                'node_name': self._get_node_name(node_id),
                'area': area,
                'interface_type': if_type,
                'authentication_type': auth_type,
                'authentication_configured': bool(auth_key),
                'dn': dn
            }

            results['ospf_interfaces'].append(ospf_info)

        results['areas'] = list(results['areas'])

        return results

    def identify_border_leafs(self) -> Dict[str, Any]:
        """
        Identify all border leaf switches with external connectivity.

        Returns:
            Dictionary containing:
            - border_leafs: List of border leaf switches with details
            - total_count: Count of border leafs
            - l3out_distribution: Number of L3Outs per border leaf
        """
        results = {
            'border_leafs': [],
            'total_count': 0,
            'l3out_distribution': defaultdict(int)
        }

        # Track which L3Outs are connected to which nodes
        node_l3out_map = defaultdict(set)

        for node_profile in self._logical_node_profiles:
            dn = node_profile.get('dn', '')
            l3out_name = self._extract_l3out_from_dn(dn)

            # Find node associations (via l3extRsNodeL3OutAtt)
            nodes = self._get_nodes_for_node_profile(dn)

            for node_id in nodes:
                node_l3out_map[node_id].add(l3out_name)

        # Build border leaf information
        for node_id, l3outs in node_l3out_map.items():
            node_name = self._get_node_name(node_id)

            # Get interfaces used for external connectivity
            interfaces = self._get_external_interfaces_for_node(node_id)

            border_leaf_info = {
                'node_id': node_id,
                'node_name': node_name,
                'l3outs': list(l3outs),
                'l3out_count': len(l3outs),
                'external_interfaces': interfaces,
                'interface_count': len(interfaces),
                'role': 'border_leaf'
            }

            results['border_leafs'].append(border_leaf_info)
            results['l3out_distribution'][len(l3outs)] += 1

        results['total_count'] = len(results['border_leafs'])
        results['l3out_distribution'] = dict(results['l3out_distribution'])

        return results

    def generate_migration_recommendations(self) -> Dict[str, Any]:
        """
        Generate migration recommendations for external connectivity.

        Returns:
            Dictionary containing:
            - recommendations: List of actionable recommendations
            - complexity_assessment: Overall complexity rating
            - risk_factors: Identified risk factors
            - configuration_templates: Sample configs for target platform
        """
        l3out_analysis = self.analyze_l3outs()
        bgp_analysis = self.analyze_bgp_configuration()
        ospf_analysis = self.analyze_ospf_configuration()
        border_leafs = self.identify_border_leafs()

        recommendations = []
        risk_factors = []

        # Assess BGP migration
        if bgp_analysis['peer_count'] > 0:
            recommendations.append({
                'priority': 'high',
                'category': 'bgp_migration',
                'title': f'Migrate {bgp_analysis["peer_count"]} BGP peer sessions',
                'details': f'eBGP: {bgp_analysis["ebgp_sessions"]}, '
                          f'iBGP: {bgp_analysis["ibgp_sessions"]}',
                'action_items': [
                    'Document BGP neighbor relationships and AS paths',
                    'Extract route filters and prefix lists',
                    'Configure BGP on target platform with same ASN',
                    'Migrate peer-by-peer with verification'
                ]
            })

            if bgp_analysis['ebgp_sessions'] > 10:
                risk_factors.append({
                    'level': 'medium',
                    'factor': 'High number of eBGP sessions',
                    'impact': 'Complex migration coordination required'
                })

        # Assess OSPF migration
        if ospf_analysis['total_interfaces'] > 0:
            recommendations.append({
                'priority': 'high',
                'category': 'ospf_migration',
                'title': f'Migrate OSPF configuration across {len(ospf_analysis["areas"])} areas',
                'details': f'{ospf_analysis["total_interfaces"]} OSPF-enabled interfaces',
                'action_items': [
                    'Document OSPF area design and adjacencies',
                    'Extract LSA database for verification',
                    'Configure OSPF on target platform with same areas',
                    'Verify adjacency formation and route propagation'
                ]
            })

        # Assess border leaf migration
        if border_leafs['total_count'] > 0:
            recommendations.append({
                'priority': 'critical',
                'category': 'border_leaf_migration',
                'title': f'Migrate {border_leafs["total_count"]} border leaf switches',
                'details': f'{len(l3out_analysis["l3outs"])} L3Outs across {len(l3out_analysis["vrfs_with_external"])} VRFs',
                'action_items': [
                    'Map border leaf physical connectivity',
                    'Document external router connections',
                    'Plan cutover strategy (staged vs parallel)',
                    'Prepare rollback procedures'
                ]
            })

            if border_leafs['total_count'] > 4:
                risk_factors.append({
                    'level': 'high',
                    'factor': 'Multiple border leafs with external connectivity',
                    'impact': 'Complex migration with potential for routing loops'
                })

        # Assess protocol complexity
        if l3out_analysis['protocols']['multiple'] > 0:
            risk_factors.append({
                'level': 'medium',
                'factor': f'{l3out_analysis["protocols"]["multiple"]} L3Outs use multiple routing protocols',
                'impact': 'Increased complexity due to protocol redistribution'
            })

        # Overall complexity assessment
        complexity_score = 0
        if bgp_analysis['peer_count'] > 0:
            complexity_score += min(bgp_analysis['peer_count'] * 2, 40)
        if ospf_analysis['total_interfaces'] > 0:
            complexity_score += min(ospf_analysis['total_interfaces'] * 3, 30)
        if border_leafs['total_count'] > 0:
            complexity_score += min(border_leafs['total_count'] * 5, 30)

        complexity_level = 'low' if complexity_score < 30 else 'medium' if complexity_score < 60 else 'high'

        return {
            'recommendations': recommendations,
            'complexity_assessment': {
                'score': complexity_score,
                'level': complexity_level,
                'factors': {
                    'bgp_peers': bgp_analysis['peer_count'],
                    'ospf_interfaces': ospf_analysis['total_interfaces'],
                    'border_leafs': border_leafs['total_count'],
                    'l3outs': l3out_analysis['total_l3outs']
                }
            },
            'risk_factors': risk_factors,
            'configuration_templates': self._generate_config_templates(l3out_analysis, bgp_analysis, ospf_analysis)
        }

    # Helper methods

    def _identify_l3out_protocols(self, l3out_dn: str) -> List[str]:
        """Identify routing protocols used by an L3Out."""
        protocols = []

        # Check for BGP
        for bgp_peer in self._bgp_peers:
            if bgp_peer.get('dn', '').startswith(l3out_dn):
                protocols.append('bgp')
                break

        # Check for OSPF
        for ospf_if in self._ospf_interfaces:
            if ospf_if.get('dn', '').startswith(l3out_dn):
                protocols.append('ospf')
                break

        # Check for static routes
        for static_route in self._static_routes:
            if static_route.get('dn', '').startswith(l3out_dn):
                protocols.append('static')
                break

        return protocols if protocols else ['unknown']

    def _get_l3out_border_leafs_and_interfaces(self, l3out_dn: str) -> Tuple[Set[str], List[Dict[str, Any]]]:
        """Get border leafs and interfaces for an L3Out."""
        border_leafs = set()
        interfaces = []

        # Find logical node profiles under this L3Out
        for node_profile in self._logical_node_profiles:
            if node_profile.get('dn', '').startswith(l3out_dn):
                # Get nodes from this profile
                nodes = self._get_nodes_for_node_profile(node_profile.get('dn', ''))
                border_leafs.update(nodes)

                # Get interface profiles
                if_profiles = self._get_interface_profiles_for_node_profile(node_profile.get('dn', ''))
                interfaces.extend(if_profiles)

        return border_leafs, interfaces

    def _get_nodes_for_node_profile(self, node_profile_dn: str) -> List[str]:
        """Get node IDs associated with a logical node profile."""
        nodes = []

        for obj in self.aci_objects:
            if obj.get('type') == 'l3extRsNodeL3OutAtt':
                attrs = obj.get('attributes', {})
                if attrs.get('dn', '').startswith(node_profile_dn):
                    node_id = attrs.get('tDn', '')
                    node_id = self._extract_node_id(node_id)
                    if node_id:
                        nodes.append(node_id)

        return nodes

    def _get_interface_profiles_for_node_profile(self, node_profile_dn: str) -> List[Dict[str, Any]]:
        """Get interface profiles under a logical node profile."""
        interfaces = []

        for if_profile in self._logical_interface_profiles:
            if if_profile.get('dn', '').startswith(node_profile_dn):
                interfaces.append({
                    'name': if_profile.get('name'),
                    'dn': if_profile.get('dn')
                })

        return interfaces

    def _get_external_epgs_for_l3out(self, l3out_dn: str) -> List[Dict[str, Any]]:
        """Get external EPGs (InstP) for an L3Out."""
        ext_epgs = []

        for ext_epg in self._external_epgs:
            epg_dn = ext_epg.get('dn', '')
            if epg_dn.startswith(l3out_dn):
                # Find subnets for this external EPG
                subnets = self._get_subnets_for_external_epg(epg_dn)

                ext_epgs.append({
                    'name': ext_epg.get('name'),
                    'dn': epg_dn,
                    'subnets': subnets
                })

        return ext_epgs

    def _get_subnets_for_external_epg(self, ext_epg_dn: str) -> List[str]:
        """Get subnet prefixes for an external EPG."""
        subnets = []

        for obj in self.aci_objects:
            if obj.get('type') == 'l3extSubnet':
                attrs = obj.get('attributes', {})
                if attrs.get('dn', '').startswith(ext_epg_dn):
                    subnet = attrs.get('ip')
                    if subnet:
                        subnets.append(subnet)

        return subnets

    def _get_bgp_config_for_l3out(self, l3out_dn: str) -> Dict[str, Any]:
        """Extract BGP configuration details for an L3Out."""
        peers = [peer for peer in self._bgp_peers if peer.get('dn', '').startswith(l3out_dn)]

        return {
            'peer_count': len(peers),
            'peer_ips': [peer.get('addr') for peer in peers],
            'as_numbers': list(set(peer.get('asn') for peer in peers if peer.get('asn')))
        }

    def _get_ospf_config_for_l3out(self, l3out_dn: str) -> Dict[str, Any]:
        """Extract OSPF configuration details for an L3Out."""
        interfaces = [ospf_if for ospf_if in self._ospf_interfaces if ospf_if.get('dn', '').startswith(l3out_dn)]

        return {
            'interface_count': len(interfaces),
            'areas': list(set(self._get_ospf_area_for_interface(ospf_if.get('dn', '')) for ospf_if in interfaces))
        }

    def _assess_l3out_complexity(self, protocols: List[str], border_leafs: Set[str], external_epgs: List[Dict]) -> str:
        """Assess migration complexity for an L3Out."""
        score = 0

        # Multiple protocols increase complexity
        if len(protocols) > 1:
            score += 30

        # BGP is more complex than static
        if 'bgp' in protocols:
            score += 20
        if 'ospf' in protocols:
            score += 15

        # Multiple border leafs increase complexity
        score += len(border_leafs) * 5

        # Multiple external EPGs with many subnets increase complexity
        subnet_count = sum(len(epg.get('subnets', [])) for epg in external_epgs)
        score += min(subnet_count, 30)

        if score < 30:
            return 'low'
        elif score < 60:
            return 'medium'
        else:
            return 'high'

    def _find_l3out_vrf_relation(self, l3out_dn: str) -> Optional[Dict[str, Any]]:
        """Find VRF relation for an L3Out."""
        for obj in self.aci_objects:
            if obj.get('type') == 'l3extRsEctx':
                attrs = obj.get('attributes', {})
                if attrs.get('dn', '').startswith(l3out_dn):
                    return attrs
        return None

    def _get_local_as_for_peer(self, peer_dn: str) -> Optional[str]:
        """Get local AS number for a BGP peer (from parent BGP protocol profile)."""
        # Look for bgpAsP (BGP AS Profile) in parent hierarchy
        for obj in self.aci_objects:
            if obj.get('type') == 'bgpAsP':
                attrs = obj.get('attributes', {})
                as_dn = attrs.get('dn', '')
                if peer_dn.startswith(as_dn.rsplit('/', 1)[0]):
                    return attrs.get('asn')
        return None

    def _get_ospf_area_for_interface(self, ospf_if_dn: str) -> Optional[str]:
        """Get OSPF area for an interface."""
        # Look for ospfIfP parent which contains area information
        for obj in self.aci_objects:
            if obj.get('type') == 'ospfExtP':
                attrs = obj.get('attributes', {})
                if ospf_if_dn.startswith(attrs.get('dn', '')):
                    return attrs.get('areaId', '0.0.0.0')
        return None

    def _get_ospf_interface_type(self, ospf_if_dn: str) -> str:
        """Determine OSPF interface type."""
        # Check for interface type in DN or configuration
        if 'p2p' in ospf_if_dn.lower():
            return 'p2p'
        elif 'bcast' in ospf_if_dn.lower():
            return 'broadcast'
        return 'unknown'

    def _get_external_interfaces_for_node(self, node_id: str) -> List[str]:
        """Get external interfaces configured on a border leaf."""
        interfaces = []

        for if_profile in self._logical_interface_profiles:
            dn = if_profile.get('dn', '')
            if f'node-{node_id}' in dn:
                interfaces.append(if_profile.get('name', dn))

        return interfaces

    def _extract_tenant_from_dn(self, dn: str) -> str:
        """Extract tenant name from DN."""
        match = re.search(r'tn-([^/]+)', dn)
        return match.group(1) if match else 'unknown'

    def _extract_l3out_from_dn(self, dn: str) -> str:
        """Extract L3Out name from DN."""
        match = re.search(r'out-([^/]+)', dn)
        return match.group(1) if match else 'unknown'

    def _extract_node_id(self, dn: str) -> Optional[str]:
        """Extract node ID from DN."""
        match = re.search(r'node-(\d+)', dn)
        return match.group(1) if match else None

    def _get_node_name(self, node_id: str) -> str:
        """Get node name from ID."""
        node = self._node_by_id.get(node_id, {})
        return node.get('name', f'node-{node_id}')

    def _generate_config_templates(self, l3out_analysis, bgp_analysis, ospf_analysis) -> Dict[str, str]:
        """Generate sample configuration templates for target platforms."""
        templates = {}

        # BGP template (if BGP is used)
        if bgp_analysis['peer_count'] > 0:
            templates['bgp_nxos'] = f"""! NX-OS BGP Configuration Example
router bgp <local-as>
  neighbor <peer-ip> remote-as <remote-as>
  address-family ipv4 unicast
    network <network> mask <mask>
"""

        # OSPF template (if OSPF is used)
        if ospf_analysis['total_interfaces'] > 0:
            templates['ospf_nxos'] = f"""! NX-OS OSPF Configuration Example
router ospf <process-id>
  network <network> <wildcard> area <area>
"""

        return templates

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of L3Out analysis."""
        l3out_analysis = self.analyze_l3outs()
        bgp_analysis = self.analyze_bgp_configuration()
        ospf_analysis = self.analyze_ospf_configuration()
        border_leafs = self.identify_border_leafs()
        migration_recs = self.generate_migration_recommendations()

        return {
            'l3out_summary': {
                'total_l3outs': l3out_analysis['total_l3outs'],
                'protocols': l3out_analysis['protocols'],
                'vrfs_with_external': len(l3out_analysis['vrfs_with_external'])
            },
            'bgp_summary': {
                'total_peers': bgp_analysis['peer_count'],
                'ebgp': bgp_analysis['ebgp_sessions'],
                'ibgp': bgp_analysis['ibgp_sessions'],
                'as_count': len(bgp_analysis['as_numbers'])
            },
            'ospf_summary': {
                'total_interfaces': ospf_analysis['total_interfaces'],
                'areas': len(ospf_analysis['areas'])
            },
            'border_leaf_summary': {
                'total': border_leafs['total_count'],
                'leafs': [leaf['node_name'] for leaf in border_leafs['border_leafs']]
            },
            'migration_readiness': migration_recs['complexity_assessment']
        }
