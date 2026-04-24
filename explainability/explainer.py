import os
import shap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from config import PLOTS_DIR


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
    Compute SHAP values using the appropriate explainer.
    - LR  → LinearExplainer
    - RF / XGBoost → TreeExplainer

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

    # RF / XGBoost - use TreeExplainer (on scaled data if scaler exists)
    else:
        # For tree models, ensure we have the raw classifier without calibration
        if hasattr(clf, 'base_estimator'):
            shap_clf = clf.base_estimator
        elif hasattr(clf, 'estimators'):
            shap_clf = clf.estimators_[0] if hasattr(clf.estimators, '__getitem__') else clf.estimators
        else:
            shap_clf = clf
        
        # Additional check for XGBoost wrapped models
        if hasattr(shap_clf, 'get_booster'):
            # XGBoost model - use directly
            pass
        elif hasattr(shap_clf, 'estimators_'):
            # Random Forest - use directly
            pass
        
        try:
            explainer = shap.TreeExplainer(shap_clf)
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
                # Return dummy values
                return np.zeros((len(X_scaled), len(X_scaled.columns))), 0.0, X

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
