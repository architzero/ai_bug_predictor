# Pre-Run Checklist for AI Bug Predictor

## ✅ GOOD NEWS: No Additional Installations Needed!

All required packages are already in `requirements.txt`:
- ✓ `imbalanced-learn==0.14.1` (includes SMOTETomek)
- ✓ `scikit-learn==1.8.0` (includes IsotonicRegression)
- ✓ All other dependencies present

## Cache Invalidation Decision

### Current Cache Version: `v10`

**IMPORTANT DECISION:** Should you clear the cache?

### Option A: Keep Cache (RECOMMENDED for faster testing)
**Pros:**
- Much faster execution (reuses git mining and feature extraction)
- Good for verifying model training improvements (Tasks 2, 3, 7, 8)

**Cons:**
- Won't see Task 4 improvements (time-windowed SZZ labeling)
- Won't see Task 5 improvements (Guava Android skip)

**When to use:** If you want to quickly verify the model training improvements work

### Option B: Clear Cache (RECOMMENDED for full verification)
**Pros:**
- Will see ALL improvements including:
  - Task 4: Flask buggy rate dropping from 87% to <60%
  - Task 5: No Guava Android duplicates
  - Fresh SZZ labels with 18-month window

**Cons:**
- Takes longer (needs to re-mine git history)

**When to use:** For complete verification of all 8 tasks

## How to Clear Cache (if choosing Option B)

### Method 1: Delete cache directory (RECOMMENDED)
```bash
# Windows
rmdir /s /q ml\cache
mkdir ml\cache
mkdir ml\cache\checkpoints
mkdir ml\cache\miner
mkdir ml\cache\szz

# Or manually delete the ml/cache folder and recreate subdirectories
```

### Method 2: Increment cache version
Edit `backend/config.py`:
```python
CACHE_VERSION = "v11"  # Change from v10 to v11
```

## Pre-Run Steps

### 1. Verify Python Environment
```bash
python --version
# Should be Python 3.8+
```

### 2. Verify Dependencies (Optional - already installed)
```bash
pip install -r requirements.txt
# Should show "Requirement already satisfied" for all packages
```

### 3. Verify Dataset Repositories Exist
Check that these directories exist and contain git repos:
- `dataset/requests`
- `dataset/flask`
- `dataset/fastapi`
- `dataset/httpx`
- `dataset/celery`
- `dataset/sqlalchemy`
- `dataset/express`
- `dataset/axios`
- `dataset/guava`

### 4. Choose Your Cache Strategy
- **Option A (Keep Cache):** Do nothing, proceed to step 5
- **Option B (Clear Cache):** Follow "How to Clear Cache" above

### 5. Run Training
```bash
python main.py
```

## What to Look For in Output

### Task 2: Isotonic Calibration
Look for:
```
Calibrating probabilities (isotonic)...
```
NOT:
```
Calibrating probabilities (sigmoid)...
```

### Task 3: Temporal Validation
Should NOT see warnings like:
```
⚠ Temporal validation warning: potential leakage detected
```
on cross-project folds (different train/test repos)

### Task 4: Time-Windowed SZZ (only if cache cleared)
Look for Flask in SZZ output:
```
SZZ: Using 548-day labeling window (cutoff: YYYY-MM-DD)
```
And Flask buggy rate should be < 60% (was 87%)

### Task 5: Guava Android Skip (only if cache cleared)
Should NOT see files like:
```
android/guava/src/...
```
in the analysis

### Task 6: Context-Relative Explanations
Explanations should NOT say:
- "high commit history (1 changes)"
- "many contributors (0 authors)"

### Task 7: Re-ranking Function
Function is implemented but needs manual integration.
Check that `_rerank_within_repo` exists in code.

### Task 8: Weighted/Honest Metrics
Look for in summary:
```
SUMMARY METRICS:
  Macro avg F1      : X.XXX  (all 9 folds)
  Weighted avg F1   : X.XXX  (by repo size — most realistic)
  Honest avg F1     : X.XXX  (excluding folds with <20 test files)
```

## Estimated Run Times

- **With Cache:** 10-20 minutes (model training only)
- **Without Cache:** 1-3 hours (git mining + feature extraction + training)

## Troubleshooting

### If you see import errors:
```bash
pip install --upgrade imbalanced-learn scikit-learn
```

### If cache issues occur:
```bash
# Clear cache and try again
rmdir /s /q ml\cache
mkdir ml\cache\checkpoints ml\cache\miner ml\cache\szz
```

### If git mining fails:
- Ensure all dataset repos are valid git repositories
- Check that PyDriller can access the repos

## Recommendation

**For first run after improvements:**
1. Clear cache (Option B) to see ALL improvements
2. Run `python main.py`
3. Verify all 8 tasks in output
4. Review `IMPLEMENTATION_SUMMARY.md` for detailed checklist

**For subsequent runs:**
- Keep cache (Option A) for faster iteration
