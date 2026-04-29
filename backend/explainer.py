import os
import shap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from functools import lru_cache
from backend.config import PLOTS_DIR
from backend.feature_constants import NON_FEATURE_COLS


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
            # XGBoost model - fix compatibility issues
            try:
                # Try to create a clean XGBoost model for SHAP
                import xgboost as xgb
                if hasattr(shap_clf, 'feature_names_in_'):
                    clean_model = xgb.XGBClassifier()
                    clean_model._Booster = shap_clf.get_booster()
                    clean_model.feature_names_in_ = shap_clf.feature_names_in_
                    shap_clf = clean_model
            except Exception as e:
                print(f"XGBoost model cleaning failed: {e}")
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
                # Use a simpler approach for problematic models
                explainer = shap.KernelExplainer(lambda x: shap_clf.predict_proba(x.reshape(1, -1))[0, 1], X_scaled[:10])
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
    """Save publication-quality global SHAP plots with improved clarity."""
    os.makedirs(PLOTS_DIR, exist_ok=True)

    # Configure matplotlib for high-quality plots
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['savefig.dpi'] = 300
    plt.rcParams['font.size'] = 11
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['axes.labelsize'] = 12
    plt.rcParams['axes.titlesize'] = 14
    plt.rcParams['xtick.labelsize'] = 10
    plt.rcParams['ytick.labelsize'] = 10
    plt.rcParams['legend.fontsize'] = 10
    plt.rcParams['figure.titlesize'] = 16

    # Bar plot — mean absolute SHAP per feature (TOP 15 for clarity)
    fig, ax = plt.subplots(figsize=(12, 8))
    shap.summary_plot(
        shap_values, 
        X_test, 
        plot_type="bar", 
        show=False,
        max_display=15,  # Show top 15 features only
        color='#1f77b4'  # Professional blue
    )
    plt.title('Feature Importance (Mean |SHAP|)', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Mean Absolute SHAP Value', fontsize=12, fontweight='bold')
    plt.ylabel('Features', fontsize=12, fontweight='bold')
    plt.grid(axis='x', alpha=0.3, linestyle='--')
    plt.tight_layout()
    plt.savefig(f"{PLOTS_DIR}/global_bar.png", dpi=300, bbox_inches="tight", facecolor='white')
    plt.close()
    print(f"  Saved → {PLOTS_DIR}/global_bar.png (300 DPI)")

    # Beeswarm — direction + distribution (TOP 20 for clarity)
    fig, ax = plt.subplots(figsize=(14, 10))
    shap.summary_plot(
        shap_values, 
        X_test, 
        show=False,
        max_display=20,  # Show top 20 features
        cmap='RdBu_r',   # Red-Blue colormap (red=high, blue=low)
        alpha=0.7
    )
    plt.title('Feature Impact Distribution', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('SHAP Value (Impact on Model Output)', fontsize=12, fontweight='bold')
    plt.ylabel('Features', fontsize=12, fontweight='bold')
    
    # Add colorbar label
    cbar = plt.gcf().axes[-1]
    cbar.set_ylabel('Feature Value', fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(f"{PLOTS_DIR}/global_beeswarm.png", dpi=300, bbox_inches="tight", facecolor='white')
    plt.close()
    print(f"  Saved → {PLOTS_DIR}/global_beeswarm.png (300 DPI)")


def _save_local_plots(shap_values, expected_value, X_test, index, label):
    """Save publication-quality local SHAP plots with improved clarity."""
    os.makedirs(PLOTS_DIR, exist_ok=True)

    # Configure matplotlib for high-quality plots
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['savefig.dpi'] = 300
    plt.rcParams['font.size'] = 11
    plt.rcParams['font.family'] = 'sans-serif'

    safe_label = label.replace("/", "_").replace("\\", "_")

    sv = shap_values[index]
    if sv.ndim == 2:
        sv = sv[:, 1]

    ev = float(expected_value) if np.ndim(expected_value) == 0 else float(expected_value)

    # Waterfall plot (TOP 10 features for clarity)
    explanation = shap.Explanation(
        values=sv,
        base_values=ev,
        data=X_test.iloc[index].values,
        feature_names=list(X_test.columns)
    )
    
    fig, ax = plt.subplots(figsize=(12, 8))
    shap.plots.waterfall(explanation, show=False, max_display=10)
    plt.title(f'SHAP Waterfall: {label}', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('SHAP Value', fontsize=11, fontweight='bold')
    plt.tight_layout()
    plt.savefig(
        f"{PLOTS_DIR}/local_waterfall_{safe_label}.png",
        dpi=300, 
        bbox_inches="tight",
        facecolor='white'
    )
    plt.close()

    # Force plot (TOP 10 features for clarity)
    fig, ax = plt.subplots(figsize=(14, 3))
    
    # Get top 10 features by absolute SHAP value
    top_indices = np.argsort(np.abs(sv))[-10:][::-1]
    sv_top = sv[top_indices]
    features_top = X_test.iloc[index].iloc[top_indices]
    feature_names_top = [X_test.columns[i] for i in top_indices]
    
    shap.force_plot(
        ev,
        sv_top,
        features_top,
        feature_names=feature_names_top,
        matplotlib=True,
        show=False,
        text_rotation=10
    )
    plt.title(f'SHAP Force Plot: {label}', fontsize=14, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig(
        f"{PLOTS_DIR}/local_force_{safe_label}.png",
        dpi=300, 
        bbox_inches="tight",
        facecolor='white'
    )
    plt.close()


def _explain_feature_human_readable(feature_name, value, shap_value, direction="increases", repo_median=None):
    """
    Convert SHAP feature contributions to human-readable explanations.
    Uses repo-median-relative thresholds to avoid misleading statements like
    "high commit history (1 changes)" or "many contributors (0 authors)".
    
    Args:
        feature_name: Name of the feature
        value: Actual feature value
        shap_value: SHAP contribution magnitude
        direction: "increases" or "decreases" risk
        repo_median: Median value of this feature across the repo (optional)
    
    Returns:
        Human-readable explanation string or None if not noteworthy
    """
    # Suppress explanations for zero or near-zero values that shouldn't be highlighted
    if feature_name in ["author_count", "commits", "coupled_file_count"] and value < 1:
        return None
    
    # Calculate ratio to repo median if available
    ratio = None
    if repo_median is not None and repo_median > 0:
        ratio = value / repo_median
    
    # Context-relative explanations
    if feature_name == "commits":
        if repo_median is None or repo_median == 0 or ratio is None:
            return None
        if ratio > 2:
            return f"Modified {ratio:.1f}× more than repo median ({int(value)} commits), indicating high churn"
        elif ratio > 1.2:
            return f"Frequently modified ({int(value)} commits, {ratio:.1f}× repo median)"
        else:
            return None  # Not noteworthy
    
    if feature_name == "author_count":
        if value == 0:
            return None  # Suppress "0 authors"
        if value >= 6:
            return f"Touched by {int(value)} authors (high coordination risk)"
        elif value >= 3:
            return f"Touched by {int(value)} authors"
        else:
            return None
    
    if feature_name == "avg_complexity":
        if repo_median and ratio and value > repo_median * 2:
            return f"Complexity in top tier ({value:.1f}, {ratio:.1f}× repo median)"
        elif repo_median and ratio and value > repo_median * 1.3:
            return f"Above-average complexity ({value:.1f}, {ratio:.1f}× repo median)"
        elif value > 15:  # Absolute threshold fallback
            return f"High cyclomatic complexity ({value:.1f})"
        else:
            return None
    
    if feature_name == "loc":
        if value > 1000:
            return f"Very large file ({int(value)} lines), harder to reason about"
        elif value > 500:
            return f"Large file ({int(value)} lines)"
        else:
            return None
    
    if feature_name == "max_complexity":
        if value > 30:
            return f"Contains very complex functions (max complexity {int(value)})"
        elif value > 15:
            return f"Has complex functions (max complexity {int(value)})"
        else:
            return None
    
    if feature_name == "coupled_file_count":
        if value == 0:
            return None
        if value >= 5:
            return f"Tightly coupled to {int(value)} files, changes cascade easily"
        elif value >= 2:
            return f"Coupled to {int(value)} files"
        else:
            return None
    
    if feature_name == "recent_bug_flag" and value > 0:
        return "Recent bug fixes detected, high regression risk"
    
    if feature_name == "burst_risk" and value > 0.5:
        return f"High burst risk ({value:.2f}), suggesting rushed development"
    
    if feature_name == "temporal_bug_risk" and value > 0.3:
        return f"Elevated temporal bug risk ({value:.2f})"
    
    # Map features to human-readable explanations (fallback for features without context-relative logic)
    feature_explanations = {
        # Complexity metrics
        "complexity_density": lambda v: f"High complexity relative to size ({v:.3f}), suggesting dense logic" if v > 0.1 else None,
        "complexity_per_function": lambda v: f"Functions are overly complex on average ({v:.1f})" if v > 5 else None,
        "complexity_vs_baseline": lambda v: f"Complexity is {v:.1f}x above language baseline" if v > 1.5 else None,
        "max_nesting_depth": lambda v: f"Deep block nesting detected (depth {v:.0f})" if v > 4 else None,
        
        # Size metrics
        "functions": lambda v: f"Many functions ({v:.0f}), increasing surface area for bugs" if v > 20 else None,
        "max_function_length": lambda v: f"Contains very long functions ({v:.0f} lines)" if v > 100 else None,
        "avg_params": lambda v: f"Functions have many parameters on average ({v:.1f})" if v > 4 else None,
        
        # Git activity metrics
        "commits_2w": lambda v: f"Very active recently ({v:.0f} commits in 2 weeks)" if v > 3 else None,
        "commits_1m": lambda v: f"Frequent recent changes ({v:.0f} commits in 1 month)" if v > 5 else None,
        "commits_3m": lambda v: f"Moderate recent activity ({v:.0f} commits in 3 months)" if v > 10 else None,
        "recent_churn_ratio": lambda v: f"High recent churn ({v:.1%} of changes are recent)" if v > 0.3 else None,
        "recent_activity_score": lambda v: f"Elevated recent activity ({v:.3f})" if v > 0.5 else None,
        
        # Code churn metrics
        "lines_added": lambda v: f"Significant additions ({v:.0f} lines added)" if v > 500 else None,
        "lines_deleted": lambda v: f"Major deletions ({v:.0f} lines removed)" if v > 300 else None,
        "max_added": lambda v: f"Very large single change ({v:.0f} lines added at once)" if v > 200 else None,
        "avg_commit_size": lambda v: f"Large average commits ({v:.1f} lines)" if v > 100 else None,
        "instability_score": lambda v: f"High instability ({v:.3f})" if v > 0.5 else None,
        "max_commit_ratio": lambda v: f"Contains massive commits ({v:.1f}x average)" if v > 3 else None,
        
        # Developer metrics
        "ownership": lambda v: f"Low ownership ({v:.1%}), no clear code owner" if v < 0.5 else None,
        "minor_contributor_ratio": lambda v: f"Many minor contributors ({v:.1%})" if v > 0.5 else None,
        
        # Temporal metrics
        "days_since_last_change": lambda v: f"Recently modified ({v:.0f} days ago)" if v < 30 else None,
        "recency_ratio": lambda v: f"Very recent changes ({v:.1%} of file age)" if v > 0.3 else None,
        "file_age_bucket": lambda v: f"File age category {v:.0f}",
        
        # Bug history metrics
        "bug_fixes": lambda v: f"History of bug fixes ({v:.0f})" if v > 2 else None,
        "bug_recency_score": lambda v: f"Recent bug activity ({v:.3f})" if v > 0.3 else None,
        "temporal_bug_memory": lambda v: f"Strong bug memory ({v:.3f})" if v > 0.5 else None,
        
        # Coupling metrics
        "max_coupling_strength": lambda v: f"Tightly coupled to other files ({v:.3f})" if v > 0.5 else None,
        "coupled_recent_missing": lambda v: f"Missing recent changes in coupled files ({v:.0f})" if v > 0 else None,
        "coupling_risk": lambda v: f"High coupling risk ({v:.3f})" if v > 0.5 else None,
        
        # Commit burst metrics
        "commit_burst_score": lambda v: f"Bursty commit pattern ({v:.3f})" if v > 0.5 else None,
        "recent_commit_burst": lambda v: f"Recent commit burst ({v:.0f})" if v > 2 else None,
        "burst_ratio": lambda v: f"High burst ratio ({v:.3f})" if v > 0.5 else None,
        
        # Test coverage
        "has_test_file": lambda v: f"{'Has' if v > 0.5 else 'No'} test file",
        
        # Language
        "language_id": lambda v: None,  # Suppress language explanations
    }
    
    # Get the explanation template
    if feature_name in feature_explanations:
        result = feature_explanations[feature_name](value)
        if result is None:
            return None
        base_explanation = result
    else:
        # Fallback for unknown features - only if value is significant
        if abs(value) < 0.01:
            return None
        base_explanation = f"High {feature_name} ({value:.3f}) affects risk"
    
    # Add direction context
    if direction == "increases":
        return f"{base_explanation}, which increases defect risk"
    else:
        return f"{base_explanation}, which decreases defect risk"


def _generate_human_readable_explanation(shap_values, feature_names, row_data, top_n=3, repo_medians=None):
    """
    Generate human-readable explanation from SHAP values.
    
    Args:
        shap_values: SHAP values for a single prediction
        feature_names: List of feature names
        row_data: Feature values for this prediction
        top_n: Number of top features to include
        repo_medians: Dict of feature_name -> median value across repo
    
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
        
        repo_median = repo_medians.get(feature_name) if repo_medians else None
        
        human_explanation = _explain_feature_human_readable(
            feature_name, feature_val, abs(shap_val), direction, repo_median
        )
        
        # Only add non-None explanations
        if human_explanation:
            explanations.append(human_explanation)
    
    return explanations


def explain_prediction(model_data, df, save_plots=True, top_local=5, sample_for_shap=None):
    """
    Compute SHAP explanations for all predictions.
    - Expects model_data to be a dict: {"model": calibrated_model, "features": feature_list}
    - LR uses LinearExplainer, RF/XGB use TreeExplainer
    - Saves global bar + beeswarm plots
    - Saves waterfall + force plots for top N riskiest files
    - Returns df with 'explanation' column (top-3 SHAP features as text)
    
    Performance optimization:
    - sample_for_shap: If set, compute SHAP on a sample of files (default: None = all files)
                       Recommended: 500-1000 for large repos (10× faster, minimal accuracy loss)
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

    # OPTIMIZATION: Sample for SHAP computation if dataset is large
    if sample_for_shap and len(X) > sample_for_shap:
        print(f"\nComputing SHAP values on sample of {sample_for_shap} files (out of {len(X)})...")
        # Stratified sampling: ensure we get both high and low risk files
        if "risk" in df.columns:
            # Sample top 50% by risk + random 50% from remainder
            top_half = int(sample_for_shap * 0.5)
            bottom_half = sample_for_shap - top_half
            
            top_indices = df.nlargest(top_half, "risk").index
            remaining = df.drop(top_indices).sample(n=min(bottom_half, len(df) - top_half), random_state=42).index
            sample_indices = top_indices.union(remaining)
        else:
            # Random sampling if no risk column
            sample_indices = df.sample(n=sample_for_shap, random_state=42).index
        
        X_sample = X.loc[sample_indices]
        df_sample = df.loc[sample_indices]
    else:
        print("\nComputing SHAP values...")
        X_sample = X
        df_sample = df
        sample_indices = df.index
    
    shap_values, expected_value, X_display = _compute_shap(model, X_sample)
    
    # Compute repo medians for context-relative explanations (use full dataset)
    repo_medians = {}
    for col in X.select_dtypes(include='number').columns:
        repo_medians[col] = float(X[col].median())

    if save_plots:
        print("Saving global SHAP plots...")
        _save_global_plots(shap_values, X_display)

        if "risk" in df.columns:
            top_indices = df["risk"].nlargest(top_local).index.tolist()
            print(f"Saving local SHAP plots for top {top_local} risky files...")
            for idx in top_indices:
                # Check if this index was in our SHAP sample
                if idx not in sample_indices:
                    continue
                pos = df_sample.index.get_loc(idx)
                label = os.path.basename(str(df.loc[idx, "file"]))
                _save_local_plots(shap_values, expected_value, X_display, pos, label)

    # build human-readable explanation text: top-3 SHAP features per row
    # For files not in sample, use a generic explanation
    explanations = []
    for i in range(len(df)):
        idx = df.index[i]
        
        if idx in sample_indices:
            # File was in SHAP sample - use actual SHAP values
            sample_pos = df_sample.index.get_loc(idx)
            row_data = X_display.iloc[sample_pos].to_dict()
            
            # Handle SHAP values dimensionality
            if shap_values[sample_pos].ndim == 2:
                shap_row = shap_values[sample_pos][:, 1] if shap_values[sample_pos].shape[1] > 1 else shap_values[sample_pos][:, 0]
            else:
                shap_row = shap_values[sample_pos]
            
            human_explanations = _generate_human_readable_explanation(
                shap_row, X_display.columns, row_data, top_n=3, repo_medians=repo_medians
            )
            
            # Format as bullet points for better readability
            explanation_text = " | ".join([f"· {exp}" for exp in human_explanations])
        else:
            # File not in sample - provide generic explanation based on risk tier
            if "risk" in df.columns:
                risk = df.loc[idx, "risk"]
                if risk >= 0.7:
                    explanation_text = "· High-risk file based on complexity and change patterns"
                elif risk >= 0.5:
                    explanation_text = "· Moderate-risk file - review recommended"
                else:
                    explanation_text = "· Lower-risk file based on historical patterns"
            else:
                explanation_text = "· Risk assessment based on code metrics"
        
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

