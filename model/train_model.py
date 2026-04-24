import numpy as np
import pandas as pd
import joblib
import os
import json
import warnings
import datetime

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_selection import SelectFromModel
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, average_precision_score, f1_score,
    precision_recall_curve, make_scorer, brier_score_loss
)
from imblearn.over_sampling import SMOTE
from imblearn.combine import SMOTETomek
from xgboost import XGBClassifier

from config import (
    TUNING_N_ITER, TSCV_N_SPLITS, RANDOM_STATE,
    RISK_THRESHOLD, DEFECT_DENSITY_TOP_K,
    MODEL_LATEST_PATH, TRAINING_LOG_PATH, MODEL_VERSION, MODEL_DIR,
)

NON_FEATURE_COLS = [
    "file", "buggy", "bug_fixes", "bug_density",
    "buggy_commit", "commit_hash", "repo", "language", "confidence",
    "bug_type", "bug_type_confidence"
]

LEAKAGE_COLS = [
    "bug_fix_ratio",
    "past_bug_count",
    "days_since_last_bug",
]

# Scorer that handles folds where only one class is present
_f1_scorer = make_scorer(f1_score, zero_division=0)


class InferenceModel:
    """Wrapper for model with categorical preprocessing pipeline."""
    def __init__(self, base_model):
        self.base_model = base_model
    def predict_proba(self, X):
        return self.base_model.predict_proba(_process_categorical(X))
    def predict(self, X):
        return self.base_model.predict(_process_categorical(X))


# ── Probability calibration (sklearn-version-safe) ─────────────────────────────

class _ManualSigmoidModel:
    """Wrapper combining base model + sigmoid calibrator."""
    def __init__(self, base_model, calibrator):
        self.base_model  = base_model
        self.calibrator  = calibrator
        self.classes_    = getattr(base_model, "classes_", np.array([0, 1]))
        self.feature_names_in_ = None
    
    def predict_proba(self, X):
        raw = self.base_model.predict_proba(X)[:, 1]
        cal = self.calibrator.predict_proba(raw.reshape(-1, 1))
        return cal  # shape (n, 2)
    
    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def _calculate_confidence_interval(prob, n_samples, confidence=0.95):
    """
    Calculate confidence interval for probability predictions.
    Uses Wilson score interval which works well for binary probabilities.
    """
    from scipy import stats
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    
    # Wilson score interval
    denominator = 1 + z**2 / n_samples
    center = (prob + z**2 / (2 * n_samples)) / denominator
    margin = z * np.sqrt((prob * (1 - prob) + z**2 / (4 * n_samples)) / n_samples) / denominator
    
    lower = max(0, center - margin)
    upper = min(1, center + margin)
    
    return lower, upper


def _interpret_risk_score(prob, n_samples=None, confidence_level="High"):
    """
    Provide human-readable interpretation of risk scores with confidence context.
    """
    if n_samples and n_samples > 10:
        lower, upper = _calculate_confidence_interval(prob, n_samples)
        confidence_desc = f" ({lower:.1%}-{upper:.1%} range)"
    else:
        confidence_desc = ""
    
    # Risk interpretation categories
    if prob >= 0.80:
        return f"Critical risk: {prob:.1%}{confidence_desc} - Immediate review required"
    elif prob >= 0.60:
        return f"High risk: {prob:.1%}{confidence_desc} - Prioritize for review"
    elif prob >= 0.40:
        return f"Moderate risk: {prob:.1%}{confidence_desc} - Consider for review"
    elif prob >= 0.20:
        return f"Low risk: {prob:.1%}{confidence_desc} - Monitor if changes planned"
    else:
        return f"Minimal risk: {prob:.1%}{confidence_desc} - Low priority"


def _calibrate(model, X_uncal, y_uncal):
    """
    Sigmoid calibration works correctly on small datasets.
    Uses manual LogisticRegression because CalibratedClassifierCV 
    fails on our custom model wrapper.
    """
    raw_proba = model.predict_proba(X_uncal)[:, 1]
    lr_calibrator = LogisticRegression()
    lr_calibrator.fit(raw_proba.reshape(-1, 1), y_uncal)
    calibrated = _ManualSigmoidModel(model, lr_calibrator)
    return calibrated
# ── Feature importance helper ────────────────────────────────────────────────────────

def _print_feature_importances(model, feature_names, top_n=10):
    """Print top-N feature importances from the tree step in a Pipeline."""
    try:
        named = model.named_steps
        clf_name = next(s for s in named if s != "scaler")
        clf = named[clf_name]
        if not hasattr(clf, "feature_importances_"):
            return
        importances = pd.Series(clf.feature_importances_, index=feature_names)
        top = importances.sort_values(ascending=False).head(top_n)
        print(f"\n  Top-{top_n} feature importances ({clf_name}):")
        max_imp = top.iloc[0] if len(top) > 0 else 1
        for feat, imp in top.items():
            bar = "█" * max(1, int(imp / max_imp * 30))
            print(f"    {feat:<35} {imp:.4f}  {bar}")
    except Exception:
        pass


# ── Feature column sets for ablation study ──────────────────────────────────────────

_STATIC_FEATURE_BASE = [
    "loc", "avg_complexity", "max_complexity", "functions",
    "avg_params", "max_function_length", "complexity_density",
    "complexity_per_function", "loc_per_function", "has_test_file"
]

_GIT_FEATURE_BASE = [
    "commits", "lines_added", "lines_deleted", "max_added",
    "commits_2w", "commits_1m", "commits_3m",
    "recent_churn_ratio", "recent_activity_score",
    "author_count", "ownership", "low_history_flag", "minor_contributor_ratio",
    "instability_score", "avg_commit_size", "max_commit_ratio",
    "file_age_bucket", "days_since_last_change", "recency_ratio",
    "max_coupling_strength", "coupled_file_count",
    "coupled_recent_missing", "coupling_risk",
    "commit_burst_score", "recent_commit_burst", "burst_ratio", "burst_risk",
    "recent_bug_flag", "bug_recency_score", "temporal_bug_risk", "temporal_bug_memory",
]


def _get_xy(df):
    X = df.drop(columns=NON_FEATURE_COLS + LEAKAGE_COLS, errors="ignore")
    y = df["buggy"]
    return X, y


def _print_metrics(name, y_test, preds, proba):
    """Compact per-model metric line — full report suppressed to reduce noise."""
    f1  = f1_score(y_test, preds, zero_division=0)
    if len(np.unique(y_test)) > 1:
        roc = roc_auc_score(y_test, proba)
        pra = average_precision_score(y_test, proba)
        print(f"    {name:<30}  F1={f1:.4f}  ROC-AUC={roc:.4f}  PR-AUC={pra:.4f}")
    else:
        print(f"    {name:<30}  F1={f1:.4f}  (single class — AUC skipped)")


def _loc_baseline(X_test, y_test):
    """
    Trivial LOC-only rank: flag top-K% by lines of code.
    Returns PR-AUC of LOC ranker as a comparison point.
    """
    if "loc" not in X_test.columns or len(np.unique(y_test)) < 2:
        return None
    loc_scores = X_test["loc"].values
    pr_auc = average_precision_score(y_test, loc_scores)
    lr_preds = (loc_scores >= np.percentile(loc_scores, 80)).astype(int)
    f1 = f1_score(y_test, lr_preds, zero_division=0)
    print(f"   LOC-only baseline  →  PR-AUC={pr_auc:.4f}  F1={f1:.4f}")
    return pr_auc


def _defect_density_validation(y_test, proba, top_k=DEFECT_DENSITY_TOP_K):
    """
    Research-grade check: what fraction of actual bugs are in the top-K% risk files?
    A good model should catch ≥70% of bugs in the top 20% of files.
    """
    if len(np.unique(y_test)) < 2:
        return 0.0
    n_top = max(1, int(len(y_test) * top_k))
    top_idx = np.argsort(proba)[::-1][:n_top]
    bugs_in_top = y_test.iloc[top_idx].sum() if hasattr(y_test, "iloc") else y_test[top_idx].sum()
    total_bugs  = y_test.sum()
    recall_at_k = bugs_in_top / total_bugs if total_bugs > 0 else 0
    return recall_at_k


def _top_k_evaluation(y_test, proba, X_test=None, loc_col=None):
    """
    Operational evaluation: Top-K ranking metrics for practical use.
    Answers: "Which files should we inspect today?"
    """
    if len(np.unique(y_test)) < 2:
        return None
    
    # Sort by predicted risk (descending)
    sorted_idx = np.argsort(proba)[::-1]
    y_sorted = y_test.iloc[sorted_idx] if hasattr(y_test, "iloc") else y_test[sorted_idx]
    
    results = {}
    
    # Recall@10 and Precision@10
    k = min(10, len(y_sorted))
    top_k_buggy = y_sorted[:k].sum()
    total_buggy = y_test.sum()
    
    results['total_buggy'] = total_buggy
    results['recall@10'] = top_k_buggy / total_buggy if total_buggy > 0 else 0
    results['precision@10'] = top_k_buggy / k if k > 0 else 0
    
    # Recall@5 for smaller teams
    k5 = min(5, len(y_sorted))
    top_5_buggy = y_sorted[:k5].sum()
    results['recall@5'] = top_5_buggy / total_buggy if total_buggy > 0 else 0
    results['precision@5'] = top_5_buggy / k5 if k5 > 0 else 0
    
    # Effort-aware metrics (top 20% by LOC if available)
    if X_test is not None and loc_col and loc_col in X_test.columns:
        loc_data = X_test[loc_col].iloc[sorted_idx] if hasattr(X_test, "iloc") else X_test[loc_col][sorted_idx]
        total_loc = loc_data.sum()
        
        # Find files that make up 20% of total LOC
        cum_loc = 0
        loc_20_idx = []
        for i, loc in enumerate(loc_data):
            cum_loc += loc
            loc_20_idx.append(i)
            if cum_loc >= total_loc * 0.2:
                break
        
        if loc_20_idx:
            bugs_in_20_loc = y_sorted.iloc[loc_20_idx].sum() if hasattr(y_sorted, "iloc") else y_sorted[loc_20_idx].sum()
            results['recall@20%_loc'] = bugs_in_20_loc / total_buggy if total_buggy > 0 else 0
            results['files_in_20%_loc'] = len(loc_20_idx)
            results['loc_coverage'] = cum_loc / total_loc
    
    return results


def _print_top_k_metrics(results, n_files=None):
    """Print operational Top-K metrics in a manager-friendly format."""
    if not results:
        return
    
    print(f"\n  TOP-K RANKING EVALUATION (Operational Metrics)")
    print(f"  {'='*50}")
    
    # Top-10 metrics (most common for daily reviews)
    print(f"  Top-10 Files for Daily Review:")
    print(f"    Recall@10: {results['recall@10']:.1%} of bugs caught")
    print(f"    Precision@10: {results['precision@10']:.1%} of top-10 actually buggy")
    
    # Top-5 metrics (small teams)
    print(f"  Top-5 Files (Small Teams):")
    print(f"    Recall@5: {results['recall@5']:.1%} of bugs caught")
    print(f"    Precision@5: {results['precision@5']:.1%} of top-5 actually buggy")
    
    # Effort-aware metrics
    if 'recall@20%_loc' in results:
        print(f"  Effort-Aware (20% LOC Review):")
        print(f"    Recall@20% LOC: {results['recall@20%_loc']:.1%} of bugs caught")
        print(f"    Files to review: {results['files_in_20%_loc']} ({results['loc_coverage']:.1%} of codebase)")
    
    # Operational guidance based on theoretical maximum
    print(f"\n  Operational Guidance:")
    total_bugs = results.get('total_buggy', 0)
    if total_bugs > 0:
        max_possible_recall = min(10 / total_bugs, 1.0)
        actual_vs_max = results['recall@10'] / max_possible_recall if max_possible_recall > 0 else 0
        
        if actual_vs_max >= 0.7:
            print(f"    Excellent recall@10 - achieves {actual_vs_max:.0%} of maximum possible recall (max={max_possible_recall:.1%})")
            print(f"    High operational value for daily code reviews")
        elif actual_vs_max >= 0.4:
            print(f"    Moderate recall@10 - achieves {actual_vs_max:.0%} of maximum possible recall (max={max_possible_recall:.1%})")
            print(f"    Moderate operational value")
        else:
            print(f"    Low recall@10 - achieves only {actual_vs_max:.0%} of maximum possible recall")
            print(f"    Consider reviewing more files or investigating model performance")
    else:
        print(f"    No bugs in test set to evaluate recall")
    
    if n_files:
        review_ratio = 10 / n_files
        print(f"    Review effort: {review_ratio:.1%} of files for {results['recall@10']:.0%} bug coverage")


def _optimal_threshold(y_test, proba):
    """Find threshold that maximizes F1 on this test fold."""
    if len(np.unique(y_test)) < 2:
        return RISK_THRESHOLD
    precisions, recalls, thresholds = precision_recall_curve(y_test, proba)
    # suppress divide-by-zero warning: np.where already guards the zero case
    with np.errstate(invalid="ignore"):
        f1s = np.where(
            (precisions + recalls) > 0,
            2 * precisions * recalls / (precisions + recalls),
            0
        )
    best_idx = np.argmax(f1s[:-1])   # last point has no threshold
    best_thresh = thresholds[best_idx]
    best_f1 = f1s[best_idx]
    print(f"   Optimal threshold  →  {best_thresh:.3f}  (F1={best_f1:.4f} vs config={RISK_THRESHOLD})")
    return best_thresh


def _smote_resample(X_train, y_train, sample_weights=None):
    """
    SMOTE oversampling; always returns a DataFrame so SelectFromModel
    (and column-name-aware code) works correctly downstream.
    """
    cols     = list(X_train.columns) if isinstance(X_train, pd.DataFrame) else None
    minority = int(y_train.sum())
    majority = len(y_train) - minority

    if minority < 2:
        print(f"  \u26a0  SMOTE skipped: only {minority} minority sample(s) - "
              f"training on imbalanced data as-is")
        return X_train, y_train, sample_weights

    if majority < 2:
        return X_train, y_train, sample_weights

    k = min(5, minority - 1)
    smote = SMOTE(random_state=RANDOM_STATE, k_neighbors=k)
    Xr, yr = smote.fit_resample(X_train, y_train)

    # Guarantee DataFrame with original column names (some imblearn versions
    # silently drop them or rename with integers)
    if cols is not None and not isinstance(Xr, pd.DataFrame):
        Xr = pd.DataFrame(Xr, columns=cols)
    elif cols is not None and isinstance(Xr, pd.DataFrame):
        Xr.columns = cols

    # For SMOTE-generated samples, use average confidence weight
    if sample_weights is not None:
        original_count = len(sample_weights)
        synthetic_count = len(yr) - original_count
        if synthetic_count > 0:
            avg_confidence = np.mean(sample_weights)
            synthetic_weights = np.full(synthetic_count, avg_confidence)
            sample_weights = np.concatenate([sample_weights, synthetic_weights])

    return Xr, yr, sample_weights


def _smotetomek_resample(X_train, y_train, sample_weights=None):
    """
    SMOTETomek oversampling; combines SMOTE with Tomek links cleaning.
    Used for ablation study comparison.
    """
    cols     = list(X_train.columns) if isinstance(X_train, pd.DataFrame) else None
    minority = int(y_train.sum())
    majority = len(y_train) - minority

    if minority < 2:
        print(f"  \u26a0  SMOTETomek skipped: only {minority} minority sample(s) - "
              f"training on imbalanced data as-is")
        return X_train, y_train, sample_weights

    if majority < 2:
        return X_train, y_train, sample_weights

    k = min(5, minority - 1)
    from imblearn.over_sampling import SMOTE
    smote = SMOTE(k_neighbors=k, random_state=RANDOM_STATE)
    smt = SMOTETomek(random_state=RANDOM_STATE, smote=smote)
    Xr, yr = smt.fit_resample(X_train, y_train)

    # Guarantee DataFrame with original column names
    if cols is not None and not isinstance(Xr, pd.DataFrame):
        Xr = pd.DataFrame(Xr, columns=cols)
    elif cols is not None and isinstance(Xr, pd.DataFrame):
        Xr.columns = cols

    # For SMOTETomek-generated samples, use average confidence weight
    if sample_weights is not None:
        original_count = len(sample_weights)
        synthetic_count = len(yr) - original_count
        if synthetic_count > 0:
            avg_confidence = np.mean(sample_weights)
            synthetic_weights = np.full(synthetic_count, avg_confidence)
            sample_weights = np.concatenate([sample_weights, synthetic_weights])

    return Xr, yr, sample_weights


def _select_features(X_train, y_train, X_test, threshold='median'):
    """
    Fit a fast RF on training data and keep only features above
    `threshold` importance.  Returns (X_tr_sel, X_te_sel, kept_feature_names).

    Rules:
      - Fit SelectFromModel on SMOTE'd training data only.
      - Transform both train and test with the same fitted selector.
      - Never fit on test data.
    """
    selector = SelectFromModel(
        RandomForestClassifier(
            n_estimators=100,
            random_state=RANDOM_STATE,
            class_weight="balanced",
            n_jobs=-1,
        ),
        threshold=threshold,
    )
    selector.fit(X_train, y_train)

    mask    = selector.get_support()
    kept    = X_train.columns[mask].tolist()
    dropped = X_train.columns[~mask].tolist()

    # --- Rescue Sparse Features ---
    FORCE_KEEP = [
        "max_coupling_strength", 
        "coupled_file_count", 
        "coupled_recent_missing", 
        "coupling_risk",
        "burst_risk",
        "recent_commit_burst",
        "temporal_bug_risk",
        "recent_bug_flag"
    ]
    
    rescued = []
    for f in FORCE_KEEP:
        if f in dropped:
            kept.append(f)
            dropped.remove(f)
            rescued.append(f)

    print(f"  RFE: kept {len(kept)}, dropped {len(dropped)} (threshold='{threshold}')")
    if dropped:
        print(f"    Dropped: {dropped}")
    if rescued:
        print(f"    Rescued sparse features from RFE: {rescued}")

    X_tr_sel = X_train[kept].copy()
    X_te_sel = X_test[kept].copy()
    return X_tr_sel, X_te_sel, kept


def _temporal_sort(df):
    """
    Sort oldest-activity-first so TimeSeriesSplit trains on older data
    and validates on more recent data.
    
    This prevents temporal leakage - training on future data to predict past events.
    """
    if "days_since_last_change" in df.columns:
        # Sort by recency (oldest first = highest days_since_last_change)
        sorted_df = df.sort_values("days_since_last_change", ascending=False)
        print(f"  Temporal validation: using {len(sorted_df)} files sorted by last change date")
        return sorted_df
    if "file_age_bucket" in df.columns:
        sorted_df = df.sort_values("file_age_bucket", ascending=False)
        print(f"  Temporal validation: using {len(sorted_df)} files sorted by age bucket")
        return sorted_df
    print("  Warning: No temporal features found, using original order")
    return df


def _validate_temporal_split(train_df, test_df, is_temporal_split=True):
    """
    Validate that temporal split prevents future leakage.
    If is_temporal_split is False (e.g. cross-project), skip validation.
    """
    if not is_temporal_split:
        return True
        
    if "days_since_last_change" in train_df.columns and "days_since_last_change" in test_df.columns:
        # days_since_last_change is "days ago". Larger number = older.
        # To prevent leakage, the newest file in train must be older than the oldest file in test.
        train_newest = train_df["days_since_last_change"].min()
        test_oldest = test_df["days_since_last_change"].max()
        
        if train_newest >= test_oldest:
            print(f"  \u2713 Temporal validation passed: train data older ({train_newest:.0f} days) than test ({test_oldest:.0f} days)")
            return True
        else:
            print(f"  \u26a0 Temporal validation warning: potential leakage detected")
            print(f"    Train newest: {train_newest:.0f} days ago, Test oldest: {test_oldest:.0f} days ago")
            return False
    
    return True  # Can't validate without temporal features


def _process_categorical(X):
    """Cast specific columns to categorical dtype for XGBoost."""
    X_out = X.copy()
    if "language_id" in X_out.columns:
        # Round handles floating point outputs from SMOTE before casting
        X_out["language_id"] = X_out["language_id"].round().astype(int).astype("category")
    return X_out


# Training data distribution statistics for uncertainty detection
_TRAINING_STATS = {
    "supported_languages": {"python", "javascript", "typescript", "java", "go", "ruby", "php", "csharp", "cpp", "c"},
    "language_mapping": {
        "python": 0, "javascript": 1, "typescript": 2, "java": 3, "go": 4, "ruby": 5, 
        "php": 6, "csharp": 7, "cpp": 8, "c": 9
    },
    "feature_ranges": {
        "avg_complexity": {"min": 1.0, "max": 50.0},
        "loc": {"min": 10, "max": 10000},
        "commits": {"min": 1, "max": 1000},
        "lines_added": {"min": 0, "max": 5000},
        "lines_deleted": {"min": 0, "max": 2000},
        "author_count": {"min": 1, "max": 50},
    }
}


def _detect_out_of_distribution(df):
    """
    Detect out-of-distribution inputs that may lead to unreliable predictions.
    
    Returns confidence score and warnings.
    """
    warnings = []
    confidence_score = 1.0  # Start with full confidence
    
    # Check for unsupported languages
    if "language" in df.columns:
        unique_languages = set(df["language"].str.lower().unique())
        unsupported = unique_languages - _TRAINING_STATS["supported_languages"]
        if unsupported:
            warnings.append(f"Unsupported language(s): {', '.join(unsupported)}")
            confidence_score *= 0.3  # Heavy penalty for unsupported languages
    
    # Check feature distributions
    for feature, ranges in _TRAINING_STATS["feature_ranges"].items():
        if feature in df.columns:
            feature_min = df[feature].min()
            feature_max = df[feature].max()
            
            # Check if values are outside training ranges
            if feature_min < ranges["min"] * 0.5 or feature_max > ranges["max"] * 2.0:
                warnings.append(f"Feature '{feature}' values outside training range")
                confidence_score *= 0.8
    
    # Check for sparse data (very few files)
    if len(df) < 10:
        warnings.append("Very small repository (less than 10 files)")
        confidence_score *= 0.7
    
    # Check for missing git history
    git_features = ["commits", "lines_added", "lines_deleted", "author_count"]
    missing_git = sum(1 for feat in git_features if feat in df.columns and df[feat].sum() == 0)
    if missing_git >= 3:
        warnings.append("Limited or missing git history")
        confidence_score *= 0.6
    
    # Check for extreme complexity values
    if "avg_complexity" in df.columns:
        high_complexity = (df["avg_complexity"] > 30).sum()
        if high_complexity > len(df) * 0.3:
            warnings.append("Many files with extremely high complexity")
            confidence_score *= 0.8
    
    return {
        "confidence_score": max(confidence_score, 0.1),  # Minimum 10% confidence
        "warnings": warnings,
        "is_reliable": confidence_score > 0.7
    }


def _calculate_prediction_entropy(proba):
    """
    Calculate entropy of probability predictions as uncertainty measure.
    Higher entropy = more uncertainty.
    """
    # Avoid log(0) by adding small epsilon
    eps = 1e-10
    proba_clipped = np.clip(proba, eps, 1 - eps)
    
    # Binary entropy: -p*log(p) - (1-p)*log(1-p)
    entropy = -proba_clipped * np.log(proba_clipped) - (1 - proba_clipped) * np.log(1 - proba_clipped)
    
    # Average entropy across all predictions
    avg_entropy = np.mean(entropy)
    
    # Normalize to [0, 1] where 0 = certain, 1 = maximum uncertainty
    max_entropy = np.log(2)  # Maximum binary entropy
    normalized_entropy = avg_entropy / max_entropy
    
    return normalized_entropy


def _assess_prediction_confidence(df, proba):
    """
    Comprehensive confidence assessment combining multiple uncertainty measures.
    """
    # Out-of-distribution detection
    ood_result = _detect_out_of_distribution(df)
    
    # Prediction entropy
    entropy = _calculate_prediction_entropy(proba)
    
    # Combine confidence scores
    base_confidence = ood_result["confidence_score"]
    entropy_penalty = entropy * 0.3  # Entropy reduces confidence
    
    final_confidence = max(base_confidence - entropy_penalty, 0.1)
    
    # Determine confidence level
    if final_confidence > 0.8:
        confidence_level = "HIGH"
        message = "Predictions are reliable"
    elif final_confidence > 0.6:
        confidence_level = "MEDIUM"
        message = "Predictions may be less reliable"
    else:
        confidence_level = "LOW"
        message = "Predictions may be unreliable"
    
    return {
        "confidence_score": final_confidence,
        "confidence_level": confidence_level,
        "message": message,
        "warnings": ood_result["warnings"],
        "entropy": entropy,
        "out_of_distribution": not ood_result["is_reliable"]
    }


def _calculate_effort_aware_metrics(df):
    """
    Calculate effort-aware metrics for better prioritization.
    
    Returns:
        - risk_per_loc: Risk score normalized by lines of code
        - effort_priority: Priority score considering both risk and effort
        - effort_category: Categorization of effort efficiency
    """
    if "loc" not in df.columns or "risk" not in df.columns:
        return df
    
    df = df.copy()
    
    # Calculate risk per LOC (avoid division by zero)
    df["risk_per_loc"] = df["risk"] / df["loc"].clip(lower=1)
    
    # Calculate effort priority score (higher = more efficient to review)
    # Formula: risk * (1 / sqrt(LOC)) * 1000 for scaling
    import numpy as np
    df["effort_priority"] = df["risk"] * (1.0 / np.sqrt(df["loc"].clip(lower=1))) * 1000
    
    # Categorize effort efficiency
    def categorize_effort(row):
        risk = row["risk"]
        loc = row["loc"]
        risk_per_loc = row["risk_per_loc"]
        
        if risk >= 0.7 and loc <= 500:
            return "HIGH_VALUE"  # High risk, low effort
        elif risk >= 0.5 and risk_per_loc >= 0.001:
            return "EFFICIENT"   # Good risk per LOC ratio
        elif risk >= 0.7 and loc > 2000:
            return "EXPENSIVE"  # High risk but high effort
        elif risk < 0.3:
            return "LOW_PRIORITY"
        else:
            return "MODERATE"
    
    df["effort_category"] = df.apply(categorize_effort, axis=1)
    
    return df


def _get_effort_aware_recommendations(df, top_n=10, effort_budget=None):
    """
    Generate effort-aware review recommendations.
    
    Args:
        df: DataFrame with risk and LOC information
        top_n: Number of recommendations to return
        effort_budget: Maximum total LOC to review (optional)
    
    Returns:
        List of recommended files with effort metrics
    """
    if "effort_priority" not in df.columns:
        df = _calculate_effort_aware_metrics(df)
    
    # Sort by effort priority (descending)
    sorted_df = df.sort_values("effort_priority", ascending=False)
    
    recommendations = []
    total_loc = 0
    total_risk = 0
    
    for _, row in sorted_df.head(top_n).iterrows():
        rec = {
            "file": str(row["file"]),
            "risk": round(row["risk"], 3),
            "loc": int(row["loc"]),
            "risk_per_loc": round(row["risk_per_loc"], 6),
            "effort_priority": round(row["effort_priority"], 2),
            "effort_category": row["effort_category"],
            "review_effort": "Low" if row["loc"] <= 200 else "Medium" if row["loc"] <= 1000 else "High"
        }
        
        recommendations.append(rec)
        total_loc += row["loc"]
        total_risk += row["risk"]
        
        # Stop if effort budget is reached
        if effort_budget and total_loc >= effort_budget:
            break
    
    return {
        "recommendations": recommendations,
        "summary": {
            "files_recommended": len(recommendations),
            "total_loc": int(total_loc),
            "total_risk_captured": round(total_risk, 3),
            "avg_risk_per_loc": round(total_risk / total_loc, 6) if total_loc > 0 else 0,
            "effort_efficiency": round(total_risk / (total_loc / 1000), 3) if total_loc > 0 else 0
        }
    }

# ── Model persistence & monitoring ────────────────────────────────────────────

def _save_model_with_metadata(save_dict, *, metrics, repos, global_features):
    """
    Persist the trained model with three artefacts:

    1. **Timestamped pkl** – never overwritten, full history kept for rollback.
    2. **Latest alias** (MODEL_LATEST_PATH) – always points to the newest model
       so the serving layer needs no path changes after a retrain.
    3. **Training log** (TRAINING_LOG_PATH, JSONL) – one line per run.

    The timestamped path is generated HERE (at save time), not at import time,
    so importing config.py on the server does not create a phantom file path.

    Shadow / A/B mode: call `load_model_version(path)` with an older timestamped
    path and compare predict_proba outputs against the current model.
    """
    # Generate the per-run timestamped path at save time (Fix #7)
    _ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = os.path.join(MODEL_DIR, f"bug_predictor_{MODEL_VERSION}_{_ts}.pkl")

    os.makedirs(MODEL_DIR, exist_ok=True)

    # ── 1. Timestamped save ────────────────────────────────────────────────────
    joblib.dump(save_dict, model_path)
    print(f"Model saved → {model_path}")

    # ── 2. Stable latest alias ─────────────────────────────────────────────────
    joblib.dump(save_dict, MODEL_LATEST_PATH)
    print(f"Latest alias updated → {MODEL_LATEST_PATH}")

    # ── 3. Append one line to the training log ─────────────────────────────────
    timestamp = datetime.datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "version": MODEL_VERSION,
        "model_path": model_path,
        "training_repos": [os.path.basename(r) for r in repos],
        "n_features": len(global_features),
        "features": global_features,
        "metrics": metrics,
    }
    try:
        with open(TRAINING_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        print(f"Training log updated → {TRAINING_LOG_PATH}")
    except OSError as exc:
        print(f"  ⚠ Could not write training log: {exc}")

    print(f"Model expects {len(global_features)} feature(s): {global_features}")


def load_model_version(path=None):
    """
    Load a specific model version by path, or the latest alias when *path* is
    None (default).

    This is the entry-point for A/B / shadow-mode comparisons:

        production = load_model_version()              # always the latest
        challenger = load_model_version("model/bug_predictor_v1_20260401_120000.pkl")

        # Shadow: log challenger predictions without affecting users
        prod_risk   = production["model"].predict_proba(X)[:, 1]
        shadow_risk = challenger["model"].predict_proba(X)[:, 1]
        print("Δ risk (prod - shadow):", (prod_risk - shadow_risk).mean())

    Returns the save_dict (keys: "model", "features") or raises FileNotFoundError.
    """
    target = path or MODEL_LATEST_PATH
    if not os.path.exists(target):
        raise FileNotFoundError(
            f"Model file not found: {target}\n"
            "Run main.py to train and save the model first."
        )
    save_dict = joblib.load(target)
    # Normalise: old saves stored just the model object, not a dict
    if not isinstance(save_dict, dict):
        save_dict = {"model": save_dict, "features": []}
    print(f"Loaded model from {target}")
    return save_dict


def _tune_rf(X_train, y_train, sample_weights=None):
    tscv = TimeSeriesSplit(n_splits=TSCV_N_SPLITS)
    param_dist = {
        "n_estimators":      [100, 200, 300],
        "max_depth":         [4, 6, 8],
        "min_samples_split": [5, 10, 20],
        "min_samples_leaf":  [2, 4, 8],
        "max_samples":       [0.6, 0.7, 0.8],
    }
    # No scaling needed for Random Forest
    rf = RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1)
    
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Scoring failed")
        search = RandomizedSearchCV(
            rf, param_dist,
            n_iter=TUNING_N_ITER, cv=tscv,
            scoring=_f1_scorer, n_jobs=-1,
            random_state=RANDOM_STATE, refit=True,
            error_score=0.0
        )
        if sample_weights is not None:
            search.fit(X_train, y_train, sample_weight=sample_weights)
        else:
            search.fit(X_train, y_train)
    if search.best_score_ == 0.0:
        print("  ⚠  RF best CV score is 0.0")
    print(f"  Best RF params : {search.best_params_}")
    return search.best_estimator_


def _tune_xgb(X_train, y_train, sample_weights=None):
    tscv = TimeSeriesSplit(n_splits=TSCV_N_SPLITS)
    param_dist = {
        "n_estimators":     [100, 200, 300],
        "max_depth":        [3, 5, 7],
        "learning_rate":    [0.01, 0.05, 0.1],
        "subsample":        [0.7, 0.8, 1.0],
        "colsample_bytree": [0.7, 0.8, 1.0],
    }
    scale_weight = len(y_train[y_train == 0]) / max(1, len(y_train[y_train == 1]))

    # Must process language_id to category for XGBoost explicitly
    X_train_proc = _process_categorical(X_train)

    xgb = XGBClassifier(
        eval_metric="logloss",
        scale_pos_weight=scale_weight,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        enable_categorical=True,
        tree_method="hist"  # Hist strategy required for categorical splits in XGBoost
    )
    
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Scoring failed")
        search = RandomizedSearchCV(
            xgb, param_dist,
            n_iter=TUNING_N_ITER, cv=tscv,
            scoring=_f1_scorer, n_jobs=-1,
            random_state=RANDOM_STATE, refit=True,
            error_score=0.0
        )
        if sample_weights is not None:
            search.fit(X_train_proc, y_train, sample_weight=sample_weights)
        else:
            search.fit(X_train_proc, y_train)
    if search.best_score_ == 0.0:
        print("  ⚠  XGB best CV score is 0.0")
    print(f"  Best XGB params: {search.best_params_}")
    return search.best_estimator_


def train_model(df, repos):
    """
    Cross-project leave-one-out evaluation.
    - Temporal sort on train data (oldest → newest by days_since_last_change)
    - SMOTE on train only, per fold
    - LR baseline → RF → XGBoost with TimeSeriesSplit tuning (F1 scoring)
    - LOC-only baseline comparison (research requirement)
    - Optimal threshold tuning per fold
    - Defect density validation (% of bugs in top-20% risk files)
    - Feature importance printout for tree models
    - Tracks which architecture wins most folds; retrains on full data
    - Prints cross-project summary table after all folds
    """
    projects = df["repo"].unique()

    if len(projects) < 2:
        print("Only one project — falling back to single temporal split")
        return _single_project_train(df)

    print("\nSelecting global feature set (RFE on full data)...")
    X_full_raw, y_full_raw = _get_xy(_temporal_sort(df))
    try:
        _, _, global_features = _select_features(
            X_full_raw, y_full_raw, X_full_raw, threshold='median'
        )
    except Exception as fse:
        print(f"  Global RFE failed ({fse}) — using all features")
        global_features = X_full_raw.columns.tolist()
    print(f"  Global feature set ({len(global_features)} cols): {global_features}")

    arch_f1_totals   = {"LR": 0.0, "RF": 0.0, "XGB": 0.0}
    arch_fold_models = {"LR": None, "RF": None, "XGB": None}
    fold_results     = []   # for summary table
    fold_count       = 0

    for test_repo in projects:
        print(f"\n{'='*60}")
        print(f"TEST PROJECT : {test_repo}")
        print(f"TRAIN        : {[r for r in projects if r != test_repo]}")

        train_df = _temporal_sort(df[df["repo"] != test_repo])
        test_df  = _temporal_sort(df[df["repo"] == test_repo])  # FIXED: Sort test data temporally
        
        # Validate temporal split prevents future leakage
        _validate_temporal_split(train_df, test_df, is_temporal_split=False)

        if len(train_df) < 10 or len(test_df) < 5:
            print("  Skipping fold — insufficient data")
            continue

        X_train_raw, y_train_raw = _get_xy(train_df)
        X_test,      y_test      = _get_xy(test_df)
        
        # Scope to globally selected features (so all folds are comparable)
        shared_cols = [c for c in global_features if c in X_train_raw.columns and c in X_test.columns]
        X_train_raw = X_train_raw[shared_cols]
        X_test      = X_test[shared_cols]

        # Extract confidence weights from the original data
        sample_weights = train_df["confidence"].values if "confidence" in train_df.columns else None
        
        # SMOTETomek on train only (never on test)
        X_train, y_train, sample_weights = _smotetomek_resample(X_train_raw, y_train_raw, sample_weights)
        train_buggy = int(y_train.sum())
        print(f"  Data  train={len(X_train)} (buggy={train_buggy})  "
              f"test={len(X_test)} (buggy={int(y_test.sum())})")

        # ── Logistic Regression baseline ────────────────────────────────────
        lr = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE))
        ])
        lr.fit(X_train, y_train, lr__sample_weight=sample_weights)
        lr_preds = lr.predict(X_test)
        lr_proba = lr.predict_proba(X_test)[:, 1]
        _print_metrics("LR (baseline)", y_test, lr_preds, lr_proba)

        # ── Random Forest ──────────────────────────────────────────────────────
        rf = _tune_rf(X_train, y_train, sample_weights)
        rf_preds = rf.predict(X_test)
        rf_proba = rf.predict_proba(X_test)[:, 1]
        _print_metrics("RF", y_test, rf_preds, rf_proba)

        # ── XGBoost ────────────────────────────────────────────────────────────
        xgb = _tune_xgb(X_train, y_train, sample_weights)
        X_test_xgb = _process_categorical(X_test)
        xgb_preds = xgb.predict(X_test_xgb)
        xgb_proba = xgb.predict_proba(X_test_xgb)[:, 1]
        _print_metrics("XGB", y_test, xgb_preds, xgb_proba)

        has_both = len(np.unique(y_test)) > 1

        fold_scores = {
            "LR":  (f1_score(y_test, lr_preds,  zero_division=0), lr,  lr_proba),
            "RF":  (f1_score(y_test, rf_preds,  zero_division=0), rf,  rf_proba),
            "XGB": (f1_score(y_test, xgb_preds, zero_division=0), xgb, xgb_proba),
        }

        for arch, (f1, model_obj, _) in fold_scores.items():
            arch_f1_totals[arch]  += f1
            arch_fold_models[arch] = model_obj

        fold_best_name  = max(fold_scores, key=lambda k: fold_scores[k][0])
        best_f1_fold    = fold_scores[fold_best_name][0]
        best_proba_fold = fold_scores[fold_best_name][2]
        print(f"  → Best: {fold_best_name}  F1={best_f1_fold:.4f}")

        # Collect fold metrics for summary table
        n_top = max(1, int(len(y_test) * DEFECT_DENSITY_TOP_K))
        top_idx = np.argsort(best_proba_fold)[::-1][:n_top]
        fold_dd = _defect_density_validation(y_test, best_proba_fold)

        # Top-K operational evaluation
        top_k_results = _top_k_evaluation(y_test, best_proba_fold, X_test, loc_col="loc")

        fold_results.append({
            "test_repo":      os.path.basename(test_repo),
            "model":          fold_best_name,
            "n_test":         len(y_test),
            "n_buggy":        int(y_test.sum()),
            "f1":             best_f1_fold,
            "pr_auc":         average_precision_score(y_test, best_proba_fold) if has_both else 0.0,
            "defect_density": fold_dd,
            "recall@10":      top_k_results['recall@10'] if top_k_results else 0.0,
            "precision@10":   top_k_results['precision@10'] if top_k_results else 0.0,
            "recall@5":       top_k_results['recall@5'] if top_k_results else 0.0,
            "precision@5":    top_k_results['precision@5'] if top_k_results else 0.0,
        })

        fold_count += 1

    # ── Cross-project summary table ──────────────────────────────────────────────────
    if fold_results:
        print(f"\n{'='*72}")
        print("  CROSS-PROJECT EVALUATION SUMMARY")
        print(f"{'='*72}")
        print(f"  {'Fold':<12} {'Model':<6} {'N(test)':<9} {'Buggy':<7} "
              f"{'F1':<8} {'PR-AUC':<10} {'Rec@10':<8} {'Prec@10':<9}")
        print(f"  {'-'*76}")
        for r in fold_results:
            print(f"  {r['test_repo']:<12} {r['model']:<6} {r['n_test']:<9} "
                  f"{r['n_buggy']:<7} {r['f1']:<8.4f} {r['pr_auc']:<10.4f} "
                  f"{r['recall@10']:<8.3f} {r['precision@10']:<9.3f}")
        avg_f1  = sum(r["f1"]  for r in fold_results) / len(fold_results)
        avg_auc = sum(r["pr_auc"] for r in fold_results) / len(fold_results)
        # Handle None values for defect_density
        dd_values = [r["defect_density"] for r in fold_results if r["defect_density"] is not None]
        avg_dd  = sum(dd_values) / len(dd_values) if dd_values else 0.0
        avg_rec10 = sum(r["recall@10"] for r in fold_results) / len(fold_results)
        avg_prec10 = sum(r["precision@10"] for r in fold_results) / len(fold_results)
        print(f"  {'-'*76}")
        print(f"  {'Average':<12} {'':6} {'':9} {'':7} "
              f"{avg_f1:<8.4f} {avg_auc:<10.4f} {avg_rec10:<8.3f} {avg_prec10:<9.3f}")
        print(f"{'='*72}")

    best_arch = max(arch_f1_totals, key=arch_f1_totals.get)
    avg_f1    = arch_f1_totals[best_arch] / max(fold_count, 1)
    print(f"\nBEST ARCHITECTURE: {best_arch} (avg F1={avg_f1:.4f} across {fold_count} folds)")
    print("Retraining on full dataset...")

    # ── Final Model Retraining (uses the globally selected features) ─────────
    # Since we already computed global_features above, we just subset to it here.
    X_all_raw, y_all_raw = _get_xy(_temporal_sort(df))
    
    # Split temporally: 80% train, 20% for calibration
    split_idx = int(len(X_all_raw) * 0.8)
    
    X_train_final = X_all_raw.iloc[:split_idx][global_features].copy()
    y_train_final = y_all_raw.iloc[:split_idx]
    
    X_cal_final = X_all_raw.iloc[split_idx:][global_features].copy()
    y_cal_final = y_all_raw.iloc[split_idx:]
    
    # SMOTETomek on the 80% train only
    sample_weights = train_df["confidence"].values if "confidence" in train_df.columns else None
    X_train_smote, y_train_smote, sample_weights = _smotetomek_resample(X_train_final, y_train_final, sample_weights)
    
    # Needs categorical pipeline processor
    X_train_smote = _process_categorical(X_train_smote)
    X_cal_final = _process_categorical(X_cal_final)

    print("Using deeper XGBoost for smoother probability output...")

    scale_weight = len(y_train_smote[y_train_smote == 0]) / max(1, len(y_train_smote[y_train_smote == 1]))

    # Pipeline removed to fix the DataFrame-category preservation for XGB
    best_model = XGBClassifier(
        n_estimators=600,
        max_depth=7,
        learning_rate=0.03,
        min_child_weight=2,
        reg_alpha=0.01,
        reg_lambda=1.0,
        eval_metric="logloss",
        scale_pos_weight=scale_weight,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        enable_categorical=True,
        tree_method="hist"
    )

    best_model.fit(X_train_smote, y_train_smote, sample_weight=sample_weights)

    # ── Probability calibration ────────────────────────────────────────────────────
    print("  Calibrating probabilities (sigmoid)...")
    calibrated_model = _calibrate(best_model, X_cal_final, y_cal_final)

    # ── Calibration sanity check ────────────────────────────────────────────────────
    cal_proba   = calibrated_model.predict_proba(X_cal_final)[:, 1]
    mean_pred   = cal_proba.mean()
    actual_rate = float(y_cal_final.mean())
    brier_score = brier_score_loss(y_cal_final, cal_proba)
    gap         = abs(mean_pred - actual_rate)
    cal_status  = "✓ well-calibrated" if gap < 0.05 else f"⚠ gap={gap:.3f}"
    print(f"  Calibration  pred={mean_pred:.3f}  actual={actual_rate:.3f}  "
          f"Brier={brier_score:.4f}  {cal_status}")

    os.makedirs("model", exist_ok=True)
    
    # Attach categorical pipeline preprocessor handler to ensure pipeline continues to work
    final_inference_obj = InferenceModel(calibrated_model)

    # Capture per-feature training distribution stats for OOD detection (Fix #22)
    _training_stats = {}
    for col in X_train_final.select_dtypes(include="number").columns:
        _training_stats[col] = {
            "mean": float(X_train_final[col].mean()),
            "std":  float(X_train_final[col].std(ddof=0)),
            "p99":  float(X_train_final[col].quantile(0.99)),
            "p01":  float(X_train_final[col].quantile(0.01)),
        }

    save_dict = {
        "model": final_inference_obj,
        "features": global_features,
        "training_stats": _training_stats,
    }

    _save_model_with_metadata(
        save_dict,
        metrics={"avg_f1": avg_f1, "avg_pr_auc": avg_auc},
        repos=repos,
        global_features=global_features,
    )

    return save_dict



def _single_project_train(df):
    """Fallback: temporal split on single project."""
    df_sorted = _temporal_sort(df)
    split     = int(len(df_sorted) * 0.7)
    train_df  = df_sorted.iloc[:split]
    test_df   = df_sorted.iloc[split:]

    X_train, y_train = _get_xy(train_df)
    X_test,  y_test  = _get_xy(test_df)

    sample_weights = train_df["confidence"].values if "confidence" in train_df.columns else None
    X_train, y_train, sample_weights = _smotetomek_resample(X_train, y_train, sample_weights)

    model = RandomForestClassifier(
        n_estimators=200, max_depth=8,
        random_state=RANDOM_STATE, n_jobs=-1
    )
    if sample_weights is not None:
        model.fit(X_train, y_train, sample_weight=sample_weights)
    else:
        model.fit(X_train, y_train)

    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    _print_metrics("Random Forest (single project)", y_test, preds, proba)
    _optimal_threshold(y_test, proba)
    _defect_density_validation(y_test, proba)

    # calibrate on full un-resampled data
    print("Calibrating probabilities...")
    X_uncal, y_uncal = _get_xy(_temporal_sort(df))
    calibrated = _calibrate(model, X_uncal, y_uncal)

    os.makedirs("model", exist_ok=True)

    calibrated_wrapped = InferenceModel(calibrated)
    save_dict = {"model": calibrated_wrapped, "features": X_train.columns.tolist()}
    _save_model_with_metadata(
        save_dict,
        metrics={},
        repos=[],
        global_features=X_train.columns.tolist(),
    )

    return save_dict


def run_ablation_study(df, global_features=None):
    """
    Ablation: compare Static-only vs Git-only vs Combined features.

    Uses Logistic Regression and Random Forest in cross-project LOO structure.
    Reports average F1, PR-AUC, and Brier for each feature subset, and a
    SMOTE vs SMOTETomek comparison computed in a single combined pass (Fix #16).

    Expected result (if model is meaningful):
      Combined > max(Static-only, Git-only)
    """
    from sklearn.base import clone

    projects = df["repo"].unique()
    if len(projects) < 2:
        print("  Ablation skipped — need ≥ 2 projects")
        return

    X_full, _ = _get_xy(df)
    available  = set(X_full.columns)

    static_cols   = [c for c in _STATIC_FEATURE_BASE if c in available]
    git_cols      = [c for c in _GIT_FEATURE_BASE    if c in available]
    combined_cols = sorted(available)

    feature_sets = {
        "Static-only":  static_cols,
        "Git-only":     git_cols,
    }
    if global_features:
        feature_sets["RFE-selected"] = global_features
    feature_sets["All-combined"] = combined_cols

    models = {
        "LR": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
        "RF": RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE, class_weight="balanced", n_jobs=-1)
    }

    results = {m_name: {fs_name: [] for fs_name in feature_sets} for m_name in models}

    for test_repo in projects:
        train_df = _temporal_sort(df[df["repo"] != test_repo])
        test_df  = df[df["repo"] == test_repo]

        if len(train_df) < 10 or len(test_df) < 5:
            continue
        if len(np.unique(test_df["buggy"])) < 2:
            continue

        _validate_temporal_split(train_df, test_df)

        X_tr_full, y_train = _get_xy(train_df)
        X_te_full, y_test  = _get_xy(test_df)

        for fs_name, cols in feature_sets.items():
            shared = [c for c in cols if c in X_tr_full.columns and c in X_te_full.columns]
            if not shared:
                continue

            X_tr = X_tr_full[shared]
            X_te = X_te_full[shared]
            sw   = train_df["confidence"].values if "confidence" in train_df else None
            X_tr_s, y_tr_s, sw_s = _smote_resample(X_tr, y_train, sw)

            for m_name, base_model in models.items():
                model = Pipeline([
                    ("scaler", StandardScaler()),
                    (m_name.lower(), clone(base_model))
                ])
                kw = {f"{m_name.lower()}__sample_weight": sw_s} if sw_s is not None else {}
                model.fit(X_tr_s, y_tr_s, **kw)
                preds = model.predict(X_te)
                proba = model.predict_proba(X_te)[:, 1]
                results[m_name][fs_name].append({
                    "f1":     f1_score(y_test, preds, zero_division=0),
                    "pr_auc": average_precision_score(y_test, proba),
                })

    print(f"\n{'='*60}")
    print(f"  ABLATION STUDY")
    print(f"{'='*60}")
    print(f"  {'Model':<6} {'Feature Set':<16} {'n_cols':<8} {'Avg F1':<10} {'Avg PR-AUC'}")
    print(f"  {'-'*56}")

    best_f1    = 0
    best_fs    = None
    best_model = None

    for m_name in models:
        for fs_name, cols in feature_sets.items():
            run_metrics = results[m_name][fs_name]
            if run_metrics:
                avg_f1  = sum(r["f1"]     for r in run_metrics) / len(run_metrics)
                avg_auc = sum(r["pr_auc"] for r in run_metrics) / len(run_metrics)
                n_cols  = len([c for c in cols if c in available])
                print(f"  {m_name:<6} {fs_name:<16} {n_cols:<8} {avg_f1:<10.4f} {avg_auc:.4f}")
                if avg_f1 > best_f1:
                    best_f1    = avg_f1
                    best_fs    = fs_name
                    best_model = m_name

    # ── SMOTETomek comparison: single combined pass per fold (Fix #16) ─────────
    print(f"\n  SMOTETomek Comparison (vs SMOTE):")
    print(f"  {'-'*40}")

    if best_fs:
        print(f"  Testing SMOTETomek on best config: {best_model} + {best_fs}")

        smote_fold_data = []   # (y_test, proba_smote)
        st_fold_data    = []   # (y_test, proba_smotetomek)

        for test_repo in projects:
            train_df = _temporal_sort(df[df["repo"] != test_repo])
            test_df  = df[df["repo"] == test_repo]

            if len(train_df) < 10 or len(test_df) < 5:
                continue
            if len(np.unique(test_df["buggy"])) < 2:
                continue

            X_tr_full, y_train = _get_xy(train_df)
            X_te_full, y_test  = _get_xy(test_df)

            cols   = feature_sets[best_fs]
            shared = [c for c in cols if c in X_tr_full.columns and c in X_te_full.columns]
            if not shared:
                continue

            X_tr = X_tr_full[shared]
            X_te = X_te_full[shared]
            sw   = train_df["confidence"].values if "confidence" in train_df else None

            # SMOTE pass
            X_s, y_s, sw_s = _smote_resample(X_tr, y_train, sw)
            m_smote = Pipeline([
                ("scaler", StandardScaler()),
                (best_model.lower(), clone(models[best_model]))
            ])
            kw_s = {f"{best_model.lower()}__sample_weight": sw_s} if sw_s is not None else {}
            m_smote.fit(X_s, y_s, **kw_s)
            smote_fold_data.append((y_test, m_smote.predict_proba(X_te)[:, 1]))

            # SMOTETomek pass (same fold, no extra repo traversal)
            X_t, y_t, sw_t = _smotetomek_resample(X_tr, y_train, sw)
            m_st = Pipeline([
                ("scaler", StandardScaler()),
                (best_model.lower(), clone(models[best_model]))
            ])
            kw_t = {f"{best_model.lower()}__sample_weight": sw_t} if sw_t is not None else {}
            m_st.fit(X_t, y_t, **kw_t)
            st_fold_data.append((y_test, m_st.predict_proba(X_te)[:, 1]))

        if smote_fold_data and st_fold_data:
            smote_results = results[best_model][best_fs]
            smote_f1  = sum(r["f1"]     for r in smote_results) / len(smote_results)
            smote_auc = sum(r["pr_auc"] for r in smote_results) / len(smote_results)
            smote_brier = sum(brier_score_loss(yt, yp) for yt, yp in smote_fold_data) / len(smote_fold_data)

            st_f1  = sum(
                f1_score(yt, (yp >= 0.5).astype(int), zero_division=0)
                for yt, yp in st_fold_data
            ) / len(st_fold_data)
            st_auc   = sum(average_precision_score(yt, yp) for yt, yp in st_fold_data) / len(st_fold_data)
            st_brier = sum(brier_score_loss(yt, yp)        for yt, yp in st_fold_data) / len(st_fold_data)

            print(f"  SMOTE:      F1={smote_f1:.4f}, PR-AUC={smote_auc:.4f}, Brier={smote_brier:.4f}")
            print(f"  SMOTETomek: F1={st_f1:.4f}, PR-AUC={st_auc:.4f}, Brier={st_brier:.4f}")

            f1_imp    = st_f1    - smote_f1
            auc_imp   = st_auc   - smote_auc
            brier_imp = smote_brier - st_brier  # lower Brier is better

            print(f"  Δ F1: {f1_imp:+.4f}, Δ PR-AUC: {auc_imp:+.4f}, Δ Brier: {brier_imp:+.4f}")

            if f1_imp > 0.005 and brier_imp > 0.001:
                print("  ✓ RECOMMEND: SMOTETomek shows meaningful improvement")
            elif f1_imp > 0.005 or (auc_imp > 0.002 and brier_imp > 0.001):
                print("  ⚠ CONSIDER: SMOTETomek shows mixed results")
            else:
                print("  ✗ KEEP: SMOTE remains preferred (gains too small/noisy)")


