"""
Analysis Planning Module - Complete Implementation
Generates comprehensive migration plans with waves, timeline, and resources.
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from analysis.engine import ACIAnalyzer


class ACIPlanner:
    """Comprehensive ACI migration planner."""

    def __init__(self, fabric_data: Dict[str, Any], mode: str):
        self.fabric_data = fabric_data
        self.mode = mode
        self.analyzer = ACIAnalyzer(fabric_data)
        self.analyzer._load_data()

    def generate_plan(self) -> Dict[str, Any]:
        """Generate comprehensive migration plan."""
        return self._generate_migration_plan()

    def _generate_migration_plan(self) -> Dict[str, Any]:
        """Generate migration plan with phases, timeline, resources."""
        # Get coupling analysis
        coupling = self.analyzer.analyze_coupling_issues()

        # Get migration waves
        waves = self.analyzer.analyze_migration_waves()

        # Calculate timeline
        timeline = self._calculate_timeline(waves)

        # Generate recommendations
        recommendations = self._generate_recommendations(coupling, waves)

        # Calculate resources
        resources = self._calculate_resources(waves)

        # Risk assessment
        risk_assessment = self._assess_risks(coupling, waves)

        return {
            'migration_waves': waves.get('waves', {}),
            'wave_summary': waves.get('summary', []),
            'recommended_order': waves.get('recommended_order', []),
            'timeline': timeline,
            'recommendations': recommendations,
            'resource_requirements': resources,
            'risk_assessment': risk_assessment,
            'total_effort_days': waves.get('total_effort_days', 0),
            'ready_for_migration': coupling.get('migration_risk_score', 100) < 50,
            'migration_risk_score': coupling.get('migration_risk_score', 0)
        }

    def _calculate_timeline(self, waves: Dict) -> List[Dict]:
        """Calculate migration timeline with phases."""
        timeline = []
        start_week = 0

        for wave_name in waves.get('recommended_order', []):
            wave_epgs = waves['waves'].get(wave_name, [])
            wave_summary = next(
                (w for w in waves.get('summary', [])
                 if wave_name in w.get('wave', '').lower().replace(' ', '_')),
                None
            )

            if not wave_summary:
                continue

            duration_weeks = max(1, wave_summary.get('estimated_days', 5) // 5)

            timeline.append({
                'phase': wave_summary.get('wave', wave_name),
                'wave_id': wave_name,
                'start_week': start_week,
                'end_week': start_week + duration_weeks,
                'duration_weeks': duration_weeks,
                'epg_count': wave_summary.get('epg_count', 0),
                'complexity': wave_name.split('_')[-1],
                'effort_days': wave_summary.get('estimated_days', 0),
                'dependencies': self._get_wave_dependencies(wave_name)
            })

            start_week += duration_weeks

        return timeline

    def _get_wave_dependencies(self, wave_name: str) -> List[str]:
        """Get dependencies for a wave."""
        # Waves must be executed in order
        wave_order = ['wave1_standalone', 'wave2_low', 'wave3_medium', 'wave4_high']
        try:
            idx = wave_order.index(wave_name)
            return wave_order[:idx]
        except ValueError:
            return []

    def _generate_recommendations(self, coupling: Dict, waves: Dict) -> List[Dict]:
        """Generate actionable recommendations."""
        recommendations = []

        stats = coupling.get('statistics', {})

        # High severity coupling issues
        high_issues = stats.get('high_severity', 0)
        if high_issues > 0:
            recommendations.append({
                'id': 'coupling-high',
                'priority': 'critical',
                'category': 'coupling',
                'title': f'Resolve {high_issues} High-Severity Coupling Issues',
                'description': 'EPGs spanning multiple devices require L2 extension or phased migration',
                'action': 'Review coupling analysis and plan L2 extension strategy',
                'estimated_hours': high_issues * 2,
                'impact': 'Blocking - must resolve before migration',
                'details': coupling.get('detailed_issues', [])[:5]
            })

        # VLAN overlaps
        shared_vlans = stats.get('shared_vlans', 0)
        if shared_vlans > 10:
            recommendations.append({
                'id': 'vlan-overlap',
                'priority': 'high',
                'category': 'vlan',
                'title': f'VLAN Namespace Conflicts ({shared_vlans} VLANs)',
                'description': 'Multiple EPGs sharing the same VLAN IDs',
                'action': 'Create VLAN remapping table and allocate new ranges',
                'estimated_hours': 8,
                'impact': 'High - may cause connectivity issues',
                'details': []
            })

        # VPC asymmetry
        vpc_issues = stats.get('vpc_asymmetry', 0)
        if vpc_issues > 0:
            recommendations.append({
                'id': 'vpc-asymmetry',
                'priority': 'high',
                'category': 'vpc',
                'title': f'VPC Asymmetry Detected ({vpc_issues} cases)',
                'description': 'EPGs have asymmetric attachments across VPC pairs',
                'action': 'Balance EPG attachments across VPC leaf pairs',
                'estimated_hours': vpc_issues * 1.5,
                'impact': 'High - impacts redundancy',
                'details': []
            })

        # Migration wave ordering
        recommendations.append({
            'id': 'wave-order',
            'priority': 'medium',
            'category': 'planning',
            'title': 'Follow Recommended Migration Wave Order',
            'description': 'Migrate standalone EPGs first, then progressively complex configurations',
            'action': f'Start with Wave 1 - {len(waves.get("waves", {}).get("wave1_standalone", []))} standalone EPGs',
            'estimated_hours': 0,
            'impact': 'Medium - reduces migration risk',
            'details': []
        })

        # Consolidation opportunities
        recommendations.append({
            'id': 'consolidation',
            'priority': 'low',
            'category': 'optimization',
            'title': 'FEX Consolidation Opportunities',
            'description': 'Underutilized FEX devices can be consolidated',
            'action': 'Review port utilization analysis for consolidation candidates',
            'estimated_hours': 16,
            'impact': 'Low - cost optimization',
            'details': []
        })

        return recommendations

    def _calculate_resources(self, waves: Dict) -> Dict[str, Any]:
        """Calculate resource requirements."""
        total_epgs = sum(
            len(wave_epgs)
            for wave_epgs in waves.get('waves', {}).values()
        )

        total_effort_days = waves.get('total_effort_days', 0)

        # Estimate personnel needs
        engineers_needed = max(2, total_effort_days // 20)  # 20 days per engineer

        return {
            'total_epgs': total_epgs,
            'total_effort_days': total_effort_days,
            'total_effort_weeks': total_effort_days / 5,
            'engineers_needed': engineers_needed,
            'estimated_duration_weeks': total_effort_days / (5 * engineers_needed),
            'roles_required': [
                {'role': 'Network Architect', 'count': 1, 'effort': '100%'},
                {'role': 'Network Engineer', 'count': engineers_needed - 1, 'effort': '100%'},
                {'role': 'Project Manager', 'count': 1, 'effort': '50%'},
                {'role': 'Security Engineer', 'count': 1, 'effort': '25%'}
            ],
            'equipment_needed': [
                {'item': 'Spine switches', 'quantity': 2, 'notes': 'Core fabric capacity'},
                {'item': 'Leaf switches', 'quantity': len(self.analyzer._leafs), 'notes': 'Replace/upgrade existing'},
                {'item': 'Migration toolkit', 'quantity': 1, 'notes': 'Automation tools'}
            ]
        }

    def _assess_risks(self, coupling: Dict, waves: Dict) -> Dict[str, Any]:
        """Assess migration risks."""
        risk_score = coupling.get('migration_risk_score', 0)

        if risk_score < 30:
            risk_level = 'low'
            risk_description = 'Low risk - straightforward migration'
        elif risk_score < 60:
            risk_level = 'medium'
            risk_description = 'Medium risk - some complexity, manageable'
        else:
            risk_level = 'high'
            risk_description = 'High risk - significant complexity, requires careful planning'

        risks = []

        stats = coupling.get('statistics', {})

        if stats.get('multi_device_epgs', 0) > 0:
            risks.append({
                'category': 'Coupling',
                'severity': 'high',
                'description': f'{stats["multi_device_epgs"]} EPGs span multiple devices',
                'mitigation': 'Plan L2 extension or phased migration'
            })

        if stats.get('cross_tenant_contracts', 0) > 0:
            risks.append({
                'category': 'Security',
                'severity': 'medium',
                'description': 'Cross-tenant contracts detected',
                'mitigation': 'Review and document contract dependencies'
            })

        if len(self.analyzer._leafs) > 20:
            risks.append({
                'category': 'Scale',
                'severity': 'medium',
                'description': 'Large fabric (>20 leafs) increases complexity',
                'mitigation': 'Consider phased approach by pod/datacenter'
            })

        return {
            'overall_risk_score': risk_score,
            'risk_level': risk_level,
            'risk_description': risk_description,
            'specific_risks': risks,
            'confidence_level': 'high' if risk_score < 40 else 'medium' if risk_score < 70 else 'low'
        }

def generate_migration_plan(fabric_data: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """Generate migration plan - public API."""
    planner = ACIPlanner(fabric_data, mode)
    return planner.generate_plan()
