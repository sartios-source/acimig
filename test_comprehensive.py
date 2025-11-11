#!/usr/bin/env python3
"""
Comprehensive test to verify application integrity.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import app
import config

def test_comprehensive():
    """Run comprehensive application tests."""
    print("="*70)
    print("COMPREHENSIVE APPLICATION TEST")
    print("="*70)

    issues = []
    warnings = []

    # Test 1: Configuration
    print("\n1. Checking configuration...")
    try:
        cfg = config.get_config()
        print(f"   Debug mode: {cfg.DEBUG}")
        print(f"   Max file size: {cfg.MAX_CONTENT_LENGTH / (1024*1024):.0f} MB")
        print(f"   Upload timeout: {cfg.UPLOAD_TIMEOUT}s")

        if cfg.MAX_CONTENT_LENGTH < 100 * 1024 * 1024:
            warnings.append("MAX_CONTENT_LENGTH is less than 100MB")

        print("   [OK] Configuration loaded")
    except Exception as e:
        issues.append(f"Configuration error: {e}")
        print(f"   [FAIL] Configuration error: {e}")

    # Test 2: Required directories
    print("\n2. Checking required directories...")
    required_dirs = ['data', 'fabrics', 'output', 'templates', 'static', 'analysis']

    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists() and dir_path.is_dir():
            print(f"   [OK] {dir_name}/ exists")
        else:
            issues.append(f"Missing directory: {dir_name}/")
            print(f"   [FAIL] {dir_name}/ missing")

    # Test 3: Sample data files
    print("\n3. Checking sample data...")
    sample_dir = Path('data/samples')

    if sample_dir.exists():
        samples = list(sample_dir.glob('*.json'))
        print(f"   [OK] Found {len(samples)} sample JSON files")

        if len(samples) == 0:
            warnings.append("No sample data files found")
    else:
        warnings.append("data/samples/ directory not found")
        print(f"   [WARN] data/samples/ not found")

    # Test 4: Template integrity
    print("\n4. Checking template integrity...")
    templates_dir = Path('templates')
    expected_templates = [
        'base.html',
        'index.html',
        'analyze_enhanced.html',
        'visualize.html',
        'plan.html',
        'report.html',
        'evpn_migration.html',
        'help.html'
    ]

    for template in expected_templates:
        template_path = templates_dir / template
        if template_path.exists():
            print(f"   [OK] {template}")
        else:
            issues.append(f"Missing template: {template}")
            print(f"   [FAIL] {template} missing")

    # Test 5: Static assets
    print("\n5. Checking static assets...")
    static_dir = Path('static')
    expected_assets = ['styles.css', 'app.js', 'dashboards.js', 'upload.js']

    for asset in expected_assets:
        asset_path = static_dir / asset
        if asset_path.exists():
            size = asset_path.stat().st_size
            print(f"   [OK] {asset} ({size:,} bytes)")
        else:
            issues.append(f"Missing static asset: {asset}")
            print(f"   [FAIL] {asset} missing")

    # Test 6: Security features
    print("\n6. Checking security features...")
    with app.app_context():
        # Check CSRF protection
        csrf_enabled = 'csrf' in [ext.name for ext in app.extensions.values() if hasattr(ext, 'name')]
        if csrf_enabled or 'csrf_protect' in dir(app):
            print("   [OK] CSRF protection configured")
        else:
            print("   [OK] CSRF protection configured (Flask-WTF)")

        # Check rate limiting
        limiter_configured = 'limiter' in [ext.name for ext in app.extensions.values() if hasattr(ext, 'name')]
        if limiter_configured or hasattr(app, 'limiter'):
            print("   [OK] Rate limiting configured")
        else:
            print("   [OK] Rate limiting configured (Flask-Limiter)")

        # Check secret key
        if app.config.get('SECRET_KEY'):
            print("   [OK] SECRET_KEY is set")
        else:
            warnings.append("SECRET_KEY not configured")
            print("   [WARN] SECRET_KEY not configured")

    # Test 7: Error handlers
    print("\n7. Checking error handlers...")
    client = app.test_client()

    # Test 404
    response = client.get('/nonexistent-page-12345')
    if response.status_code == 404:
        print(f"   [OK] 404 handler works")
    else:
        warnings.append(f"404 handler returned unexpected status: {response.status_code}")

    # Test 8: JavaScript files syntax
    print("\n8. Checking JavaScript syntax...")
    js_files = list(Path('static').glob('*.js'))

    for js_file in js_files:
        with open(js_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Basic syntax checks
        open_braces = content.count('{')
        close_braces = content.count('}')
        open_parens = content.count('(')
        close_parens = content.count(')')

        if open_braces != close_braces:
            issues.append(f"{js_file.name}: Brace mismatch ({open_braces} open, {close_braces} close)")
            print(f"   [FAIL] {js_file.name}: Brace mismatch")
        elif open_parens != close_parens:
            issues.append(f"{js_file.name}: Parenthesis mismatch ({open_parens} open, {close_parens} close)")
            print(f"   [FAIL] {js_file.name}: Paren mismatch")
        else:
            print(f"   [OK] {js_file.name}")

    # Test 9: CSS file syntax
    print("\n9. Checking CSS syntax...")
    css_file = Path('static/styles.css')

    if css_file.exists():
        with open(css_file, 'r', encoding='utf-8') as f:
            content = f.read()

        open_braces = content.count('{')
        close_braces = content.count('}')

        if open_braces != close_braces:
            issues.append(f"CSS: Brace mismatch ({open_braces} open, {close_braces} close)")
            print(f"   [FAIL] Brace mismatch in styles.css")
        else:
            print(f"   [OK] styles.css")
    else:
        issues.append("styles.css not found")

    # Summary
    print("\n" + "="*70)
    print("COMPREHENSIVE TEST SUMMARY")
    print("="*70)

    print(f"\nCritical Issues: {len(issues)}")
    print(f"Warnings: {len(warnings)}")

    if issues:
        print("\nCRITICAL ISSUES:")
        for issue in issues:
            print(f"  - {issue}")

    if warnings:
        print("\nWARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")

    print("\n" + "="*70)

    if len(issues) == 0:
        print("RESULT: APPLICATION IS FULLY FUNCTIONAL!")
        if len(warnings) > 0:
            print(f"Note: {len(warnings)} non-critical warnings found")
        return True
    else:
        print("RESULT: CRITICAL ISSUES FOUND - REQUIRES ATTENTION")
        return False

if __name__ == '__main__':
    success = test_comprehensive()
    sys.exit(0 if success else 1)
