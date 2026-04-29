"""
Quick validation script to check SZZ v2.6 churn-weighted labeling impact.
Run after: python main.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.config import REPOS, SZZ_CACHE_DIR
from backend.szz import extract_bug_labels_with_confidence

def validate_bug_rates():
    """Check bug rates for all repositories."""
    print("=" * 70)
    print("SZZ v2.6 CHURN-WEIGHTED LABELING VALIDATION")
    print("=" * 70)
    print()
    
    results = []
    
    for repo_path in REPOS:
        if not os.path.exists(repo_path):
            continue
        
        repo_name = os.path.basename(repo_path)
        print(f"Analyzing {repo_name}...")
        
        # Get buggy files with confidence
        buggy_dict = extract_bug_labels_with_confidence(repo_path, SZZ_CACHE_DIR)
        
        # Count files in repo (approximate)
        from backend.analysis import analyze_repository
        try:
            static_results = analyze_repository(repo_path)
            total_files = len(static_results)
        except Exception:
            total_files = 0
        
        buggy_count = len(buggy_dict)
        bug_rate = (buggy_count / total_files * 100) if total_files > 0 else 0
        
        # Calculate average confidence
        avg_confidence = sum(buggy_dict.values()) / len(buggy_dict) if buggy_dict else 0
        
        results.append({
            'repo': repo_name,
            'total': total_files,
            'buggy': buggy_count,
            'rate': bug_rate,
            'confidence': avg_confidence
        })
        
        print(f"  Total files: {total_files}")
        print(f"  Buggy files: {buggy_count}")
        print(f"  Bug rate: {bug_rate:.1f}%")
        print(f"  Avg confidence: {avg_confidence:.2f}")
        print()
    
    # Summary table
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Repository':<15} {'Total':<8} {'Buggy':<8} {'Rate':<10} {'Confidence':<12}")
    print("-" * 70)
    
    for r in results:
        print(f"{r['repo']:<15} {r['total']:<8} {r['buggy']:<8} {r['rate']:<9.1f}% {r['confidence']:<12.2f}")
    
    print("-" * 70)
    
    # Calculate overall stats
    total_all = sum(r['total'] for r in results)
    buggy_all = sum(r['buggy'] for r in results)
    overall_rate = (buggy_all / total_all * 100) if total_all > 0 else 0
    
    print(f"{'OVERALL':<15} {total_all:<8} {buggy_all:<8} {overall_rate:<9.1f}%")
    print()
    
    # Validation checks
    print("=" * 70)
    print("VALIDATION CHECKS")
    print("=" * 70)
    
    high_rate_repos = [r for r in results if r['rate'] > 70]
    low_rate_repos = [r for r in results if r['rate'] < 10]
    healthy_repos = [r for r in results if 30 <= r['rate'] <= 65]
    
    print(f"✓ Healthy bug rates (30-65%): {len(healthy_repos)}/{len(results)}")
    print(f"⚠ High bug rates (>70%): {len(high_rate_repos)}/{len(results)}")
    print(f"⚠ Low bug rates (<10%): {len(low_rate_repos)}/{len(results)}")
    print()
    
    if high_rate_repos:
        print("High rate repositories:")
        for r in high_rate_repos:
            print(f"  - {r['repo']}: {r['rate']:.1f}%")
        print()
    
    if low_rate_repos:
        print("Low rate repositories:")
        for r in low_rate_repos:
            print(f"  - {r['repo']}: {r['rate']:.1f}%")
        print()
    
    # Expected vs actual
    print("=" * 70)
    print("EXPECTED vs ACTUAL")
    print("=" * 70)
    
    expected = {
        'flask': 50,
        'express': 45,
        'sqlalchemy': 55,
        'axios': 50,
        'requests': 55,
        'fastapi': 40,
        'httpx': 50,
        'celery': 60,
        'guava': 45
    }
    
    print(f"{'Repository':<15} {'Expected':<12} {'Actual':<12} {'Diff':<10}")
    print("-" * 70)
    
    for r in results:
        repo_lower = r['repo'].lower()
        if repo_lower in expected:
            exp = expected[repo_lower]
            actual = r['rate']
            diff = actual - exp
            status = "✓" if abs(diff) < 15 else "⚠"
            print(f"{r['repo']:<15} {exp:<11.1f}% {actual:<11.1f}% {diff:+9.1f}% {status}")
    
    print()
    print("=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    validate_bug_rates()
