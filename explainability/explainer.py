import os
import shap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from functools import lru_cache
from config import PLOTS_DIR


# Global SHAP explainer cache to avoid recomputation
_SHAP_EXPLAINER_CACHE = {}


def _get_model_hash(model):
    """Generate a hash for the model to use as cache key."""
    try:
        # Use model's memory address as a simple hash
        return str(id(model))
    except Exception:
        return "default"


def _get_cached_explainer(model, X_sample):
    """Get or create SHAP explainer with caching."""
    model_hash = _get_model_hash(model)
    
    if model_hash in _SHAP_EXPLAINER_CACHE:
        return _SHAP_EXPLAINER_CACHE[model_hash]
    
    # Create new explainer
    try:
        explainer = shap.TreeExplainer(model)
        _SHAP_EXPLAINER_CACHE[model_hash] = explainer
        return explainer
    except Exception:
        # Fallback to KernelExplainer
        explainer = shap.KernelExplainer(model.predict, X_sample[:10])
        _SHAP_EXPLAINER_CACHE[model_hash] = explainer
        return explainer


NON_FEATURE_COLS = [
    "file", "buggy", "bug_fixes", "bug_density",
    "buggy_commit", "commit_hash", "repo", "risk", "risky",
    "bug_fix_ratio", "past_bug_count", "days_since_last_bug",
    "explanation",
]


def _get_features(df):
    return df.drop(columns=NON_FEATURE_COLS, errors="ignore")


def _unwrap(model):
    """
    Unwrap a calibration wrapper to get the inner sklearn Pipeline.

    Handles two cases:
      - CalibratedClassifierCV  (sklearn < 1.4)  → .estimator
      - _ManualCalibratedModel  (sklearn >= 1.4 fallback) → .base_model
    """
    from sklearn.calibration import CalibratedClassifierCV
    if isinstance(model, CalibratedClassifierCV):
        return model.estimator
    if hasattr(model, "base_model"):        # _ManualCalibratedModel
        return model.base_model
    return model


def _unwrap_to_base(model):
    """
    Unwrap calibration wrappers and return the inner estimator (Pipeline or
    bare classifier). Handles CalibratedClassifierCV, _ManualSigmoidModel
    (base_model attribute), and legacy base_estimator. (Fix #17)
    """
    inner = _unwrap(model)   # strip outer calibration layer
    if hasattr(inner, "base_model"):
        return inner.base_model
    if hasattr(inner, "base_estimator"):
        return inner.base_estimator
    if hasattr(inner, "estimators_"):
        return inner.estimators_[0]
    return inner


def _get_clf(model):
    """Extract classifier step from pipeline regardless of name."""
    base = _unwrap_to_base(model)
    if hasattr(base, "named_steps"):
        step_name = [s for s in base.named_steps if s != "scaler"][0]
        return base.named_steps[step_name]
    return base


def _get_scaler(model):
    """Return the scaler step from a Pipeline, or None."""
    base = _unwrap_to_base(model)
    if hasattr(base, "named_steps"):
        return base.named_steps.get("scaler", None)
    return None


def _compute_shap(model, X):
    """
    Compute SHAP values using the appropriate explainer with caching.
    - LR  → LinearExplainer
    - RF / XGBoost → TreeExplainer (cached)

    CRITICAL: for Pipeline models, X must be transformed through the
    scaler before passing to TreeExplainer, because the tree model was
    fitted on scaled data (otherwise there is a feature-count mismatch
    between what the XGBoost model knows and what SHAP receives).

    X_display stays as the original (human-readable) values for plots.
    Returns (shap_values_class1, expected_value, X_display).
    """
    # First, unwrap any calibration wrapper to get the base model
    from sklearn.calibration import CalibratedClassifierCV
    if isinstance(model, CalibratedClassifierCV):
        base_model = model.estimator
    elif hasattr(model, "base_model"):  # _ManualCalibratedModel
        base_model = model.base_model
    else:
        base_model = model
    
    clf    = _get_clf(base_model)
    scaler = _get_scaler(base_model)

    # Pre-scale X if there is a scaler in the pipeline
    if scaler is not None:
        X_scaled = pd.DataFrame(
            scaler.transform(X),
            columns=X.columns,
            index=X.index
        )
    else:
        X_scaled = X

    # LR - use LinearExplainer (on scaled data)
    if hasattr(clf, "coef_"):
        # Fix for SHAP compatibility with scikit-learn 1.5+ 
        if type(clf).__name__ == "LogisticRegression" and not hasattr(clf, "multi_class"):
            clf.multi_class = "ovr"
            
        explainer = shap.LinearExplainer(
            clf, X_scaled, feature_perturbation="interventional"
        )
        shap_vals = np.array(explainer.shap_values(X_scaled))
        if shap_vals.ndim == 3:
            shap_vals = shap_vals[0]
        ev = explainer.expected_value
        ev = float(ev[0]) if hasattr(ev, "__len__") else float(ev)
        return shap_vals, ev, X   # X_display = original

    # RF / XGBoost - use TreeExplainer (cached)
    else:
        # For tree models, ensure we have the raw classifier without calibration
        if hasattr(clf, 'base_estimator'):
            shap_clf = clf.base_estimator
        elif hasattr(clf, 'estimators'):
            shap_clf = clf.estimators_[0] if hasattr(clf.estimators, '__getitem__') else clf.estimators
        else:
            shap_clf = clf
        
        try:
            # Use cached explainer for performance
            explainer = _get_cached_explainer(shap_clf, X_scaled)
            shap_vals = explainer.shap_values(X_scaled)
        except Exception as e:
            print(f"SHAP TreeExplainer failed: {e}")
            print(f"Model type: {type(shap_clf)}")
            # Fallback to using the original model with a different explainer
            try:
                explainer = shap.KernelExplainer(shap_clf.predict, X_scaled[:10])  # Use subset for performance
                shap_vals = explainer.shap_values(X_scaled)
            except Exception as e2:
                print(f"SHAP KernelExplainer also failed: {e2}")
                raise RuntimeError(
                    f"SHAP explainability failed for this model type. "
                    f"TreeExplainer error: {e}. KernelExplainer error: {e2}"
                ) from e2

    # list output: [class_0_array, class_1_array] — older SHAP + RF
    if isinstance(shap_vals, list):
        return shap_vals[1], explainer.expected_value[1], X

    shap_vals = np.array(shap_vals)

    # 3D array: (n_samples, n_features, n_classes) — newer SHAP + RF
    if shap_vals.ndim == 3:
        return shap_vals[:, :, 1], explainer.expected_value[1], X

    # 2D array: (n_samples, n_features) — XGBoost
    return shap_vals, explainer.expected_value, X


def _save_global_plots(shap_values, X_test):
    os.makedirs(PLOTS_DIR, exist_ok=True)

    # bar plot — mean absolute SHAP per feature
    plt.figure()
    shap.summary_plot(shap_values, X_test, plot_type="bar", show=False)
    plt.tight_layout()
    plt.savefig(f"{PLOTS_DIR}/global_bar.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved → {PLOTS_DIR}/global_bar.png")

    # beeswarm — direction + distribution
    plt.figure()
    shap.summary_plot(shap_values, X_test, show=False)
    plt.tight_layout()
    plt.savefig(f"{PLOTS_DIR}/global_beeswarm.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved → {PLOTS_DIR}/global_beeswarm.png")


def _save_local_plots(shap_values, expected_value, X_test, index, label):
    os.makedirs(PLOTS_DIR, exist_ok=True)

    safe_label = label.replace("/", "_").replace("\\", "_")

    sv = shap_values[index]
    if sv.ndim == 2:
        sv = sv[:, 1]

    ev = float(expected_value) if np.ndim(expected_value) == 0 else float(expected_value)

    # waterfall
    explanation = shap.Explanation(
        values=sv,
        base_values=ev,
        data=X_test.iloc[index].values,
        feature_names=list(X_test.columns)
    )
    plt.figure()
    shap.plots.waterfall(explanation, show=False)
    plt.tight_layout()
    plt.savefig(
        f"{PLOTS_DIR}/local_waterfall_{safe_label}.png",
        dpi=150, bbox_inches="tight"
    )
    plt.close()

    # force plot
    plt.figure()
    shap.force_plot(
        ev,
        sv,
        X_test.iloc[index],
        matplotlib=True,
        show=False
    )
    plt.tight_layout()
    plt.savefig(
        f"{PLOTS_DIR}/local_force_{safe_label}.png",
        dpi=150, bbox_inches="tight"
    )
    plt.close()


def _explain_feature_human_readable(feature_name, value, shap_value, direction="increases"):
    """
    Convert SHAP feature contributions to human-readable explanations.
    
    Args:
        feature_name: Name of the feature
        value: Actual feature value
        shap_value: SHAP contribution magnitude
        direction: "increases" or "decreases" risk
    
    Returns:
        Human-readable explanation string
    """
    # Map features to human-readable explanations
    feature_explanations = {
        # Complexity metrics
        "avg_complexity": lambda v: f"Contains high cyclomatic complexity ({v:.1f}), making testing and reasoning harder",
        "max_complexity": lambda v: f"Has very complex functions (max {v:.0f}), indicating difficult-to-maintain code",
        "complexity_density": lambda v: f"High complexity relative to size ({v:.3f}), suggesting dense logic",
        "complexity_per_function": lambda v: f"Functions are overly complex on average ({v:.1f})",
        "complexity_vs_baseline": lambda v: f"Complexity is {v:.1f}x above language baseline, indicating structural issues",
        "max_nesting_depth": lambda v: f"Deep block nesting detected (depth {v:.0f}), indicating hard-to-follow control flow",
        
        # Size metrics
        "loc": lambda v: f"Large file ({v:.0f} lines), harder to comprehensively review",
        "functions": lambda v: f"Many functions ({v:.0f}), increasing surface area for bugs",
        "max_function_length": lambda v: f"Contains very long functions ({v:.0f} lines), violating single responsibility",
        "avg_params": lambda v: f"Functions have many parameters on average ({v:.1f}), indicating complex interfaces",
        
        # Git activity metrics
        "commits": lambda v: f"High commit history ({v:.0f} changes), suggesting frequent modifications",
        "commits_2w": lambda v: f"Very active recently ({v:.0f} commits in 2 weeks), indicating instability",
        "commits_1m": lambda v: f"Frequent recent changes ({v:.0f} commits in 1 month), potential churn",
        "commits_3m": lambda v: f"Moderate recent activity ({v:.0f} commits in 3 months)",
        "recent_churn_ratio": lambda v: f"High recent churn ({v:.1%} of changes are recent)",
        "recent_activity_score": lambda v: f"Elevated recent activity ({v:.3f}), suggesting ongoing development",
        
        # Code churn metrics
        "lines_added": lambda v: f"Significant additions ({v:.0f} lines added), introducing new complexity",
        "lines_deleted": lambda v: f"Major deletions ({v:.0f} lines removed), potentially breaking existing code",
        "max_added": lambda v: f"Very large single change ({v:.0f} lines added at once), risky modification",
        "avg_commit_size": lambda v: f"Large average commits ({v:.1f} lines), indicating complex changes",
        "instability_score": lambda v: f"High instability ({v:.3f}), suggesting volatile code",
        "max_commit_ratio": lambda v: f"Contains massive commits ({v:.1f}x average), increasing risk",
        
        # Developer metrics
        "author_count": lambda v: f"Many contributors ({v:.0f} authors), potentially inconsistent style",
        "ownership": lambda v: f"Low ownership ({v:.1%}), suggesting no one understands this code well",
        "minor_contributor_ratio": lambda v: f"Many minor contributors ({v:.1%}), indicating scattered knowledge",
        
        # Temporal metrics
        "days_since_last_change": lambda v: f"Recently modified ({v:.0f} days ago), may contain new bugs",
        "recency_ratio": lambda v: f"Very recent changes ({v:.1%} of file age), suggesting active development",
        "file_age_bucket": lambda v: f"File age category {v:.0f}, indicating maturity level",
        
        # Bug history metrics
        "bug_fixes": lambda v: f"History of bug fixes ({v:.0f}), suggesting problematic area",
        "bug_recency_score": lambda v: f"Recent bug activity ({v:.3f}), indicating ongoing issues",
        "recent_bug_flag": lambda v: f"Recent bug fixes detected ({v:.0f}), high regression risk",
        "temporal_bug_risk": lambda v: f"Elevated temporal bug risk ({v:.3f})",
        "temporal_bug_memory": lambda v: f"Strong bug memory ({v:.3f}), historically problematic",
        
        # Coupling metrics
        "max_coupling_strength": lambda v: f"Tightly coupled to other files ({v:.3f}), changes cascade easily",
        "coupled_file_count": lambda v: f"High coupling ({v:.0f} coupled files), changes affect many areas",
        "coupled_recent_missing": lambda v: f"Missing recent changes in coupled files ({v:.0f}), potential inconsistency",
        "coupling_risk": lambda v: f"High coupling risk ({v:.3f}), likely to cause regressions",
        
        # Commit burst metrics
        "commit_burst_score": lambda v: f"Bursty commit pattern ({v:.3f}), suggesting rushed development",
        "recent_commit_burst": lambda v: f"Recent commit burst ({v:.0f}), indicating intense activity",
        "burst_ratio": lambda v: f"High burst ratio ({v:.3f}), potentially rushed changes",
        "burst_risk": lambda v: f"High burst risk ({v:.3f}), suggesting development pressure",
        
        # Test coverage
        "has_test_file": lambda v: f"{'Has' if v > 0.5 else 'No'} test file, {'reducing' if v > 0.5 else 'increasing'} confidence",
        
        # Language
        "language_id": lambda v: f"Language type {v:.0f}, affects complexity expectations",
    }
    
    # Get the explanation template
    if feature_name in feature_explanations:
        base_explanation = feature_explanations[feature_name](value)
    else:
        # Fallback for unknown features
        base_explanation = f"High {feature_name} ({value:.3f}) affects risk"
    
    # Add direction context
    if direction == "increases":
        return f"This {base_explanation.lower()}, which increases defect risk"
    else:
        return f"This {base_explanation.lower()}, which decreases defect risk"


def _generate_human_readable_explanation(shap_values, feature_names, row_data, top_n=3):
    """
    Generate human-readable explanation from SHAP values.
    
    Args:
        shap_values: SHAP values for a single prediction
        feature_names: List of feature names
        row_data: Feature values for this prediction
        top_n: Number of top features to include
    
    Returns:
        Human-readable explanation string
    """
    # Get top contributing features
    contrib = pd.Series(shap_values, index=feature_names)
    top_features = contrib.abs().sort_values(ascending=False).head(top_n)
    
    explanations = []
    for feature_name in top_features.index:
        shap_val = contrib[feature_name]
        feature_val = row_data.get(feature_name, 0)
        direction = "increases" if shap_val > 0 else "decreases"
        
        human_explanation = _explain_feature_human_readable(
            feature_name, feature_val, abs(shap_val), direction
        )
        explanations.append(human_explanation)
    
    return explanations


def explain_prediction(model_data, df, save_plots=True, top_local=5):
    """
    Compute SHAP explanations for all predictions.
    - Expects model_data to be a dict: {"model": calibrated_model, "features": feature_list}
    - LR uses LinearExplainer, RF/XGB use TreeExplainer
    - Saves global bar + beeswarm plots
    - Saves waterfall + force plots for top N riskiest files
    - Returns df with 'explanation' column (top-3 SHAP features as text)
    """
    if isinstance(model_data, dict) and "features" in model_data:
        model    = model_data["model"]
        features = model_data["features"]
    else:
        # Fallback for old/saved formats
        model    = model_data
        features = getattr(model, "feature_names_in_", None)

    X = _get_features(df)
    if features is not None:
        missing = [c for c in features if c not in X.columns]
        for c in missing:
            X[c] = 0
        X = X[features]

    print("\nComputing SHAP values...")
    shap_values, expected_value, X_display = _compute_shap(model, X)

    if save_plots:
        print("Saving global SHAP plots...")
        _save_global_plots(shap_values, X_display)

        if "risk" in df.columns:
            top_indices = df["risk"].nlargest(top_local).index.tolist()
            print(f"Saving local SHAP plots for top {top_local} risky files...")
            for idx in top_indices:
                pos = df.index.get_loc(idx)
                label = os.path.basename(str(df.loc[idx, "file"]))
                _save_local_plots(shap_values, expected_value, X_display, pos, label)

    # build human-readable explanation text: top-3 SHAP features per row
    explanations = []
    for i in range(len(X)):
        row_data = X_display.iloc[i].to_dict()
        # Handle SHAP values dimensionality
        if shap_values[i].ndim == 2:
            shap_row = shap_values[i][:, 1] if shap_values[i].shape[1] > 1 else shap_values[i][:, 0]
        else:
            shap_row = shap_values[i]
        
        human_explanations = _generate_human_readable_explanation(
            shap_row, X_display.columns, row_data, top_n=3
        )
        
        # Format as bullet points for better readability
        explanation_text = " | ".join([f"· {exp}" for exp in human_explanations])
        explanations.append(explanation_text)

    result = df.copy()
    result["explanation"] = explanations

    return result


def generate_counterfactual_explanation(
    model_data: dict,
    file_row: pd.Series,
    risk_threshold: float = 0.40,
    top_n: int = 3,
) -> list[dict]:
    """
    Generate counterfactual explanations for a single high-risk file.

    Answers the question: "What would need to change for this file's
    predicted risk to drop below `risk_threshold`?"

    Strategy: greedy single-feature perturbation search.
    For each numeric feature, simulate reducing it toward the training
    dataset's median (the 'safe' reference value). Report the features
    that produce the largest risk drop when moved toward their median.

    Args:
        model_data : dict with keys 'model', 'features', 'training_stats'
        file_row   : a single DataFrame row (pd.Series) for the file
        risk_threshold : target risk to drop below (default 0.40)
        top_n      : number of counterfactual suggestions to return

    Returns:
        List of dicts, each with:
          - feature       : feature name
          - current_value : current value of that feature
          - target_value  : value to move toward
          - risk_before   : original risk probability
          - risk_after    : simulated risk after perturbation
          - risk_delta    : reduction in risk (positive = improvement)
          - action        : human-readable suggestion string
    """
    if not isinstance(model_data, dict):
        return []

    model    = model_data.get("model")
    features = model_data.get("features", [])
    stats    = model_data.get("training_stats", {})

    if model is None or not features:
        return []

    # Build baseline feature vector
    row_data = {}
    for feat in features:
        row_data[feat] = file_row.get(feat, 0)

    baseline_df = pd.DataFrame([row_data])[features]

    try:
        risk_before = float(model.predict_proba(baseline_df)[0, 1])
    except Exception:
        return []

    if risk_before < risk_threshold:
        return []  # Already below threshold — no counterfactual needed

    # For each numeric feature, perturb toward its training median
    candidates = []
    for feat in features:
        feat_stats = stats.get(feat)
        if feat_stats is None:
            continue
        current = float(row_data.get(feat, 0))
        # Use midpoint between current and median as the target
        median_approx = float(feat_stats.get("mean", current))
        if abs(median_approx - current) < 1e-6:
            continue

        perturbed = row_data.copy()
        perturbed[feat] = median_approx
        perturbed_df = pd.DataFrame([perturbed])[features]

        try:
            risk_after = float(model.predict_proba(perturbed_df)[0, 1])
        except Exception:
            continue

        delta = risk_before - risk_after
        if delta <= 0.005:  # Ignore negligible changes
            continue

        # Build a human-readable action string
        direction = "reduce" if median_approx < current else "increase"
        action = _counterfactual_action_text(feat, current, median_approx, direction)

        candidates.append({
            "feature":       feat,
            "current_value": round(current, 4),
            "target_value":  round(median_approx, 4),
            "risk_before":   round(risk_before, 3),
            "risk_after":    round(risk_after, 3),
            "risk_delta":    round(delta, 3),
            "action":        action,
        })

    # Return top-N by risk reduction
    candidates.sort(key=lambda x: x["risk_delta"], reverse=True)
    return candidates[:top_n]


def _counterfactual_action_text(feature: str, current: float, target: float, direction: str) -> str:
    """Convert a feature perturbation into a developer-facing action recommendation."""
    _ACTION_TEMPLATES = {
        "avg_complexity":       f"Refactor to reduce average cyclomatic complexity from {current:.1f} toward {target:.1f} (split complex functions)",
        "max_complexity":       f"Break up the most complex function (current peak: {current:.0f}, target: {target:.0f})",
        "max_nesting_depth":    f"Flatten deeply nested blocks (current depth: {current:.0f}, target: {target:.0f})",
        "commits_2w":           f"Reduce commit frequency — {current:.0f} commits in 2 weeks suggests instability",
        "instability_score":    f"Stabilize the file — instability score {current:.3f} is above healthy range",
        "minor_contributor_ratio": f"Improve code ownership — {current:.1%} minor contributors, assign a primary owner",
        "coupling_risk":        f"Reduce coupling — decouple from {current:.0f} tightly bound files",
        "burst_risk":           f"Avoid commit bursts — concentrated changes increase risk",
        "author_count":         f"Reduce number of contributors ({current:.0f}) — too many hands causes inconsistency",
        "loc":                  f"Split this file — {current:.0f} lines is above healthy size",
        "max_function_length":  f"Break up long functions (max {current:.0f} lines, target {target:.0f})",
        "recent_churn_ratio":   f"Stabilize — {current:.1%} of changes are very recent, wait before adding more",
        "temporal_bug_risk":    f"Address historical defects in this file before new changes",
        "has_test_file":        f"Add a test file — this file has no corresponding unit tests",
    }
    if feature in _ACTION_TEMPLATES:
        return _ACTION_TEMPLATES[feature]
    return f"{direction.capitalize()} {feature.replace('_', ' ')} from {current:.3f} toward {target:.3f} to reduce defect risk"

