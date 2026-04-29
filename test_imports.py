#!/usr/bin/env python
"""Test script to verify all imports work correctly."""

print("Testing imports...")

try:
    print("1. Testing backend.config...")
    from backend.config import REPOS, MODEL_LATEST_PATH
    print("   ✓ backend.config")
    
    print("2. Testing backend.analysis...")
    from backend.analysis import analyze_repository
    print("   ✓ backend.analysis")
    
    print("3. Testing backend.git_mining...")
    from backend.git_mining import mine_git_data
    print("   ✓ backend.git_mining")
    
    print("4. Testing backend.features...")
    from backend.features import build_features
    print("   ✓ backend.features")
    
    print("5. Testing backend.labeling...")
    from backend.labeling import create_labels
    print("   ✓ backend.labeling")
    
    print("6. Testing backend.train...")
    from backend.train import train_model, load_model_version
    print("   ✓ backend.train")
    
    print("7. Testing backend.predict...")
    from backend.predict import predict
    print("   ✓ backend.predict")
    
    print("8. Testing backend.explainer...")
    from backend.explainer import explain_prediction
    print("   ✓ backend.explainer")
    
    print("9. Testing backend.szz...")
    from backend.szz import extract_bug_labels
    print("   ✓ backend.szz")
    
    print("10. Testing backend.database...")
    from backend.database import DatabaseManager
    print("   ✓ backend.database")
    
    print("\n✅ All imports successful!")
    print("\nYou can now run:")
    print("  python main.py          # Train model")
    print("  python bug_predictor.py <repo_path>  # Analyze single repo")
    print("  python app_ui.py        # Start web UI (Ctrl+C to stop)")
    
except ImportError as e:
    print(f"\n❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
