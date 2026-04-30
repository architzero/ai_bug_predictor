#!/usr/bin/env python
"""Test script to verify frontend setup"""

import sys
import os

def test_imports():
    """Test all required imports"""
    print("Testing imports...")
    try:
        import flask
        import flask_limiter
        import flask_caching
        import authlib
        print("✓ All Flask dependencies available")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    return True

def test_templates():
    """Test template files exist"""
    print("\nTesting templates...")
    templates = [
        'frontend/templates/base.html',
        'frontend/templates/index.html',
        'frontend/templates/scan.html',
        'frontend/templates/results.html',
        'frontend/templates/dashboard.html',
        'frontend/templates/about.html',
        'frontend/templates/404.html',
        'frontend/templates/500.html'
    ]
    
    all_exist = True
    for template in templates:
        if os.path.exists(template):
            print(f"✓ {template}")
        else:
            print(f"✗ {template} missing")
            all_exist = False
    
    return all_exist

def test_static_files():
    """Test static files exist"""
    print("\nTesting static files...")
    static_files = [
        'frontend/assets/js/app.js',
        'frontend/assets/css/main.css'
    ]
    
    all_exist = True
    for static_file in static_files:
        if os.path.exists(static_file):
            print(f"✓ {static_file}")
        else:
            print(f"✗ {static_file} missing")
            all_exist = False
    
    return all_exist

def test_config_files():
    """Test configuration files exist"""
    print("\nTesting configuration files...")
    config_files = [
        'wsgi.py',
        'Procfile',
        '.env.example',
        'requirements.txt'
    ]
    
    all_exist = True
    for config_file in config_files:
        if os.path.exists(config_file):
            print(f"✓ {config_file}")
        else:
            print(f"✗ {config_file} missing")
            all_exist = False
    
    return all_exist

def test_app_structure():
    """Test app_ui.py has required routes"""
    print("\nTesting app structure...")
    
    if not os.path.exists('app_ui.py'):
        print("✗ app_ui.py missing")
        return False
    
    with open('app_ui.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_routes = [
        '@app.route("/")',
        '@app.route("/scan/<scan_id>")',
        '@app.route("/results/<scan_id>")',
        '@app.route("/dashboard")',
        '@app.route("/about")',
        '@app.route("/api/scan_repo"',
        '@app.route("/api/scan_progress/<scan_id>")',
        '@app.route("/api/recent_scans")',
        '@app.route("/health")',
        '@app.errorhandler(404)',
        '@app.errorhandler(500)',
        '@app.after_request'
    ]
    
    all_exist = True
    for route in required_routes:
        if route in content:
            print(f"✓ {route}")
        else:
            print(f"✗ {route} missing")
            all_exist = False
    
    return all_exist

def main():
    """Run all tests"""
    print("=" * 60)
    print("Frontend Setup Verification")
    print("=" * 60)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Templates", test_templates()))
    results.append(("Static Files", test_static_files()))
    results.append(("Config Files", test_config_files()))
    results.append(("App Structure", test_app_structure()))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:20} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All checks passed! Ready to run: python wsgi.py")
        return 0
    else:
        print("\n✗ Some checks failed. Please fix the issues above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
