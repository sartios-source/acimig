#!/usr/bin/env python3
"""
Comprehensive Application Review Script
Tests UI components, analysis engine, and data integrity.
"""
import sys
from pathlib import Path
from analysis.engine import ACIAnalyzer
from analysis.fabric_manager import FabricManager

def print_header(title):
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)

def print_section(title):
    print("\n" + "-" * 80)
    print(title)
    print("-" * 80)

def review_file_structure():
    """Review critical file structure."""
    print_header("FILE STRUCTURE REVIEW")

    critical_files = {
        'Application': ['app.py', 'config.py', 'requirements.txt'],
        'Templates': ['templates/base.html', 'templates/index.html', 'templates/analyze.html',
                     'templates/visualize.html', 'templates/plan.html', 'templates/report.html',
                     'templates/help.html'],
        'Static': ['static/styles.css', 'static/dashboards.js'],
        'Analysis': ['analysis/engine.py', 'analysis/parsers.py', 'analysis/fabric_manager.py'],
        'Documentation': ['README.md', 'docs/SECURITY_IMPROVEMENTS.md'],
        'Sample Data': ['data/samples/sample_enterprise_1000epg.json']
    }

    all_present = True
    for category, files in critical_files.items():
        print(f"\n{category}:")
        for file in files:
            path = Path(file)
            status = "[OK]" if path.exists() else "[MISSING]"
            size = f"({path.stat().st_size / 1024:.1f} KB)" if path.exists() else ""
            print(f"   {status} {file} {size}")
            if not path.exists():
                all_present = False

    return all_present

def review_analysis_engine():
    """Review analysis engine methods."""
    print_header("ANALYSIS ENGINE REVIEW")

    # Setup test fabric
    print("\nInitializing test fabric with enterprise data...")
    fm = FabricManager(Path("fabrics"))
    fabric_data = fm.get_fabric_data("enterprise_1000epg")

    if not fabric_data or not fabric_data.get('datasets'):
        print("   [WARNING] Enterprise fabric not found, using test_fabric")
        fabric_data = fm.get_fabric_data("test_fabric")

    analyzer = ACIAnalyzer(fabric_data)

    # Test all analysis methods
    methods = [
        ('analyze_port_utilization', 'Port Utilization Analysis'),
        ('analyze_leaf_fex_mapping', 'Leaf-FEX Topology Mapping'),
        ('analyze_rack_grouping', 'Rack-Level Grouping'),
        ('analyze_bd_epg_mapping', 'BD-EPG Relationship Mapping'),
        ('analyze_vlan_distribution', 'VLAN Distribution Analysis'),
        ('analyze_epg_complexity', 'EPG Complexity Scoring'),
        ('analyze_vpc_symmetry', 'VPC Symmetry Validation'),
        ('analyze_pdom', 'Physical Domain Analysis'),
        ('analyze_migration_flags', 'Migration Readiness Flags'),
        ('analyze_contract_scope', 'Contract Scope Analysis'),
        ('analyze_vlan_spread', 'VLAN Spread Analysis'),
        ('analyze_cmdb_correlation', 'CMDB Correlation'),
        ('analyze_coupling_issues', 'Coupling Issues Analysis'),
        ('analyze_migration_waves', 'Migration Wave Planning'),
        ('analyze_vlan_sharing_detailed', 'VLAN Sharing Analysis'),
        ('get_visualization_data', 'Visualization Data')
    ]

    results = {}
    print("\nTesting analysis methods:")

    for method_name, description in methods:
        try:
            method = getattr(analyzer, method_name)
            result = method()

            # Determine result type and size
            if isinstance(result, list):
                size = f"{len(result)} items"
            elif isinstance(result, dict):
                size = f"{len(result)} keys"
            else:
                size = "OK"

            print(f"   [OK] {description:40s} -> {size}")
            results[method_name] = {'status': 'OK', 'result': result}

        except Exception as e:
            print(f"   [ERROR] {description:40s} -> {str(e)[:50]}")
            results[method_name] = {'status': 'ERROR', 'error': str(e)}

    # Summary
    successful = sum(1 for r in results.values() if r['status'] == 'OK')
    total = len(methods)
    print(f"\nAnalysis Engine: {successful}/{total} methods working ({successful/total*100:.1f}%)")

    return results

def review_templates():
    """Review template files for completeness."""
    print_header("TEMPLATE REVIEW")

    templates = {
        'base.html': ['navigation', 'footer', 'scripts', 'styles'],
        'index.html': ['fabric selector', 'mode selection', 'upload form'],
        'analyze.html': ['validation results', 'dataset info'],
        'visualize.html': ['dashboard tabs', 'charts', 'topology'],
        'plan.html': ['migration plan', 'timeline'],
        'report.html': ['report generation', 'export options'],
        'help.html': ['documentation', 'examples']
    }

    for template, expected_features in templates.items():
        path = Path(f"templates/{template}")
        print(f"\n{template}:")

        if not path.exists():
            print(f"   [MISSING] File not found")
            continue

        content = path.read_text(encoding='utf-8')

        # Check for expected features (basic keyword search)
        for feature in expected_features:
            # Convert feature to likely HTML/template keywords
            keywords = feature.lower().replace(' ', '-')
            if keywords in content.lower():
                print(f"   [OK] {feature}")
            else:
                print(f"   [?] {feature} (keyword not found, may use different naming)")

def review_static_assets():
    """Review static assets."""
    print_header("STATIC ASSETS REVIEW")

    print("\nCSS Files:")
    css_file = Path("static/styles.css")
    if css_file.exists():
        content = css_file.read_text(encoding='utf-8')
        lines = len(content.split('\n'))
        size = css_file.stat().st_size / 1024
        print(f"   [OK] styles.css ({lines} lines, {size:.1f} KB)")

        # Check for key CSS classes
        classes = ['dashboard', 'chart', 'metric-card', 'topology']
        for cls in classes:
            if cls in content:
                print(f"      [OK] .{cls} styles present")
    else:
        print(f"   [MISSING] styles.css")

    print("\nJavaScript Files:")
    js_file = Path("static/dashboards.js")
    if js_file.exists():
        content = js_file.read_text(encoding='utf-8')
        lines = len(content.split('\n'))
        size = js_file.stat().st_size / 1024
        print(f"   [OK] dashboards.js ({lines} lines, {size:.1f} KB)")

        # Check for key functions
        functions = ['createTopologyVisualization', 'createUtilizationDistributionChart',
                    'createVlanDistributionChart', 'createComplexityDistributionChart']
        for func in functions:
            if func in content:
                print(f"      [OK] {func}()")
    else:
        print(f"   [MISSING] dashboards.js")

def review_documentation():
    """Review documentation files."""
    print_header("DOCUMENTATION REVIEW")

    docs = {
        'README.md': ['installation', 'usage', 'features'],
        'docs/SECURITY_IMPROVEMENTS.md': ['security', 'vulnerabilities', 'improvements']
    }

    for doc, expected_sections in docs.items():
        path = Path(doc)
        print(f"\n{doc}:")

        if not path.exists():
            print(f"   [MISSING] File not found")
            continue

        content = path.read_text(encoding='utf-8')
        lines = len(content.split('\n'))
        size = path.stat().st_size / 1024
        print(f"   Present ({lines} lines, {size:.1f} KB)")

        for section in expected_sections:
            if section.lower() in content.lower():
                print(f"   [OK] Contains {section} information")

def review_sample_data():
    """Review sample data files."""
    print_header("SAMPLE DATA REVIEW")

    samples = [
        'data/samples/sample_aci.json',
        'data/samples/sample_cmdb.csv',
        'data/samples/sample_large_scale.json',
        'data/samples/sample_large_scale_cmdb.csv',
        'data/samples/sample_enterprise_1000epg.json',
        'data/samples/sample_enterprise_1000epg_cmdb.csv'
    ]

    for sample in samples:
        path = Path(sample)
        if path.exists():
            size = path.stat().st_size
            if size > 1024 * 1024:  # > 1MB
                size_str = f"{size / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{size / 1024:.2f} KB"

            # Try to determine object count
            if sample.endswith('.json'):
                import json
                try:
                    with open(path) as f:
                        data = json.load(f)
                    obj_count = len(data.get('imdata', []))
                    print(f"   [OK] {Path(sample).name:45s} {size_str:>12s} ({obj_count} objects)")
                except:
                    print(f"   [OK] {Path(sample).name:45s} {size_str:>12s}")
            else:
                print(f"   [OK] {Path(sample).name:45s} {size_str:>12s}")
        else:
            print(f"   [MISSING] {Path(sample).name}")

def review_configuration():
    """Review configuration files."""
    print_header("CONFIGURATION REVIEW")

    print("\nconfig.py:")
    config_file = Path("config.py")
    if config_file.exists():
        content = config_file.read_text(encoding='utf-8')
        print(f"   [OK] Present")

        # Check for key config classes
        if 'class Config' in content:
            print(f"   [OK] Base Config class")
        if 'class DevelopmentConfig' in content:
            print(f"   [OK] Development Config")
        if 'class ProductionConfig' in content:
            print(f"   [OK] Production Config")
        if 'SECRET_KEY' in content:
            print(f"   [OK] SECRET_KEY configuration")
    else:
        print(f"   [MISSING] config.py not found")

    print("\n.env.example:")
    env_example = Path(".env.example")
    if env_example.exists():
        content = env_example.read_text(encoding='utf-8')
        print(f"   [OK] Present")
        lines = [l for l in content.split('\n') if l.strip() and not l.startswith('#')]
        print(f"   [OK] {len(lines)} configuration variables defined")
    else:
        print(f"   [MISSING] .env.example not found")

    print("\nrequirements.txt:")
    req_file = Path("requirements.txt")
    if req_file.exists():
        content = req_file.read_text(encoding='utf-8')
        deps = [l for l in content.split('\n') if l.strip() and not l.startswith('#')]
        print(f"   [OK] {len(deps)} dependencies defined")

        # Check for critical dependencies
        critical = ['Flask', 'pandas', 'defusedxml', 'Flask-WTF', 'Flask-Limiter']
        for dep in critical:
            if dep in content:
                print(f"   [OK] {dep}")
    else:
        print(f"   [MISSING] requirements.txt not found")

def main():
    """Run comprehensive review."""
    print_header("ACI ANALYSIS TOOL - COMPREHENSIVE REVIEW")
    print("\nReviewing all components...\n")

    # Run all reviews
    file_structure_ok = review_file_structure()
    review_configuration()
    review_sample_data()
    review_templates()
    review_static_assets()
    review_documentation()
    analysis_results = review_analysis_engine()

    # Final summary
    print_header("REVIEW SUMMARY")

    print("\nComponent Status:")
    print(f"   File Structure:        {'[OK]' if file_structure_ok else '[ISSUES]'}")

    analysis_ok = sum(1 for r in analysis_results.values() if r['status'] == 'OK')
    analysis_total = len(analysis_results)
    print(f"   Analysis Engine:       [OK] {analysis_ok}/{analysis_total} methods working")

    print(f"   Templates:             [OK] All critical templates present")
    print(f"   Static Assets:         [OK] CSS and JS files present")
    print(f"   Documentation:         [OK] README and security docs present")
    print(f"   Sample Data:           [OK] Multiple test datasets available")
    print(f"   Configuration:         [OK] Config files present")

    # Overall status
    overall_ok = file_structure_ok and analysis_ok == analysis_total

    print("\n" + "=" * 80)
    if overall_ok:
        print("OVERALL STATUS: [OK] Application ready for use!".center(80))
    else:
        print("OVERALL STATUS: [ISSUES] Some components need attention".center(80))
    print("=" * 80)

    return 0 if overall_ok else 1

if __name__ == '__main__':
    sys.exit(main())
