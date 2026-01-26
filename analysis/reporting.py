"""
Comprehensive Reporting Module for ACI Migrator
Generates professional reports in CSV, Markdown, HTML, and JSON formats.
"""
from typing import Dict, Any, List
from datetime import datetime
import json
import csv
from io import StringIO


def generate_report(fabric_data: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """
    Generate comprehensive analysis report.

    Args:
        fabric_data: Complete fabric data including datasets and metadata
        mode: Migration mode (fixed)

    Returns:
        Dictionary with all report sections
    """
    from analysis.engine import ACIAnalyzer
    from analysis.planning import ACIPlanner

    # Initialize analyzer
    analyzer = ACIAnalyzer(fabric_data)
    analyzer._load_data()

    # Initialize planner
    planner = ACIPlanner(fabric_data, mode)

    # Collect all analysis data
    port_util = analyzer.analyze_port_utilization()
    leaf_fex = analyzer.analyze_leaf_fex_mapping()
    vlan_dist = analyzer.analyze_vlan_distribution()
    epg_complex = analyzer.analyze_epg_complexity()
    migration_flags = analyzer.analyze_migration_flags()
    vpc_symmetry = analyzer.analyze_vpc_symmetry()
    contract_scope = analyzer.analyze_contract_scope()
    coupling = analyzer.analyze_coupling_issues()

    # Get planning data
    plan_data = planner.generate_plan()

    # Build comprehensive report
    report = {
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'fabric_name': fabric_data.get('name', 'Unknown'),
        'datasets': fabric_data.get('datasets', []),

        # Summary statistics
        'summary_stats': _generate_summary_stats(analyzer, mode),

        # Executive summary
        'executive_summary': _generate_executive_summary(
            analyzer, plan_data, mode
        ),

        # Migration opportunities
        'opportunities': _generate_opportunities(
            port_util, vlan_dist, epg_complex, coupling
        ),

        # Requirements and prerequisites
        'requirements': _generate_requirements(mode, plan_data),

        # Detailed analyses
        'analyses': {
            'port_utilization': port_util,
            'leaf_fex_mapping': leaf_fex,
            'vlan_distribution': vlan_dist,
            'epg_complexity': epg_complex,
            'migration_flags': migration_flags,
            'vpc_symmetry': vpc_symmetry,
            'contract_scope': contract_scope,
            'coupling_issues': coupling
        },

        # Migration plan
        'migration_plan': plan_data,

        # Recommendations
        'recommendations': _generate_recommendations(
            analyzer, plan_data, mode, coupling
        ),

        # Risk assessment
        'risks': plan_data.get('risk_assessment', {}),

        # Resource requirements
        'resources': plan_data.get('resource_requirements', {})
    }

    return report


def _generate_summary_stats(analyzer, mode: str) -> List[Dict[str, Any]]:
    """Generate high-level summary statistics."""
    stats = [
        {
            'category': 'Infrastructure',
            'metrics': [
                {'label': 'Total Leaf Switches', 'value': len(analyzer._leafs)},
                {'label': 'Total FEX Devices', 'value': len(analyzer._fexes)},
                {'label': 'Total Interfaces', 'value': len(analyzer._interfaces)}
            ]
        },
        {
            'category': 'Logical Configuration',
            'metrics': [
                {'label': 'Total Tenants', 'value': len(analyzer._tenants)},
                {'label': 'Total VRFs', 'value': len(analyzer._vrfs)},
                {'label': 'Total Bridge Domains', 'value': len(analyzer._bds)},
                {'label': 'Total EPGs', 'value': len(analyzer._epgs)},
                {'label': 'Total Contracts', 'value': len(analyzer._contracts)}
            ]
        }
    ]

    waves = analyzer.analyze_migration_waves()
    stats.append({
        'category': 'Migration Readiness',
        'metrics': [
            {'label': 'Migration Waves', 'value': len(waves.get('waves', {}))},
            {'label': 'Total EPGs to Migrate', 'value': len(analyzer._epgs)},
            {'label': 'Estimated Timeline (weeks)', 'value': waves.get('total_effort_days', 0) // 5}
        ]
    })

    return stats


def _generate_executive_summary(analyzer, plan_data: Dict, mode: str) -> str:
    """Generate executive summary text."""
    summary_parts = []

    # Overview
    summary_parts.append(
        "This report provides a comprehensive analysis of the ACI fabric "
        "for migration planning."
    )

    # Infrastructure summary
    summary_parts.append(
        f"\n\nThe fabric consists of {len(analyzer._leafs)} leaf switches, "
        f"{len(analyzer._fexes)} FEX devices, and {len(analyzer._epgs)} EPGs "
        f"across {len(analyzer._tenants)} tenants."
    )

    risk_score = plan_data.get('migration_risk_score', 0)
    if risk_score < 30:
        readiness = "excellent"
    elif risk_score < 50:
        readiness = "good"
    elif risk_score < 70:
        readiness = "moderate"
    else:
        readiness = "challenging"

    summary_parts.append(
        f"\n\nMigration readiness assessment: {readiness.upper()} "
        f"(risk score: {risk_score}/100). "
    )

    total_weeks = plan_data.get('total_effort_days', 0) // 5
    summary_parts.append(
        f"The estimated migration timeline is {total_weeks} weeks, "
        f"organized into {len(plan_data.get('migration_waves', {}))} waves."
    )

    return ''.join(summary_parts)


def _generate_opportunities(
    port_util: List,
    vlan_dist: Dict,
    epg_complex: List,
    coupling: Dict
) -> List[Dict[str, Any]]:
    """Identify optimization opportunities."""
    opportunities = []

    # Port consolidation opportunities
    consolidation_candidates = sum(
        1 for p in port_util if p.get('consolidation_score', 0) >= 60
    )
    if consolidation_candidates > 0:
        opportunities.append({
            'title': 'Port Consolidation',
            'description': f'{consolidation_candidates} ports identified as consolidation candidates',
            'impact': 'Medium',
            'effort': 'Low',
            'savings': f'~{consolidation_candidates * 2} ports'
        })

    # VLAN optimization
    total_vlans = vlan_dist.get('statistics', {}).get('total_vlans_used', 0)
    overlaps = len(vlan_dist.get('overlaps', []))
    if overlaps > 0:
        opportunities.append({
            'title': 'VLAN Namespace Optimization',
            'description': f'{overlaps} VLAN overlaps detected across {total_vlans} total VLANs',
            'impact': 'High',
            'effort': 'Medium',
            'savings': 'Reduced complexity'
        })

    # EPG complexity reduction
    complex_epgs = sum(1 for e in epg_complex if e.get('complexity_score', 0) >= 70)
    if complex_epgs > 0:
        opportunities.append({
            'title': 'EPG Simplification',
            'description': f'{complex_epgs} highly complex EPGs can be simplified',
            'impact': 'Medium',
            'effort': 'High',
            'savings': 'Easier migration'
        })

    # Decoupling opportunities
    high_coupling = coupling.get('high_coupling_groups', [])
    if len(high_coupling) > 0:
        opportunities.append({
            'title': 'Tenant Decoupling',
            'description': f'{len(high_coupling)} tenant groups with high coupling',
            'impact': 'High',
            'effort': 'High',
            'savings': 'Independent migration waves'
        })

    return opportunities


def _generate_requirements(mode: str, plan_data: Dict) -> List[Dict[str, Any]]:
    """Generate requirements and prerequisites."""
    requirements = []

    requirements.extend([
        {
            'category': 'Infrastructure',
            'items': [
                'Target fabric capacity validated for current workload',
                'Sufficient switch ports for migration period',
                'Network connectivity for staged migration'
            ]
        },
        {
            'category': 'Network Configuration',
            'items': [
                'IP addressing plan for the target fabric',
                'Routing design and control-plane plan',
                'VLAN allocation and remapping plan',
                'Multicast or replication strategy (if applicable)'
            ]
        },
        {
            'category': 'Team Resources',
            'items': [
                f"Network engineers: {plan_data.get('resource_requirements', {}).get('engineers', 2)}",
                f"Estimated effort: {plan_data.get('total_effort_days', 0)} person-days",
                'Migration runbooks and change windows'
            ]
        },
        {
            'category': 'Testing',
            'items': [
                'Lab environment or staging fabric for validation',
                'Test plans for each migration wave',
                'Rollback procedures documented'
            ]
        }
    ])

    return requirements


def _generate_recommendations(
    analyzer,
    plan_data: Dict,
    mode: str,
    coupling: Dict
) -> List[Dict[str, Any]]:
    """Generate actionable recommendations."""
    recommendations = []

    # Get migration flags
    flags = analyzer.analyze_migration_flags()

    recommendations.append({
        'priority': 'Critical',
        'title': 'Follow Wave-Based Migration',
        'description': 'Execute migration in planned waves to minimize risk',
        'action_items': [
            f"Start with Wave 1: {plan_data.get('migration_waves', {}).get('wave1_standalone', {}).get('epg_count', 0)} standalone EPGs",
            'Validate each wave before proceeding to next',
            'Maintain parallel operation during transition'
        ]
    })

    if coupling.get('migration_risk_score', 0) > 50:
        recommendations.append({
            'priority': 'High',
            'title': 'Address High Tenant Coupling',
            'description': 'High interdependencies detected between tenants',
            'action_items': [
                'Review shared contracts and refactor if possible',
                'Consider migrating coupled tenants together',
                'Document all cross-tenant dependencies'
            ]
        })

    # VLAN recommendations
    vlan_dist = analyzer.analyze_vlan_distribution()
    if len(vlan_dist.get('overlaps', [])) > 0:
        recommendations.append({
            'priority': 'Medium',
            'title': 'Resolve VLAN Overlaps',
            'description': f"{len(vlan_dist['overlaps'])} VLAN overlaps require resolution",
            'action_items': [
                'Review overlapping VLAN allocations',
                'Plan VLAN remapping to avoid conflicts',
                'Update documentation with final VLAN mapping'
            ]
        })

    # Flag-based recommendations
    for flag in flags[:5]:  # Top 5 flags
        if flag.get('severity') in ['Critical', 'High']:
            recommendations.append({
                'priority': flag['severity'],
                'title': flag['description'],
                'description': f"Found in: {flag.get('object', 'Multiple objects')}",
                'action_items': [flag.get('recommendation', 'Review configuration')]
            })

    return recommendations


def generate_markdown_report(fabric_data: Dict[str, Any], mode: str) -> str:
    """Generate comprehensive Markdown report."""
    report = generate_report(fabric_data, mode)

    md_parts = []

    # Header
    md_parts.append("# ACI Migration Analysis Report\n\n")
    md_parts.append(f"**Fabric:** {report['fabric_name']}  \n")
    md_parts.append(f"**Generated:** {report['generated']}  \n")

    md_parts.append("---\n\n")

    # Executive Summary
    md_parts.append("## Executive Summary\n\n")
    md_parts.append(report['executive_summary'])
    md_parts.append("\n\n")

    # Summary Statistics
    md_parts.append("## Summary Statistics\n\n")
    for stat_group in report['summary_stats']:
        md_parts.append(f"### {stat_group['category']}\n\n")
        for metric in stat_group['metrics']:
            md_parts.append(f"- **{metric['label']}:** {metric['value']}\n")
        md_parts.append("\n")

    # Opportunities
    if report['opportunities']:
        md_parts.append("## Optimization Opportunities\n\n")
        for opp in report['opportunities']:
            md_parts.append(f"### {opp['title']}\n\n")
            md_parts.append(f"**Description:** {opp['description']}  \n")
            md_parts.append(f"**Impact:** {opp['impact']}  \n")
            md_parts.append(f"**Effort:** {opp['effort']}  \n")
            md_parts.append(f"**Savings:** {opp['savings']}\n\n")

    # Requirements
    md_parts.append("## Requirements & Prerequisites\n\n")
    for req in report['requirements']:
        md_parts.append(f"### {req['category']}\n\n")
        for item in req['items']:
            md_parts.append(f"- {item}\n")
        md_parts.append("\n")

    # Migration Plan
    if report['migration_plan']:
        md_parts.append("## Migration Plan\n\n")
        plan = report['migration_plan']

        md_parts.append(f"**Total Effort:** {plan.get('total_effort_days', 0)} person-days  \n")
        md_parts.append(f"**Migration Risk Score:** {plan.get('migration_risk_score', 0)}/100  \n")
        md_parts.append(f"**Ready for Migration:** {'Yes' if plan.get('ready_for_migration') else 'No'}\n\n")

        # Timeline
        if plan.get('timeline'):
            md_parts.append("### Migration Timeline\n\n")
            md_parts.append("| Phase | Start Week | Duration | EPGs | Complexity |\n")
            md_parts.append("|-------|------------|----------|------|------------|\n")
            for phase in plan['timeline']:
                md_parts.append(
                    f"| {phase['phase']} | Week {phase['start_week']} | "
                    f"{phase['duration_weeks']} weeks | {phase['epg_count']} | "
                    f"{phase['complexity']} |\n"
                )
            md_parts.append("\n")

    # Recommendations
    md_parts.append("## Recommendations\n\n")
    for rec in report['recommendations']:
        md_parts.append(f"### [{rec['priority']}] {rec['title']}\n\n")
        md_parts.append(f"{rec['description']}\n\n")
        if rec.get('action_items'):
            md_parts.append("**Action Items:**\n\n")
            for action in rec['action_items']:
                md_parts.append(f"- {action}\n")
        md_parts.append("\n")

    # Risk Assessment
    if report.get('risks'):
        md_parts.append("## Risk Assessment\n\n")
        risks = report['risks']
        for risk_level in ['critical_risks', 'high_risks', 'medium_risks']:
            if risks.get(risk_level):
                level_name = risk_level.replace('_', ' ').title()
                md_parts.append(f"### {level_name}\n\n")
                for risk in risks[risk_level]:
                    md_parts.append(f"- **{risk.get('title', 'Unknown')}:** {risk.get('description', '')}\n")
                md_parts.append("\n")

    # Detailed Analysis Summary
    md_parts.append("## Detailed Analysis Summary\n\n")

    analyses = report['analyses']

    # Port Utilization
    if analyses.get('port_utilization'):
        ports = analyses['port_utilization']
        md_parts.append(f"### Port Utilization\n\n")
        md_parts.append(f"- Total ports analyzed: {len(ports)}\n")
        if ports:
            avg_util = sum(p.get('utilization_pct', 0) for p in ports) / len(ports)
            md_parts.append(f"- Average utilization: {avg_util:.1f}%\n")
            consolidation = sum(1 for p in ports if p.get('consolidation_score', 0) >= 60)
            md_parts.append(f"- Consolidation candidates: {consolidation}\n")
        md_parts.append("\n")

    # VLAN Distribution
    if analyses.get('vlan_distribution'):
        vlan = analyses['vlan_distribution']
        stats = vlan.get('statistics', {})
        md_parts.append(f"### VLAN Distribution\n\n")
        md_parts.append(f"- Total VLANs used: {stats.get('total_vlans_used', 0)}\n")
        md_parts.append(f"- VLAN overlaps: {len(vlan.get('overlaps', []))}\n")
        md_parts.append(f"- Max VLAN spread: {stats.get('max_vlan_spread', 0)}\n")
        md_parts.append("\n")

    # Migration Flags
    if analyses.get('migration_flags'):
        flags = analyses['migration_flags']
        md_parts.append(f"### Migration Flags\n\n")
        md_parts.append(f"- Total flags: {len(flags)}\n")
        critical = sum(1 for f in flags if f.get('severity') == 'Critical')
        high = sum(1 for f in flags if f.get('severity') == 'High')
        md_parts.append(f"- Critical: {critical}\n")
        md_parts.append(f"- High: {high}\n")
        md_parts.append("\n")

    # Footer
    md_parts.append("---\n\n")
    md_parts.append("*Report generated by ACI Migrator - Professional ACI Migration Tool*\n")

    return ''.join(md_parts)


def generate_csv_report(fabric_data: Dict[str, Any], mode: str) -> str:
    """Generate comprehensive CSV report with multiple sections."""
    report = generate_report(fabric_data, mode)

    output = StringIO()

    # Section 1: Summary Statistics
    output.write("SUMMARY STATISTICS\n")
    output.write("Category,Metric,Value\n")
    for stat_group in report['summary_stats']:
        category = stat_group['category']
        for metric in stat_group['metrics']:
            output.write(f"{category},{metric['label']},{metric['value']}\n")
    output.write("\n")

    # Section 2: Opportunities
    output.write("OPTIMIZATION OPPORTUNITIES\n")
    output.write("Title,Description,Impact,Effort,Savings\n")
    for opp in report['opportunities']:
        output.write(
            f"\"{opp['title']}\",\"{opp['description']}\","
            f"{opp['impact']},{opp['effort']},\"{opp['savings']}\"\n"
        )
    output.write("\n")

    # Section 3: Recommendations
    output.write("RECOMMENDATIONS\n")
    output.write("Priority,Title,Description,Action Items\n")
    for rec in report['recommendations']:
        actions = '; '.join(rec.get('action_items', []))
        output.write(
            f"{rec['priority']},\"{rec['title']}\",\"{rec['description']}\","
            f"\"{actions}\"\n"
        )
    output.write("\n")

    # Section 4: Port Utilization
    analyses = report['analyses']
    if analyses.get('port_utilization'):
        output.write("PORT UTILIZATION\n")
        output.write("Node,Port,Speed,Active VLANs,Utilization %,Consolidation Score\n")
        for port in analyses['port_utilization'][:100]:  # Top 100
            output.write(
                f"{port.get('node', '')},{port.get('port', '')},"
                f"{port.get('speed', '')},{port.get('active_vlans', 0)},"
                f"{port.get('utilization_pct', 0):.1f},"
                f"{port.get('consolidation_score', 0)}\n"
            )
        output.write("\n")

    # Section 5: VLAN Distribution
    if analyses.get('vlan_distribution'):
        vlan_dist = analyses['vlan_distribution']
        output.write("VLAN DISTRIBUTION\n")
        output.write("VLAN,EPG Count,Tenant,BD\n")
        for vlan_id, info in list(vlan_dist.get('vlan_to_epgs', {}).items())[:100]:
            output.write(
                f"{vlan_id},{info.get('count', 0)},"
                f"{info.get('tenant', '')},{info.get('bd', '')}\n"
            )
        output.write("\n")

    # Section 6: EPG Complexity
    if analyses.get('epg_complexity'):
        output.write("EPG COMPLEXITY\n")
        output.write("EPG,Tenant,Complexity Score,Contracts,BDs,Interfaces\n")
        for epg in analyses['epg_complexity'][:100]:  # Top 100
            output.write(
                f"\"{epg.get('epg', '')}\",{epg.get('tenant', '')},"
                f"{epg.get('complexity_score', 0)},{epg.get('contract_count', 0)},"
                f"{epg.get('bd_count', 0)},{epg.get('interface_count', 0)}\n"
            )
        output.write("\n")

    # Section 7: Migration Flags
    if analyses.get('migration_flags'):
        output.write("MIGRATION FLAGS\n")
        output.write("Severity,Type,Description,Object,Recommendation\n")
        for flag in analyses['migration_flags']:
            output.write(
                f"{flag.get('severity', '')},{flag.get('type', '')},"
                f"\"{flag.get('description', '')}\",\"{flag.get('object', '')}\" ,"
                f"\"{flag.get('recommendation', '')}\"\n"
            )
        output.write("\n")

    # Section 8: Migration Timeline
    if report['migration_plan'].get('timeline'):
        output.write("MIGRATION TIMELINE\n")
        output.write("Phase,Start Week,Duration (weeks),EPG Count,Complexity,Effort (days)\n")
        for phase in report['migration_plan']['timeline']:
            output.write(
                f"\"{phase['phase']}\",{phase['start_week']},"
                f"{phase['duration_weeks']},{phase['epg_count']},"
                f"{phase['complexity']},{phase['effort_days']}\n"
            )
        output.write("\n")

    return output.getvalue()


def generate_html_report(fabric_data: Dict[str, Any], mode: str) -> str:
    """Generate professional HTML report with styling."""
    report = generate_report(fabric_data, mode)

    html_parts = []

    # HTML Header with embedded CSS
    html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACI Migration Analysis Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .report-container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #1a73e8;
            border-bottom: 3px solid #1a73e8;
            padding-bottom: 10px;
        }
        h2 {
            color: #2c3e50;
            margin-top: 30px;
            border-left: 4px solid #1a73e8;
            padding-left: 15px;
        }
        h3 {
            color: #34495e;
            margin-top: 20px;
        }
        .metadata {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .metadata p {
            margin: 5px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #1a73e8;
            color: white;
            font-weight: 600;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .stat-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #1a73e8;
        }
        .stat-label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #1a73e8;
        }
        .opportunity {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .recommendation {
            background: #d1ecf1;
            border-left: 4px solid #17a2b8;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .priority-critical {
            color: #dc3545;
            font-weight: bold;
        }
        .priority-high {
            color: #fd7e14;
            font-weight: bold;
        }
        .priority-medium {
            color: #ffc107;
            font-weight: bold;
        }
        .priority-low {
            color: #28a745;
            font-weight: bold;
        }
        ul {
            margin: 10px 0;
        }
        li {
            margin: 5px 0;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #ddd;
            text-align: center;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="report-container">
""")

    # Report Header
    html_parts.append(f"""
        <h1>ACI Migration Analysis Report</h1>
        <div class="metadata">
            <p><strong>Fabric:</strong> {report['fabric_name']}</p>
            <p><strong>Generated:</strong> {report['generated']}</p>
        </div>
""")

    # Executive Summary
    html_parts.append(f"""
        <h2>Executive Summary</h2>
        <p>{report['executive_summary']}</p>
""")

    # Summary Statistics
    html_parts.append("<h2>Summary Statistics</h2>")
    for stat_group in report['summary_stats']:
        html_parts.append(f"<h3>{stat_group['category']}</h3>")
        html_parts.append('<div class="stat-grid">')
        for metric in stat_group['metrics']:
            html_parts.append(f"""
                <div class="stat-card">
                    <div class="stat-label">{metric['label']}</div>
                    <div class="stat-value">{metric['value']}</div>
                </div>
            """)
        html_parts.append('</div>')

    # Opportunities
    if report['opportunities']:
        html_parts.append("<h2>Optimization Opportunities</h2>")
        for opp in report['opportunities']:
            html_parts.append(f"""
                <div class="opportunity">
                    <h3>{opp['title']}</h3>
                    <p><strong>Description:</strong> {opp['description']}</p>
                    <p><strong>Impact:</strong> {opp['impact']} |
                       <strong>Effort:</strong> {opp['effort']} |
                       <strong>Savings:</strong> {opp['savings']}</p>
                </div>
            """)

    # Recommendations
    html_parts.append("<h2>Recommendations</h2>")
    for rec in report['recommendations']:
        priority_class = f"priority-{rec['priority'].lower()}"
        html_parts.append(f"""
            <div class="recommendation">
                <h3><span class="{priority_class}">[{rec['priority']}]</span> {rec['title']}</h3>
                <p>{rec['description']}</p>
        """)
        if rec.get('action_items'):
            html_parts.append("<p><strong>Action Items:</strong></p><ul>")
            for action in rec['action_items']:
                html_parts.append(f"<li>{action}</li>")
            html_parts.append("</ul>")
        html_parts.append("</div>")

    # Migration Timeline
    if report['migration_plan'].get('timeline'):
        html_parts.append("<h2>Migration Timeline</h2>")
        html_parts.append("""
            <table>
                <thead>
                    <tr>
                        <th>Phase</th>
                        <th>Start Week</th>
                        <th>Duration</th>
                        <th>EPGs</th>
                        <th>Complexity</th>
                        <th>Effort (days)</th>
                    </tr>
                </thead>
                <tbody>
        """)
        for phase in report['migration_plan']['timeline']:
            html_parts.append(f"""
                <tr>
                    <td>{phase['phase']}</td>
                    <td>Week {phase['start_week']}</td>
                    <td>{phase['duration_weeks']} weeks</td>
                    <td>{phase['epg_count']}</td>
                    <td>{phase['complexity']}</td>
                    <td>{phase['effort_days']}</td>
                </tr>
            """)
        html_parts.append("</tbody></table>")

    # Analysis Summary
    html_parts.append("<h2>Detailed Analysis Summary</h2>")
    analyses = report['analyses']

    # Port Utilization
    if analyses.get('port_utilization'):
        ports = analyses['port_utilization']
        html_parts.append("<h3>Port Utilization</h3>")
        html_parts.append("<ul>")
        html_parts.append(f"<li>Total ports analyzed: {len(ports)}</li>")
        if ports:
            avg_util = sum(p.get('utilization_pct', 0) for p in ports) / len(ports)
            html_parts.append(f"<li>Average utilization: {avg_util:.1f}%</li>")
            consolidation = sum(1 for p in ports if p.get('consolidation_score', 0) >= 60)
            html_parts.append(f"<li>Consolidation candidates: {consolidation}</li>")
        html_parts.append("</ul>")

    # VLAN Distribution
    if analyses.get('vlan_distribution'):
        vlan = analyses['vlan_distribution']
        stats = vlan.get('statistics', {})
        html_parts.append("<h3>VLAN Distribution</h3>")
        html_parts.append("<ul>")
        html_parts.append(f"<li>Total VLANs used: {stats.get('total_vlans_used', 0)}</li>")
        html_parts.append(f"<li>VLAN overlaps: {len(vlan.get('overlaps', []))}</li>")
        html_parts.append(f"<li>Max VLAN spread: {stats.get('max_vlan_spread', 0)}</li>")
        html_parts.append("</ul>")

    # Migration Flags
    if analyses.get('migration_flags'):
        flags = analyses['migration_flags']
        html_parts.append("<h3>Migration Flags</h3>")
        html_parts.append("<ul>")
        html_parts.append(f"<li>Total flags: {len(flags)}</li>")
        critical = sum(1 for f in flags if f.get('severity') == 'Critical')
        high = sum(1 for f in flags if f.get('severity') == 'High')
        html_parts.append(f"<li>Critical: {critical}</li>")
        html_parts.append(f"<li>High: {high}</li>")
        html_parts.append("</ul>")

    # Footer
    html_parts.append("""
        <div class="footer">
            <p><em>Report generated by ACI Migrator - Professional ACI Migration Tool</em></p>
        </div>
    </div>
</body>
</html>
""")

    return ''.join(html_parts)


def generate_json_report(fabric_data: Dict[str, Any], mode: str) -> str:
    """Generate machine-readable JSON report."""
    report = generate_report(fabric_data, mode)

    # Make report JSON-serializable
    json_report = {
        'metadata': {
            'generated': report['generated'],
            'fabric_name': report['fabric_name'],
            'dataset_count': len(report['datasets'])
        },
        'summary_stats': report['summary_stats'],
        'executive_summary': report['executive_summary'],
        'opportunities': report['opportunities'],
        'requirements': report['requirements'],
        'recommendations': report['recommendations'],
        'migration_plan': report['migration_plan'],
        'risks': report.get('risks', {}),
        'resources': report.get('resources', {}),
        'analyses': {
            'port_utilization_count': len(report['analyses'].get('port_utilization', [])),
            'vlan_distribution': report['analyses'].get('vlan_distribution', {}).get('statistics', {}),
            'epg_complexity_count': len(report['analyses'].get('epg_complexity', [])),
            'migration_flags_count': len(report['analyses'].get('migration_flags', [])),
            'vpc_symmetry_count': len(report['analyses'].get('vpc_symmetry', [])),
        }
    }

    return json.dumps(json_report, indent=2)
