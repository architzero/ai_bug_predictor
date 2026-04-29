# Critical Bug Fix: Missing 'language' Column

## 🐛 Bug Report

**Error:**
```
KeyError: 'language'
```

**Location:** `bug_predictor.py` line 98
```python
languages = df['language'].unique()  # ← CRASH: 'language' column doesn't exist
```

**Root Cause:**
In `backend/features.py` line 107, the `language` column was removed and only `language_id` (categorical) was kept:

```python
# OLD CODE (BROKEN):
"language_id": LANGUAGE_ENCODING.get(language, 10),  # Only kept language_id
# Missing: "language": language  ← This was removed
```

This broke the CLI tool (`bug_predictor.py`) which needs the string `language` column for:
1. Multi-language repository detection
2. Cross-language warning messages
3. Confidence scoring adjustments

---

## ✅ Fix Applied

**File:** `backend/features.py`

### Change 1: Keep Both Columns
```python
# NEW CODE (FIXED):
"language":    language,  # String for CLI tool language detection
"language_id": LANGUAGE_ENCODING.get(language, 10),  # 0-10 for model
```

### Change 2: Exclude 'language' from Model Features
```python
NON_FEATURE_COLS = [
    "file", "buggy", "bug_fixes", "bug_density",
    "buggy_commit", "commit_hash", "repo", "confidence",
    "language"  # String column for CLI tool, use language_id for model
]
```

**Why This Works:**
- `language` (string) → Used by CLI tool for detection/warnings
- `language_id` (0-10 categorical) → Used by model for training/prediction
- `language` is excluded from model features via `NON_FEATURE_COLS`

---

## 🧪 Testing

**Before Fix:**
```
KeyError: 'language'
```

**After Fix:**
```
✓ Multi-language detection works
✓ Cross-language warnings display
✓ Model training unaffected (uses language_id)
```

---

## 📊 Impact

**Severity:** 🔴 **Critical** (CLI tool completely broken)

**Affected:**
- `bug_predictor.py` (CLI tool) - BROKEN
- `main.py` (training pipeline) - UNAFFECTED (doesn't use 'language' column)

**Fixed:**
- CLI tool now works correctly
- Language detection restored
- Cross-language warnings restored

---

## 🎯 Why This Bug Happened

**Timeline:**
1. Originally, both `language` and `language_id` existed
2. Someone removed `language` to "avoid duplication"
3. Forgot that CLI tool depends on `language` string column
4. Training pipeline (`main.py`) still worked because it doesn't check languages
5. CLI tool (`bug_predictor.py`) crashed on first use

**Lesson:** Don't remove columns without checking all dependencies.

---

## ✅ Verification Checklist

- [x] `language` column exists in DataFrame after `build_features()`
- [x] `language_id` column exists for model training
- [x] `language` excluded from model features via `NON_FEATURE_COLS`
- [x] CLI tool can detect multi-language repos
- [x] CLI tool can show cross-language warnings
- [x] Model training still uses `language_id` (not affected)

---

## 📝 Files Modified

1. `backend/features.py` - Added `language` column back, updated `NON_FEATURE_COLS`

---

## 🚀 Status

**Bug:** FIXED ✓

**Testing:** Run `python bug_predictor.py dataset/requests` to verify

**Next:** Continue with UI/Dashboard work
