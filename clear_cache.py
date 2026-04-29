"""
Cache Management Utility for AI Bug Predictor
Helps clear cache to see all improvements (especially Tasks 4 & 5)
"""

import os
import shutil
import sys

def clear_cache():
    """Clear the ML cache directory to force fresh data collection."""
    cache_dir = os.path.join("ml", "cache")
    
    if not os.path.exists(cache_dir):
        print(f"✓ Cache directory doesn't exist: {cache_dir}")
        print("  Creating fresh cache structure...")
        create_cache_structure()
        return
    
    print(f"⚠ About to delete cache directory: {cache_dir}")
    print("  This will force:")
    print("  - Fresh git mining (slower but shows Task 4 improvements)")
    print("  - Fresh SZZ labeling with 18-month window")
    print("  - Fresh file analysis (shows Task 5 Guava Android skip)")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        try:
            shutil.rmtree(cache_dir)
            print(f"✓ Deleted: {cache_dir}")
            create_cache_structure()
            print("\n✓ Cache cleared successfully!")
            print("  Run 'python main.py' to retrain with fresh data")
        except Exception as e:
            print(f"✗ Error clearing cache: {e}")
            sys.exit(1)
    else:
        print("✗ Cache clearing cancelled")
        sys.exit(0)

def create_cache_structure():
    """Create the cache directory structure."""
    cache_dir = os.path.join("ml", "cache")
    subdirs = ["checkpoints", "miner", "szz"]
    
    os.makedirs(cache_dir, exist_ok=True)
    for subdir in subdirs:
        subdir_path = os.path.join(cache_dir, subdir)
        os.makedirs(subdir_path, exist_ok=True)
        print(f"  ✓ Created: {subdir_path}")

def check_cache_status():
    """Check current cache status."""
    cache_dir = os.path.join("ml", "cache")
    
    print("=" * 70)
    print("CACHE STATUS")
    print("=" * 70)
    
    if not os.path.exists(cache_dir):
        print("✓ No cache exists - will create fresh data on next run")
        return
    
    # Check subdirectories
    subdirs = {
        "checkpoints": os.path.join(cache_dir, "checkpoints"),
        "miner": os.path.join(cache_dir, "miner"),
        "szz": os.path.join(cache_dir, "szz")
    }
    
    for name, path in subdirs.items():
        if os.path.exists(path):
            files = os.listdir(path)
            print(f"  {name:12} : {len(files)} cached files")
        else:
            print(f"  {name:12} : (not found)")
    
    print()
    print("RECOMMENDATION:")
    print("  - To see ALL improvements (Tasks 1-8): Clear cache")
    print("  - To test quickly (Tasks 2,3,7,8 only): Keep cache")
    print()

if __name__ == "__main__":
    print("=" * 70)
    print("AI BUG PREDICTOR - CACHE MANAGEMENT")
    print("=" * 70)
    print()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        clear_cache()
    else:
        check_cache_status()
        print("Usage:")
        print("  python clear_cache.py           # Check cache status")
        print("  python clear_cache.py --clear   # Clear cache (interactive)")
        print()
