"""
Core Analysis Engine for ACI Fabric Analysis
Provides 12+ analysis types for offboard, onboard, and EVPN migration modes.
"""
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from pathlib import Path
import json
import re
import logging

logger = logging.getLogger(__name__)


class ACIAnalyzer:
    """
    Main analysis engine for ACI fabric data.

    Supports:
    - Port utilization analysis
    - Leaf-FEX topology mapping
    - Rack-level grouping with CMDB correlation
    - BD-EPG relationship mapping
    - VLAN distribution and overlap detection
    - EPG complexity scoring
    - VPC symmetry validation
    - Contract scope analysis
    - Migration readiness flags
    """

    def __init__(self, fabric_data: Dict[str, Any]):
        self.fabric_data = fabric_data
        self.datasets = fabric_data.get('datasets', [])

        # Cached parsed data
        self._aci_objects = None
        self._cmdb_records = None

        # Categorized ACI objects (populated by _categorize_objects)
        self._fexes = []
        self._leafs = []
        self._epgs = []
        self._bds = []
        self._vrfs = []
        self._tenants = []
        self._contracts = []
        self._path_attachments = []
        self._subnets = []
        self._interfaces = []
        self._physical_domains = []

        # Lookup dictionaries for performance
        self._fex_by_id = {}
        self._leaf_by_id = {}
        self._epg_by_dn = {}
        self._bd_by_dn = {}

    def _load_data(self):
        """Load and parse all datasets (ACI and CMDB)."""
        if self._aci_objects is not None:
            return

        self._aci_objects = []
        self._cmdb_records = []

        from . import parsers

        for dataset in self.datasets:
            try:
                path = Path(dataset['path'])
                if not path.exists():
                    logger.warning(f"Dataset file not found: {path}")
                    continue

                # Read file with encoding fallback
                content = self._read_file_safe(path)

                if dataset['type'] == 'aci':
                    parsed = parsers.parse_aci(content, dataset['format'])
                    self._aci_objects.extend(parsed['objects'])
                    logger.info(f"Loaded {len(parsed['objects'])} ACI objects from {dataset['filename']}")

                elif dataset['type'] == 'cmdb':
                    parsed = parsers.parse_cmdb_csv(content)
                    self._cmdb_records.extend(parsed)
                    logger.info(f"Loaded {len(parsed)} CMDB records from {dataset['filename']}")

            except Exception as e:
                logger.error(f"Error loading dataset {dataset.get('filename')}: {str(e)}")

        # Categorize objects for efficient lookups
        self._categorize_objects()

    def _read_file_safe(self, path: Path) -> str:
        """Read file with encoding fallback."""
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Cannot decode file: {path}")

    def _categorize_objects(self):
        """Categorize ACI objects by type for efficient access."""
        for obj in self._aci_objects:
            obj_type = obj.get('type')
            attrs = obj.get('attributes', {})

            if obj_type == 'eqptFex':
                self._fexes.append(attrs)
                fex_id = attrs.get('id')
                if fex_id:
                    self._fex_by_id[fex_id] = attrs

            elif obj_type == 'fabricNode':
                if attrs.get('role') == 'leaf':
                    self._leafs.append(attrs)
                    node_id = attrs.get('id')
                    if node_id:
                        self._leaf_by_id[node_id] = attrs

            elif obj_type == 'fvAEPg':
                self._epgs.append(attrs)
                dn = attrs.get('dn')
                if dn:
                    self._epg_by_dn[dn] = attrs

            elif obj_type == 'fvBD':
                self._bds.append(attrs)
                dn = attrs.get('dn')
                if dn:
                    self._bd_by_dn[dn] = attrs

            elif obj_type == 'fvCtx':
                self._vrfs.append(attrs)

            elif obj_type == 'fvTenant':
                self._tenants.append(attrs)

            elif obj_type == 'vzBrCP':
                self._contracts.append(attrs)

            elif obj_type == 'fvRsPathAtt':
                self._path_attachments.append(attrs)

            elif obj_type == 'fvSubnet':
                self._subnets.append(attrs)

            elif obj_type == 'ethpmPhysIf':
                self._interfaces.append(attrs)

            elif obj_type == 'physDomP':
                self._physical_domains.append(attrs)

        logger.info(
            f"Categorized objects: {len(self._fexes)} FEX, {len(self._leafs)} leafs, "
            f"{len(self._epgs)} EPGs, {len(self._bds)} BDs, {len(self._contracts)} contracts"
        )

    def validate(self) -> List[Dict[str, Any]]:
        """Validate loaded data and return validation results."""
        self._load_data()

        results = []

        # Check if data was loaded
        if not self._aci_objects:
            results.append({
                'level': 'error',
                'message': 'No ACI data loaded',
                'details': 'Upload ACI JSON/XML files to begin analysis'
            })
            return results

        # Basic statistics
        results.append({
            'level': 'info',
            'message': 'Data loaded successfully',
            'details': f'{len(self._aci_objects)} total ACI objects'
        })

        # Validate key objects
        if not self._fexes and not self._leafs:
            results.append({
                'level': 'warning',
                'message': 'No fabric nodes found',
                'details': 'Expected eqptFex or fabricNode objects'
            })

        if not self._epgs:
            results.append({
                'level': 'warning',
                'message': 'No EPGs found',
                'details': 'Expected fvAEPg objects for policy analysis'
            })

        if not self._bds:
            results.append({
                'level': 'warning',
                'message': 'No Bridge Domains found',
                'details': 'Expected fvBD objects for network analysis'
            })

        # CMDB validation
        if self._cmdb_records:
            results.append({
                'level': 'info',
                'message': 'CMDB data loaded',
                'details': f'{len(self._cmdb_records)} device records'
            })
        else:
            results.append({
                'level': 'info',
                'message': 'No CMDB data loaded',
                'details': 'Upload CMDB CSV for rack-level analysis'
            })

        # Check for common issues
        if len(self._path_attachments) == 0 and len(self._epgs) > 0:
            results.append({
                'level': 'warning',
                'message': 'EPGs found but no path attachments',
                'details': 'EPG to infrastructure bindings may be missing from export'
            })

        return results

    def analyze_port_utilization(self) -> List[Dict[str, Any]]:
        """
        Analyze port utilization across all FEX devices.
        Returns list of FEX with utilization metrics and consolidation scores.
        """
        self._load_data()

        if not self._fexes:
            return []

        results = []

        for fex in self._fexes:
            fex_id = fex.get('id', '')
            fex_serial = fex.get('ser', '')
            fex_model = fex.get('model', '')
            fex_dn = fex.get('dn', '')

            # Extract leaf ID from DN (topology/pod-X/node-Y/sys/extch-Z)
            leaf_id = self._extract_leaf_from_fex_dn(fex_dn)

            # Determine total ports based on model
            total_ports = self._get_fex_port_count(fex_model)

            # Count interfaces for this FEX
            fex_interfaces = [
                iface for iface in self._interfaces
                if f'eth{fex_id}/' in iface.get('id', '')
            ]

            # Count connected (up) ports
            connected_ports = sum(
                1 for iface in fex_interfaces
                if iface.get('operSt') == 'up'
            )

            # Calculate utilization
            utilization_pct = (connected_ports / total_ports * 100) if total_ports > 0 else 0

            # Calculate consolidation score (0-100)
            # Higher score = better candidate for consolidation
            consolidation_score = self._calculate_consolidation_score(
                utilization_pct, fex.get('operSt'), len(fex_interfaces)
            )

            results.append({
                'fex_id': fex_id,
                'serial': fex_serial,
                'model': fex_model,
                'leaf_id': leaf_id,
                'total_ports': total_ports,
                'connected_ports': connected_ports,
                'utilization_pct': round(utilization_pct, 2),
                'status': fex.get('operSt', 'unknown'),
                'consolidation_score': consolidation_score,
                'recommendation': self._get_consolidation_recommendation(consolidation_score, utilization_pct)
            })

        # Sort by consolidation score (highest first)
        results.sort(key=lambda x: x['consolidation_score'], reverse=True)

        return results

    def analyze_leaf_fex_mapping(self) -> Dict[str, Any]:
        """
        Analyze leaf-to-FEX topology mappings.
        Returns leaf switches with their attached FEX devices.
        """
        self._load_data()

        mappings = []

        for leaf in self._leafs:
            leaf_id = leaf.get('id', '')
            leaf_name = leaf.get('name', '')
            leaf_model = leaf.get('model', '')
            leaf_serial = leaf.get('serial', '')

            # Find all FEX attached to this leaf
            attached_fex = []
            for fex in self._fexes:
                fex_dn = fex.get('dn', '')
                if f'node-{leaf_id}' in fex_dn:
                    attached_fex.append({
                        'fex_id': fex.get('id'),
                        'serial': fex.get('ser'),
                        'model': fex.get('model'),
                        'status': fex.get('operSt', 'unknown')
                    })

            mappings.append({
                'leaf_id': leaf_id,
                'leaf_name': leaf_name,
                'leaf_model': leaf_model,
                'leaf_serial': leaf_serial,
                'fex_count': len(attached_fex),
                'attached_fex': attached_fex,
                'overloaded': len(attached_fex) > 12  # Flag if >12 FEX per leaf
            })

        # Calculate statistics
        total_fex = len(self._fexes)
        fex_with_leaf = sum(len(m['attached_fex']) for m in mappings)
        avg_fex_per_leaf = fex_with_leaf / len(mappings) if mappings else 0

        return {
            'mappings': mappings,
            'statistics': {
                'total_leafs': len(self._leafs),
                'total_fex': total_fex,
                'avg_fex_per_leaf': round(avg_fex_per_leaf, 2),
                'overloaded_leafs': sum(1 for m in mappings if m['overloaded'])
            }
        }

    def analyze_rack_grouping(self) -> Dict[str, Any]:
        """
        Analyze rack-level grouping using CMDB data.
        Identifies FEX grouped by rack location.
        """
        self._load_data()

        if not self._cmdb_records:
            return {
                'racks': {},
                'mismatches': [],
                'message': 'No CMDB data available. Upload CMDB CSV for rack analysis.'
            }

        # Group devices by rack
        racks = defaultdict(lambda: {
            'devices': [],
            'site': None,
            'building': None,
            'hall': None
        })

        # Create serial number lookup for FEX
        fex_by_serial = {fex.get('ser'): fex for fex in self._fexes if fex.get('ser')}
        leaf_by_serial = {leaf.get('serial'): leaf for leaf in self._leafs if leaf.get('serial')}

        for record in self._cmdb_records:
            serial = record.get('serial_number', '')
            rack = record.get('rack', 'Unknown')
            site = record.get('site', '')
            building = record.get('building', '')
            hall = record.get('hall', '')

            # Determine device type
            device_type = 'unknown'
            device_id = None
            if serial in fex_by_serial:
                device_type = 'fex'
                device_id = fex_by_serial[serial].get('id')
            elif serial in leaf_by_serial:
                device_type = 'leaf'
                device_id = leaf_by_serial[serial].get('id')

            racks[rack]['devices'].append({
                'serial': serial,
                'type': device_type,
                'id': device_id,
                'site': site
            })

            # Set rack location info from first device
            if racks[rack]['site'] is None:
                racks[rack]['site'] = site
                racks[rack]['building'] = building
                racks[rack]['hall'] = hall

        # Identify racks with mixed sites (potential mismatches)
        mismatches = []
        for rack_name, rack_data in racks.items():
            sites = set(d['site'] for d in rack_data['devices'] if d['site'])
            if len(sites) > 1:
                mismatches.append({
                    'rack': rack_name,
                    'sites': list(sites),
                    'device_count': len(rack_data['devices']),
                    'issue': 'Devices from multiple sites in same rack'
                })

        return {
            'racks': dict(racks),
            'mismatches': mismatches,
            'statistics': {
                'total_racks': len(racks),
                'total_devices': len(self._cmdb_records),
                'mismatched_racks': len(mismatches),
                'correlation_rate': round(
                    (len(fex_by_serial) + len(leaf_by_serial)) / len(self._cmdb_records) * 100, 2
                ) if self._cmdb_records else 0
            }
        }

    def analyze_bd_epg_mapping(self) -> Dict[str, Any]:
        """
        Analyze Bridge Domain to EPG relationships.
        Shows which EPGs are in which BDs and subnet configurations.
        """
        self._load_data()

        mappings = []

        for bd in self._bds:
            bd_name = bd.get('name', '')
            bd_dn = bd.get('dn', '')
            vrf_name = bd.get('vrf', '')

            # Extract tenant from DN
            tenant = self._extract_tenant_from_dn(bd_dn)

            # Find EPGs in this BD
            epgs_in_bd = [
                epg for epg in self._epgs
                if epg.get('bd') == bd_name and tenant in epg.get('dn', '')
            ]

            # Find subnets in this BD
            bd_subnets = [
                subnet for subnet in self._subnets
                if bd_dn in subnet.get('dn', '')
            ]

            mappings.append({
                'bd_name': bd_name,
                'tenant': tenant,
                'vrf': vrf_name,
                'epg_count': len(epgs_in_bd),
                'epgs': [epg.get('name') for epg in epgs_in_bd],
                'subnets': [subnet.get('ip') for subnet in bd_subnets],
                'arp_flood': bd.get('arpFlood', 'no'),
                'unicast_route': bd.get('unicastRoute', 'yes')
            })

        return {
            'mappings': mappings,
            'statistics': {
                'total_bds': len(self._bds),
                'total_epgs': len(self._epgs),
                'bds_without_epgs': sum(1 for m in mappings if m['epg_count'] == 0),
                'bds_without_subnets': sum(1 for m in mappings if not m['subnets'])
            }
        }

    def analyze_vlan_distribution(self) -> Dict[str, Any]:
        """
        Analyze VLAN distribution across EPGs and path attachments.
        Identifies VLAN overlaps and usage patterns.
        """
        self._load_data()

        vlan_usage = defaultdict(list)

        # Extract VLANs from path attachments
        for path in self._path_attachments:
            encap = path.get('encap', '')  # Format: vlan-XXX
            vlan_match = re.search(r'vlan-(\d+)', encap)

            if vlan_match:
                vlan_id = int(vlan_match.group(1))
                epg_dn = self._extract_epg_from_path_dn(path.get('dn', ''))

                vlan_usage[vlan_id].append({
                    'epg_dn': epg_dn,
                    'path': path.get('tDn', ''),
                    'mode': path.get('mode', 'regular')
                })

        # Identify overlaps (same VLAN used by multiple EPGs)
        overlaps = []
        for vlan_id, usages in vlan_usage.items():
            unique_epgs = set(u['epg_dn'] for u in usages)
            if len(unique_epgs) > 1:
                overlaps.append({
                    'vlan': vlan_id,
                    'epg_count': len(unique_epgs),
                    'epgs': list(unique_epgs),
                    'total_bindings': len(usages),
                    'severity': 'high' if len(unique_epgs) > 3 else 'medium'
                })

        # VLAN usage statistics
        vlan_ids = list(vlan_usage.keys())

        return {
            'vlan_usage': {str(k): v for k, v in vlan_usage.items()},
            'overlaps': overlaps,
            'statistics': {
                'total_vlans_used': len(vlan_ids),
                'vlan_range': f'{min(vlan_ids)}-{max(vlan_ids)}' if vlan_ids else 'N/A',
                'overlap_count': len(overlaps),
                'total_path_attachments': len(self._path_attachments)
            }
        }

    def analyze_epg_complexity(self) -> List[Dict[str, Any]]:
        """
        Calculate EPG complexity scores based on:
        - Number of path attachments
        - Number of unique VLANs
        - Number of contracts (providers/consumers)
        - Spread across leafs/FEX
        """
        self._load_data()

        results = []

        for epg in self._epgs:
            epg_name = epg.get('name', '')
            epg_dn = epg.get('dn', '')
            tenant = self._extract_tenant_from_dn(epg_dn)

            # Count path attachments for this EPG
            paths = [p for p in self._path_attachments if epg_dn in p.get('dn', '')]

            # Extract unique VLANs
            vlans = set()
            for path in paths:
                encap = path.get('encap', '')
                vlan_match = re.search(r'vlan-(\d+)', encap)
                if vlan_match:
                    vlans.add(int(vlan_match.group(1)))

            # Extract unique leafs/nodes
            nodes = set()
            for path in paths:
                node_match = re.search(r'node-(\d+)', path.get('tDn', ''))
                if node_match:
                    nodes.add(node_match.group(1))

            # Calculate complexity score (0-100)
            complexity_score = self._calculate_epg_complexity_score(
                path_count=len(paths),
                vlan_count=len(vlans),
                node_count=len(nodes)
            )

            results.append({
                'epg_name': epg_name,
                'tenant': tenant,
                'bd': epg.get('bd', ''),
                'path_count': len(paths),
                'vlan_count': len(vlans),
                'node_count': len(nodes),
                'complexity_score': complexity_score,
                'complexity_level': self._get_complexity_level(complexity_score)
            })

        # Sort by complexity score (highest first)
        results.sort(key=lambda x: x['complexity_score'], reverse=True)

        return results

    def analyze_vpc_symmetry(self) -> Dict[str, Any]:
        """
        Analyze VPC symmetry - check if EPG bindings are symmetric across VPC pairs.
        Identifies asymmetric configurations that could cause traffic issues.
        """
        self._load_data()

        # Group path attachments by EPG
        epg_paths = defaultdict(list)
        for path in self._path_attachments:
            epg_dn = self._extract_epg_from_path_dn(path.get('dn', ''))
            epg_paths[epg_dn].append(path)

        asymmetric_bindings = []

        # Check each EPG for symmetric bindings
        for epg_dn, paths in epg_paths.items():
            # Extract node pairs (potential VPC pairs)
            node_vlans = defaultdict(set)

            for path in paths:
                tdn = path.get('tDn', '')
                node_match = re.search(r'node-(\d+)', tdn)
                encap = path.get('encap', '')
                vlan_match = re.search(r'vlan-(\d+)', encap)

                if node_match and vlan_match:
                    node_id = node_match.group(1)
                    vlan_id = vlan_match.group(1)
                    node_vlans[node_id].add(vlan_id)

            # Look for potential asymmetry (nodes with different VLAN sets)
            if len(node_vlans) > 1:
                node_list = list(node_vlans.items())
                for i in range(len(node_list) - 1):
                    node1, vlans1 = node_list[i]
                    node2, vlans2 = node_list[i + 1]

                    if vlans1 != vlans2:
                        asymmetric_bindings.append({
                            'epg': self._extract_epg_name_from_dn(epg_dn),
                            'node1': node1,
                            'node1_vlans': list(vlans1),
                            'node2': node2,
                            'node2_vlans': list(vlans2),
                            'missing_in_node1': list(vlans2 - vlans1),
                            'missing_in_node2': list(vlans1 - vlans2)
                        })

        return {
            'asymmetric_bindings': asymmetric_bindings,
            'statistics': {
                'total_epgs_checked': len(epg_paths),
                'asymmetric_epgs': len(asymmetric_bindings),
                'symmetry_rate': round(
                    (len(epg_paths) - len(asymmetric_bindings)) / len(epg_paths) * 100, 2
                ) if epg_paths else 100
            }
        }

    def analyze_pdom(self) -> Dict[str, Any]:
        """Analyze physical domain configurations."""
        self._load_data()

        domains = []
        for pdom in self._physical_domains:
            domains.append({
                'name': pdom.get('name', ''),
                'dn': pdom.get('dn', '')
            })

        return {
            'domains': domains,
            'count': len(domains)
        }

    def analyze_migration_flags(self) -> List[Dict[str, Any]]:
        """
        Identify potential migration issues and flags.
        Checks for configurations that may complicate migration.
        """
        self._load_data()

        flags = []

        # Check for EPGs without path attachments
        unbound_epgs = [
            epg for epg in self._epgs
            if not any(epg.get('dn', '') in p.get('dn', '') for p in self._path_attachments)
        ]

        if unbound_epgs:
            flags.append({
                'severity': 'medium',
                'category': 'unbound_epgs',
                'count': len(unbound_epgs),
                'message': f'{len(unbound_epgs)} EPGs without path attachments',
                'recommendation': 'Review EPGs for unused policies or missing bindings'
            })

        # Check for BDs without subnets
        bds_without_subnets = [
            bd for bd in self._bds
            if not any(bd.get('dn', '') in s.get('dn', '') for s in self._subnets)
        ]

        if bds_without_subnets:
            flags.append({
                'severity': 'low',
                'category': 'bds_without_subnets',
                'count': len(bds_without_subnets),
                'message': f'{len(bds_without_subnets)} Bridge Domains without subnets',
                'recommendation': 'Verify L2 vs L3 forwarding requirements'
            })

        # Check for VRFs without BDs
        vrfs_without_bds = []
        for vrf in self._vrfs:
            vrf_name = vrf.get('name', '')
            has_bd = any(bd.get('vrf') == vrf_name for bd in self._bds)
            if not has_bd:
                vrfs_without_bds.append(vrf_name)

        if vrfs_without_bds:
            flags.append({
                'severity': 'low',
                'category': 'unused_vrfs',
                'count': len(vrfs_without_bds),
                'message': f'{len(vrfs_without_bds)} VRFs without Bridge Domains',
                'recommendation': 'Clean up unused VRF instances before migration'
            })

        # Check for high VLAN overlap
        vlan_analysis = self.analyze_vlan_distribution()
        high_overlaps = [o for o in vlan_analysis['overlaps'] if o['severity'] == 'high']

        if high_overlaps:
            flags.append({
                'severity': 'high',
                'category': 'vlan_overlaps',
                'count': len(high_overlaps),
                'message': f'{len(high_overlaps)} VLANs with high EPG overlap (>3 EPGs)',
                'recommendation': 'Review VLAN allocation strategy for migration'
            })

        return flags

    def analyze_contract_scope(self) -> List[Dict[str, Any]]:
        """
        Analyze contract scopes (context, tenant, global).
        Identifies inter-tenant and global contracts.
        """
        self._load_data()

        results = []

        scope_counts = defaultdict(int)

        for contract in self._contracts:
            contract_name = contract.get('name', '')
            contract_dn = contract.get('dn', '')
            tenant = self._extract_tenant_from_dn(contract_dn)
            scope = contract.get('scope', 'context')
            priority = contract.get('prio', 'default')

            scope_counts[scope] += 1

            results.append({
                'contract_name': contract_name,
                'tenant': tenant,
                'scope': scope,
                'priority': priority,
                'complexity': 'high' if scope == 'global' else 'medium' if scope == 'tenant' else 'low'
            })

        return results

    def analyze_vlan_spread(self) -> Dict[str, Any]:
        """Alias for analyze_vlan_distribution."""
        return self.analyze_vlan_distribution()

    def analyze_cmdb_correlation(self) -> Dict[str, Any]:
        """
        Correlate ACI device data with CMDB records.
        Identifies matched and unmatched devices.
        """
        self._load_data()

        if not self._cmdb_records:
            return {
                'correlated': [],
                'uncorrelated': [],
                'correlation_rate': 0,
                'message': 'No CMDB data available'
            }

        # Build serial number sets
        aci_serials = set()
        for fex in self._fexes:
            if fex.get('ser'):
                aci_serials.add(fex.get('ser'))
        for leaf in self._leafs:
            if leaf.get('serial'):
                aci_serials.add(leaf.get('serial'))

        cmdb_serials = set(r.get('serial_number') for r in self._cmdb_records if r.get('serial_number'))

        # Find matches
        correlated = []
        for record in self._cmdb_records:
            serial = record.get('serial_number', '')
            if serial in aci_serials:
                correlated.append({
                    'serial': serial,
                    'rack': record.get('rack'),
                    'site': record.get('site'),
                    'status': 'matched'
                })

        # Find unmatched
        uncorrelated_cmdb = [
            {
                'serial': r.get('serial_number'),
                'rack': r.get('rack'),
                'site': r.get('site'),
                'reason': 'Not found in ACI fabric'
            }
            for r in self._cmdb_records
            if r.get('serial_number') not in aci_serials
        ]

        uncorrelated_aci = [
            {
                'serial': s,
                'reason': 'Not found in CMDB'
            }
            for s in aci_serials
            if s not in cmdb_serials
        ]

        correlation_rate = (len(correlated) / len(cmdb_serials) * 100) if cmdb_serials else 0

        return {
            'correlated': correlated,
            'uncorrelated_cmdb': uncorrelated_cmdb,
            'uncorrelated_aci': uncorrelated_aci,
            'correlation_rate': round(correlation_rate, 2),
            'statistics': {
                'total_cmdb_records': len(self._cmdb_records),
                'total_aci_devices': len(aci_serials),
                'matched_devices': len(correlated),
                'unmatched_cmdb': len(uncorrelated_cmdb),
                'unmatched_aci': len(uncorrelated_aci)
            }
        }

    def get_visualization_data(self) -> Dict[str, Any]:
        """
        Get data for topology visualization.
        Returns leaf-FEX topology and port density information.
        """
        self._load_data()

        # Build topology structure
        topology_nodes = []
        topology_edges = []

        # Add leaf nodes
        for leaf in self._leafs:
            topology_nodes.append({
                'id': f"leaf-{leaf.get('id')}",
                'type': 'leaf',
                'name': leaf.get('name'),
                'model': leaf.get('model')
            })

        # Add FEX nodes and edges
        for fex in self._fexes:
            fex_id = fex.get('id')
            fex_dn = fex.get('dn', '')
            leaf_id = self._extract_leaf_from_fex_dn(fex_dn)

            topology_nodes.append({
                'id': f"fex-{fex_id}",
                'type': 'fex',
                'name': f"FEX-{fex_id}",
                'model': fex.get('model')
            })

            if leaf_id:
                topology_edges.append({
                    'source': f"leaf-{leaf_id}",
                    'target': f"fex-{fex_id}"
                })

        # Port density data
        port_util = self.analyze_port_utilization()
        density = [
            {
                'device': f"FEX-{p['fex_id']}",
                'utilization': p['utilization_pct']
            }
            for p in port_util
        ]

        return {
            'topology': {
                'nodes': topology_nodes,
                'edges': topology_edges
            },
            'density': density,
            'racks': []  # Populated if CMDB data available
        }

    # Helper methods

    def _extract_leaf_from_fex_dn(self, dn: str) -> Optional[str]:
        """Extract leaf node ID from FEX DN."""
        match = re.search(r'node-(\d+)', dn)
        return match.group(1) if match else None

    def _extract_tenant_from_dn(self, dn: str) -> str:
        """Extract tenant name from DN."""
        match = re.search(r'tn-([^/]+)', dn)
        return match.group(1) if match else 'unknown'

    def _extract_epg_from_path_dn(self, dn: str) -> str:
        """Extract EPG DN from path attachment DN."""
        # DN format: uni/tn-X/ap-Y/epg-Z/rspathAtt-[...]
        match = re.search(r'(uni/tn-[^/]+/ap-[^/]+/epg-[^/]+)', dn)
        return match.group(1) if match else ''

    def _extract_epg_name_from_dn(self, dn: str) -> str:
        """Extract EPG name from DN."""
        match = re.search(r'epg-([^/]+)', dn)
        return match.group(1) if match else 'unknown'

    def _get_fex_port_count(self, model: str) -> int:
        """Get port count based on FEX model."""
        port_map = {
            'N2K-C2248TP': 48,
            'N2K-C2348UPQ': 48,
            'N2K-C2232PP': 32,
            'N2K-C2348TQ': 48,
            'N2K-C2224TP': 24,
            'N2K-C2232TM': 32,
            'N2K-C2248PQ': 48
        }

        for key, count in port_map.items():
            if key in model:
                return count

        return 48  # Default assumption

    def _calculate_consolidation_score(self, utilization: float, status: str, interface_count: int) -> int:
        """Calculate FEX consolidation score (0-100, higher = better candidate)."""
        score = 0

        # Low utilization = high score
        if utilization < 20:
            score += 40
        elif utilization < 40:
            score += 30
        elif utilization < 60:
            score += 15
        else:
            score += 5

        # Operational status
        if status == 'down':
            score += 30
        elif status == 'up':
            score += 10

        # Few interfaces configured
        if interface_count < 5:
            score += 20
        elif interface_count < 10:
            score += 10

        # Additional factors
        if utilization == 0:
            score += 10  # Completely unused

        return min(score, 100)

    def _get_consolidation_recommendation(self, score: int, utilization: float) -> str:
        """Get consolidation recommendation based on score."""
        if score >= 80:
            return 'Strong candidate for consolidation or decommission'
        elif score >= 60:
            return 'Consider consolidation with other low-utilization FEX'
        elif score >= 40:
            return 'Monitor utilization trends'
        else:
            return 'Retain - adequate utilization'

    def _calculate_epg_complexity_score(self, path_count: int, vlan_count: int, node_count: int) -> int:
        """Calculate EPG complexity score (0-100)."""
        score = 0

        # Path attachment complexity
        if path_count > 20:
            score += 40
        elif path_count > 10:
            score += 30
        elif path_count > 5:
            score += 20
        else:
            score += 10

        # VLAN diversity
        if vlan_count > 5:
            score += 30
        elif vlan_count > 2:
            score += 20
        else:
            score += 10

        # Node spread
        if node_count > 10:
            score += 30
        elif node_count > 5:
            score += 20
        else:
            score += 10

        return min(score, 100)

    def _get_complexity_level(self, score: int) -> str:
        """Get complexity level description."""
        if score >= 70:
            return 'high'
        elif score >= 40:
            return 'medium'
        else:
            return 'low'

    # ==================== Coupling & Migration Analysis ====================

    def analyze_coupling_issues(self) -> Dict[str, Any]:
        """
        Comprehensive coupling analysis for migration planning.

        Identifies:
        - EPGs spanning multiple devices (FEX, leafs)
        - Shared VLANs across EPGs (namespace collision risk)
        - Cross-tenant contract dependencies
        - Multi-device EPG deployments

        Returns detailed coupling metrics and migration risks.
        """
        self._load_data()

        coupling_issues = []
        device_coupling = defaultdict(lambda: {"epgs": [], "vlans": set()})
        vlan_sharing = defaultdict(list)  # vlan -> list of EPGs

        # Analyze each EPG for coupling
        for epg in self._epgs:
            epg_dn = epg.get("dn", "")
            epg_name = epg.get("name", "")

            # Get path attachments for this EPG
            epg_paths = [p for p in self._path_attachments
                        if epg_dn in p.get("dn", "")]

            if not epg_paths:
                continue

            # Extract devices and VLANs
            devices = set()
            vlans = set()

            for path in epg_paths:
                path_dn = path.get("tDn", "")
                encap = path.get("encap", "")

                # Extract device from path
                if "fex-" in path_dn:
                    match = re.search(r"node-(\d+).*fex-(\d+)", path_dn)
                    if match:
                        leaf_id, fex_id = match.groups()
                        devices.add(f"fex-{fex_id}")
                elif "node-" in path_dn:
                    match = re.search(r"node-(\d+)", path_dn)
                    if match:
                        devices.add(f"leaf-{match.group(1)}")

                # Extract VLAN
                if "vlan-" in encap:
                    vlan = encap.split("vlan-")[1]
                    vlans.add(vlan)
                    vlan_sharing[vlan].append(epg_name)

            # Track device usage
            for device in devices:
                device_coupling[device]["epgs"].append(epg_name)
                device_coupling[device]["vlans"].update(vlans)

            # Identify coupling issues
            if len(devices) > 1:
                # Multi-device EPG (coupling!)
                issue_type = "multi_fex" if all("fex" in d for d in devices) else "fex_leaf_mix"
                severity = "high" if len(devices) > 3 else "medium"

                coupling_issues.append({
                    "epg": epg_name,
                    "tenant": self._extract_tenant_from_dn(epg_dn),
                    "issue_type": issue_type,
                    "severity": severity,
                    "devices": list(devices),
                    "device_count": len(devices),
                    "vlans": list(vlans),
                    "description": f"EPG spans {len(devices)} devices",
                    "migration_impact": "Must migrate all devices simultaneously or implement L2 extension"
                })

        # Detect shared VLANs (coupling risk)
        for vlan, epg_list in vlan_sharing.items():
            if len(epg_list) > 1:
                coupling_issues.append({
                    "epg": ", ".join(epg_list[:3]) + (f" +{len(epg_list)-3} more" if len(epg_list) > 3 else ""),
                    "tenant": "multiple",
                    "issue_type": "shared_vlan",
                    "severity": "medium",
                    "vlan": vlan,
                    "epg_count": len(epg_list),
                    "description": f"VLAN {vlan} shared by {len(epg_list)} EPGs",
                    "migration_impact": "VLAN conflict risk during migration; requires VLAN remapping"
                })

        # Detect cross-tenant contracts (coupling)
        cross_tenant_contracts = []
        for contract in self._contracts:
            scope = contract.get("scope", "")
            if scope in ["tenant", "global"]:
                cross_tenant_contracts.append(contract.get("name", ""))

        if cross_tenant_contracts:
            coupling_issues.append({
                "issue_type": "cross_tenant_contracts",
                "severity": "high",
                "contract_count": len(cross_tenant_contracts),
                "contracts": cross_tenant_contracts[:5],
                "description": f"{len(cross_tenant_contracts)} cross-tenant contracts",
                "migration_impact": "Tenant migration order constrained by contract dependencies"
            })

        # Calculate coupling statistics
        multi_device_epgs = sum(1 for issue in coupling_issues if issue["issue_type"] in ["multi_fex", "fex_leaf_mix"])
        shared_vlan_count = sum(1 for issue in coupling_issues if issue["issue_type"] == "shared_vlan")

        # Device coupling density
        high_density_devices = [
            {"device": device, "epg_count": len(data["epgs"]), "vlan_count": len(data["vlans"])}
            for device, data in device_coupling.items()
            if len(data["epgs"]) > 10
        ]

        return {
            "issues": sorted(coupling_issues, key=lambda x:
                           {"high": 3, "medium": 2, "low": 1}.get(x.get("severity", "low"), 0), reverse=True),
            "statistics": {
                "total_issues": len(coupling_issues),
                "high_severity": sum(1 for i in coupling_issues if i.get("severity") == "high"),
                "medium_severity": sum(1 for i in coupling_issues if i.get("severity") == "medium"),
                "low_severity": sum(1 for i in coupling_issues if i.get("severity") == "low"),
                "multi_device_epgs": multi_device_epgs,
                "shared_vlans": shared_vlan_count,
                "cross_tenant_contracts": len(cross_tenant_contracts),
                "devices_analyzed": len(device_coupling)
            },
            "high_density_devices": sorted(high_density_devices,
                                          key=lambda x: x["epg_count"], reverse=True)[:20],
            "migration_risk_score": self._calculate_migration_risk(coupling_issues)
        }

    def analyze_migration_waves(self) -> Dict[str, Any]:
        """
        Analyze and group EPGs into migration waves based on coupling.

        Strategy:
        - Wave 1: Standalone EPGs (no coupling) - easiest to migrate
        - Wave 2: EPGs with low coupling (same device, no shared VLANs)
        - Wave 3: EPGs with medium coupling (multi-device or shared VLANs)
        - Wave 4: EPGs with high coupling (multi-device + shared VLANs + contracts)

        Returns migration wave recommendations with estimated effort.
        """
        self._load_data()

        # Get coupling data
        coupling_data = self.analyze_coupling_issues()
        coupled_epgs = set()
        for issue in coupling_data["issues"]:
            if "epg" in issue:
                epg_name = issue["epg"].split(",")[0].strip()  # Handle multi-EPG issues
                coupled_epgs.add(epg_name)

        # Categorize EPGs by coupling level
        waves = {
            "wave1_standalone": [],
            "wave2_low_coupling": [],
            "wave3_medium_coupling": [],
            "wave4_high_coupling": []
        }

        for epg in self._epgs:
            epg_name = epg.get("name", "")
            epg_dn = epg.get("dn", "")
            tenant = self._extract_tenant_from_dn(epg_dn)

            # Get EPG path attachments
            epg_paths = [p for p in self._path_attachments if epg_dn in p.get("dn", "")]
            device_count = len(set(p.get("tDn", "") for p in epg_paths))

            # Find coupling issues for this EPG
            epg_issues = [i for i in coupling_data["issues"]
                         if epg_name in i.get("epg", "")]
            high_severity_issues = sum(1 for i in epg_issues if i.get("severity") == "high")
            medium_severity_issues = sum(1 for i in epg_issues if i.get("severity") == "medium")

            epg_info = {
                "epg": epg_name,
                "tenant": tenant,
                "device_count": device_count,
                "path_count": len(epg_paths),
                "issues": len(epg_issues),
                "high_issues": high_severity_issues,
                "medium_issues": medium_severity_issues
            }

            # Assign to wave
            if not epg_issues:
                waves["wave1_standalone"].append(epg_info)
            elif high_severity_issues > 0:
                waves["wave4_high_coupling"].append(epg_info)
            elif medium_severity_issues > 1 or device_count > 2:
                waves["wave3_medium_coupling"].append(epg_info)
            else:
                waves["wave2_low_coupling"].append(epg_info)

        # Calculate effort estimates (person-hours per wave)
        effort_per_epg = {
            "wave1_standalone": 1,      # 1 hour each
            "wave2_low_coupling": 2,    # 2 hours each
            "wave3_medium_coupling": 4, # 4 hours each
            "wave4_high_coupling": 8    # 8 hours each
        }

        wave_summary = []
        for wave_name, epgs in waves.items():
            effort = len(epgs) * effort_per_epg[wave_name]
            wave_summary.append({
                "wave": wave_name.replace("_", " ").title(),
                "epg_count": len(epgs),
                "estimated_hours": effort,
                "estimated_days": round(effort / 8, 1),
                "description": self._get_wave_description(wave_name)
            })

        total_effort = sum(w["estimated_hours"] for w in wave_summary)

        return {
            "waves": waves,
            "summary": wave_summary,
            "total_epgs": sum(len(epgs) for epgs in waves.values()),
            "total_effort_hours": total_effort,
            "total_effort_days": round(total_effort / 8, 1),
            "recommended_order": ["wave1_standalone", "wave2_low_coupling",
                                 "wave3_medium_coupling", "wave4_high_coupling"]
        }

    def analyze_vlan_sharing_detailed(self) -> Dict[str, Any]:
        """
        Detailed VLAN sharing analysis for migration planning.

        Identifies:
        - VLANs shared across multiple EPGs
        - VLANs shared across multiple devices
        - VLAN namespace collision risks
        - VLAN remapping requirements
        """
        self._load_data()

        vlan_usage = defaultdict(lambda: {"epgs": set(), "devices": set(), "tenants": set()})

        for path in self._path_attachments:
            encap = path.get("encap", "")
            path_dn = path.get("dn", "")
            target_dn = path.get("tDn", "")

            if "vlan-" not in encap:
                continue

            vlan = encap.split("vlan-")[1]
            epg_dn = path_dn.split("/rspathAtt")[0] if "/rspathAtt" in path_dn else path_dn
            epg_name = self._extract_epg_from_path_dn(path_dn)
            tenant = self._extract_tenant_from_dn(epg_dn)

            # Extract device
            device = "unknown"
            if "fex-" in target_dn:
                match = re.search(r"fex-(\d+)", target_dn)
                if match:
                    device = f"fex-{match.group(1)}"
            elif "node-" in target_dn:
                match = re.search(r"node-(\d+)", target_dn)
                if match:
                    device = f"leaf-{match.group(1)}"

            vlan_usage[vlan]["epgs"].add(epg_name)
            vlan_usage[vlan]["devices"].add(device)
            vlan_usage[vlan]["tenants"].add(tenant)

        # Identify sharing issues
        sharing_issues = []
        for vlan, data in vlan_usage.items():
            epg_count = len(data["epgs"])
            device_count = len(data["devices"])
            tenant_count = len(data["tenants"])

            if epg_count > 1 or device_count > 1 or tenant_count > 1:
                severity = "high" if tenant_count > 1 else ("medium" if epg_count > 2 else "low")
                sharing_issues.append({
                    "vlan": vlan,
                    "epg_count": epg_count,
                    "device_count": device_count,
                    "tenant_count": tenant_count,
                    "epgs": list(data["epgs"])[:5],
                    "devices": list(data["devices"])[:5],
                    "tenants": list(data["tenants"]),
                    "severity": severity,
                    "migration_risk": "VLAN collision during migration - requires remapping"
                })

        return {
            "sharing_issues": sorted(sharing_issues,
                                    key=lambda x: (x["tenant_count"], x["epg_count"]), reverse=True),
            "statistics": {
                "total_vlans_used": len(vlan_usage),
                "shared_vlans": len(sharing_issues),
                "multi_tenant_vlans": sum(1 for i in sharing_issues if i["tenant_count"] > 1),
                "multi_device_vlans": sum(1 for i in sharing_issues if i["device_count"] > 1)
            }
        }

    def _calculate_migration_risk(self, coupling_issues: List[Dict[str, Any]]) -> int:
        """Calculate overall migration risk score (0-100)."""
        if not coupling_issues:
            return 0

        risk_score = 0

        # Weight by severity
        for issue in coupling_issues:
            severity = issue.get("severity", "low")
            if severity == "high":
                risk_score += 10
            elif severity == "medium":
                risk_score += 5
            else:
                risk_score += 2

        return min(risk_score, 100)

    def _get_wave_description(self, wave_name: str) -> str:
        """Get description for migration wave."""
        descriptions = {
            "wave1_standalone": "Standalone EPGs with no coupling - easiest to migrate",
            "wave2_low_coupling": "EPGs with minimal coupling - straightforward migration",
            "wave3_medium_coupling": "EPGs with moderate coupling - requires coordination",
            "wave4_high_coupling": "Highly coupled EPGs - complex migration requiring careful planning"
        }
        return descriptions.get(wave_name, "Unknown wave")
