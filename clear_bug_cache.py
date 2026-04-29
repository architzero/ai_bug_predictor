"""
Clear Bug Type Cache

Run this script to delete the bug type classifier cache,
forcing it to retrain with the new refined keywords.
"""

import os
import shutil

def clear_bug_type_cache():
    """Delete bug type classifier cache."""
    cache_paths = [
        ".szz_cache",
        "ml/bug_type_classifier.pkl"
    ]
    
    deleted = []
    not_found = []
    
    for path in cache_paths:
        if os.path.exists(path):
            if os.path.isdir(path):
                # Delete bug_types.json files in all subdirectories
                for root, dirs, files in os.walk(path):
                    for file in files:
                        if file == "bug_types.json" or file == "bug_type_classifier.pkl":
                            file_path = os.path.join(root, file)
                            try:
                                os.remove(file_path)
                                deleted.append(file_path)
                                print(f"✓ Deleted: {file_path}")
                            except Exception as e:
                                print(f"✗ Failed to delete {file_path}: {e}")
            else:
                try:
                    os.remove(path)
                    deleted.append(path)
                    print(f"✓ Deleted: {path}")
                except Exception as e:
                    print(f"✗ Failed to delete {path}: {e}")
        else:
            not_found.append(path)
    
    print(f"\n{'='*60}")
    print(f"  CACHE CLEARING SUMMARY")
    print(f"{'='*60}")
    print(f"  Deleted: {len(deleted)} file(s)")
    print(f"  Not found: {len(not_found)} file(s)")
    
    if deleted:
        print(f"\n  ✓ Bug type cache cleared successfully")
        print(f"  ✓ Next run of main.py will retrain with new keywords")
    else:
        print(f"\n  ℹ No cache files found (already clean)")
    
    print(f"{'='*60}\n")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  CLEARING BUG TYPE CACHE")
    print("="*60 + "\n")
    
    clear_bug_type_cache()
    
    print("Next steps:")
    print("  1. Run: python main.py")
    print("  2. Verify bug type distribution (no category > 35%)")
    print("  3. Check output for improved classification")
