"""
ACI Contract to ACL Translation Engine
Translates ACI contracts (vzBrCP), subjects, and filters into traditional ACLs
for migration to non-ACI platforms.
"""
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ACLRule:
    """Represents a single ACL rule entry."""
    sequence: int
    action: str  # permit, deny
    protocol: str  # tcp, udp, icmp, ip, etc.
    source: str  # Source address/network
    source_port: Optional[str] = None
    destination: str = 'any'  # Destination address/network
    dest_port: Optional[str] = None
    established: bool = False
    log: bool = False
    description: str = ''


class ContractTranslator:
    """
    Translates ACI contracts, subjects, and filters to traditional ACLs.

    Supports:
    - Contract parsing and subject extraction
    - Filter to ACL rule translation
    - Provider/Consumer EPG identification
    - Directionality analysis (in/out ACLs)
    - Multi-vendor ACL format generation (IOS, NX-OS, EOS, Junos)
    - Contract scope handling (tenant, VRF, global)
    """

    def __init__(self, aci_objects: List[Dict[str, Any]]):
        """
        Initialize contract translator with ACI object data.

        Args:
            aci_objects: List of parsed ACI objects from JSON/XML
        """
        self.aci_objects = aci_objects

        # Categorized objects
        self._contracts = []
        self._subjects = []
        self._filters = []
        self._filter_entries = []
        self._epgs = []
        self._consumers = []
        self._providers = []
        self._bd_epg_map = {}

        # Lookup dictionaries
        self._contract_by_dn = {}
        self._subject_by_dn = {}
        self._filter_by_dn = {}
        self._epg_by_dn = {}

        self._categorize_objects()

    def _categorize_objects(self):
        """Extract contract-related objects from ACI data."""
        for obj in self.aci_objects:
            obj_type = obj.get('type')
            attrs = obj.get('attributes', {})
            dn = attrs.get('dn', '')

            # Contracts
            if obj_type == 'vzBrCP':
                self._contracts.append(attrs)
                if dn:
                    self._contract_by_dn[dn] = attrs

            # Subjects (within contracts)
            elif obj_type == 'vzSubj':
                self._subjects.append(attrs)
                if dn:
                    self._subject_by_dn[dn] = attrs

            # Filters
            elif obj_type == 'vzFilter':
                self._filters.append(attrs)
                if dn:
                    self._filter_by_dn[dn] = attrs

            # Filter entries (individual rules within filters)
            elif obj_type == 'vzEntry':
                self._filter_entries.append(attrs)

            # EPGs
            elif obj_type == 'fvAEPg':
                self._epgs.append(attrs)
                if dn:
                    self._epg_by_dn[dn] = attrs

            # Consumer relationships
            elif obj_type == 'fvRsCons':
                self._consumers.append(attrs)

            # Provider relationships
            elif obj_type == 'fvRsProv':
                self._providers.append(attrs)

        logger.info(
            f"Contract Translation: Found {len(self._contracts)} contracts, "
            f"{len(self._subjects)} subjects, {len(self._filters)} filters, "
            f"{len(self._filter_entries)} filter entries"
        )

    def analyze_contracts(self) -> Dict[str, Any]:
        """
        Analyze all contracts and their relationships.

        Returns:
            Dictionary containing:
            - contracts: List of contracts with provider/consumer mappings
            - total_contracts: Total count
            - scopes: Distribution by scope (tenant, VRF, global)
            - complexity: Contract complexity metrics
        """
        results = {
            'contracts': [],
            'total_contracts': len(self._contracts),
            'scopes': {'tenant': 0, 'vrf': 0, 'global': 0, 'application-profile': 0},
            'complexity': {
                'simple': 0,  # 1 subject, 1 filter
                'medium': 0,  # 2-5 subjects or filters
                'complex': 0  # 6+ subjects or filters
            }
        }

        for contract in self._contracts:
            dn = contract.get('dn', '')
            name = contract.get('name')
            scope = contract.get('scope', 'context')  # context = VRF, tenant, global, application-profile

            # Find subjects for this contract
            subjects = self._find_subjects_for_contract(dn)

            # Find providers and consumers
            providers = self._find_providers_for_contract(dn)
            consumers = self._find_consumers_for_contract(dn)

            # Calculate complexity
            complexity_score = len(subjects) + sum(len(s.get('filters', [])) for s in subjects)
            if complexity_score <= 2:
                complexity_level = 'simple'
                results['complexity']['simple'] += 1
            elif complexity_score <= 5:
                complexity_level = 'medium'
                results['complexity']['medium'] += 1
            else:
                complexity_level = 'complex'
                results['complexity']['complex'] += 1

            contract_info = {
                'name': name,
                'dn': dn,
                'scope': scope,
                'description': contract.get('descr', ''),
                'subjects': subjects,
                'providers': providers,
                'consumers': consumers,
                'complexity': complexity_level,
                'subject_count': len(subjects),
                'rule_count': sum(s.get('filter_entry_count', 0) for s in subjects),
                'acl_recommendation': self._recommend_acl_placement(providers, consumers)
            }

            results['contracts'].append(contract_info)

            # Track scope distribution
            if scope in results['scopes']:
                results['scopes'][scope] += 1

        return results

    def translate_contract_to_acl(self, contract_dn: str) -> Dict[str, Any]:
        """
        Translate a specific contract to ACL rules.

        Args:
            contract_dn: Distinguished name of the contract to translate

        Returns:
            Dictionary containing:
            - contract_name: Name of the contract
            - acl_rules: List of ACLRule objects
            - provider_acls: ACLs for provider EPGs (outbound)
            - consumer_acls: ACLs for consumer EPGs (inbound)
            - config_templates: Multi-vendor ACL configurations
        """
        contract = self._contract_by_dn.get(contract_dn)
        if not contract:
            return {'error': f'Contract not found: {contract_dn}'}

        contract_name = contract.get('name')
        subjects = self._find_subjects_for_contract(contract_dn)

        results = {
            'contract_name': contract_name,
            'acl_rules': [],
            'provider_acls': [],
            'consumer_acls': [],
            'config_templates': {}
        }

        # Track sequence number for ACL rules
        sequence = 10

        # Process each subject
        for subject in subjects:
            subject_name = subject['name']

            # Process filters in subject
            for filter_dn in subject.get('filters', []):
                filter_obj = self._filter_by_dn.get(filter_dn)
                if not filter_obj:
                    continue

                filter_name = filter_obj.get('name')

                # Find filter entries for this filter
                filter_entries = self._find_filter_entries(filter_dn)

                for entry in filter_entries:
                    # Translate filter entry to ACL rule
                    acl_rule = self._translate_filter_entry_to_acl(
                        entry, sequence, f"{contract_name}:{subject_name}:{filter_name}"
                    )
                    results['acl_rules'].append(acl_rule)
                    sequence += 10

        # Determine provider and consumer ACLs based on directionality
        providers = self._find_providers_for_contract(contract_dn)
        consumers = self._find_consumers_for_contract(contract_dn)

        # Provider ACL (applied outbound on provider EPG interfaces)
        # Allows traffic FROM provider TO consumer
        provider_acl_name = f"ACL_{contract_name}_PROVIDER_OUT"
        results['provider_acls'] = {
            'name': provider_acl_name,
            'direction': 'outbound',
            'applied_to': [p['name'] for p in providers],
            'rules': results['acl_rules'],
            'description': f'Outbound ACL for provider EPGs of contract {contract_name}'
        }

        # Consumer ACL (applied inbound on consumer EPG interfaces)
        # Allows traffic FROM consumer TO provider
        consumer_acl_name = f"ACL_{contract_name}_CONSUMER_IN"
        # Reverse source/dest for consumer perspective
        consumer_rules = self._reverse_acl_rules(results['acl_rules'])
        results['consumer_acls'] = {
            'name': consumer_acl_name,
            'direction': 'inbound',
            'applied_to': [c['name'] for c in consumers],
            'rules': consumer_rules,
            'description': f'Inbound ACL for consumer EPGs of contract {contract_name}'
        }

        # Generate multi-vendor configurations
        results['config_templates'] = {
            'ios': self._generate_ios_acl(results['provider_acls']),
            'nxos': self._generate_nxos_acl(results['provider_acls']),
            'eos': self._generate_eos_acl(results['provider_acls']),
            'junos': self._generate_junos_acl(results['provider_acls'])
        }

        return results

    def translate_all_contracts(self) -> Dict[str, Any]:
        """
        Translate all contracts to ACLs.

        Returns:
            Dictionary with translations for all contracts
        """
        results = {
            'translations': [],
            'summary': {
                'total_contracts': len(self._contracts),
                'total_acls_generated': 0,
                'total_rules': 0
            }
        }

        for contract in self._contracts:
            dn = contract.get('dn')
            translation = self.translate_contract_to_acl(dn)

            if 'error' not in translation:
                results['translations'].append(translation)
                results['summary']['total_acls_generated'] += 2  # Provider + Consumer ACL
                results['summary']['total_rules'] += len(translation.get('acl_rules', []))

        return results

    def _translate_filter_entry_to_acl(self, entry: Dict[str, Any], sequence: int, description: str) -> ACLRule:
        """Translate a single ACI filter entry to an ACL rule."""
        # Extract filter entry attributes
        protocol = entry.get('prot', 'ip')  # tcp, udp, icmp, ip
        ether_type = entry.get('etherT', 'ip')  # ip, arp, etc.
        dest_from_port = entry.get('dFromPort', 'unspecified')
        dest_to_port = entry.get('dToPort', 'unspecified')
        source_from_port = entry.get('sFromPort', 'unspecified')
        source_to_port = entry.get('sToPort', 'unspecified')
        established = entry.get('stateful') == 'yes'
        apply_to_frag = entry.get('applyToFrag') == 'yes'

        # Normalize protocol
        if protocol == 'unspecified':
            protocol = 'ip'

        # Format port specifications
        dest_port = self._format_port_range(dest_from_port, dest_to_port)
        source_port = self._format_port_range(source_from_port, source_to_port)

        # Create ACL rule
        return ACLRule(
            sequence=sequence,
            action='permit',  # ACI contracts are permit-by-definition
            protocol=protocol,
            source='any',  # Will be replaced with actual source EPG subnets
            source_port=source_port,
            destination='any',  # Will be replaced with actual dest EPG subnets
            dest_port=dest_port,
            established=established,
            log=False,
            description=description
        )

    def _format_port_range(self, from_port: str, to_port: str) -> Optional[str]:
        """Format port range for ACL rule."""
        if from_port == 'unspecified' or from_port is None:
            return None

        # Named ports (e.g., 'http', 'https')
        if not from_port.isdigit():
            return from_port

        if to_port == 'unspecified' or from_port == to_port:
            return f"eq {from_port}"
        else:
            return f"range {from_port} {to_port}"

    def _reverse_acl_rules(self, rules: List[ACLRule]) -> List[ACLRule]:
        """Reverse ACL rules for opposite direction (consumer perspective)."""
        reversed_rules = []
        for rule in rules:
            reversed_rule = ACLRule(
                sequence=rule.sequence,
                action=rule.action,
                protocol=rule.protocol,
                source=rule.destination,  # Swap source and dest
                source_port=rule.dest_port,
                destination=rule.source,
                dest_port=rule.source_port,
                established=rule.established,
                log=rule.log,
                description=f"{rule.description} (reversed)"
            )
            reversed_rules.append(reversed_rule)
        return reversed_rules

    def _find_subjects_for_contract(self, contract_dn: str) -> List[Dict[str, Any]]:
        """Find all subjects within a contract."""
        subjects = []
        for subject in self._subjects:
            subj_dn = subject.get('dn', '')
            if subj_dn.startswith(contract_dn + '/'):
                # Find filters referenced by this subject
                filters = self._find_filters_for_subject(subj_dn)

                subjects.append({
                    'name': subject.get('name'),
                    'dn': subj_dn,
                    'filters': filters,
                    'filter_entry_count': sum(len(self._find_filter_entries(f)) for f in filters)
                })
        return subjects

    def _find_filters_for_subject(self, subject_dn: str) -> List[str]:
        """Find filters referenced by a subject (via rsSubjFiltAtt relationship)."""
        filters = []

        # In ACI data, filters are referenced via vzRsSubjFiltAtt objects
        for obj in self.aci_objects:
            if obj.get('type') == 'vzRsSubjFiltAtt':
                attrs = obj.get('attributes', {})
                parent_dn = attrs.get('dn', '').rsplit('/rssubjFiltAtt-', 1)[0]

                if parent_dn == subject_dn:
                    # Get target filter DN
                    tn_filter_name = attrs.get('tnVzFilterName')
                    if tn_filter_name:
                        # Construct filter DN
                        tenant = self._extract_tenant_from_dn(subject_dn)
                        filter_dn = f"uni/tn-{tenant}/flt-{tn_filter_name}"
                        filters.append(filter_dn)

        return filters

    def _find_filter_entries(self, filter_dn: str) -> List[Dict[str, Any]]:
        """Find all filter entries within a filter."""
        entries = []
        for entry in self._filter_entries:
            entry_dn = entry.get('dn', '')
            if entry_dn.startswith(filter_dn + '/'):
                entries.append(entry)
        return entries

    def _find_providers_for_contract(self, contract_dn: str) -> List[Dict[str, Any]]:
        """Find EPGs that provide this contract."""
        providers = []
        contract_name = self._extract_name_from_dn(contract_dn)

        for prov in self._providers:
            if prov.get('tnVzBrCPName') == contract_name:
                # Get parent EPG
                epg_dn = prov.get('dn', '').rsplit('/rsprov-', 1)[0]
                epg = self._epg_by_dn.get(epg_dn)
                if epg:
                    providers.append({
                        'name': epg.get('name'),
                        'dn': epg_dn,
                        'tenant': self._extract_tenant_from_dn(epg_dn)
                    })
        return providers

    def _find_consumers_for_contract(self, contract_dn: str) -> List[Dict[str, Any]]:
        """Find EPGs that consume this contract."""
        consumers = []
        contract_name = self._extract_name_from_dn(contract_dn)

        for cons in self._consumers:
            if cons.get('tnVzBrCPName') == contract_name:
                # Get parent EPG
                epg_dn = cons.get('dn', '').rsplit('/rscons-', 1)[0]
                epg = self._epg_by_dn.get(epg_dn)
                if epg:
                    consumers.append({
                        'name': epg.get('name'),
                        'dn': epg_dn,
                        'tenant': self._extract_tenant_from_dn(epg_dn)
                    })
        return consumers

    def _recommend_acl_placement(self, providers: List[Dict], consumers: List[Dict]) -> Dict[str, Any]:
        """Recommend where ACLs should be applied."""
        return {
            'provider_interfaces': [p['name'] for p in providers],
            'consumer_interfaces': [c['name'] for c in consumers],
            'recommendation': 'Apply provider ACL outbound on provider EPG interfaces, '
                            'consumer ACL inbound on consumer EPG interfaces'
        }

    def _extract_tenant_from_dn(self, dn: str) -> str:
        """Extract tenant name from DN."""
        match = re.search(r'tn-([^/]+)', dn)
        return match.group(1) if match else 'common'

    def _extract_name_from_dn(self, dn: str) -> str:
        """Extract object name from DN (last component)."""
        return dn.split('/')[-1].split('-', 1)[1] if '-' in dn.split('/')[-1] else ''

    # Multi-vendor ACL configuration generators

    def _generate_ios_acl(self, acl_config: Dict[str, Any]) -> str:
        """Generate Cisco IOS ACL configuration."""
        lines = [f"! Cisco IOS ACL Configuration",
                f"! {acl_config['description']}",
                f"ip access-list extended {acl_config['name']}"]

        for rule in acl_config.get('rules', []):
            line = f" {rule.sequence} {rule.action} {rule.protocol}"
            line += f" {rule.source}"
            if rule.source_port:
                line += f" {rule.source_port}"
            line += f" {rule.destination}"
            if rule.dest_port:
                line += f" {rule.dest_port}"
            if rule.established:
                line += " established"
            if rule.log:
                line += " log"
            lines.append(line)

        lines.append("!\n")
        return '\n'.join(lines)

    def _generate_nxos_acl(self, acl_config: Dict[str, Any]) -> str:
        """Generate Cisco NX-OS ACL configuration."""
        lines = [f"! Cisco NX-OS ACL Configuration",
                f"! {acl_config['description']}",
                f"ip access-list {acl_config['name']}"]

        for rule in acl_config.get('rules', []):
            line = f"  {rule.sequence} {rule.action} {rule.protocol}"
            line += f" {rule.source}"
            if rule.source_port:
                line += f" {rule.source_port}"
            line += f" {rule.destination}"
            if rule.dest_port:
                line += f" {rule.dest_port}"
            if rule.established:
                line += " established"
            if rule.log:
                line += " log"
            lines.append(line)

        lines.append("!\n")
        return '\n'.join(lines)

    def _generate_eos_acl(self, acl_config: Dict[str, Any]) -> str:
        """Generate Arista EOS ACL configuration."""
        lines = [f"! Arista EOS ACL Configuration",
                f"! {acl_config['description']}",
                f"ip access-list {acl_config['name']}"]

        for rule in acl_config.get('rules', []):
            line = f"   {rule.sequence} {rule.action} {rule.protocol}"
            line += f" {rule.source}"
            if rule.source_port:
                line += f" {rule.source_port}"
            line += f" {rule.destination}"
            if rule.dest_port:
                line += f" {rule.dest_port}"
            if rule.established:
                line += " established"
            if rule.log:
                line += " log"
            lines.append(line)

        lines.append("!\n")
        return '\n'.join(lines)

    def _generate_junos_acl(self, acl_config: Dict[str, Any]) -> str:
        """Generate Juniper Junos firewall filter configuration."""
        lines = [f"/* Junos Firewall Filter Configuration */",
                f"/* {acl_config['description']} */",
                f"firewall {{",
                f"    family inet {{",
                f"        filter {acl_config['name']} {{"]

        for rule in acl_config.get('rules', []):
            term_name = f"term-{rule.sequence}"
            lines.append(f"            term {term_name} {{")
            lines.append(f"                from {{")

            # Protocol
            if rule.protocol != 'ip':
                lines.append(f"                    protocol {rule.protocol};")

            # Source
            if rule.source != 'any':
                lines.append(f"                    source-address {rule.source};")
            if rule.source_port:
                lines.append(f"                    source-port {rule.source_port};")

            # Destination
            if rule.destination != 'any':
                lines.append(f"                    destination-address {rule.destination};")
            if rule.dest_port:
                lines.append(f"                    destination-port {rule.dest_port};")

            lines.append(f"                }}")
            lines.append(f"                then {rule.action};")
            lines.append(f"            }}")

        lines.extend([
            f"        }}",
            f"    }}",
            f"}}\n"
        ])

        return '\n'.join(lines)

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of contract translation."""
        contract_analysis = self.analyze_contracts()
        all_translations = self.translate_all_contracts()

        return {
            'contract_summary': {
                'total_contracts': contract_analysis['total_contracts'],
                'complexity_distribution': contract_analysis['complexity'],
                'scope_distribution': contract_analysis['scopes']
            },
            'translation_summary': all_translations['summary'],
            'migration_readiness': {
                'contracts_ready': contract_analysis['total_contracts'],
                'acls_required': all_translations['summary']['total_acls_generated'],
                'total_rules': all_translations['summary']['total_rules'],
                'average_rules_per_contract': (
                    all_translations['summary']['total_rules'] / contract_analysis['total_contracts']
                    if contract_analysis['total_contracts'] > 0 else 0
                )
            }
        }
