# ⚠️ CRITICAL: YOU MUST RETRAIN

## Why Retrain is Required

**Current State:**
```
Model expects:     26 features (trained WITH correlation filtering)
Inference produces: 43 features (NO correlation filtering after fix)
Result:            17 features missing → zero-filled → bad predictions
```

**After Retrain:**
```
Model expects:     43 features (trained WITHOUT correlation filtering)
Inference produces: 43 features (NO correlation filtering)
Result:            Perfect match → no missing features → good predictions
```

---

## What I Fixed

I removed `filter_correlated_features()` from `bug_predictor.py` line 127.

**This was correct** - correlation filtering should only happen during training, not inference.

**But** - your current model was trained WITH correlation filtering, so it expects only 26 features.

**Solution** - Retrain the model WITHOUT correlation filtering.

---

## How to Retrain

```bash
python main.py
```

**Time:** 10-20 minutes

**What happens:**
1. Loads all 9 training repos
2. Trains model with 43 features (no correlation filtering at inference)
3. Saves new model to `ml/models/bug_predictor_latest.pkl`
4. Updates training stats with medians for imputation

---

## After Retrain - Test

```bash
python bug_predictor.py dataset/requests
```

**Expected:**
- ✅ No "Missing features" warning
- ✅ Confidence: MEDIUM or HIGH (not LOW)
- ✅ Risk scores spread across range
- ✅ Plots folder opens automatically

---

## SHAP Plots Location

**After running `bug_predictor.py`:**

1. **Auto-opens** (Windows only): Plots folder opens in Explorer automatically
2. **Manual**: Full path printed in output
3. **Location**: `C:\Users\archi\project\ai-bug-predictor\ml\plots\`

**Files:**
- `global_bar.png` - Feature importance ranking
- `global_beeswarm.png` - Feature value distribution
- `local_waterfall_*.png` - Per-file explanations (top 5 risky files)

---

## Summary

**Must Do:** Run `python main.py` (retrain)

**Why:** Schema mismatch (26 vs 43 features)

**Time:** 10-20 minutes

**Then:** Run `python bug_predictor.py dataset/requests` to verify

**Result:** No missing features, better predictions, plots auto-open
