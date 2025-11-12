"""
VLAN Pool and Namespace Management Analysis Module
Analyzes ACI VLAN pools, allocation domains, encapsulation usage,
and namespace management for complete migration planning.
"""
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class VLANRange:
    """Represents a VLAN range allocation."""
    from_vlan: int
    to_vlan: int
    allocation_mode: str  # static, dynamic
    pool_name: str
    role: str  # external, internal


class VLANPoolAnalyzer:
    """
    Analyzes ACI VLAN pool configurations and namespace management.

    Supports:
    - VLAN pool identification and range extraction
    - Allocation mode analysis (static vs dynamic)
    - VLAN usage and consumption tracking
    - Namespace conflict detection
    - Pool-to-domain mapping (physical, VMM, L3)
    - Migration planning for VLAN re-numbering
    - Encapsulation overlap detection
    - VLAN optimization recommendations
    """

    def __init__(self, aci_objects: List[Dict[str, Any]]):
        """
        Initialize VLAN pool analyzer with ACI object data.

        Args:
            aci_objects: List of parsed ACI objects from JSON/XML
        """
        self.aci_objects = aci_objects

        # Categorized objects
        self._vlan_pools = []
        self._vlan_ranges = []
        self._physical_domains = []
        self._vmm_domains = []
        self._l3_domains = []
        self._epgs = []
        self._path_attachments = []

        # Lookup dictionaries
        self._pool_by_dn = {}
        self._domain_pool_map = defaultdict(set)
        self._vlan_usage_map = defaultdict(list)

        self._categorize_objects()

    def _categorize_objects(self):
        """Extract VLAN pool-related objects from ACI data."""
        for obj in self.aci_objects:
            obj_type = obj.get('type')
            attrs = obj.get('attributes', {})
            dn = attrs.get('dn', '')

            # VLAN pools
            if obj_type == 'fvnsVlanInstP':
                self._vlan_pools.append(attrs)
                if dn:
                    self._pool_by_dn[dn] = attrs

            # VLAN ranges (blocks within pools)
            elif obj_type == 'fvnsEncapBlk':
                self._vlan_ranges.append(attrs)

            # Physical domains
            elif obj_type == 'physDomP':
                self._physical_domains.append(attrs)

            # VMM domains
            elif obj_type == 'vmmDomP':
                self._vmm_domains.append(attrs)

            # L3 domains
            elif obj_type == 'l3extDomP':
                self._l3_domains.append(attrs)

            # EPGs (for VLAN usage tracking)
            elif obj_type == 'fvAEPg':
                self._epgs.append(attrs)

            # Path attachments (for encapsulation usage)
            elif obj_type == 'fvRsPathAtt':
                self._path_attachments.append(attrs)
                # Track VLAN usage
                encap = attrs.get('encap', '')
                if encap.startswith('vlan-'):
                    vlan_id = int(encap.split('-')[1])
                    self._vlan_usage_map[vlan_id].append({
                        'epg_dn': self._extract_epg_from_path_dn(attrs.get('dn', '')),
                        'interface': attrs.get('tDn', '')
                    })

        logger.info(
            f"VLAN Pool Analysis: Found {len(self._vlan_pools)} VLAN pools, "
            f"{len(self._vlan_ranges)} VLAN ranges, "
            f"{len(self._physical_domains)} physical domains, "
            f"{len(self._vmm_domains)} VMM domains"
        )

    def analyze_vlan_pools(self) -> Dict[str, Any]:
        """
        Analyze all VLAN pool configurations.

        Returns:
            Dictionary containing:
            - pools: List of VLAN pools with ranges and allocations
            - total_pools: Count of VLAN pools
            - allocation_modes: Distribution by allocation mode
            - total_vlans_allocated: Total VLAN IDs allocated across all pools
            - fragmentation: Pool fragmentation metrics
        """
        results = {
            'pools': [],
            'total_pools': len(self._vlan_pools),
            'allocation_modes': {'static': 0, 'dynamic': 0},
            'total_vlans_allocated': 0,
            'fragmentation': {
                'highly_fragmented': 0,  # >5 ranges per pool
                'moderately_fragmented': 0,  # 2-5 ranges
                'contiguous': 0  # 1 range
            }
        }

        for pool in self._vlan_pools:
            dn = pool.get('dn', '')
            name = pool.get('name')
            alloc_mode = pool.get('allocMode', 'static')

            # Count allocation mode
            if alloc_mode in results['allocation_modes']:
                results['allocation_modes'][alloc_mode] += 1

            # Find VLAN ranges in this pool
            ranges = self._get_vlan_ranges_for_pool(dn)

            # Calculate pool statistics
            vlan_count = sum(r['to_vlan'] - r['from_vlan'] + 1 for r in ranges)
            results['total_vlans_allocated'] += vlan_count

            # Assess fragmentation
            range_count = len(ranges)
            if range_count == 1:
                results['fragmentation']['contiguous'] += 1
                fragmentation_level = 'contiguous'
            elif range_count <= 5:
                results['fragmentation']['moderately_fragmented'] += 1
                fragmentation_level = 'moderate'
            else:
                results['fragmentation']['highly_fragmented'] += 1
                fragmentation_level = 'high'

            # Find domains using this pool
            domains = self._get_domains_for_pool(dn)

            # Check for VLAN overlap with other pools
            overlaps = self._check_pool_overlap(ranges, dn)

            pool_info = {
                'name': name,
                'dn': dn,
                'allocation_mode': alloc_mode,
                'ranges': ranges,
                'range_count': range_count,
                'vlan_count': vlan_count,
                'fragmentation': fragmentation_level,
                'domains': domains,
                'domain_count': len(domains),
                'overlaps': overlaps,
                'migration_complexity': self._assess_pool_migration_complexity(
                    alloc_mode, range_count, vlan_count, overlaps
                )
            }

            results['pools'].append(pool_info)

        return results

    def analyze_vlan_usage(self) -> Dict[str, Any]:
        """
        Analyze VLAN usage across the fabric.

        Returns:
            Dictionary containing:
            - used_vlans: Set of VLAN IDs currently in use
            - unused_vlans: VLAN IDs allocated but not used
            - usage_by_vlan: Detailed usage per VLAN ID
            - top_vlans: Most heavily used VLANs
            - utilization_rate: Percentage of allocated VLANs in use
        """
        pool_analysis = self.analyze_vlan_pools()

        # Get all allocated VLANs from pools
        allocated_vlans = set()
        for pool in pool_analysis['pools']:
            for range_info in pool['ranges']:
                for vlan_id in range(range_info['from_vlan'], range_info['to_vlan'] + 1):
                    allocated_vlans.add(vlan_id)

        # Get used VLANs
        used_vlans = set(self._vlan_usage_map.keys())

        # Calculate unused VLANs
        unused_vlans = allocated_vlans - used_vlans

        # Usage details per VLAN
        usage_by_vlan = []
        for vlan_id in sorted(used_vlans):
            usages = self._vlan_usage_map[vlan_id]
            usage_by_vlan.append({
                'vlan_id': vlan_id,
                'usage_count': len(usages),
                'epgs': list(set(u['epg_dn'] for u in usages)),
                'interfaces': [u['interface'] for u in usages]
            })

        # Top VLANs by usage
        top_vlans = sorted(usage_by_vlan, key=lambda x: x['usage_count'], reverse=True)[:20]

        # Utilization rate
        utilization_rate = (len(used_vlans) / len(allocated_vlans) * 100) if allocated_vlans else 0

        results = {
            'used_vlans': sorted(list(used_vlans)),
            'unused_vlans': sorted(list(unused_vlans)),
            'usage_by_vlan': usage_by_vlan,
            'top_vlans': top_vlans,
            'statistics': {
                'allocated': len(allocated_vlans),
                'used': len(used_vlans),
                'unused': len(unused_vlans),
                'utilization_rate': round(utilization_rate, 2)
            }
        }

        return results

    def detect_namespace_conflicts(self) -> Dict[str, Any]:
        """
        Detect VLAN namespace conflicts and overlaps.

        Returns:
            Dictionary containing:
            - conflicts: List of VLAN ID conflicts between pools/domains
            - pool_overlaps: Overlapping VLAN ranges between pools
            - recommendations: Conflict resolution recommendations
        """
        pool_analysis = self.analyze_vlan_pools()

        conflicts = []
        pool_overlaps = []

        # Check for overlaps between pools
        pools = pool_analysis['pools']
        for i, pool1 in enumerate(pools):
            for pool2 in pools[i+1:]:
                overlap = self._find_range_overlap(pool1['ranges'], pool2['ranges'])
                if overlap:
                    pool_overlaps.append({
                        'pool1': pool1['name'],
                        'pool2': pool2['name'],
                        'overlapping_vlans': overlap,
                        'severity': 'high' if len(overlap) > 100 else 'medium' if len(overlap) > 10 else 'low'
                    })

        # Check for VLANs used in multiple domains with different purposes
        vlan_domain_map = defaultdict(set)
        for domain_type, domains in [('physical', self._physical_domains),
                                      ('vmm', self._vmm_domains),
                                      ('l3', self._l3_domains)]:
            for domain in domains:
                pool_dn = self._get_pool_for_domain(domain.get('dn', ''))
                if pool_dn:
                    pool = self._pool_by_dn.get(pool_dn)
                    if pool:
                        for range_info in self._get_vlan_ranges_for_pool(pool_dn):
                            for vlan_id in range(range_info['from_vlan'], range_info['to_vlan'] + 1):
                                vlan_domain_map[vlan_id].add((domain_type, domain.get('name', 'unknown')))

        # Find VLANs used across multiple domain types
        for vlan_id, domain_set in vlan_domain_map.items():
            if len(domain_set) > 1:
                domain_types = set(dt for dt, _ in domain_set)
                if len(domain_types) > 1:
                    conflicts.append({
                        'vlan_id': vlan_id,
                        'domains': [{'type': dt, 'name': dn} for dt, dn in domain_set],
                        'conflict_type': 'cross_domain',
                        'severity': 'high',
                        'description': f'VLAN {vlan_id} used in multiple domain types: {", ".join(domain_types)}'
                    })

        # Generate recommendations
        recommendations = []

        if pool_overlaps:
            recommendations.append({
                'priority': 'high',
                'category': 'pool_overlap',
                'title': f'{len(pool_overlaps)} VLAN pool overlaps detected',
                'action': 'Review and consolidate overlapping VLAN pools',
                'details': 'Overlapping pools can cause encapsulation conflicts'
            })

        if conflicts:
            recommendations.append({
                'priority': 'critical',
                'category': 'namespace_conflict',
                'title': f'{len(conflicts)} VLAN namespace conflicts detected',
                'action': 'Resolve VLAN ID conflicts before migration',
                'details': 'Same VLAN used for different purposes in different domains'
            })

        return {
            'conflicts': conflicts,
            'pool_overlaps': pool_overlaps,
            'recommendations': recommendations,
            'conflict_count': len(conflicts),
            'overlap_count': len(pool_overlaps)
        }

    def generate_vlan_migration_plan(self) -> Dict[str, Any]:
        """
        Generate VLAN migration and re-numbering plan.

        Returns:
            Dictionary containing:
            - migration_strategy: Recommended approach (direct mapping, renumbering, consolidation)
            - vlan_mapping: Old VLAN to new VLAN mapping
            - consolidation_opportunities: VLANs that can be merged
            - risk_assessment: Migration risk factors
        """
        pool_analysis = self.analyze_vlan_pools()
        usage_analysis = self.analyze_vlan_usage()
        conflict_analysis = self.detect_namespace_conflicts()

        # Determine migration strategy
        strategy = 'direct_mapping'  # Default: keep same VLAN IDs
        reasons = []

        if conflict_analysis['conflict_count'] > 0:
            strategy = 'renumbering_required'
            reasons.append('Namespace conflicts detected')

        if pool_analysis['fragmentation']['highly_fragmented'] > 0:
            strategy = 'consolidation'
            reasons.append('Highly fragmented VLAN pools')

        if usage_analysis['statistics']['utilization_rate'] < 50:
            strategy = 'consolidation'
            reasons.append('Low VLAN utilization (<50%)')

        # Generate VLAN mapping (for renumbering scenarios)
        vlan_mapping = []
        if strategy == 'renumbering_required':
            vlan_mapping = self._generate_vlan_renumbering_map(
                usage_analysis['used_vlans'],
                conflict_analysis['conflicts']
            )

        # Identify consolidation opportunities
        consolidation_opportunities = []
        if strategy == 'consolidation':
            consolidation_opportunities = self._identify_consolidation_opportunities(
                pool_analysis['pools'],
                usage_analysis['usage_by_vlan']
            )

        # Risk assessment
        risk_factors = []

        if len(usage_analysis['used_vlans']) > 500:
            risk_factors.append({
                'factor': 'High VLAN count',
                'impact': 'Complex migration with many VLAN translations',
                'mitigation': 'Automate VLAN mapping with scripts'
            })

        if conflict_analysis['conflict_count'] > 10:
            risk_factors.append({
                'factor': 'Multiple namespace conflicts',
                'impact': 'Requires careful VLAN renumbering',
                'mitigation': 'Plan cutover in maintenance window with rollback plan'
            })

        if pool_analysis['allocation_modes']['dynamic'] > 0:
            risk_factors.append({
                'factor': 'Dynamic VLAN allocation in use',
                'impact': 'Target platform may not support dynamic allocation',
                'mitigation': 'Convert to static allocation before migration'
            })

        return {
            'migration_strategy': strategy,
            'strategy_reasons': reasons,
            'vlan_mapping': vlan_mapping,
            'consolidation_opportunities': consolidation_opportunities,
            'risk_assessment': {
                'risk_level': 'high' if len(risk_factors) > 2 else 'medium' if len(risk_factors) > 0 else 'low',
                'risk_factors': risk_factors
            },
            'migration_steps': self._generate_migration_steps(strategy)
        }

    def _get_vlan_ranges_for_pool(self, pool_dn: str) -> List[Dict[str, Any]]:
        """Get VLAN ranges for a specific pool."""
        ranges = []

        for vlan_range in self._vlan_ranges:
            range_dn = vlan_range.get('dn', '')
            if range_dn.startswith(pool_dn):
                from_vlan = self._parse_vlan_id(vlan_range.get('from', 'vlan-1'))
                to_vlan = self._parse_vlan_id(vlan_range.get('to', 'vlan-1'))
                alloc_mode = vlan_range.get('allocMode', 'inherit')
                role = vlan_range.get('role', 'external')

                ranges.append({
                    'from_vlan': from_vlan,
                    'to_vlan': to_vlan,
                    'allocation_mode': alloc_mode,
                    'role': role,
                    'vlan_count': to_vlan - from_vlan + 1
                })

        return ranges

    def _parse_vlan_id(self, vlan_str: str) -> int:
        """Parse VLAN ID from string format (e.g., 'vlan-100' -> 100)."""
        if vlan_str.startswith('vlan-'):
            return int(vlan_str.split('-')[1])
        return int(vlan_str)

    def _get_domains_for_pool(self, pool_dn: str) -> List[Dict[str, Any]]:
        """Get domains (physical, VMM, L3) that use a specific VLAN pool."""
        domains = []

        # Check physical domains
        for domain in self._physical_domains:
            if self._domain_uses_pool(domain.get('dn', ''), pool_dn):
                domains.append({
                    'type': 'physical',
                    'name': domain.get('name'),
                    'dn': domain.get('dn')
                })

        # Check VMM domains
        for domain in self._vmm_domains:
            if self._domain_uses_pool(domain.get('dn', ''), pool_dn):
                domains.append({
                    'type': 'vmm',
                    'name': domain.get('name'),
                    'dn': domain.get('dn')
                })

        # Check L3 domains
        for domain in self._l3_domains:
            if self._domain_uses_pool(domain.get('dn', ''), pool_dn):
                domains.append({
                    'type': 'l3',
                    'name': domain.get('name'),
                    'dn': domain.get('dn')
                })

        return domains

    def _domain_uses_pool(self, domain_dn: str, pool_dn: str) -> bool:
        """Check if a domain uses a specific VLAN pool."""
        # Look for rsVlanNs relationship
        for obj in self.aci_objects:
            if obj.get('type') in ['infraRsVlanNs', 'vmmRsVlanNs', 'l3extRsVlanNs']:
                attrs = obj.get('attributes', {})
                if attrs.get('dn', '').startswith(domain_dn):
                    target_dn = attrs.get('tDn', '')
                    if target_dn == pool_dn:
                        return True
        return False

    def _get_pool_for_domain(self, domain_dn: str) -> Optional[str]:
        """Get VLAN pool DN for a domain."""
        for obj in self.aci_objects:
            if obj.get('type') in ['infraRsVlanNs', 'vmmRsVlanNs', 'l3extRsVlanNs']:
                attrs = obj.get('attributes', {})
                if attrs.get('dn', '').startswith(domain_dn):
                    return attrs.get('tDn')
        return None

    def _check_pool_overlap(self, ranges: List[Dict[str, Any]], exclude_pool_dn: str) -> List[Dict[str, Any]]:
        """Check if a pool's ranges overlap with other pools."""
        overlaps = []

        for other_pool in self._vlan_pools:
            other_dn = other_pool.get('dn', '')
            if other_dn == exclude_pool_dn:
                continue

            other_ranges = self._get_vlan_ranges_for_pool(other_dn)
            overlap_vlans = self._find_range_overlap(ranges, other_ranges)

            if overlap_vlans:
                overlaps.append({
                    'pool_name': other_pool.get('name'),
                    'pool_dn': other_dn,
                    'overlapping_vlans': overlap_vlans,
                    'overlap_count': len(overlap_vlans)
                })

        return overlaps

    def _find_range_overlap(self, ranges1: List[Dict[str, Any]], ranges2: List[Dict[str, Any]]) -> List[int]:
        """Find overlapping VLAN IDs between two sets of ranges."""
        set1 = set()
        for r in ranges1:
            set1.update(range(r['from_vlan'], r['to_vlan'] + 1))

        set2 = set()
        for r in ranges2:
            set2.update(range(r['from_vlan'], r['to_vlan'] + 1))

        overlap = sorted(list(set1 & set2))
        return overlap

    def _assess_pool_migration_complexity(self, alloc_mode: str, range_count: int,
                                          vlan_count: int, overlaps: List[Dict]) -> str:
        """Assess migration complexity for a VLAN pool."""
        score = 0

        # Dynamic allocation adds complexity
        if alloc_mode == 'dynamic':
            score += 30

        # Fragmentation adds complexity
        if range_count > 5:
            score += 20
        elif range_count > 1:
            score += 10

        # Large pools add complexity
        if vlan_count > 500:
            score += 20
        elif vlan_count > 100:
            score += 10

        # Overlaps add complexity
        if overlaps:
            score += len(overlaps) * 15

        if score < 30:
            return 'low'
        elif score < 60:
            return 'medium'
        else:
            return 'high'

    def _generate_vlan_renumbering_map(self, used_vlans: List[int],
                                        conflicts: List[Dict]) -> List[Dict[str, Any]]:
        """Generate VLAN renumbering mapping to resolve conflicts."""
        mapping = []

        # Identify VLANs that need renumbering (those in conflicts)
        conflict_vlans = set(c['vlan_id'] for c in conflicts)

        # Allocate new VLAN IDs from a clean range (e.g., 2000-2999)
        new_vlan_start = 2000
        new_vlan_current = new_vlan_start

        for old_vlan in sorted(conflict_vlans):
            mapping.append({
                'old_vlan': old_vlan,
                'new_vlan': new_vlan_current,
                'reason': 'Conflict resolution'
            })
            new_vlan_current += 1

        return mapping

    def _identify_consolidation_opportunities(self, pools: List[Dict],
                                               usage_by_vlan: List[Dict]) -> List[Dict[str, Any]]:
        """Identify opportunities to consolidate VLAN pools."""
        opportunities = []

        # Find lightly used pools (utilization < 30%)
        for pool in pools:
            pool_vlans = set()
            for range_info in pool['ranges']:
                pool_vlans.update(range(range_info['from_vlan'], range_info['to_vlan'] + 1))

            used_in_pool = sum(1 for v in usage_by_vlan if v['vlan_id'] in pool_vlans)
            utilization = (used_in_pool / len(pool_vlans) * 100) if pool_vlans else 0

            if utilization < 30 and len(pool_vlans) > 50:
                opportunities.append({
                    'pool_name': pool['name'],
                    'allocated_vlans': len(pool_vlans),
                    'used_vlans': used_in_pool,
                    'utilization': round(utilization, 2),
                    'recommendation': 'Consolidate with other pools or reduce range'
                })

        return opportunities

    def _generate_migration_steps(self, strategy: str) -> List[str]:
        """Generate migration steps based on strategy."""
        if strategy == 'direct_mapping':
            return [
                '1. Document current VLAN allocations',
                '2. Configure same VLAN IDs on target platform',
                '3. Migrate EPG-by-EPG with VLAN preservation',
                '4. Verify VLAN connectivity after each EPG migration'
            ]
        elif strategy == 'renumbering_required':
            return [
                '1. Document all current VLAN assignments',
                '2. Generate conflict-free VLAN mapping',
                '3. Pre-configure new VLANs on target platform',
                '4. Migrate with VLAN translation (staged approach)',
                '5. Update documentation and network diagrams',
                '6. Verify end-to-end connectivity'
            ]
        elif strategy == 'consolidation':
            return [
                '1. Analyze VLAN usage and identify unused VLANs',
                '2. Design consolidated VLAN scheme',
                '3. Create VLAN mapping (old to new)',
                '4. Configure target platform with optimized VLAN ranges',
                '5. Migrate with VLAN consolidation',
                '6. Reclaim unused VLAN IDs'
            ]
        else:
            return ['Custom migration plan required']

    def _extract_epg_from_path_dn(self, dn: str) -> str:
        """Extract EPG DN from path attachment DN."""
        match = re.search(r'(uni/tn-[^/]+/ap-[^/]+/epg-[^/]+)', dn)
        return match.group(1) if match else ''

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of VLAN pool analysis."""
        pool_analysis = self.analyze_vlan_pools()
        usage_analysis = self.analyze_vlan_usage()
        conflict_analysis = self.detect_namespace_conflicts()
        migration_plan = self.generate_vlan_migration_plan()

        return {
            'pool_summary': {
                'total_pools': pool_analysis['total_pools'],
                'total_vlans_allocated': pool_analysis['total_vlans_allocated'],
                'allocation_modes': pool_analysis['allocation_modes']
            },
            'usage_summary': usage_analysis['statistics'],
            'conflict_summary': {
                'conflicts': conflict_analysis['conflict_count'],
                'overlaps': conflict_analysis['overlap_count']
            },
            'migration_summary': {
                'strategy': migration_plan['migration_strategy'],
                'risk_level': migration_plan['risk_assessment']['risk_level'],
                'mapping_required': len(migration_plan['vlan_mapping']) > 0
            }
        }
