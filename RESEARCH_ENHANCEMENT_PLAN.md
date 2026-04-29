# RESEARCH-GRADE ENHANCEMENT PLAN
## Deep Analysis & Industry-Grade Fixes

### CRITICAL PROBLEMS IDENTIFIED

#### Problem 1: Label Noise (87% buggy rate)
**Root Cause Analysis:**
- Current SZZ: ANY file touched in bug-fix commit = buggy
- Reality: Not all files in a bug-fix commit contain bugs
- Example: Bug in auth.py, but commit also updates README.md
- Result: README.md incorrectly labeled as buggy

**Research-Based Solution:**
1. **Stricter Bug-Fix Detection:**
   - Require issue tracker references (#123, JIRA-456)
   - Detect revert commits (strong bug signal)
   - Use commit message NLP scoring
   - Require minimum code changes (not just docs)

2. **File-Level Filtering:**
   - Only label files with substantive code changes
   - Exclude documentation-only changes
   - Require minimum lines changed (e.g., >3 lines)
   - Check if deleted lines were actual code (not comments)

3. **Confidence-Based Thresholding:**
   - Only label files with confidence >0.6 as buggy
   - Use probabilistic labels instead of binary
   - Weight by commit message strength

**Expected Impact:**
- Flask: 87% → 35-45% (realistic)
- Express: 85% → 30-40%
- Overall: More accurate ground truth

#### Problem 2: Defects@20% = 32.9% (CRITICAL)
**Root Cause Analysis:**
- Model optimized for F1 (classification)
- NOT optimized for ranking (top-K recall)
- XGBoost default objective: binary classification
- Need: Learning-to-rank objective

**Research-Based Solution:**
1. **Learning-to-Rank (LTR) Objective:**
   ```python
   # Use pairwise ranking loss
   objective='rank:pairwise'  # or 'rank:ndcg'
   ```

2. **Ranking-Aware Training:**
   - Group files by repository
   - Optimize NDCG@20 instead of F1
   - Use listwise loss functions

3. **Post-Ranking Calibration:**
   - Re-rank within repositories
   - Use percentile-based scoring
   - Boost high-confidence predictions

**Expected Impact:**
- Defects@20%: 32.9% → 65-75% (realistic target)
- Better prioritization for code review

#### Problem 3: Probability Saturation (100% everywhere)
**Root Cause Analysis:**
- Isotonic regression can over-fit on small calibration sets
- XGBoost naturally produces extreme probabilities
- No probability capping mechanism

**Research-Based Solution:**
1. **Temperature Scaling:**
   ```python
   # Scale logits before sigmoid
   calibrated_prob = sigmoid(logits / temperature)
   ```

2. **Platt Scaling with Regularization:**
   ```python
   # L2-regularized logistic regression
   LogisticRegression(C=1.0, penalty='l2')
   ```

3. **Probability Capping:**
   ```python
   # Cap extreme probabilities
   prob = np.clip(prob, 0.05, 0.95)
   ```

4. **Beta Calibration:**
   - More flexible than Platt scaling
   - Better for skewed distributions

**Expected Impact:**
- Probabilities: 55%-92% range (realistic)
- Fewer 100% predictions
- Better calibration metrics

#### Problem 4: Tiny Repos Distorting Metrics
**Already Addressed:**
- Weighted average by repo size ✓
- Honest average excluding <20 files ✓
- Flagging small repos ✓

**Additional Enhancement:**
- Bootstrap confidence intervals
- Statistical significance testing

#### Problem 5: SHAP Errors
**Root Cause:**
- XGBoost wrapper compatibility
- Feature names not preserved

**Solution:**
- Fix model wrapping
- Ensure feature_names_in_ is set

### IMPLEMENTATION PRIORITY

**Phase 1: Critical Fixes (Immediate)**
1. Stricter SZZ labeling (reduce noise)
2. Learning-to-rank objective
3. Probability calibration improvements

**Phase 2: Enhancements (Next)**
4. Better bug-fix detection
5. SHAP error fixes
6. Confidence intervals

### RESEARCH REFERENCES

1. **Learning to Rank:**
   - Liu, T. Y. (2009). "Learning to rank for information retrieval"
   - Burges et al. (2005). "Learning to Rank using Gradient Descent"

2. **Calibration:**
   - Guo et al. (2017). "On Calibration of Modern Neural Networks"
   - Kull et al. (2019). "Beyond temperature scaling"

3. **SZZ Improvements:**
   - da Costa et al. (2017). "A Framework for Evaluating the Results of the SZZ Approach"
   - Rodríguez-Pérez et al. (2018). "Reproducibility and Replicability of SZZ"

4. **Defect Prediction:**
   - Kamei et al. (2013). "A large-scale empirical study of just-in-time quality assurance"
   - Yang et al. (2016). "Effort-aware just-in-time defect prediction"

### METRICS TO TRACK

**Before:**
- Defects@20%: 32.9%
- Flask buggy: 87%
- Prob saturation: Many 100%

**After (Targets):**
- Defects@20%: >65%
- Flask buggy: 35-45%
- Prob range: 55-92%
- Calibration error: <0.05

### VALIDATION STRATEGY

1. **Cross-validation on held-out repos**
2. **Temporal validation (train on old, test on new)**
3. **Calibration curve analysis**
4. **Ranking metrics (NDCG, MAP)**
5. **Real-world simulation (top-K review)**
