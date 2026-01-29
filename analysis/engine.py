"""
Core Analysis Engine for ACI Fabric Analysis
Provides 12+ analysis types for ACI migration analysis.
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
        self._aci_object_index = set()

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
        self._l1_interfaces = []
        self._physical_domains = []
        self._epg_contract_consumers = []
        self._epg_contract_providers = []
        self._epg_domain_attachments = []
        self._epg_bd_relations = []
        self._bd_vrf_relations = []

        # Lookup dictionaries for performance
        self._fex_by_id = {}
        self._leaf_by_id = {}
        self._epg_by_dn = {}
        self._bd_by_dn = {}
        self._epg_bd_map = {}
        self._bd_vrf_map = {}
        self._aci_class_counts = {}

    def _load_data(self):
        """Load and parse all datasets (ACI and CMDB)."""
        if self._aci_objects is not None:
            return

        self._aci_objects = []
        self._cmdb_records = []
        self._aci_object_index = set()
        self._aci_class_counts = defaultdict(int)

        from . import parsers

        for dataset in self.datasets:
            try:
                if not isinstance(dataset, dict):
                    logger.warning(f"Skipping invalid dataset entry: {dataset}")
                    continue

                # Allow in-memory datasets used by tests or tooling
                objects = dataset.get('objects')
                if objects is not None:
                    if isinstance(objects, dict) and 'imdata' in objects:
                        self._add_aci_objects(objects.get('imdata', []))
                        logger.info("Loaded ACI objects from in-memory imdata dataset")
                        continue
                    if isinstance(objects, list):
                        self._add_aci_objects(objects)
                        logger.info("Loaded ACI objects from in-memory dataset list")
                        continue

                records = dataset.get('records')
                if isinstance(records, list):
                    self._cmdb_records.extend(records)
                    logger.info("Loaded CMDB records from in-memory dataset list")
                    continue

                path_value = dataset.get('path')
                if not path_value:
                    logger.warning(f"Dataset missing path: {dataset.get('filename')}")
                    continue

                path = Path(path_value)
                if not path.exists():
                    logger.warning(f"Dataset file not found: {path}")
                    continue

                # Read file with encoding fallback
                content = self._read_file_safe(path)

                dataset_type = dataset.get('type')
                if dataset_type in {'aci', 'aci_json'}:
                    dataset_format = dataset.get('format')
                    if not dataset_format and path.suffix:
                        dataset_format = path.suffix.lstrip('.').lower()
                    if not dataset_format:
                        dataset_format = 'json'
                    parsed = parsers.parse_aci(content, dataset_format)
                    self._add_aci_objects(parsed['objects'])
                    logger.info(f"Loaded {len(parsed['objects'])} ACI objects from {dataset['filename']}")

                elif dataset_type == 'cmdb':
                    normalized_path = dataset.get('normalized_path')
                    if normalized_path and Path(normalized_path).exists():
                        try:
                            normalized_content = Path(normalized_path).read_text(encoding='utf-8')
                            parsed = json.loads(normalized_content)
                            if isinstance(parsed, list):
                                self._cmdb_records.extend(parsed)
                                logger.info(f"Loaded {len(parsed)} CMDB records from normalized file {normalized_path}")
                                continue
                        except Exception as e:
                            logger.warning(f"Failed to load normalized CMDB data: {str(e)}")
                    parsed = parsers.parse_cmdb_csv(content)
                    self._cmdb_records.extend(parsed)
                    logger.info(f"Loaded {len(parsed)} CMDB records from {dataset['filename']}")
                elif dataset_type == 'mcp_import' and isinstance(dataset.get('objects'), list):
                    self._add_aci_objects(dataset['objects'])
                    logger.info(f"Loaded {len(dataset['objects'])} ACI objects from MCP import dataset")

            except Exception as e:
                logger.error(f"Error loading dataset {dataset.get('filename')}: {str(e)}")

        # Categorize objects for efficient lookups
        self._categorize_objects()

    def _add_aci_objects(self, objects: List[Dict[str, Any]]):
        """Add ACI objects with de-duplication."""
        for obj in objects:
            obj_type = obj.get('type')
            attrs = obj.get('attributes', {})
            dn = attrs.get('dn') or obj.get('dn')
            if obj_type in {'eqptExtCh', 'eqptCh'}:
                if obj_type == 'eqptExtCh' or (dn and ('extch' in dn or 'fex-' in dn)):
                    obj_type = 'eqptFex'
                    obj['type'] = obj_type
            if dn:
                key = (obj_type, dn)
            else:
                key = (obj_type, json.dumps(attrs, sort_keys=True))

            if key in self._aci_object_index:
                continue
            self._aci_object_index.add(key)
            self._aci_objects.append(obj)

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
            if obj_type:
                self._aci_class_counts[obj_type] += 1

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
                if not attrs.get('id'):
                    iface_id = self._extract_interface_id_from_dn(attrs.get('dn', ''))
                    if iface_id:
                        attrs['id'] = iface_id
                self._interfaces.append(attrs)

            elif obj_type == 'l1PhysIf':
                if not attrs.get('id'):
                    iface_id = self._extract_interface_id_from_dn(attrs.get('dn', ''))
                    if iface_id:
                        attrs['id'] = iface_id
                self._l1_interfaces.append(attrs)

            elif obj_type == 'physDomP':
                self._physical_domains.append(attrs)

            elif obj_type == 'fvRsCons':
                self._epg_contract_consumers.append(attrs)

            elif obj_type == 'fvRsProv':
                self._epg_contract_providers.append(attrs)

            elif obj_type == 'fvRsDomAtt':
                self._epg_domain_attachments.append(attrs)

            elif obj_type == 'fvRsBd':
                self._epg_bd_relations.append(attrs)
                epg_dn = self._extract_epg_dn_from_relation_dn(attrs.get('dn', ''))
                bd_name = attrs.get('tnFvBDName') or self._extract_bd_name_from_dn(attrs.get('tDn', ''))
                if epg_dn and bd_name:
                    self._epg_bd_map[epg_dn] = bd_name

            elif obj_type == 'fvRsCtx':
                self._bd_vrf_relations.append(attrs)
                bd_dn = self._extract_bd_dn_from_relation_dn(attrs.get('dn', ''))
                vrf_name = attrs.get('tnFvCtxName') or self._extract_vrf_name_from_dn(attrs.get('tDn', ''))
                if bd_dn and vrf_name:
                    self._bd_vrf_map[bd_dn] = vrf_name

        self._ensure_leafs_for_fex()

        logger.info(
            f"Categorized objects: {len(self._fexes)} FEX, {len(self._leafs)} leafs, "
            f"{len(self._epgs)} EPGs, {len(self._bds)} BDs, {len(self._contracts)} contracts"
        )

    def _ensure_leafs_for_fex(self):
        """Ensure leaf entries exist for any detected FEX devices."""
        for fex in self._fexes:
            fex_dn = fex.get('dn', '')
            leaf_id = self._extract_leaf_from_fex_dn(fex_dn)
            if not leaf_id or leaf_id in self._leaf_by_id:
                continue
            pod_id = None
            match = re.search(r'pod-(\d+)', fex_dn)
            if match:
                pod_id = match.group(1)
            leaf_dn = f"topology/pod-{pod_id}/node-{leaf_id}" if pod_id else f"topology/node-{leaf_id}"
            placeholder = {
                'id': leaf_id,
                'name': f"leaf-{leaf_id}",
                'role': 'leaf',
                'dn': leaf_dn
            }
            self._leafs.append(placeholder)
            self._leaf_by_id[leaf_id] = placeholder

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

    def get_port_utilization_quality(self) -> Dict[str, Any]:
        """Return data quality signals for port utilization analysis."""
        self._load_data()

        interface_counts = {
            'ethpmPhysIf': self._aci_class_counts.get('ethpmPhysIf', 0),
            'l1PhysIf': self._aci_class_counts.get('l1PhysIf', 0),
            'fvRsPathAtt': self._aci_class_counts.get('fvRsPathAtt', 0)
        }

        interface_source = 'ethpmPhysIf' if self._interfaces else 'l1PhysIf' if self._l1_interfaces else ''
        interface_candidates = self._interfaces if self._interfaces else self._l1_interfaces
        ports_total = len(interface_candidates)
        ports_with_state = sum(1 for iface in interface_candidates if iface.get('operSt'))

        fex_id_set = {str(f.get('id')) for f in self._fexes if f.get('id') is not None}
        matched = 0
        if interface_candidates:
            for iface in interface_candidates:
                iface_id = iface.get('id', '')
                match = re.match(r'^eth(\d+)/', iface_id)
                if match and match.group(1) in fex_id_set:
                    matched += 1
        ports_unmatched = max(ports_total - matched, 0)

        reasons = []
        if not self._fexes:
            reasons.append('No FEX inventory loaded (eqptFex missing).')
        if interface_counts['ethpmPhysIf'] == 0 and interface_counts['l1PhysIf'] == 0:
            reasons.append('No interface operational data loaded (ethpmPhysIf/l1PhysIf missing).')
        if ports_total > 0 and matched == 0 and interface_candidates:
            reasons.append('Interface data present, but no interfaces matched to FEX IDs.')
        if interface_counts['fvRsPathAtt'] == 0:
            reasons.append('No path attachment data loaded (fvRsPathAtt missing).')

        utilization_data_present = bool(self._fexes) and ports_total > 0 and matched > 0
        path_attachment_available = bool(self._fexes) and interface_counts['fvRsPathAtt'] > 0

        return {
            'utilization_data_present': utilization_data_present,
            'interface_objects_loaded': interface_counts,
            'ports_total': ports_total,
            'ports_with_state': ports_with_state,
            'ports_matched_to_fex': matched,
            'ports_unmatched': ports_unmatched,
            'interface_source': interface_source,
            'path_attachment_available': path_attachment_available,
            'reasons': reasons
        }

    def analyze_port_utilization(self) -> List[Dict[str, Any]]:
        """
        Analyze port utilization across all FEX devices.
        Returns list of FEX with utilization metrics and consolidation scores.
        """
        self._load_data()

        if not self._fexes:
            return []

        results = []
        quality = self.get_port_utilization_quality()
        interface_candidates = self._interfaces if self._interfaces else self._l1_interfaces
        interface_source = quality.get('interface_source') or ''
        path_attachment_available = quality.get('path_attachment_available')

        for fex in self._fexes:
            fex_id = fex.get('id', '')
            fex_norm = self._normalize_fex_id(fex_id)
            fex_serial = fex.get('ser', '')
            fex_model = fex.get('model', '')
            fex_dn = fex.get('dn', '')

            # Extract leaf ID from DN (topology/pod-X/node-Y/sys/extch-Z)
            leaf_id = self._extract_leaf_from_fex_dn(fex_dn)
            fex_identifier = self._build_fex_identifier(str(fex_id), leaf_id, fex_serial)

            # Determine total ports based on model
            total_ports = self._get_fex_port_count(fex_model)

            # Count interfaces for this FEX
            fex_interfaces = [
                iface for iface in interface_candidates
                if fex_norm and iface.get('id', '').startswith(f'eth{fex_norm}/')
            ] if interface_candidates else []

            utilization_known = True
            utilization_reason = None

            # Count connected (up) ports
            connected_ports = None
            if not quality.get('utilization_data_present'):
                if path_attachment_available:
                    connected_ports = self._count_fex_ports_from_path_attachments(str(fex_id))
                    if connected_ports is None:
                        utilization_known = False
                        utilization_reason = 'Insufficient interface data to compute utilization'
                    else:
                        utilization_known = True
                        utilization_reason = 'Using fvRsPathAtt bindings (interface data missing)'
                else:
                    utilization_known = False
                    utilization_reason = 'Insufficient interface data to compute utilization'
            elif total_ports <= 0:
                if path_attachment_available:
                    connected_ports = self._count_fex_ports_from_path_attachments(str(fex_id))
                    if connected_ports is None:
                        utilization_known = False
                        utilization_reason = 'Unknown total port count for FEX model'
                    else:
                        utilization_known = True
                        utilization_reason = 'Using fvRsPathAtt bindings (unknown total ports)'
                else:
                    utilization_known = False
                    utilization_reason = 'Unknown total port count for FEX model'
            elif len(fex_interfaces) == 0:
                if path_attachment_available:
                    connected_ports = self._count_fex_ports_from_path_attachments(str(fex_id))
                    if connected_ports is None:
                        utilization_known = False
                        utilization_reason = 'No interfaces matched to this FEX'
                    else:
                        utilization_known = True
                        utilization_reason = 'Using fvRsPathAtt bindings (no interfaces matched)'
                else:
                    utilization_known = False
                    utilization_reason = 'No interfaces matched to this FEX'
            else:
                connected_ports = sum(
                    1 for iface in fex_interfaces
                    if iface.get('operSt') == 'up'
                )
                utilization_reason = f'Using {interface_source} operational state'

            if total_ports <= 0:
                utilization_known = False
                utilization_reason = 'Unknown total port count for FEX model'
                connected_ports = None
            elif connected_ports is not None and connected_ports > total_ports:
                connected_ports = total_ports

            utilization_pct = None
            if utilization_known and connected_ports is not None and total_ports > 0:
                utilization_pct = round((connected_ports / total_ports * 100), 2)

            consolidation_score = self._calculate_consolidation_score(
                utilization_pct, fex.get('operSt'), len(fex_interfaces)
            )
            recommendation = self._get_consolidation_recommendation(consolidation_score, utilization_pct)

            results.append({
                'fex_id': fex_id,
                'fex_identifier': fex_identifier,
                'serial': fex_serial,
                'model': fex_model,
                'leaf_id': leaf_id,
                'total_ports': total_ports,
                'connected_ports': connected_ports,
                'utilization_pct': utilization_pct,
                'utilization_known': utilization_known,
                'utilization_reason': utilization_reason,
                'utilization_source': interface_source if utilization_known and interface_candidates else 'fvRsPathAtt' if connected_ports is not None else 'unknown',
                'status': fex.get('operSt', 'unknown'),
                'consolidation_score': consolidation_score,
                'recommendation': recommendation,
                'flagged': consolidation_score is not None and consolidation_score >= 60
            })

        # Sort by consolidation score (highest first)
        results.sort(key=lambda x: x['consolidation_score'] or 0, reverse=True)

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
                    identifier = self._build_fex_identifier(str(fex.get('id')), leaf_id, fex.get('ser'))
                    attached_fex.append({
                        'fex_id': fex.get('id'),
                        'identifier': identifier,
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
            vrf_name = self._get_vrf_name_for_bd(bd)

            # Extract tenant from DN
            tenant = self._extract_tenant_from_dn(bd_dn)

            # Find EPGs in this BD
            epgs_in_bd = []
            for epg in self._epgs:
                if self._get_bd_name_for_epg(epg) == bd_name and tenant in epg.get('dn', ''):
                    epgs_in_bd.append(epg)

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

    def analyze_vlan_coupling_index(self) -> Dict[str, Any]:
        """
        Build a VLAN coupling index focused on migration coupling and blast radius.
        """
        self._load_data()

        # Tunable scoring constants (favor coupling + blast radius)
        bd_score = 10
        vrf_score = 15
        tenant_score = 20
        service_graph_score = 15
        binding_score_10 = 10
        binding_score_50 = 20
        pdom_score = 15

        def score_epg(count: int) -> int:
            if count <= 1:
                return 0
            if count == 2:
                return 5
            if 3 <= count <= 5:
                return 10
            return 20

        def extract_epg_dn_from_relation(dn: str) -> str:
            match = re.search(r'(uni/tn-[^/]+/ap-[^/]+/epg-[^/]+)', dn or '')
            return match.group(1) if match else ''

        def extract_contract_name(attrs: Dict[str, Any]) -> str:
            name = attrs.get('tnVzBrCPName') or ''
            if name:
                return name
            tdn = attrs.get('tDn', '') or attrs.get('dn', '')
            if 'brc-' in tdn:
                return tdn.split('brc-')[-1].split('/')[0].strip()
            return ''

        bd_by_name = {bd.get('name'): bd for bd in self._bds if bd.get('name')}
        fex_by_id = {str(f.get('id')): f for f in self._fexes if f.get('id') is not None}
        leaf_by_id = {str(l.get('id')): l for l in self._leafs if l.get('id') is not None}
        cmdb_by_serial = {r.get('serial_number'): r for r in self._cmdb_records if r.get('serial_number')}

        epg_contracts = defaultdict(set)
        for rel in (self._epg_contract_consumers + self._epg_contract_providers):
            epg_dn = extract_epg_dn_from_relation(rel.get('dn', ''))
            contract = extract_contract_name(rel)
            if epg_dn and contract:
                epg_contracts[epg_dn].add(contract)

        epg_domains = defaultdict(set)
        for rel in self._epg_domain_attachments:
            epg_dn = extract_epg_dn_from_relation(rel.get('dn', ''))
            domain_dn = rel.get('tDn', '')
            if epg_dn and domain_dn:
                epg_domains[epg_dn].add(domain_dn)

        vlan_index = defaultdict(lambda: {
            'epgs': set(),
            'bds': set(),
            'vrfs': set(),
            'tenants': set(),
            'contracts': set(),
            'graphs': set(),
            'leafs': set(),
            'fexes': set(),
            'racks': set(),
            'pdoms': set(),
            'total_bindings': 0
        })

        # Walk path attachments to populate coupling map
        for path in self._path_attachments:
            encap = path.get('encap', '')
            vlan_match = re.search(r'vlan-(\d+)', encap)
            if not vlan_match:
                continue
            vlan_id = int(vlan_match.group(1))
            epg_dn = self._extract_epg_from_path_dn(path.get('dn', ''))
            tdn = path.get('tDn', '')

            vlan_entry = vlan_index[vlan_id]
            vlan_entry['total_bindings'] += 1
            if epg_dn:
                vlan_entry['epgs'].add(epg_dn)

                tenant = self._extract_tenant_from_dn(epg_dn)
                if tenant:
                    vlan_entry['tenants'].add(tenant)

                bd_name = self._epg_bd_map.get(epg_dn)
                if bd_name:
                    vlan_entry['bds'].add(bd_name)
                    bd_obj = bd_by_name.get(bd_name)
                    if bd_obj:
                        vrf_name = self._get_vrf_name_for_bd(bd_obj)
                        if vrf_name:
                            vlan_entry['vrfs'].add(vrf_name)

                if epg_dn in epg_contracts:
                    vlan_entry['contracts'].update(epg_contracts[epg_dn])

                if epg_dn in epg_domains:
                    vlan_entry['pdoms'].update(epg_domains[epg_dn])

            # Attachment spread
            leaf_ids = self._extract_nodes_from_tdn(tdn)
            for leaf_id in leaf_ids:
                vlan_entry['leafs'].add(str(leaf_id))
                leaf_obj = leaf_by_id.get(str(leaf_id))
                if leaf_obj:
                    serial = leaf_obj.get('serial') or leaf_obj.get('ser')
                    if serial and serial in cmdb_by_serial:
                        rack = cmdb_by_serial[serial].get('rack')
                        if rack:
                            vlan_entry['racks'].add(rack)

            fex_id = None
            if 'extpaths-' in tdn:
                match = re.search(r'extpaths-(\d+)', tdn)
                if match:
                    fex_id = match.group(1)
            elif 'fex-' in tdn:
                match = re.search(r'fex-(\d+)', tdn)
                if match:
                    fex_id = match.group(1)

            if fex_id:
                fex_obj = fex_by_id.get(str(fex_id))
                leaf_hint = self._extract_leaf_from_fex_dn(fex_obj.get('dn', '')) if fex_obj else None
                serial = fex_obj.get('ser') if fex_obj else None
                fex_identifier = ':'.join([p for p in [
                    f'leaf-{leaf_hint}' if leaf_hint else None,
                    f'fex-{fex_id}' if fex_id else None,
                    f'serial-{serial}' if serial else None
                ] if p])
                if fex_identifier:
                    vlan_entry['fexes'].add(fex_identifier)
                if serial and serial in cmdb_by_serial:
                    rack = cmdb_by_serial[serial].get('rack')
                    if rack:
                        vlan_entry['racks'].add(rack)

        contract_data_present = bool(self._epg_contract_consumers or self._epg_contract_providers)
        pdom_data_present = bool(self._epg_domain_attachments)

        rows = []
        for vlan_id, data in sorted(vlan_index.items()):
            epg_count = len(data['epgs'])
            leaf_count = len(data['leafs'])
            fex_count = len(data['fexes'])
            rack_count = len(data['racks'])
            tenant_count = len(data['tenants'])
            bd_count = len(data['bds'])
            vrf_count = len(data['vrfs'])
            contract_count = len(data['contracts']) if contract_data_present else None
            pdom_count = len(data['pdoms']) if pdom_data_present else None

            epg_score = score_epg(epg_count)
            bd_penalty = bd_score if bd_count > 1 else 0
            vrf_penalty = vrf_score if vrf_count > 1 else 0
            tenant_penalty = tenant_score if tenant_count > 1 else 0
            service_graph_penalty = service_graph_score if data.get('graphs') else 0
            bindings_penalty = binding_score_50 if data['total_bindings'] > 50 else binding_score_10 if data['total_bindings'] > 10 else 0
            pdom_penalty = pdom_score if (pdom_count or 0) > 1 else 0

            coupling_score = min(
                epg_score + bd_penalty + vrf_penalty + tenant_penalty +
                service_graph_penalty + bindings_penalty + pdom_penalty, 100
            )
            if coupling_score >= 35:
                coupling_level = 'high'
            elif coupling_score >= 15:
                coupling_level = 'medium'
            else:
                coupling_level = 'low'

            why = []
            if epg_count > 1:
                why.append(f'VLAN shared by {epg_count} EPGs')
            if tenant_count > 1:
                why.append(f'Used across {tenant_count} tenants')
            if bd_count > 1:
                why.append(f'Spans {bd_count} bridge domains')
            if vrf_count > 1:
                why.append(f'Spans {vrf_count} VRFs')
            if data['total_bindings'] > 10:
                why.append(f'{data["total_bindings"]} bindings')
            if leaf_count > 1 or fex_count > 1:
                why.append(f'Blast radius spans {leaf_count} leafs and {fex_count} FEX identifiers')
            if rack_count > 1:
                why.append(f'Racks impacted: {rack_count}')
            if not why:
                why.append('Limited coupling detected')

            rows.append({
                'vlan_id': vlan_id,
                'epg_count': epg_count,
                'epgs': sorted(list(data['epgs'])),
                'bd_count': bd_count,
                'bds': sorted(list(data['bds'])),
                'vrf_count': vrf_count,
                'vrfs': sorted(list(data['vrfs'])),
                'tenant_count': tenant_count,
                'tenants': sorted(list(data['tenants'])),
                'contract_count': contract_count,
                'contracts': sorted(list(data['contracts'])),
                'service_graph_present': None,
                'graphs': [],
                'attachment_spread': {
                    'leafs': sorted(list(data['leafs'])),
                    'fex_identifiers': sorted(list(data['fexes'])),
                    'racks': sorted(list(data['racks'])),
                    'total_bindings': data['total_bindings']
                },
                'pdom_count': pdom_count,
                'pdoms': sorted(list(data['pdoms'])),
                'blast_radius': leaf_count + fex_count + rack_count,
                'coupling_score': coupling_score,
                'coupling_level': coupling_level,
                'why': '; '.join(why),
                'flagged': coupling_level in {'high'}
            })

        return {
            'vlans': rows,
            'statistics': {
                'total_vlans': len(rows),
                'high_coupling': sum(1 for r in rows if r['coupling_level'] == 'high'),
                'avg_coupling_score': round(sum(r['coupling_score'] for r in rows) / len(rows), 2) if rows else None
            }
        }

    def analyze_vlan_coupling_detail(self) -> Dict[int, Dict[str, Any]]:
        """Build detailed VLAN -> EPG -> binding mapping for visualization."""
        self._load_data()

        bd_by_name = {bd.get('name'): bd for bd in self._bds if bd.get('name')}
        fex_by_id = {str(f.get('id')): f for f in self._fexes if f.get('id') is not None}
        leaf_by_id = {str(l.get('id')): l for l in self._leafs if l.get('id') is not None}
        cmdb_by_serial = {r.get('serial_number'): r for r in self._cmdb_records if r.get('serial_number')}

        vlan_map = defaultdict(lambda: {'epgs': {}})

        for path in self._path_attachments:
            encap = path.get('encap', '')
            vlan_match = re.search(r'vlan-(\d+)', encap)
            if not vlan_match:
                continue
            vlan_id = int(vlan_match.group(1))

            epg_dn = self._extract_epg_from_path_dn(path.get('dn', ''))
            if not epg_dn:
                continue

            tenant = self._extract_tenant_from_dn(epg_dn) or ''
            app = self._extract_app_profile_from_dn(epg_dn) or ''
            epg_name = epg_dn.split('/epg-')[-1] if '/epg-' in epg_dn else epg_dn
            bd_name = self._epg_bd_map.get(epg_dn)
            vrf_name = ''
            if bd_name and bd_name in bd_by_name:
                vrf_name = self._get_vrf_name_for_bd(bd_by_name[bd_name]) or ''

            tdn = path.get('tDn', '') or ''
            nodes = self._extract_nodes_from_tdn(tdn) or []

            interface = self._extract_interface_id_from_dn(tdn) or ''
            if not interface:
                match = re.search(r'pathep-\[(.*?)\]', tdn)
                interface = match.group(1) if match else ''

            fex_id = None
            if 'extpaths-' in tdn:
                match = re.search(r'extpaths-(\d+)', tdn)
                if match:
                    fex_id = match.group(1)
            elif 'fex-' in tdn:
                match = re.search(r'fex-(\d+)', tdn)
                if match:
                    fex_id = match.group(1)

            binding_type = 'fex' if fex_id else 'leaf'
            fex_obj = fex_by_id.get(str(fex_id)) if fex_id else None
            fex_serial = fex_obj.get('ser') if fex_obj else None
            leaf_hint = None
            if fex_obj:
                leaf_hint = self._extract_leaf_from_fex_dn(fex_obj.get('dn', ''))
            if not leaf_hint and nodes:
                leaf_hint = nodes[0]

            leaf_ids = nodes or ([leaf_hint] if leaf_hint else [None])

            for leaf_id in leaf_ids:
                leaf_obj = leaf_by_id.get(str(leaf_id)) if leaf_id is not None else None
                leaf_name = leaf_obj.get('name') if leaf_obj else None
                leaf_role = leaf_obj.get('role') if leaf_obj else None
                leaf_serial = None
                if leaf_obj:
                    leaf_serial = leaf_obj.get('serial') or leaf_obj.get('ser')

                cmdb_record = None
                if fex_serial and fex_serial in cmdb_by_serial:
                    cmdb_record = cmdb_by_serial.get(fex_serial)
                elif leaf_serial and leaf_serial in cmdb_by_serial:
                    cmdb_record = cmdb_by_serial.get(leaf_serial)

                binding_key = '|'.join([p for p in [
                    binding_type,
                    f'leaf-{leaf_id}' if leaf_id is not None else None,
                    f'fex-{fex_id}' if fex_id else None,
                    f'serial-{fex_serial}' if fex_serial else None,
                    f'path-{tdn}' if tdn else None,
                    f'interface-{interface}' if interface else None
                ] if p])

                epg_key = '|'.join([tenant, app, epg_name])
                epg_entry = vlan_map[vlan_id]['epgs'].setdefault(epg_key, {
                    'tenant': tenant,
                    'app': app,
                    'epg': epg_name,
                    'bd': bd_name or '',
                    'vrf': vrf_name or '',
                    'bindings': [],
                    '_binding_keys': set()
                })

                if binding_key in epg_entry['_binding_keys']:
                    continue
                epg_entry['_binding_keys'].add(binding_key)

                epg_entry['bindings'].append({
                    'binding_type': binding_type,
                    'leafId': leaf_id,
                    'leafName': leaf_name,
                    'leafRole': leaf_role,
                    'fexId': fex_id,
                    'fexSerial': fex_serial,
                    'rack': cmdb_record.get('rack') if cmdb_record else None,
                    'site': cmdb_record.get('site') if cmdb_record else None,
                    'building': cmdb_record.get('building') if cmdb_record else None,
                    'hall': cmdb_record.get('hall') if cmdb_record else None,
                    'interface': interface or None,
                    'path': tdn or None,
                    'encap': encap or None
                })

        output = {}
        for vlan_id, data in vlan_map.items():
            epgs = []
            for epg_entry in data['epgs'].values():
                epg_entry.pop('_binding_keys', None)
                epgs.append(epg_entry)
            output[vlan_id] = {'epgs': epgs}

        return output

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
        cmdb_by_serial = {r.get('serial_number'): r for r in self._cmdb_records if r.get('serial_number')}
        vlan_coupling = self.analyze_vlan_coupling_index()
        vlan_coupling_map = {v['vlan_id']: v for v in vlan_coupling.get('vlans', [])}
        epg_contracts = defaultdict(set)
        for rel in (self._epg_contract_consumers + self._epg_contract_providers):
            epg_dn = self._extract_epg_dn_from_relation_dn(rel.get('dn', ''))
            contract = rel.get('tnVzBrCPName') or ''
            if not contract:
                tdn = rel.get('tDn', '')
                if 'brc-' in tdn:
                    contract = tdn.split('brc-')[-1].split('/')[0].strip()
            if epg_dn and contract:
                epg_contracts[epg_dn].add(contract)

        for epg in self._epgs:
            epg_name = epg.get('name', '')
            epg_dn = epg.get('dn', '')
            tenant = self._extract_tenant_from_dn(epg_dn)
            app_profile = self._extract_app_profile_from_dn(epg_dn)
            bd_name = self._epg_bd_map.get(epg_dn)
            vrf_name = ''
            if bd_name:
                bd_obj = next((bd for bd in self._bds if bd.get('name') == bd_name), None)
                if bd_obj:
                    vrf_name = self._get_vrf_name_for_bd(bd_obj)

            # Count path attachments for this EPG
            paths = [p for p in self._path_attachments if epg_dn in p.get('dn', '')]

            # Extract unique VLANs
            vlans = set()
            leafs = set()
            fex_identifiers = set()
            racks = set()
            for path in paths:
                encap = path.get('encap', '')
                vlan_match = re.search(r'vlan-(\d+)', encap)
                if vlan_match:
                    vlans.add(int(vlan_match.group(1)))

                tdn = path.get('tDn', '')
                for node_id in self._extract_nodes_from_tdn(tdn):
                    leafs.add(node_id)
                    leaf_obj = self._leaf_by_id.get(str(node_id))
                    leaf_serial = leaf_obj.get('serial') if leaf_obj else None
                    if leaf_serial and leaf_serial in cmdb_by_serial:
                        rack = cmdb_by_serial[leaf_serial].get('rack')
                        if rack:
                            racks.add(rack)

                fex_id = None
                if 'extpaths-' in tdn:
                    match = re.search(r'extpaths-(\d+)', tdn)
                    if match:
                        fex_id = match.group(1)
                elif 'fex-' in tdn:
                    match = re.search(r'fex-(\d+)', tdn)
                    if match:
                        fex_id = match.group(1)
                if fex_id:
                    fex_obj = self._fex_by_id.get(str(fex_id), {})
                    fex_serial = fex_obj.get('ser')
                    leaf_hint = self._extract_leaf_from_fex_dn(fex_obj.get('dn', '')) if fex_obj else None
                    fex_identifiers.add(self._build_fex_identifier(str(fex_id), leaf_hint, fex_serial))
                    if fex_serial and fex_serial in cmdb_by_serial:
                        rack = cmdb_by_serial[fex_serial].get('rack')
                        if rack:
                            racks.add(rack)

            # Extract unique leafs/nodes
            nodes = set()
            for path in paths:
                for node_id in self._extract_nodes_from_tdn(path.get('tDn', '')):
                    nodes.add(node_id)

            # Calculate complexity score (0-100)
            complexity_score = self._calculate_epg_complexity_score(
                path_count=len(paths),
                vlan_count=len(vlans),
                node_count=len(nodes)
            )

            reasons = []
            if len(paths) > 0:
                reasons.append(f'{len(paths)} path attachments')
            if len(vlans) > 1:
                reasons.append(f'{len(vlans)} VLANs')
            if len(nodes) > 1:
                reasons.append(f'{len(nodes)} nodes')
            if not reasons:
                reasons.append('No path attachments detected')

            contract_list = sorted(list(epg_contracts.get(epg_dn, set())))
            vlan_coupling_refs = []
            cross_tenant = False
            for vlan in vlans:
                info = vlan_coupling_map.get(vlan)
                if not info:
                    continue
                if info.get('coupling_level') in {'medium', 'high', 'critical'}:
                    vlan_coupling_refs.append({
                        'vlan_id': vlan,
                        'coupling_level': info.get('coupling_level'),
                        'coupling_score': info.get('coupling_score'),
                        'reason': info.get('why')
                    })
                if info.get('tenant_count', 1) > 1:
                    cross_tenant = True

            results.append({
                'epg_name': epg_name,
                'epg_dn': epg_dn,
                'app_profile': app_profile,
                'tenant': tenant,
                'bd': bd_name or epg.get('bd', ''),
                'vrf': vrf_name or None,
                'path_count': len(paths),
                'vlan_count': len(vlans),
                'vlans': sorted(list(vlans)),
                'node_count': len(nodes),
                'leaf_binding_count': len(leafs),
                'fex_binding_count': len(fex_identifiers),
                'rack_spread': len(racks) if racks else None,
                'contracts_count': len(contract_list) if contract_list else None,
                'contracts': contract_list,
                'service_graph_present': None,
                'cross_tenant_coupling_present': cross_tenant,
                'complexity_score': complexity_score,
                'complexity_level': self._get_complexity_level(complexity_score),
                'why': '; '.join(reasons),
                'flagged': self._get_complexity_level(complexity_score) == 'high',
                'vlan_coupling_refs': vlan_coupling_refs
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
                encap = path.get('encap', '')
                vlan_match = re.search(r'vlan-(\d+)', encap)

                if vlan_match:
                    vlan_id = vlan_match.group(1)
                    for node_id in self._extract_nodes_from_tdn(tdn):
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

        # Check for high VLAN coupling (blast radius)
        vlan_coupling = self.analyze_vlan_coupling_index()
        high_coupling = [v for v in vlan_coupling.get('vlans', []) if v.get('coupling_level') in {'high', 'critical'}]
        if high_coupling:
            flags.append({
                'severity': 'high',
                'category': 'vlan_coupling',
                'count': len(high_coupling),
                'message': f'{len(high_coupling)} VLANs with high coupling blast radius',
                'recommendation': 'Prioritize VLAN decoupling before migration'
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

    def analyze_migration_units(self) -> Dict[str, Any]:
        """
        Build actionable migration units grouped by leaf/FEX with coupling-driven difficulty.
        """
        self._load_data()

        fabric_name = self.fabric_data.get('name') or self.fabric_data.get('fabric_name') or 'unknown'
        cmdb_by_serial = {r.get('serial_number'): r for r in self._cmdb_records if r.get('serial_number')}
        fex_by_id = {str(f.get('id')): f for f in self._fexes if f.get('id') is not None}
        leaf_by_id = {str(l.get('id')): l for l in self._leafs if l.get('id') is not None}

        vlan_coupling = self.analyze_vlan_coupling_index()
        vlan_coupling_map = {v['vlan_id']: v for v in vlan_coupling.get('vlans', [])}

        port_util = self.analyze_port_utilization()
        util_by_fex = {p.get('fex_identifier'): p for p in port_util if p.get('fex_identifier')}

        vpc_symmetry = self.analyze_vpc_symmetry()
        asymmetric_nodes = set()
        for item in vpc_symmetry.get('asymmetric_bindings', []):
            asymmetric_nodes.add(str(item.get('node1')))
            asymmetric_nodes.add(str(item.get('node2')))

        units = {}

        for path in self._path_attachments:
            encap = path.get('encap', '')
            vlan_match = re.search(r'vlan-(\d+)', encap)
            if not vlan_match:
                continue
            vlan_id = int(vlan_match.group(1))
            epg_dn = self._extract_epg_from_path_dn(path.get('dn', ''))
            tenant = self._extract_tenant_from_dn(epg_dn) if epg_dn else 'unknown'
            bd_name = self._epg_bd_map.get(epg_dn)
            vrf_name = ''
            if bd_name and bd_name in {bd.get('name') for bd in self._bds}:
                bd_obj = next((bd for bd in self._bds if bd.get('name') == bd_name), None)
                if bd_obj:
                    vrf_name = self._get_vrf_name_for_bd(bd_obj)

            tdn = path.get('tDn', '')
            nodes = self._extract_nodes_from_tdn(tdn)
            if not nodes:
                nodes = ['unknown']

            fex_id = None
            if 'extpaths-' in tdn:
                match = re.search(r'extpaths-(\d+)', tdn)
                if match:
                    fex_id = match.group(1)
            elif 'fex-' in tdn:
                match = re.search(r'fex-(\d+)', tdn)
                if match:
                    fex_id = match.group(1)

            vpc_pair = None
            protpaths_match = re.search(r'protpaths-(\d+)-(\d+)', tdn)
            if protpaths_match:
                vpc_pair = f"vpc-{protpaths_match.group(1)}-{protpaths_match.group(2)}"

            for node_id in nodes:
                leaf_id = str(node_id)
                unit_type = 'leaf'
                fex_identifier = None
                fex_serial = None
                fex_model = None
                fex_display = None

                if fex_id:
                    fex_obj = fex_by_id.get(str(fex_id), {})
                    fex_serial = fex_obj.get('ser')
                    fex_model = fex_obj.get('model')
                    fex_identifier = self._build_fex_identifier(str(fex_id), leaf_id, fex_serial)
                    fex_display = f"{fex_serial or 'unknown'} / {fex_model or 'unknown'} / fex-{fex_id}"
                    unit_type = 'fex'

                unit_key = f"leaf-{leaf_id}"
                if fex_identifier:
                    unit_key = f"{unit_key}:{fex_identifier}"

                unit = units.get(unit_key)
                if not unit:
                    leaf_obj = leaf_by_id.get(str(leaf_id), {})
                    leaf_serial = leaf_obj.get('serial') or leaf_obj.get('ser')
                    cmdb_record = None
                    if fex_serial and fex_serial in cmdb_by_serial:
                        cmdb_record = cmdb_by_serial[fex_serial]
                    elif leaf_serial and leaf_serial in cmdb_by_serial:
                        cmdb_record = cmdb_by_serial[leaf_serial]

                    unit = {
                        'fabric_name': fabric_name,
                        'site': cmdb_record.get('site') if cmdb_record else 'Unknown',
                        'building': cmdb_record.get('building') if cmdb_record else 'Unknown',
                        'hall': cmdb_record.get('hall') if cmdb_record else 'Unknown',
                        'rack': cmdb_record.get('rack') if cmdb_record else 'Unknown',
                        'unit_location': cmdb_record.get('unitlocation') if cmdb_record else 'Unknown',
                        'leaf_id': leaf_id,
                        'leaf_or_vpc': vpc_pair or f"leaf-{leaf_id}",
                        'fex_identifier': fex_identifier,
                        'fex_display': fex_display,
                        'unit_type': unit_type,
                        'rewire_required': None,
                        'ports': set(),
                        'bindings': 0,
                        'epgs': set(),
                        'vlans': set(),
                        'bds': set(),
                        'vrfs': set(),
                        'tenants': set(),
                        'contracts': set(),
                        'service_graph_present': None,
                        'vpc_symmetry': 'Unknown',
                        'utilization_pct': None,
                        'utilization_known': False,
                        'ports_total': None,
                        'ports_connected': None,
                        'why': []
                    }

                    if fex_identifier and fex_identifier in util_by_fex:
                        util = util_by_fex[fex_identifier]
                        unit['utilization_pct'] = util.get('utilization_pct')
                        unit['utilization_known'] = util.get('utilization_pct') is not None
                        unit['ports_total'] = util.get('total_ports')
                        unit['ports_connected'] = util.get('connected_ports')

                    if leaf_id in asymmetric_nodes:
                        unit['vpc_symmetry'] = 'Bad'
                    elif vpc_symmetry.get('statistics', {}).get('total_epgs_checked', 0) > 0:
                        unit['vpc_symmetry'] = 'OK'

                    units[unit_key] = unit

                unit['ports'].add(tdn)
                unit['bindings'] += 1
                if epg_dn:
                    unit['epgs'].add(epg_dn)
                unit['vlans'].add(vlan_id)
                if bd_name:
                    unit['bds'].add(bd_name)
                if vrf_name:
                    unit['vrfs'].add(vrf_name)
                if tenant:
                    unit['tenants'].add(tenant)

        rows = []
        for unit_key, unit in units.items():
            vlan_infos = [vlan_coupling_map.get(vlan_id) for vlan_id in unit['vlans']]
            vlan_infos = [v for v in vlan_infos if v]

            worst_vlan = None
            if vlan_infos:
                worst_vlan = sorted(vlan_infos, key=lambda v: v.get('coupling_score', 0), reverse=True)[0]

            coupled_vlan_count = sum(
                1 for v in vlan_infos if v.get('coupling_level') in {'medium', 'high'}
            )

            top_coupled = sorted(vlan_infos, key=lambda v: v.get('coupling_score', 0), reverse=True)[:3]

            cross_tenant = any(v.get('tenant_count', 1) > 1 for v in vlan_infos) or len(unit['tenants']) > 1
            service_graph_present = any(v.get('service_graph_present') for v in vlan_infos) if vlan_infos else None
            if all(v.get('service_graph_present') is None for v in vlan_infos):
                service_graph_present = None

            difficulty_score = 0
            reasons = []
            if worst_vlan:
                worst_score = worst_vlan.get('coupling_score') or 0
                top_sum = sum(v.get('coupling_score') or 0 for v in top_coupled)
                difficulty_score += worst_score + (top_sum / 2)
                reasons.append(f"Worst VLAN {worst_vlan.get('vlan_id')} ({worst_vlan.get('coupling_level')})")

            if cross_tenant:
                difficulty_score += 15
                reasons.append('Cross-tenant coupling present')

            if service_graph_present:
                difficulty_score += 15
                reasons.append('Service graph present')

            if unit['vpc_symmetry'] == 'Bad':
                difficulty_score += 10
                reasons.append('VPC asymmetry detected')

            if unit['bindings'] > 50:
                difficulty_score += 10
                reasons.append('High attachment spread (>50 bindings)')
            elif unit['bindings'] > 10:
                difficulty_score += 5
                reasons.append('Moderate attachment spread (>10 bindings)')

            blocked = unit['unit_type'] == 'fex' and not unit['utilization_known']
            if blocked:
                difficulty_bucket = 'Blocked'
                difficulty_score = None
                reasons.append('Utilization data missing')
            elif difficulty_score >= 25:
                difficulty_bucket = 'Hard'
            elif difficulty_score >= 10:
                difficulty_bucket = 'Medium'
            else:
                difficulty_bucket = 'Easy'

            recommendation = 'Migrate as-is'
            if difficulty_bucket == 'Hard':
                recommendation = 'Decouple VLANs and reduce blast radius before migration'
            elif difficulty_bucket == 'Medium':
                recommendation = 'Bundle migration with dependency-aware sequencing'
            elif difficulty_bucket == 'Blocked':
                recommendation = 'Collect utilization/interface data before migration'

            row = {
                'unit_id': unit_key,
                'fabric_name': unit['fabric_name'],
                'site': unit['site'],
                'building': unit['building'],
                'hall': unit['hall'],
                'rack': unit['rack'],
                'leaf_or_vpc': unit['leaf_or_vpc'],
                'leaf_id': unit['leaf_id'],
                'fex_identifier': unit.get('fex_identifier') or 'N/A',
                'fex_display': unit.get('fex_display') or 'N/A',
                'ports_used': len(unit['ports']),
                'bindings': unit['bindings'],
                'utilization_pct': unit['utilization_pct'],
                'utilization_known': unit['utilization_known'],
                'ports_total': unit['ports_total'],
                'ports_connected': unit['ports_connected'],
                'ports': sorted(list(unit['ports'])),
                'impacted_epg_count': len(unit['epgs']),
                'impacted_epgs': sorted(list(unit['epgs'])),
                'impacted_vlan_count': len(unit['vlans']),
                'impacted_vlans': sorted(list(unit['vlans'])),
                'impacted_bd_count': len(unit['bds']),
                'impacted_bds': sorted(list(unit['bds'])),
                'impacted_vrf_count': len(unit['vrfs']),
                'impacted_vrfs': sorted(list(unit['vrfs'])),
                'impacted_tenant_count': len(unit['tenants']),
                'impacted_tenants': sorted(list(unit['tenants'])),
                'rewire_required': unit['rewire_required'],
                'worst_vlan_id': worst_vlan.get('vlan_id') if worst_vlan else None,
                'worst_vlan_level': worst_vlan.get('coupling_level') if worst_vlan else None,
                'worst_vlan_score': worst_vlan.get('coupling_score') if worst_vlan else None,
                'worst_vlan_display': f"{worst_vlan.get('vlan_id')} ({worst_vlan.get('coupling_level')})" if worst_vlan else None,
                'coupled_vlan_count': coupled_vlan_count,
                'top_coupled_vlans': [{
                    'vlan_id': v.get('vlan_id'),
                    'level': v.get('coupling_level'),
                    'score': v.get('coupling_score'),
                    'reason': v.get('why')
                } for v in top_coupled],
                'service_graph_present': service_graph_present,
                'cross_tenant_coupling_present': cross_tenant,
                'vpc_symmetry': unit['vpc_symmetry'],
                'score': difficulty_score,
                'difficulty_bucket': difficulty_bucket,
                'recommendation': recommendation,
                'why': reasons,
                'flagged': difficulty_bucket in {'Hard', 'Blocked'}
            }
            rows.append(row)

        stats = {
            'total_units': len(rows),
            'easy': sum(1 for r in rows if r['difficulty_bucket'] == 'Easy'),
            'medium': sum(1 for r in rows if r['difficulty_bucket'] == 'Medium'),
            'hard': sum(1 for r in rows if r['difficulty_bucket'] == 'Hard'),
            'blocked': sum(1 for r in rows if r['difficulty_bucket'] == 'Blocked')
        }

        return {'units': rows, 'statistics': stats}

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

        # Build serial number sets + ACI lookup
        aci_serials = set()
        aci_by_serial = {}
        for fex in self._fexes:
            serial = fex.get('ser')
            if serial:
                aci_serials.add(serial)
                aci_by_serial[serial] = {
                    'type': 'fex',
                    'id': fex.get('id'),
                    'name': fex.get('name') or f"FEX-{fex.get('id')}",
                    'model': fex.get('model')
                }
        for leaf in self._leafs:
            serial = leaf.get('serial')
            if serial:
                aci_serials.add(serial)
                aci_by_serial[serial] = {
                    'type': 'leaf',
                    'id': leaf.get('id'),
                    'name': leaf.get('name') or f"leaf-{leaf.get('id')}",
                    'model': leaf.get('model')
                }

        cmdb_serials = set(r.get('serial_number') for r in self._cmdb_records if r.get('serial_number'))

        # Find matches (ACI model is source of truth if present)
        correlated = []
        for record in self._cmdb_records:
            serial = record.get('serial_number', '')
            if serial in aci_serials:
                aci_info = aci_by_serial.get(serial, {})
                cmdb_model = record.get('model')
                aci_model = aci_info.get('model')
                model = aci_model or cmdb_model
                correlated.append({
                    'serial': serial,
                    'device_type': aci_info.get('type'),
                    'device_id': aci_info.get('id'),
                    'device_name': aci_info.get('name'),
                    'model': model,
                    'aci_model': aci_model,
                    'cmdb_model': cmdb_model,
                    'model_source': 'aci' if aci_model else 'cmdb',
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

    def _extract_nodes_from_tdn(self, tdn: str) -> List[str]:
        """Extract leaf node IDs from a path attachment target DN."""
        if not tdn:
            return []

        protpaths_match = re.search(r'protpaths-(\d+)-(\d+)', tdn)
        if protpaths_match:
            return [protpaths_match.group(1), protpaths_match.group(2)]

        paths_match = re.search(r'paths-(\d+)', tdn)
        if paths_match:
            return [paths_match.group(1)]

        node_match = re.search(r'node-(\d+)', tdn)
        if node_match:
            return [node_match.group(1)]

        return []

    def _extract_tenant_from_dn(self, dn: str) -> str:
        """Extract tenant name from DN."""
        match = re.search(r'tn-([^/]+)', dn)
        return match.group(1) if match else 'unknown'

    def _extract_app_profile_from_dn(self, dn: str) -> str:
        """Extract application profile name from DN."""
        match = re.search(r'ap-([^/]+)', dn)
        return match.group(1) if match else ''

    def _extract_bd_name_from_dn(self, dn: str) -> str:
        """Extract BD name from DN."""
        match = re.search(r'BD-([^/]+)', dn)
        return match.group(1) if match else ''

    def _extract_vrf_name_from_dn(self, dn: str) -> str:
        """Extract VRF name from DN."""
        match = re.search(r'ctx-([^/]+)', dn)
        return match.group(1) if match else ''

    def _extract_bd_dn_from_relation_dn(self, dn: str) -> str:
        """Extract BD DN from a relation DN."""
        match = re.search(r'(uni/tn-[^/]+/BD-[^/]+)', dn)
        return match.group(1) if match else ''

    def _extract_epg_dn_from_relation_dn(self, dn: str) -> str:
        """Extract EPG DN from a relation DN."""
        match = re.search(r'(uni/tn-[^/]+/ap-[^/]+/epg-[^/]+)', dn)
        return match.group(1) if match else ''

    def _extract_node_id_from_dn(self, dn: str) -> Optional[str]:
        """Extract node ID from DN."""
        match = re.search(r'node-(\d+)', dn)
        return match.group(1) if match else None

    def _normalize_fex_id(self, value: str) -> Optional[str]:
        """Normalize FEX ID to digits only for matching."""
        if value is None:
            return None
        match = re.search(r'(\d+)', str(value))
        return match.group(1) if match else None

    def _extract_interface_id_from_dn(self, dn: str) -> str:
        """Extract interface ID from DN."""
        match = re.search(r'phys-\[(.*?)\]', dn)
        if match:
            return match.group(1)
        match = re.search(r'aggr-\[(.*?)\]', dn)
        if match:
            return match.group(1)
        return ''

    def _count_fex_ports_from_path_attachments(self, fex_id: str) -> Optional[int]:
        """
        Count unique FEX host ports using fvRsPathAtt target DNs.
        This is a fallback when ethpmPhysIf/l1PhysIf data is missing or unmatched.
        """
        if not fex_id:
            return None
        fex_norm = self._normalize_fex_id(fex_id)
        if not fex_norm:
            return None

        port_keys = set()
        for att in self._path_attachments:
            tdn = att.get('tDn', '') or att.get('dn', '')
            if not tdn:
                continue

            # Typical FEX path format: topology/pod-1/paths-101/extpaths-1101/pathep-[eth1/11]
            match = re.search(r'paths-(\d+)/extpaths-(\d+)/pathep-\[([^\]]+)\]', tdn)
            if match:
                leaf_id = match.group(1)
                fex_match = match.group(2)
                interface_id = match.group(3)
                if str(fex_match) == str(fex_norm) or str(fex_match).endswith(str(fex_norm)):
                    port_keys.add(f"{leaf_id}:{fex_id}:{interface_id}")
                continue

            # vPC / protpaths format: topology/pod-1/protpaths-101-102/extpaths-1101/pathep-[eth1/11]
            match = re.search(r'protpaths-(\d+)-(\d+)/extpaths-(\d+)/pathep-\[([^\]]+)\]', tdn)
            if match:
                leaf_a = match.group(1)
                leaf_b = match.group(2)
                fex_match = match.group(3)
                interface_id = match.group(4)
                if str(fex_match) == str(fex_norm) or str(fex_match).endswith(str(fex_norm)):
                    port_keys.add(f"{leaf_a}:{fex_id}:{interface_id}")
                    port_keys.add(f"{leaf_b}:{fex_id}:{interface_id}")
                continue

            # Alternate format without pathep section
            match = re.search(r'paths-(\d+)/extpaths-(\d+)', tdn)
            if match:
                leaf_id = match.group(1)
                fex_match = match.group(2)
                if str(fex_match) == str(fex_norm) or str(fex_match).endswith(str(fex_norm)):
                    port_keys.add(f"{leaf_id}:{fex_id}:unknown")
                continue

            # Fallback: extpaths appears in DN without leaf context
            match = re.search(r'extpaths-(\d+)', tdn)
            if match and (str(match.group(1)) == str(fex_norm) or str(match.group(1)).endswith(str(fex_norm))):
                port_keys.add(f"unknown:{fex_id}:unknown")

        if not port_keys:
            return None
        return len(port_keys)

    def _get_bd_name_for_epg(self, epg: Dict[str, Any]) -> str:
        """Resolve BD name for an EPG using attributes or relation map."""
        bd_name = epg.get('bd', '')
        if bd_name:
            return bd_name
        epg_dn = epg.get('dn', '')
        if epg_dn and epg_dn in self._epg_bd_map:
            return self._epg_bd_map[epg_dn]
        return ''

    def _get_vrf_name_for_bd(self, bd: Dict[str, Any]) -> str:
        """Resolve VRF name for a BD using attributes or relation map."""
        vrf_name = bd.get('vrf', '')
        if vrf_name:
            return vrf_name
        bd_dn = bd.get('dn', '')
        if bd_dn and bd_dn in self._bd_vrf_map:
            return self._bd_vrf_map[bd_dn]
        return ''

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
        if not model:
            return 0
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

        return 0  # Unknown model: avoid false certainty

    def _build_fex_identifier(self, fex_id: str, leaf_id: Optional[str], serial: Optional[str]) -> str:
        """Build a stable FEX identifier (avoid assuming fex_id is globally unique)."""
        parts = []
        if leaf_id:
            parts.append(f'leaf-{leaf_id}')
        if fex_id:
            parts.append(f'fex-{fex_id}')
        if serial:
            parts.append(f'serial-{serial}')
        return ':'.join(parts) if parts else f'fex-{fex_id}'

    def _calculate_consolidation_score(self, utilization: Optional[float], status: str, interface_count: int) -> Optional[int]:
        """Calculate FEX consolidation score (0-100, higher = better candidate)."""
        if utilization is None:
            return None

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

    def _get_consolidation_recommendation(self, score: Optional[int], utilization: Optional[float]) -> str:
        """Get consolidation recommendation based on score."""
        if score is None or utilization is None:
            return 'Needs utilization data'
        if score >= 80:
            return 'Strong candidate for consolidation or decommission'
        if score >= 60:
            return 'Consider consolidation with other low-utilization FEX'
        if score >= 40:
            return 'Monitor utilization trends'
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

    def analyze_device_epg_vlan_mapping(self) -> Dict[str, Any]:
        """
        Comprehensive device -> EPG -> VLAN mapping analysis.
        Shows complete deployment picture: which EPGs are on which devices with which VLANs.

        Returns hierarchical mapping:
        - Leaf/FEX -> EPGs deployed -> VLANs used
        - Allows filtering and drill-down by any dimension
        """
        self._load_data()

        # Build comprehensive mapping structure
        device_map = {}  # device_id -> {epgs: [], vlans: set(), tenants: set()}
        epg_map = {}     # epg_dn -> {devices: [], vlans: [], tenant: str}
        vlan_map = {}    # vlan -> {devices: [], epgs: [], tenants: set()}

        # Process all path attachments
        for path in self._path_attachments:
            path_dn = path.get('dn', '')
            target_dn = path.get('tDn', '')
            encap = path.get('encap', '')

            # Extract EPG info
            epg_dn = path_dn.split('/rspathAtt')[0] if '/rspathAtt' in path_dn else ''
            epg_name = self._extract_epg_from_path_dn(path_dn)
            tenant = self._extract_tenant_from_dn(epg_dn)

            # Extract device
            device_id = 'unknown'
            device_type = 'unknown'
            if 'fex-' in target_dn:
                match = re.search(r'node-(\d+).*fex-(\d+)', target_dn)
                if match:
                    leaf_id, fex_id = match.groups()
                    device_id = f'fex-{fex_id}'
                    device_type = 'fex'
            elif 'extpaths-' in target_dn:
                match = re.search(r'extpaths-(\d+)', target_dn)
                if match:
                    device_id = f'fex-{match.group(1)}'
                    device_type = 'fex'
            elif 'protpaths-' in target_dn:
                match = re.search(r'protpaths-(\d+)-(\d+)', target_dn)
                if match:
                    device_id = f'leaf-{match.group(1)}'
                    device_type = 'leaf'
            elif 'paths-' in target_dn:
                match = re.search(r'paths-(\d+)', target_dn)
                if match:
                    device_id = f'leaf-{match.group(1)}'
                    device_type = 'leaf'
            elif 'node-' in target_dn:
                match = re.search(r'node-(\d+)', target_dn)
                if match:
                    device_id = f'leaf-{match.group(1)}'
                    device_type = 'leaf'

            # Extract VLAN
            vlan = None
            if 'vlan-' in encap:
                vlan = encap.split('vlan-')[1]

            # Build device mapping
            if device_id not in device_map:
                device_map[device_id] = {
                    'device_id': device_id,
                    'device_type': device_type,
                    'epgs': set(),
                    'vlans': set(),
                    'tenants': set(),
                    'epg_details': []
                }

            device_map[device_id]['epgs'].add(epg_name)
            device_map[device_id]['tenants'].add(tenant)
            if vlan:
                device_map[device_id]['vlans'].add(vlan)

            device_map[device_id]['epg_details'].append({
                'epg': epg_name,
                'epg_dn': epg_dn,
                'tenant': tenant,
                'vlan': vlan
            })

            # Build EPG mapping
            if epg_dn not in epg_map:
                epg_map[epg_dn] = {
                    'epg_name': epg_name,
                    'tenant': tenant,
                    'devices': set(),
                    'vlans': set()
                }

            epg_map[epg_dn]['devices'].add(device_id)
            if vlan:
                epg_map[epg_dn]['vlans'].add(vlan)

            # Build VLAN mapping
            if vlan:
                if vlan not in vlan_map:
                    vlan_map[vlan] = {
                        'vlan': vlan,
                        'devices': set(),
                        'epgs': set(),
                        'tenants': set()
                    }

                vlan_map[vlan]['devices'].add(device_id)
                vlan_map[vlan]['epgs'].add(epg_name)
                vlan_map[vlan]['tenants'].add(tenant)

        # Convert sets to lists for JSON serialization
        for device_id, data in device_map.items():
            data['epgs'] = list(data['epgs'])
            data['vlans'] = sorted([int(v) for v in data['vlans']]) if data['vlans'] else []
            data['tenants'] = list(data['tenants'])
            data['epg_count'] = len(data['epgs'])
            data['vlan_count'] = len(data['vlans'])
            data['tenant_count'] = len(data['tenants'])

        for epg_dn, data in epg_map.items():
            data['devices'] = list(data['devices'])
            data['vlans'] = sorted([int(v) for v in data['vlans']]) if data['vlans'] else []
            data['device_count'] = len(data['devices'])
            data['vlan_count'] = len(data['vlans'])

        for vlan, data in vlan_map.items():
            data['devices'] = list(data['devices'])
            data['epgs'] = list(data['epgs'])
            data['tenants'] = list(data['tenants'])
            data['device_count'] = len(data['devices'])
            data['epg_count'] = len(data['epgs'])
            data['tenant_count'] = len(data['tenants'])

        # Build hierarchical view: Leaf -> FEX -> EPGs
        hierarchy = []
        for leaf in self._leafs:
            leaf_id = f"leaf-{leaf.get('id')}"
            leaf_data = {
                'leaf_id': leaf.get('id'),
                'leaf_name': leaf.get('name'),
                'leaf_model': leaf.get('model'),
                'fex_devices': [],
                'direct_epgs': []
            }

            # Add EPGs directly on this leaf
            if leaf_id in device_map:
                leaf_data['direct_epgs'] = device_map[leaf_id]['epg_details']

            # Find FEX attached to this leaf
            for fex in self._fexes:
                fex_dn = fex.get('dn', '')
                if f"node-{leaf.get('id')}" in fex_dn:
                    fex_id = f"fex-{fex.get('id')}"
                    fex_data = {
                        'fex_id': fex.get('id'),
                        'fex_model': fex.get('model'),
                        'fex_serial': fex.get('ser'),
                        'status': fex.get('operSt'),
                        'epgs': []
                    }

                    # Add EPGs on this FEX
                    if fex_id in device_map:
                        fex_data['epgs'] = device_map[fex_id]['epg_details']
                        fex_data['epg_count'] = len(device_map[fex_id]['epgs'])
                        fex_data['vlan_count'] = len(device_map[fex_id]['vlans'])
                        fex_data['tenant_count'] = len(device_map[fex_id]['tenants'])
                    else:
                        fex_data['epg_count'] = 0
                        fex_data['vlan_count'] = 0
                        fex_data['tenant_count'] = 0

                    leaf_data['fex_devices'].append(fex_data)

            # Calculate leaf totals
            leaf_data['total_epgs'] = len(leaf_data['direct_epgs'])
            leaf_data['total_fex'] = len(leaf_data['fex_devices'])
            for fex in leaf_data['fex_devices']:
                leaf_data['total_epgs'] += fex.get('epg_count', 0)

            hierarchy.append(leaf_data)

        # Statistics
        total_devices = len(device_map)
        devices_with_multiple_tenants = sum(1 for d in device_map.values() if d['tenant_count'] > 1)
        vlans_spanning_devices = sum(1 for v in vlan_map.values() if v['device_count'] > 1)
        epgs_spanning_devices = sum(1 for e in epg_map.values() if e['device_count'] > 1)

        return {
            'device_map': device_map,
            'epg_map': {k: v for k, v in epg_map.items()},
            'vlan_map': vlan_map,
            'hierarchy': hierarchy,
            'statistics': {
                'total_devices': total_devices,
                'total_epgs_mapped': len(epg_map),
                'total_vlans_used': len(vlan_map),
                'devices_with_multiple_tenants': devices_with_multiple_tenants,
                'vlans_spanning_devices': vlans_spanning_devices,
                'epgs_spanning_devices': epgs_spanning_devices
            }
        }

    def get_data_completeness(self) -> Dict[str, Any]:
        """
        Comprehensive data completeness analysis.
        Returns detailed validation results for UI display.
        """
        self._load_data()

        # Count all object types present in the dataset
        type_counts = defaultdict(int)
        for obj in self._aci_objects:
            obj_type = obj.get('type')
            if obj_type:
                type_counts[obj_type] += 1

        # Define required and optional object types
        object_definitions = [
            {
                'label': 'EPGs (fvAEPg)',
                'type': 'fvAEPg',
                'required': True,
                'description': 'Application Endpoint Groups - defines workload placement',
                'collection_command': 'moquery -c fvAEPg -o json > epgs.json'
            },
            {
                'label': 'Leafs (fabricNode)',
                'type': 'fabricNode',
                'required': True,
                'description': 'Leaf switches - fabric infrastructure',
                'collection_command': 'moquery -c fabricNode -o json > nodes.json'
            },
            {
                'label': 'Path Attachments (fvRsPathAtt)',
                'type': 'fvRsPathAtt',
                'required': True,
                'description': 'EPG bindings to physical interfaces',
                'collection_command': 'moquery -c fvRsPathAtt -o json > paths.json'
            },
            {
                'label': 'Bridge Domains (fvBD)',
                'type': 'fvBD',
                'required': True,
                'description': 'Layer 2 forwarding domains',
                'collection_command': 'moquery -c fvBD -o json > bridge_domains.json'
            },
            {
                'label': 'VRFs (fvCtx)',
                'type': 'fvCtx',
                'required': True,
                'description': 'Layer 3 routing contexts',
                'collection_command': 'moquery -c fvCtx -o json > vrfs.json'
            },
            {
                'label': 'Tenants (fvTenant)',
                'type': 'fvTenant',
                'required': True,
                'description': 'Multi-tenancy containers',
                'collection_command': 'moquery -c fvTenant -o json > tenants.json'
            },
            {
                'label': 'Subnets (fvSubnet)',
                'type': 'fvSubnet',
                'required': True,
                'description': 'IP subnet definitions',
                'collection_command': 'moquery -c fvSubnet -o json > subnets.json'
            },
            {
                'label': 'Physical Interfaces (ethpmPhysIf)',
                'type': 'ethpmPhysIf',
                'required': True,
                'description': 'Physical interface inventory for utilization and cabling analysis',
                'collection_command': 'moquery -c ethpmPhysIf -o json > interfaces.json'
            },
            {
                'label': 'Physical Domains (physDomP)',
                'type': 'physDomP',
                'required': True,
                'description': 'Physical domains for VLAN/domain mapping',
                'collection_command': 'moquery -c physDomP -o json > phys_domains.json'
            },
            {
                'label': 'FEX Devices (eqptFex)',
                'type': 'eqptFex',
                'required': True,
                'description': 'Fabric Extenders - required for port utilization and consolidation analysis',
                'collection_command': 'moquery -c eqptFex -o json > fex.json'
            },
            {
                'label': 'Contracts (vzBrCP)',
                'type': 'vzBrCP',
                'required': False,
                'description': 'Inter-EPG communication policies',
                'collection_command': 'moquery -c vzBrCP -o json > contracts.json'
            },
            {
                'label': 'Contract Subjects (vzSubj)',
                'type': 'vzSubj',
                'required': False,
                'description': 'Contract subjects for ACL translation',
                'collection_command': 'moquery -c vzSubj -o json > contract_subjects.json'
            },
            {
                'label': 'Contract Filters (vzFilter)',
                'type': 'vzFilter',
                'required': False,
                'description': 'Contract filters for ACL translation',
                'collection_command': 'moquery -c vzFilter -o json > contract_filters.json'
            },
            {
                'label': 'Contract Entries (vzEntry)',
                'type': 'vzEntry',
                'required': False,
                'description': 'Filter entries (rules) for ACL translation',
                'collection_command': 'moquery -c vzEntry -o json > contract_entries.json'
            },
            {
                'label': 'Subject Filter Attachments (vzRsSubjFiltAtt)',
                'type': 'vzRsSubjFiltAtt',
                'required': False,
                'description': 'Filter bindings to contract subjects',
                'collection_command': 'moquery -c vzRsSubjFiltAtt -o json > subj_filter_bindings.json'
            },
            {
                'label': 'Contract Consumers (fvRsCons)',
                'type': 'fvRsCons',
                'required': False,
                'description': 'EPG-to-contract consumer mappings',
                'collection_command': 'moquery -c fvRsCons -o json > contract_consumers.json'
            },
            {
                'label': 'Contract Providers (fvRsProv)',
                'type': 'fvRsProv',
                'required': False,
                'description': 'EPG-to-contract provider mappings',
                'collection_command': 'moquery -c fvRsProv -o json > contract_providers.json'
            },
            {
                'label': 'VPC Domains (vpcDom)',
                'type': 'vpcDom',
                'required': False,
                'description': 'VPC domain configuration',
                'collection_command': 'moquery -c vpcDom -o json > vpc_domains.json'
            },
            {
                'label': 'Port Channels (pcAggrIf)',
                'type': 'pcAggrIf',
                'required': False,
                'description': 'Port-channel aggregated interfaces',
                'collection_command': 'moquery -c pcAggrIf -o json > port_channels.json'
            },
            {
                'label': 'LACP Entities (lacpEntity)',
                'type': 'lacpEntity',
                'required': False,
                'description': 'LACP configuration entities',
                'collection_command': 'moquery -c lacpEntity -o json > lacp.json'
            },
            {
                'label': 'VPC Interfaces (vpcIf)',
                'type': 'vpcIf',
                'required': False,
                'description': 'VPC interface details',
                'collection_command': 'moquery -c vpcIf -o json > vpc_interfaces.json'
            },
            {
                'label': 'L3Out (l3extOut)',
                'type': 'l3extOut',
                'required': False,
                'description': 'External routed network definitions',
                'collection_command': 'moquery -c l3extOut -o json > l3outs.json'
            },
            {
                'label': 'External EPGs (l3extInstP)',
                'type': 'l3extInstP',
                'required': False,
                'description': 'External EPGs for L3Out',
                'collection_command': 'moquery -c l3extInstP -o json > l3ext_epgs.json'
            },
            {
                'label': 'L3Out Node Profiles (l3extLNodeP)',
                'type': 'l3extLNodeP',
                'required': False,
                'description': 'Border leaf associations for L3Out',
                'collection_command': 'moquery -c l3extLNodeP -o json > l3ext_nodes.json'
            },
            {
                'label': 'L3Out Interface Profiles (l3extLIfP)',
                'type': 'l3extLIfP',
                'required': False,
                'description': 'External interface profiles for L3Out',
                'collection_command': 'moquery -c l3extLIfP -o json > l3ext_interfaces.json'
            },
            {
                'label': 'L3Out Node Attachments (l3extRsNodeL3OutAtt)',
                'type': 'l3extRsNodeL3OutAtt',
                'required': False,
                'description': 'L3Out node attachments',
                'collection_command': 'moquery -c l3extRsNodeL3OutAtt -o json > l3ext_node_attach.json'
            },
            {
                'label': 'L3Out Subnets (l3extSubnet)',
                'type': 'l3extSubnet',
                'required': False,
                'description': 'L3Out external subnets',
                'collection_command': 'moquery -c l3extSubnet -o json > l3ext_subnets.json'
            },
            {
                'label': 'L3Out VRF Binding (l3extRsEctx)',
                'type': 'l3extRsEctx',
                'required': False,
                'description': 'L3Out to VRF bindings',
                'collection_command': 'moquery -c l3extRsEctx -o json > l3ext_vrf_binding.json'
            },
            {
                'label': 'BGP Peers (bgpPeerP)',
                'type': 'bgpPeerP',
                'required': False,
                'description': 'BGP peer configurations',
                'collection_command': 'moquery -c bgpPeerP -o json > bgp_peers.json'
            },
            {
                'label': 'OSPF Interfaces (ospfIfP)',
                'type': 'ospfIfP',
                'required': False,
                'description': 'OSPF interface configurations',
                'collection_command': 'moquery -c ospfIfP -o json > ospf_interfaces.json'
            },
            {
                'label': 'Static Routes (ipRouteP)',
                'type': 'ipRouteP',
                'required': False,
                'description': 'Static route configurations',
                'collection_command': 'moquery -c ipRouteP -o json > static_routes.json'
            },
            {
                'label': 'VLAN Pools (fvnsVlanInstP)',
                'type': 'fvnsVlanInstP',
                'required': False,
                'description': 'VLAN pool definitions',
                'collection_command': 'moquery -c fvnsVlanInstP -o json > vlan_pools.json'
            },
            {
                'label': 'VLAN Ranges (fvnsEncapBlk)',
                'type': 'fvnsEncapBlk',
                'required': False,
                'description': 'VLAN allocation ranges',
                'collection_command': 'moquery -c fvnsEncapBlk -o json > vlan_ranges.json'
            },
            {
                'label': 'VMM Domains (vmmDomP)',
                'type': 'vmmDomP',
                'required': False,
                'description': 'VMM domains for VLAN bindings',
                'collection_command': 'moquery -c vmmDomP -o json > vmm_domains.json'
            },
            {
                'label': 'L3 Domains (l3extDomP)',
                'type': 'l3extDomP',
                'required': False,
                'description': 'L3 domains for VLAN bindings',
                'collection_command': 'moquery -c l3extDomP -o json > l3_domains.json'
            },
            {
                'label': 'VLAN Namespace Bindings (infraRsVlanNs)',
                'type': 'infraRsVlanNs',
                'required': False,
                'description': 'VLAN pool bindings for physical domains',
                'collection_command': 'moquery -c infraRsVlanNs -o json > vlan_bindings_phys.json'
            },
            {
                'label': 'VLAN Namespace Bindings (vmmRsVlanNs)',
                'type': 'vmmRsVlanNs',
                'required': False,
                'description': 'VLAN pool bindings for VMM domains',
                'collection_command': 'moquery -c vmmRsVlanNs -o json > vlan_bindings_vmm.json'
            },
            {
                'label': 'VLAN Namespace Bindings (l3extRsVlanNs)',
                'type': 'l3extRsVlanNs',
                'required': False,
                'description': 'VLAN pool bindings for L3 domains',
                'collection_command': 'moquery -c l3extRsVlanNs -o json > vlan_bindings_l3.json'
            },
            {
                'label': 'Access Port Groups (infraAccPortGrp)',
                'type': 'infraAccPortGrp',
                'required': False,
                'description': 'Access port policy groups',
                'collection_command': 'moquery -c infraAccPortGrp -o json > access_port_groups.json'
            },
            {
                'label': 'Bundle Port Groups (infraAccBndlGrp)',
                'type': 'infraAccBndlGrp',
                'required': False,
                'description': 'Port-channel policy groups',
                'collection_command': 'moquery -c infraAccBndlGrp -o json > bundle_port_groups.json'
            },
            {
                'label': 'Interface Profiles (infraAccPortP)',
                'type': 'infraAccPortP',
                'required': False,
                'description': 'Interface profile definitions',
                'collection_command': 'moquery -c infraAccPortP -o json > interface_profiles.json'
            },
            {
                'label': 'Port Selectors (infraHPortS)',
                'type': 'infraHPortS',
                'required': False,
                'description': 'Port selector definitions',
                'collection_command': 'moquery -c infraHPortS -o json > port_selectors.json'
            },
            {
                'label': 'AEP Domain Bindings (infraRsDomP)',
                'type': 'infraRsDomP',
                'required': False,
                'description': 'Attachable Entity Profile domain bindings',
                'collection_command': 'moquery -c infraRsDomP -o json > aep_domain_bindings.json'
            },
            {
                'label': 'Attachable Entity Profiles (infraAttEntityP)',
                'type': 'infraAttEntityP',
                'required': False,
                'description': 'Attachable Entity Profiles for physical connectivity',
                'collection_command': 'moquery -c infraAttEntityP -o json > aeps.json'
            },
            {
                'label': 'LLDP Neighbors (lldpAdjEp)',
                'type': 'lldpAdjEp',
                'required': False,
                'description': 'LLDP neighbor discovery',
                'collection_command': 'moquery -c lldpAdjEp -o json > lldp_neighbors.json'
            },
            {
                'label': 'CDP Neighbors (cdpAdjEp)',
                'type': 'cdpAdjEp',
                'required': False,
                'description': 'CDP neighbor discovery',
                'collection_command': 'moquery -c cdpAdjEp -o json > cdp_neighbors.json'
            }
        ]

        object_types = {}
        for obj_def in object_definitions:
            count = type_counts.get(obj_def['type'], 0)
            object_types[obj_def['label']] = {
                'count': count,
                'required': obj_def['required'],
                'description': obj_def['description'],
                'collection_command': obj_def['collection_command'],
                'aci_class': obj_def['type']
            }

        # Calculate completeness score
        total_required = sum(1 for obj in object_types.values() if obj['required'])
        present_required = sum(1 for obj in object_types.values() if obj['required'] and obj['count'] > 0)
        optional_present = sum(1 for obj in object_types.values() if not obj['required'] and obj['count'] > 0)

        # Weighted score: required=70%, optional=30%
        required_score = (present_required / total_required * 70) if total_required > 0 else 0
        optional_score = (optional_present / (len(object_types) - total_required) * 30) if len(object_types) > total_required else 0
        completeness_score = round(required_score + optional_score)

        # Missing required data
        missing_required = [
            {
                'type': obj_name,
                'description': obj_info['description'],
                'collection_command': obj_info['collection_command']
            }
            for obj_name, obj_info in object_types.items()
            if obj_info['required'] and obj_info['count'] == 0
        ]

        # Analysis capabilities
        module_requirements = {
            'Port Utilization': ['eqptFex', 'ethpmPhysIf'],
            'Topology Mapping': ['fabricNode'],
            'EPG Complexity': ['fvAEPg', 'fvRsPathAtt'],
            'BD-EPG Mapping': ['fvBD', 'fvAEPg', 'fvSubnet'],
            'Contract Translation': ['vzBrCP', 'vzSubj', 'vzFilter', 'vzEntry', 'vzRsSubjFiltAtt', 'fvRsCons', 'fvRsProv', 'fvAEPg'],
            'VLAN Distribution': ['fvRsPathAtt'],
            'VPC Analysis': ['vpcDom', 'pcAggrIf', 'lacpEntity', 'vpcIf', 'fvRsPathAtt'],
            'L3Out Analysis': ['l3extOut', 'l3extInstP', 'l3extLNodeP', 'l3extLIfP', 'l3extRsNodeL3OutAtt', 'l3extSubnet', 'l3extRsEctx', 'bgpPeerP', 'ospfIfP', 'ipRouteP', 'fvCtx'],
            'VLAN Pool Analysis': ['fvnsVlanInstP', 'fvnsEncapBlk', 'physDomP', 'vmmDomP', 'l3extDomP', 'infraRsVlanNs', 'vmmRsVlanNs', 'l3extRsVlanNs', 'fvRsPathAtt', 'fvAEPg'],
            'Physical Connectivity': ['ethpmPhysIf', 'infraAccPortGrp', 'infraAccBndlGrp', 'infraAccPortP', 'infraHPortS', 'infraRsDomP', 'infraAttEntityP', 'lldpAdjEp', 'cdpAdjEp', 'fvRsPathAtt', 'fabricNode'],
            'Migration Planning': ['fvAEPg', 'fvRsPathAtt', 'fvBD', 'fvCtx', 'fvSubnet']
        }

        capabilities = {}
        for module, required_types in module_requirements.items():
            missing_types = [t for t in required_types if type_counts.get(t, 0) == 0]
            capabilities[module] = {
                'enabled': len(missing_types) == 0,
                'reason': f"Missing: {', '.join(missing_types)}" if missing_types else None,
                'missing_types': missing_types
            }

        capabilities['CMDB Correlation'] = {
            'enabled': self._cmdb_records is not None and len(self._cmdb_records) > 0,
            'reason': 'Missing CMDB data' if not (self._cmdb_records and len(self._cmdb_records) > 0) else None
        }

        # Suggestions
        suggestions = []

        if len(self._bds) == 0:
            suggestions.append({
                'text': 'Upload Bridge Domain data to enable BD-EPG mapping analysis',
                'command': 'moquery -c fvBD -o json > bridge_domains.json'
            })

        if len(self._contracts) == 0:
            suggestions.append({
                'text': 'Upload Contract data to detect inter-tenant dependencies',
                'command': 'moquery -c vzBrCP -o json > contracts.json'
            })

        if type_counts.get('vzSubj', 0) == 0 or type_counts.get('vzFilter', 0) == 0 or type_counts.get('vzEntry', 0) == 0:
            suggestions.append({
                'text': 'Upload contract subjects and filters to enable ACL translation',
                'command': 'moquery -c vzSubj -o json > contract_subjects.json'
            })

        if type_counts.get('l3extOut', 0) == 0:
            suggestions.append({
                'text': 'Upload L3Out data to analyze external connectivity impact',
                'command': 'moquery -c l3extOut -o json > l3outs.json'
            })

        if type_counts.get('fvnsVlanInstP', 0) == 0:
            suggestions.append({
                'text': 'Upload VLAN pool data to analyze VLAN namespace conflicts',
                'command': 'moquery -c fvnsVlanInstP -o json > vlan_pools.json'
            })

        if type_counts.get('vpcDom', 0) == 0:
            suggestions.append({
                'text': 'Upload VPC domain data to validate dual-homing symmetry',
                'command': 'moquery -c vpcDom -o json > vpc_domains.json'
            })

        if type_counts.get('ethpmPhysIf', 0) == 0:
            suggestions.append({
                'text': 'Upload physical interface data for port utilization and cabling analysis',
                'command': 'moquery -c ethpmPhysIf -o json > interfaces.json'
            })

        if not self._cmdb_records:
            suggestions.append({
                'text': 'Upload CMDB data (CSV) for rack-level correlation and physical location mapping',
                'command': None
            })

        if len(self._fexes) == 0:
            suggestions.append({
                'text': 'Upload FEX data for port utilization and consolidation analysis',
                'command': 'moquery -c eqptFex -o json > fex.json'
            })

        # Data quality checks
        quality_issues = []

        invalid_encap = [
            p for p in self._path_attachments
            if not re.search(r'vlan-(\d+)', p.get('encap', ''))
        ]
        if invalid_encap:
            quality_issues.append({
                'category': 'path_attachment_encap',
                'message': f'{len(invalid_encap)} path attachments missing or invalid VLAN encap',
                'severity': 'high'
            })

        missing_tdn = [
            p for p in self._path_attachments
            if not p.get('tDn') or not self._extract_nodes_from_tdn(p.get('tDn', ''))
        ]
        if missing_tdn:
            quality_issues.append({
                'category': 'path_attachment_target',
                'message': f'{len(missing_tdn)} path attachments missing target path (tDn)',
                'severity': 'high'
            })

        epgs_without_paths = [
            epg for epg in self._epgs
            if not any(epg.get('dn', '') in p.get('dn', '') for p in self._path_attachments)
        ]
        if epgs_without_paths:
            quality_issues.append({
                'category': 'epgs_without_paths',
                'message': f'{len(epgs_without_paths)} EPGs without path attachments',
                'severity': 'medium'
            })

        bds_without_subnets = [
            bd for bd in self._bds
            if not any(bd.get('dn', '') in s.get('dn', '') for s in self._subnets)
        ]
        if bds_without_subnets:
            quality_issues.append({
                'category': 'bds_without_subnets',
                'message': f'{len(bds_without_subnets)} Bridge Domains without subnets',
                'severity': 'medium'
            })

        # Required attribute validation per class
        required_attrs = {
            'fvAEPg': ['dn', 'name'],
            'fvRsPathAtt': ['dn', 'tDn', 'encap'],
            'fabricNode': ['dn', 'id', 'role', 'name'],
            'eqptFex': ['dn', 'id', 'ser', 'model'],
            'fvBD': ['dn', 'name'],
            'fvCtx': ['dn', 'name'],
            'fvTenant': ['dn', 'name'],
            'fvSubnet': ['dn', 'ip'],
            'ethpmPhysIf': ['dn', 'operSt', 'operSpeed'],
            'physDomP': ['dn', 'name']
        }

        missing_attr_counts = defaultdict(int)
        for obj in self._aci_objects:
            obj_type = obj.get('type')
            if obj_type not in required_attrs:
                continue
            attrs = obj.get('attributes', {})
            for attr in required_attrs[obj_type]:
                if not attrs.get(attr):
                    missing_attr_counts[(obj_type, attr)] += 1

        for (obj_type, attr), count in missing_attr_counts.items():
            quality_issues.append({
                'category': f'{obj_type}_missing_{attr}',
                'message': f'{count} {obj_type} objects missing required attribute {attr}',
                'severity': 'high' if obj_type in {'fvRsPathAtt', 'fabricNode', 'fvAEPg'} else 'medium'
            })

        return {
            'completeness_score': completeness_score,
            'object_counts': object_types,
            'missing_required': missing_required,
            'analysis_capabilities': capabilities,
            'module_requirements': module_requirements,
            'data_quality': {
                'issues': quality_issues,
                'issue_count': len(quality_issues)
            },
            'suggestions': suggestions,
            'total_objects': len(self._aci_objects) if self._aci_objects else 0,
            'has_cmdb': self._cmdb_records is not None and len(self._cmdb_records) > 0
        }

    # ==================== Advanced Migration Analysis Methods ====================
    # These methods use the new analysis modules for complete ACI migration

    def analyze_vpc_configuration(self) -> Dict[str, Any]:
        """
        Analyze VPC and port-channel configurations for migration.

        Returns comprehensive VPC topology, port-channel details, dual-homed endpoints,
        and redundancy mapping recommendations for migration planning.
        """
        self._load_data()

        try:
            from .vpc_analysis import VPCAnalyzer
            analyzer = VPCAnalyzer(self._aci_objects)
            return analyzer.get_summary()
        except Exception as e:
            logger.error(f"VPC analysis failed: {str(e)}")
            return {'error': str(e)}

    def analyze_contract_to_acl_translation(self) -> Dict[str, Any]:
        """
        Translate ACI contracts to traditional ACLs for non-ACI platforms.

        Returns contract analysis, ACL translations, and multi-vendor ACL configurations.
        """
        self._load_data()

        try:
            from .contract_translation import ContractTranslator
            translator = ContractTranslator(self._aci_objects)
            return translator.get_summary()
        except Exception as e:
            logger.error(f"Contract translation failed: {str(e)}")
            return {'error': str(e)}

    def analyze_l3out_connectivity(self) -> Dict[str, Any]:
        """
        Analyze L3Out configurations and external connectivity.

        Returns L3Out inventory, BGP/OSPF configurations, border leaf identification,
        and migration recommendations for external connectivity.
        """
        self._load_data()

        try:
            from .l3out_analysis import L3OutAnalyzer
            analyzer = L3OutAnalyzer(self._aci_objects)
            return analyzer.get_summary()
        except Exception as e:
            logger.error(f"L3Out analysis failed: {str(e)}")
            return {'error': str(e)}

    def analyze_vlan_pools(self) -> Dict[str, Any]:
        """
        Analyze VLAN pool configurations and namespace management.

        Returns VLAN pool inventory, usage analysis, conflict detection,
        and VLAN migration planning recommendations.
        """
        self._load_data()

        try:
            from .vlan_pool_analysis import VLANPoolAnalyzer
            analyzer = VLANPoolAnalyzer(self._aci_objects)
            return analyzer.get_summary()
        except Exception as e:
            logger.error(f"VLAN pool analysis failed: {str(e)}")
            return {'error': str(e)}

    def analyze_physical_connectivity(self) -> Dict[str, Any]:
        """
        Analyze physical connectivity and interface policies.

        Returns interface inventory, policy group analysis, neighbor discovery,
        and cabling migration plan.
        """
        self._load_data()

        try:
            from .physical_connectivity import PhysicalConnectivityAnalyzer
            analyzer = PhysicalConnectivityAnalyzer(self._aci_objects)
            return analyzer.get_summary()
        except Exception as e:
            logger.error(f"Physical connectivity analysis failed: {str(e)}")
            return {'error': str(e)}

    def generate_complete_migration_assessment(self) -> Dict[str, Any]:
        """
        Generate comprehensive migration assessment combining all analysis modules.

        Returns unified migration readiness report with recommendations across
        all dimensions: VPC/port-channels, contracts, L3Out, VLANs, and physical connectivity.
        """
        self._load_data()

        assessment = {
            'summary': {
                'fabric_name': self.fabric_data.get('name', 'Unknown'),
                'assessment_date': self.fabric_data.get('uploaded_at', 'Unknown'),
                'total_objects': len(self._aci_objects) if self._aci_objects else 0
            },
            'vpc_assessment': {},
            'contract_assessment': {},
            'l3out_assessment': {},
            'vlan_assessment': {},
            'physical_assessment': {},
            'overall_readiness': {},
            'critical_issues': [],
            'recommendations': []
        }

        # Run all analyses
        try:
            assessment['vpc_assessment'] = self.analyze_vpc_configuration()
        except Exception as e:
            logger.error(f"VPC assessment failed: {str(e)}")
            assessment['critical_issues'].append({
                'category': 'vpc',
                'message': 'VPC analysis failed',
                'details': str(e)
            })

        try:
            assessment['contract_assessment'] = self.analyze_contract_to_acl_translation()
        except Exception as e:
            logger.error(f"Contract assessment failed: {str(e)}")
            assessment['critical_issues'].append({
                'category': 'contracts',
                'message': 'Contract translation failed',
                'details': str(e)
            })

        try:
            assessment['l3out_assessment'] = self.analyze_l3out_connectivity()
        except Exception as e:
            logger.error(f"L3Out assessment failed: {str(e)}")
            assessment['critical_issues'].append({
                'category': 'l3out',
                'message': 'L3Out analysis failed',
                'details': str(e)
            })

        try:
            assessment['vlan_assessment'] = self.analyze_vlan_pools()
        except Exception as e:
            logger.error(f"VLAN assessment failed: {str(e)}")
            assessment['critical_issues'].append({
                'category': 'vlan',
                'message': 'VLAN analysis failed',
                'details': str(e)
            })

        try:
            assessment['physical_assessment'] = self.analyze_physical_connectivity()
        except Exception as e:
            logger.error(f"Physical assessment failed: {str(e)}")
            assessment['critical_issues'].append({
                'category': 'physical',
                'message': 'Physical connectivity analysis failed',
                'details': str(e)
            })

        # Calculate overall readiness score
        readiness_scores = []

        # VPC readiness (if available)
        if 'migration_readiness' in assessment.get('vpc_assessment', {}):
            vpc_readiness = assessment['vpc_assessment']['migration_readiness']
            if isinstance(vpc_readiness, dict) and 'percentage' in vpc_readiness:
                readiness_scores.append(vpc_readiness['percentage'])

        # Contract translation complexity
        if 'migration_readiness' in assessment.get('contract_assessment', {}):
            contract_readiness = assessment['contract_assessment']['migration_readiness']
            if isinstance(contract_readiness, dict):
                # Convert contracts to readiness score (inverse of complexity)
                avg_rules = contract_readiness.get('average_rules_per_contract', 0)
                score = 100 - min(avg_rules * 2, 50)  # Cap at 50% penalty
                readiness_scores.append(score)

        # L3Out complexity
        if 'migration_readiness' in assessment.get('l3out_assessment', {}):
            l3out_readiness = assessment['l3out_assessment']['migration_readiness']
            if isinstance(l3out_readiness, dict) and 'percentage' in l3out_readiness:
                readiness_scores.append(l3out_readiness['percentage'])

        # VLAN migration complexity
        if 'migration_summary' in assessment.get('vlan_assessment', {}):
            vlan_migration = assessment['vlan_assessment']['migration_summary']
            if isinstance(vlan_migration, dict):
                risk_level = vlan_migration.get('risk_level', 'medium')
                score = {'low': 90, 'medium': 60, 'high': 30}.get(risk_level, 50)
                readiness_scores.append(score)

        # Calculate overall score
        overall_score = sum(readiness_scores) / len(readiness_scores) if readiness_scores else 50

        assessment['overall_readiness'] = {
            'score': round(overall_score, 2),
            'level': 'high' if overall_score >= 80 else 'medium' if overall_score >= 50 else 'low',
            'component_scores': {
                'vpc': readiness_scores[0] if len(readiness_scores) > 0 else 0,
                'contracts': readiness_scores[1] if len(readiness_scores) > 1 else 0,
                'l3out': readiness_scores[2] if len(readiness_scores) > 2 else 0,
                'vlan': readiness_scores[3] if len(readiness_scores) > 3 else 0
            },
            'ready_for_migration': overall_score >= 70
        }

        # Generate unified recommendations
        if overall_score < 70:
            assessment['recommendations'].append({
                'priority': 'critical',
                'category': 'overall',
                'title': 'Additional data collection required before migration',
                'details': f'Overall readiness score: {overall_score:.1f}%. Aim for 70%+ before proceeding.'
            })

        if len(assessment['critical_issues']) > 0:
            assessment['recommendations'].append({
                'priority': 'critical',
                'category': 'data_collection',
                'title': 'Resolve analysis failures',
                'details': f'{len(assessment["critical_issues"])} analysis modules failed. Check data completeness.'
            })

        return assessment
