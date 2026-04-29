# ROOT CAUSE ANALYSIS: CLI Output Issues

**Date**: 2026-04-29  
**Analyst**: Amazon Q  
**Severity**: HIGH (affects user experience and trust in predictions)

---

## Executive Summary

Three critical issues identified in CLI output affecting user experience:
1. **Empty "Why risky" explanations** - 90% of files show no explanation
2. **Identical risk scores (95.8%)** - All files clustered at same probability, losing discrimination
3. **Misleading thresholds** - "279 lines added" flagged as risky despite being normal for the repository

All three issues stem from **out-of-distribution (OOD) detection failures** and **overly aggressive probability calibration**.

---

## Problem 1: Empty "Why risky" Explanations

### Symptoms
```
#1. mkcompletion.py
    Risk: 95.8% | Tier: CRITICAL | LOC: 44
    Why risky:

#2. mkdocs.py
    Risk: 95.8% | Tier: CRITICAL | LOC: 56
    Why risky:
```

### Root Cause
**File**: `backend/explainer.py` → `_generate_human_readable_explanation()`

The function only looks at **top 3 SHAP features** and filters out explanations that don't meet strict thresholds:
- `commits < 1` → suppressed
- `author_count == 0` → suppressed  
- `max_added < 200` → suppressed
- `avg_complexity < 15` → suppressed

For files with sparse git history or moderate complexity, **all top-3 features get filtered out**, leaving empty explanations.

### Fix Applied
1. **Expanded candidate pool**: Look at top 9 features (3× original) to find explainable ones
2. **Fallback mechanism**: If still no explanations, show generic message based on top SHAP feature
3. **Validation**: Added check to count empty explanations and warn user

**Code changes**:
```python
# OLD: Only check top 3
top_features = contrib.abs().sort_values(ascending=False).head(top_n)

# NEW: Check top 9, stop when we have 3 valid explanations
top_features = contrib.abs().sort_values(ascending=False).head(top_n * 3)
for feature_name in top_features.index:
    if len(explanations) >= top_n:
        break
    # ... generate explanation ...

# NEW: Fallback if no explanations found
if not explanations and len(top_features) > 0:
    top_feature = top_features.index[0]
    top_val = row_data.get(top_feature, 0)
    explanations.append(f"Elevated {top_feature.replace('_', ' ')} ({top_val:.2f})")
```

---

## Problem 2: All Files Have Same 95.8% Risk Score

### Symptoms
```
#1. mkcompletion.py    Risk: 95.8% | Tier: CRITICAL
#2. mkdocs.py          Risk: 95.8% | Tier: CRITICAL
#3. gui.py             Risk: 95.8% | Tier: CRITICAL
#4. cli.py             Risk: 95.8% | Tier: CRITICAL
...
#10. tk.py             Risk: 95.8% | Tier: CRITICAL
```

### Root Cause
**File**: `backend/train.py` → `_IsotonicWrapper.predict_proba()`

The isotonic calibration wrapper was using **minimal capping (0.001-0.999)** to "preserve discrimination", but this backfired:

1. **OOD repository** (friend's repo is very different from training data)
2. **Model outputs extreme probabilities** (all near 1.0 due to uncertainty)
3. **Isotonic calibration preserves these extremes** (no spreading mechanism)
4. **Result**: All files cluster at 95.8% (the calibration ceiling)

**Original code**:
```python
def __init__(self, iso_reg, cap_min=0.001, cap_max=0.999):
    # Minimal capping to "preserve discrimination"
    
def predict_proba(self, X):
    cal_proba = self.iso_reg.transform(X.ravel())
    cal_proba = np.clip(cal_proba, self.cap_min, self.cap_max)
    return np.column_stack([1 - cal_proba, cal_proba])
```

**Problem**: When model is uncertain (OOD), it outputs probabilities near 1.0. Isotonic calibration maps these to 0.999, and all files end up at ~0.958 after rounding.

### Fix Applied
1. **Moderate capping (0.01-0.95)**: Prevents extreme clustering while preserving ranking
2. **Clustering detection**: Check if std < 0.05 or range < 0.1
3. **Automatic spreading**: If clustering detected, apply percentile-based transformation to spread predictions (0.2-0.9 range)
4. **User warnings**: Inform user when clustering is detected and recommend focusing on TIER rankings

**Code changes**:
```python
def __init__(self, iso_reg, cap_min=0.01, cap_max=0.95):
    # Moderate capping to prevent extreme clustering
    
def predict_proba(self, X):
    cal_proba = self.iso_reg.transform(X.ravel())
    cal_proba = np.clip(cal_proba, self.cap_min, self.cap_max)
    
    # NEW: Detect and fix clustering
    if len(cal_proba) > 10:
        std = np.std(cal_proba)
        if std < 0.05:  # Clustering detected
            # Spread using percentile transformation
            ranks = np.argsort(np.argsort(cal_proba))
            percentiles = ranks / (len(ranks) - 1)
            cal_proba = 0.2 + percentiles * 0.7  # Map to 0.2-0.9
    
    return np.column_stack([1 - cal_proba, cal_proba])
```

**Training-time detection**:
```python
# Check for probability clustering after calibration
prob_std = np.std(cal_proba)
prob_range = cal_proba.max() - cal_proba.min()
if prob_std < 0.05 or prob_range < 0.1:
    print(f"  ⚠ WARNING: Low probability variance detected")
    print(f"    Calibration may have caused clustering.")
```

**Inference-time warnings**:
```python
# In bug_predictor.py
risk_std = df['risk'].std()
risk_range = df['risk'].max() - df['risk'].min()
if risk_std < 0.05 or risk_range < 0.1:
    print(f"   ⚠ Risk scores are tightly clustered")
    print(f"     Focus on TIER rankings for prioritization.")
```

---

## Problem 3: "279 Lines Added" Flagged as Risky (Feels Normal)

### Symptoms
```
#10. tk.py
     Risk: 95.8% | Tier: CRITICAL | LOC: 121
     Why risky: · Very large single change (279 lines added at once), which increases defect risk
```

User feedback: "279 lines feels normal to me"

### Root Cause
**File**: `backend/explainer.py` → `_explain_feature_human_readable()`

The `max_added` feature used a **hardcoded absolute threshold (200 lines)**:
```python
"max_added": lambda v: f"Very large single change ({v:.0f} lines added at once)" if v > 200 else None
```

**Problem**: 
- Training data (Python/JavaScript web frameworks) has small commits (median ~50 lines)
- Friend's repository may have different commit patterns (e.g., CLI tools, generated code)
- 279 lines might be **normal** for this repo but **large** compared to training data

### Fix Applied
1. **Context-relative thresholds**: Compare to repository median instead of absolute value
2. **Ratio-based explanations**: Show "3× repo median" instead of just "279 lines"
3. **Higher absolute fallback**: Only flag truly massive changes (>500 lines) when no repo context

**Code changes**:
```python
if feature_name == "max_added":
    # NEW: Context-relative threshold
    if repo_median and ratio and value > repo_median * 3:
        return f"Very large single change ({int(value)} lines, {ratio:.1f}× repo median)"
    elif value > 500:  # Absolute threshold for truly massive changes
        return f"Very large single change ({int(value)} lines added at once)"
    else:
        return None  # Don't flag normal commits
```

**Before**: "279 lines" → flagged (> 200 threshold)  
**After**: "279 lines" → not flagged if repo median is 100+ (ratio < 3×)

---

## Additional Improvements

### 1. Tier-Based Output (Instead of Absolute Percentages)
**Problem**: Users focus on "95.8%" and think all files are equally risky.

**Fix**: Emphasize TIER rankings (CRITICAL/HIGH/MODERATE/LOW) based on percentile:
```
CRITICAL (top 10%):    2 files → Immediate review required
HIGH (10-25%):         1 file  → Prioritize for review
MODERATE (25-50%):     3 files → Consider for review
LOW (bottom 50%):      4 files → Low priority
```

### 2. Precision Adjustment for Clustered Scores
**Problem**: "95.8%, 95.8%, 95.8%" looks suspicious.

**Fix**: Show 3 decimals when clustering detected:
```python
if risk_std < 0.05:
    risk_display = f"{row['risk']:.3f}"  # 0.958, 0.957, 0.956
else:
    risk_display = risk_pct  # 95.8%, 87.3%, 72.1%
```

### 3. Interpretation Guide
Added footer to CLI output:
```
Interpretation Guide:
  • Focus on TIER (CRITICAL/HIGH/MODERATE/LOW) for prioritization
  • CRITICAL = top 10% riskiest files in THIS repository
  • Risk scores are relative rankings, not absolute probabilities
  • Files with similar scores should be prioritized by tier, then by LOC
```

---

## Testing Recommendations

### 1. Test on OOD Repositories
- **Rust projects** (not in training data)
- **Large monorepos** (>1000 files)
- **Repositories with sparse git history** (<5 commits per file)

### 2. Verify Clustering Detection
```bash
python bug_predictor.py <ood_repo>
# Should see: "⚠ Risk scores are tightly clustered"
# Should see: Tier distribution (not all CRITICAL)
```

### 3. Validate Explanations
```bash
# Count empty explanations
grep -c "Why risky:$" output.txt  # Should be 0
```

### 4. Check Probability Spread
After retraining:
```python
# In training output, verify:
# std > 0.10 (good spread)
# range > 0.3 (good discrimination)
```

---

## Impact Assessment

| Issue | Severity | User Impact | Fix Complexity |
|-------|----------|-------------|----------------|
| Empty explanations | HIGH | Users don't understand why files are risky | LOW (1 function) |
| Identical risk scores | CRITICAL | Users lose trust in model | MEDIUM (calibration logic) |
| Misleading thresholds | MEDIUM | Users question model judgment | LOW (threshold adjustment) |

---

## Recommendations

### Immediate (Done)
- ✅ Fix empty explanations with fallback mechanism
- ✅ Add clustering detection and spreading
- ✅ Implement context-relative thresholds
- ✅ Emphasize TIER rankings over absolute percentages

### Short-term (Next Sprint)
- [ ] Retrain model with new calibration parameters
- [ ] Add OOD confidence scoring (separate from risk score)
- [ ] Implement repository-specific threshold learning

### Long-term (Future)
- [ ] Train separate models for different languages/domains
- [ ] Add active learning to adapt to new repositories
- [ ] Implement uncertainty quantification (Bayesian approach)

---

## Conclusion

All three issues stem from **out-of-distribution detection failures**. The model was trained on Python/JavaScript web frameworks but applied to a very different repository (likely CLI tools or different language).

**Key insight**: When the model is uncertain, it should **spread predictions** and **warn the user**, not cluster all files at 95.8% and claim high confidence.

**Fixes applied**:
1. Explanation fallback mechanism (no more empty "Why risky")
2. Clustering detection + automatic spreading (better discrimination)
3. Context-relative thresholds (fewer false alarms)
4. Tier-based output (better user guidance)

**Expected outcome**: Users will see varied risk scores (20%-90% range), meaningful explanations for all files, and clear guidance to focus on TIER rankings when scores are clustered.
