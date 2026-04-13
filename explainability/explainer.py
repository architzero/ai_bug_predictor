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


def _get_clf(model):
    """Extract classifier step from pipeline regardless of name."""
    pipe = _unwrap(model)
    step_name = [s for s in pipe.named_steps if s != "scaler"][0]
    return pipe.named_steps[step_name]


def _get_scaler(model):
    """Return the scaler step from a Pipeline, or None."""
    pipe = _unwrap(model)
    if not hasattr(pipe, "named_steps"):
        return None
    return pipe.named_steps.get("scaler", None)


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
    clf    = _get_clf(model)
    scaler = _get_scaler(model)

    # Pre-scale X if there is a scaler in the pipeline
    if scaler is not None:
        X_scaled = pd.DataFrame(
            scaler.transform(X),
            columns=X.columns,
            index=X.index
        )
    else:
        X_scaled = X

    # LR — use LinearExplainer (on scaled data)
    if hasattr(clf, "coef_"):
        explainer = shap.LinearExplainer(
            clf, X_scaled, feature_perturbation="interventional"
        )
        shap_vals = np.array(explainer.shap_values(X_scaled))
        if shap_vals.ndim == 3:
            shap_vals = shap_vals[0]
        ev = explainer.expected_value
        ev = float(ev[0]) if hasattr(ev, "__len__") else float(ev)
        return shap_vals, ev, X   # X_display = original

    # RF / XGBoost — use TreeExplainer on scaled data
    explainer = shap.TreeExplainer(clf)
    shap_vals = explainer.shap_values(X_scaled)

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

    # build explanation text: top-3 SHAP features per row
    explanations = []
    for i in range(len(X)):
        contrib = pd.Series(shap_values[i], index=X_display.columns)
        top3 = contrib.abs().sort_values(ascending=False).head(3)
        explanations.append(", ".join(top3.index))

    result = df.copy()
    result["explanation"] = explanations

    return result
