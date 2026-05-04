"""
Verification script - checks if test/example/demo files are properly excluded.
Run this after training to verify the fixes worked.
"""

import os
import json

def verify_filtering():
    """Verify that test/example/demo files are excluded from training."""
    
    # Check if benchmarks.json exists
    benchmarks_path = os.path.join("ml", "benchmarks.json")
    if not os.path.exists(benchmarks_path):
        print("❌ benchmarks.json not found. Run training first.")
        return False
    
    # Load benchmarks
    with open(benchmarks_path, "r") as f:
        data = json.load(f)
    
    # Check for problematic patterns in file paths
    problematic_patterns = [
        "test", "tests", "__tests__", "spec", "specs",
        "example", "examples", "sample", "samples",
        "demo", "demos", "benchmark", "benchmarks"
    ]
    
    issues_found = []
    
    # Check each repository's files
    for repo_name, repo_data in data.items():
        if repo_name in ["metadata", "timestamp"]:
            continue
            
        files = repo_data.get("files_analyzed", [])
        
        for file_path in files:
            file_lower = file_path.lower()
            for pattern in problematic_patterns:
                if f"/{pattern}/" in file_lower or f"\\{pattern}\\" in file_lower:
                    issues_found.append((repo_name, file_path, pattern))
                    break
    
    # Report results
    print("\n" + "="*70)
    print("🔍 VERIFICATION RESULTS")
    print("="*70)
    
    if not issues_found:
        print("\n✅ SUCCESS! No test/example/demo files found in training data.")
        print("   Your filtering is working correctly.")
        return True
    else:
        print(f"\n❌ ISSUES FOUND: {len(issues_found)} problematic files detected")
        print("\n📋 First 10 problematic files:")
        for repo, file_path, pattern in issues_found[:10]:
            print(f"   {repo}: {file_path} (matched: {pattern})")
        
        print(f"\n💡 Action required:")
        print(f"   1. Clear caches: python clear_caches_minimal.py")
        print(f"   2. Retrain: python main.py")
        print(f"   3. Verify again: python verify_filtering.py")
        return False

if __name__ == "__main__":
    verify_filtering()
