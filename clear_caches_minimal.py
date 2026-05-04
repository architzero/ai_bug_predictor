"""
Minimal cache clearing script - clears miner and SZZ caches to force fresh analysis.
Run this after updating skip patterns to ensure changes take effect.
"""

import os
import shutil

def clear_caches():
    """Clear miner and SZZ caches."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(base_dir, "ml", "cache")
    
    miner_cache = os.path.join(cache_dir, "miner")
    szz_cache = os.path.join(cache_dir, "szz")
    
    cleared = []
    
    # Clear miner cache
    if os.path.exists(miner_cache):
        for file in os.listdir(miner_cache):
            file_path = os.path.join(miner_cache, file)
            try:
                os.remove(file_path)
                cleared.append(f"miner/{file}")
            except Exception as e:
                print(f"  ⚠️  Could not delete {file}: {e}")
    
    # Clear SZZ cache
    if os.path.exists(szz_cache):
        for file in os.listdir(szz_cache):
            file_path = os.path.join(szz_cache, file)
            try:
                os.remove(file_path)
                cleared.append(f"szz/{file}")
            except Exception as e:
                print(f"  ⚠️  Could not delete {file}: {e}")
    
    print(f"\n✅ Cache clearing complete!")
    print(f"   Cleared {len(cleared)} cache files")
    print(f"\n📋 Next steps:")
    print(f"   1. Run: python main.py")
    print(f"   2. Verify output has no test/example files")
    print(f"   3. Check top risky files are real source code\n")

if __name__ == "__main__":
    print("🧹 Clearing miner and SZZ caches...")
    clear_caches()
