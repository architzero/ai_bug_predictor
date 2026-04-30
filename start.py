#!/usr/bin/env python
"""
AI Bug Predictor - Startup Script
Checks environment and starts the server
"""

import os
import sys
import subprocess

def check_env():
    """Check if .env file exists and has required variables"""
    if not os.path.exists('.env'):
        print("⚠️  .env file not found")
        print("   Run: cp .env.example .env")
        print("   Then edit .env with your values")
        return False
    
    with open('.env', 'r') as f:
        content = f.read()
    
    required = ['FLASK_SECRET_KEY', 'GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET']
    missing = []
    
    for var in required:
        if f'{var}=your_' in content or f'{var}=' not in content:
            missing.append(var)
    
    if missing:
        print(f"⚠️  Missing environment variables: {', '.join(missing)}")
        print("   Edit .env and set these values")
        return False
    
    return True

def check_model():
    """Check if model exists"""
    model_path = 'ml/models/bug_predictor_latest.pkl'
    if not os.path.exists(model_path):
        print("⚠️  Model not found")
        print("   Run: python main.py")
        print("   This will train the model (takes ~10 minutes)")
        return False
    return True

def main():
    print("=" * 60)
    print("AI Bug Predictor - Starting Server")
    print("=" * 60)
    
    print("\n1. Checking environment...")
    if not check_env():
        sys.exit(1)
    print("   ✓ Environment configured")
    
    print("\n2. Checking model...")
    if not check_model():
        print("\n   Starting in scan-only mode (limited functionality)")
    else:
        print("   ✓ Model loaded")
    
    print("\n3. Starting server...")
    print("   URL: http://localhost:5000")
    print("   Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    try:
        subprocess.run([sys.executable, 'wsgi.py'])
    except KeyboardInterrupt:
        print("\n\nServer stopped")
        sys.exit(0)

if __name__ == '__main__':
    main()
