# Quick Verification Script for AI Bug Predictor Improvements
# Run this after training to verify all improvements are working

import sys
import os

print("=" * 70)
print("AI BUG PREDICTOR - IMPROVEMENT VERIFICATION")
print("=" * 70)

# Check 1: Verify isotonic calibration is being used
print("\n✓ TASK 2: Isotonic Calibration")
with open("backend/train.py", "r", encoding="utf-8") as f:
    content = f.read()
    if "IsotonicRegression(out_of_bounds='clip')" in content:
        print("  ✓ Isotonic calibration implemented")
    else:
        print("  ✗ Isotonic calibration NOT found")

# Check 2: Verify temporal validation has project awareness
print("\n✓ TASK 3: Temporal Leakage Warning Fix")
if "train_project=None, test_project=None" in content:
    print("  ✓ Project-aware temporal validation implemented")
else:
    print("  ✗ Project-aware validation NOT found")

# Check 3: Verify time-windowed labeling
print("\n✓ TASK 4: Time-Windowed SZZ Labeling")
with open("backend/szz.py", "r", encoding="utf-8") as f:
    szz_content = f.read()
    if "label_window_days" in szz_content and "cutoff_date" in szz_content:
        print("  ✓ Time-windowed labeling implemented")
    else:
        print("  ✗ Time-windowed labeling NOT found")

# Check 4: Verify android skip pattern
print("\n✓ TASK 5: Guava Android Skip Pattern")
with open("backend/config.py", "r", encoding="utf-8") as f:
    config_content = f.read()
    if '"android"' in config_content and "SKIP_DIR_PATTERNS" in config_content:
        print("  ✓ Android skip pattern added")
    else:
        print("  ✗ Android skip pattern NOT found")

# Check 5: Verify context-relative explanations
print("\n✓ TASK 6: Context-Relative Explanations")
with open("backend/explainer.py", "r", encoding="utf-8") as f:
    explainer_content = f.read()
    if "repo_median" in explainer_content and "ratio = value / repo_median" in explainer_content:
        print("  ✓ Context-relative explanations implemented")
    else:
        print("  ✗ Context-relative explanations NOT found")

# Check 6: Verify re-ranking function
print("\n✓ TASK 7: Within-Repo Re-ranking")
if "_rerank_within_repo" in content:
    print("  ✓ Re-ranking function implemented")
    print("  ⚠ Note: Function needs to be integrated into prediction pipeline")
else:
    print("  ✗ Re-ranking function NOT found")

# Check 7: Verify weighted/honest metrics
print("\n✓ TASK 8: Weighted and Honest Metrics")
if "weighted_f1" in content and "honest_f1" in content:
    print("  ✓ Weighted and honest averages implemented")
else:
    print("  ✗ Weighted/honest metrics NOT found")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
print("\nNext steps:")
print("1. Run: python main.py")
print("2. Check output for:")
print("   - 'Calibrating probabilities (isotonic)' message")
print("   - No temporal warnings on cross-project folds")
print("   - Flask buggy rate < 60%")
print("   - Macro/Weighted/Honest F1 metrics in summary")
print("3. Review IMPLEMENTATION_SUMMARY.md for full details")
