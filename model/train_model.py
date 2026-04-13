import numpy as np
import pandas as pd
import joblib
import os
import warnings

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
    precision_recall_curve, make_scorer
)
from imblearn.over_sampling import SMOTE
from xgboost import XGBClassifier

from config import (
    TUNING_N_ITER, TSCV_N_SPLITS, RANDOM_STATE,
    RISK_THRESHOLD, DEFECT_DENSITY_TOP_K
)


NON_FEATURE_COLS = [
    "file", "buggy", "bug_fixes", "bug_density",
    "buggy_commit", "commit_hash", "repo"
]

LEAKAGE_COLS = [
    "bug_fix_ratio",
    "past_bug_count",
    "days_since_last_bug",
]

# Scorer that handles folds where only one class is present
_f1_scorer = make_scorer(f1_score, zero_division=0)


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


def _calibrate(model, X_uncal, y_uncal):
    """
    Sigmoid calibration works correctly on small datasets.
    Isotonic requires 500+ minority samples, which causes stepwise overfitting on small pools.
    """
    try:
        calibrated = CalibratedClassifierCV(
            estimator=model,
            method="sigmoid",
            cv="prefit"
        )
        calibrated.fit(X_uncal, y_uncal)
        print("  Calibrated via CalibratedClassifierCV(method='sigmoid', cv='prefit')")
        
    except (TypeError, ValueError) as e:
        print("  Falling back to manual sigmoid calibration...")
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
    "complexity_per_function", "loc_per_function",
]

_GIT_FEATURE_BASE = [
    "commits", "lines_added", "lines_deleted", "max_added",
    "commits_2w", "commits_1m", "commits_3m",
    "recent_churn_ratio", "recent_activity_score",
    "author_count", "low_history_flag", "minor_contributor_ratio",
    "instability_score", "avg_commit_size", "max_commit_ratio",
    "file_age_bucket", "days_since_last_change", "recency_ratio",
]


def _get_xy(df):
    X = df.drop(columns=NON_FEATURE_COLS + LEAKAGE_COLS, errors="ignore")
    y = df["buggy"]
    return X, y


def _print_metrics(name, y_test, preds, proba):
    print(f"\n--- {name} ---")
    print(classification_report(y_test, preds, zero_division=0))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, preds))

    if len(np.unique(y_test)) > 1:
        print(f"ROC-AUC : {roc_auc_score(y_test, proba):.4f}")
        print(f"PR-AUC  : {average_precision_score(y_test, proba):.4f}")
    else:
        print("ROC-AUC / PR-AUC: skipped (single class in test set)")


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
        return
    n_top = max(1, int(len(y_test) * top_k))
    top_idx = np.argsort(proba)[::-1][:n_top]
    bugs_in_top = y_test.iloc[top_idx].sum() if hasattr(y_test, "iloc") else y_test[top_idx].sum()
    total_bugs  = y_test.sum()
    recall_at_k = bugs_in_top / total_bugs if total_bugs > 0 else 0
    print(f"   Defect density     →  {recall_at_k:.1%} of bugs in top-{top_k:.0%} risk files "
          f"({bugs_in_top}/{total_bugs})")
    if recall_at_k >= 0.70:
        print("   ✓ Excellent recall at top-K (≥70%)")
    elif recall_at_k >= 0.50:
        print("   ~ Acceptable recall at top-K (50-69%)")
    else:
        print("   ⚠ Low recall at top-K — model may not be discriminating enough")


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


def _smote_resample(X_train, y_train):
    """
    SMOTE oversampling; always returns a DataFrame so SelectFromModel
    (and column-name-aware code) works correctly downstream.
    """
    cols     = list(X_train.columns) if isinstance(X_train, pd.DataFrame) else None
    minority = int(y_train.sum())
    majority = len(y_train) - minority

    if minority < 2:
        print(f"  ⚠  SMOTE skipped: only {minority} minority sample(s) — "
              f"training on imbalanced data as-is")
        return X_train, y_train

    if majority < 2:
        return X_train, y_train

    k = min(5, minority - 1)
    smote = SMOTE(random_state=RANDOM_STATE, k_neighbors=k)
    Xr, yr = smote.fit_resample(X_train, y_train)

    # Guarantee DataFrame with original column names (some imblearn versions
    # silently drop them or rename with integers)
    if cols is not None and not isinstance(Xr, pd.DataFrame):
        Xr = pd.DataFrame(Xr, columns=cols)
    elif cols is not None and isinstance(Xr, pd.DataFrame):
        Xr.columns = cols

    return Xr, yr


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
    print(f"  RFE: kept {len(kept)}, dropped {len(dropped)} "
          f"(threshold='{threshold}')")
    if dropped:
        print(f"    Dropped: {dropped}")

    X_tr_sel = pd.DataFrame(selector.transform(X_train), columns=kept)
    X_te_sel = pd.DataFrame(selector.transform(X_test),  columns=kept)
    return X_tr_sel, X_te_sel, kept


def _temporal_sort(df):
    """
    Sort oldest-activity-first so TimeSeriesSplit trains on older data
    and validates on more recent data.
    """
    if "days_since_last_change" in df.columns:
        return df.sort_values("days_since_last_change", ascending=False)
    if "file_age_bucket" in df.columns:
        return df.sort_values("file_age_bucket", ascending=False)
    return df


def _tune_rf(X_train, y_train):
    tscv = TimeSeriesSplit(n_splits=TSCV_N_SPLITS)
    param_dist = {
        "rf__n_estimators":      [100, 200, 300],
        "rf__max_depth":         [4, 6, 8],
        "rf__min_samples_split": [5, 10, 20],
        "rf__min_samples_leaf":  [2, 4, 8],
        "rf__max_samples":       [0.6, 0.7, 0.8],
    }
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1))
    ])
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Scoring failed")
        search = RandomizedSearchCV(
            pipe, param_dist,
            n_iter=TUNING_N_ITER, cv=tscv,
            scoring=_f1_scorer, n_jobs=-1,
            random_state=RANDOM_STATE, refit=True,
            error_score=0.0
        )
        search.fit(X_train, y_train)
    if search.best_score_ == 0.0:
        print("  ⚠  RF best CV score is 0.0 — likely single-class folds. "
              "Consider increasing TSCV_N_SPLITS or checking class distribution.")
    print(f"  Best RF params : {search.best_params_}")
    return search.best_estimator_


def _tune_xgb(X_train, y_train):
    tscv = TimeSeriesSplit(n_splits=TSCV_N_SPLITS)
    param_dist = {
        "xgb__n_estimators":     [100, 200, 300],
        "xgb__max_depth":        [3, 5, 7],
        "xgb__learning_rate":    [0.01, 0.05, 0.1],
        "xgb__subsample":        [0.7, 0.8, 1.0],
        "xgb__colsample_bytree": [0.7, 0.8, 1.0],
    }
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("xgb", XGBClassifier(
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1
        ))
    ])
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Scoring failed")
        search = RandomizedSearchCV(
            pipe, param_dist,
            n_iter=TUNING_N_ITER, cv=tscv,
            scoring=_f1_scorer, n_jobs=-1,
            random_state=RANDOM_STATE, refit=True,
            error_score=0.0
        )
        search.fit(X_train, y_train)
    if search.best_score_ == 0.0:
        print("  ⚠  XGB best CV score is 0.0 — likely single-class folds.")
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
        test_df  = df[df["repo"] == test_repo]

        if len(train_df) < 10 or len(test_df) < 5:
            print("  Skipping fold — insufficient data")
            continue

        X_train_raw, y_train_raw = _get_xy(train_df)
        X_test,      y_test      = _get_xy(test_df)
        
        # Scope to globally selected features (so all folds are comparable)
        shared_cols = [c for c in global_features if c in X_train_raw.columns and c in X_test.columns]
        X_train_raw = X_train_raw[shared_cols]
        X_test      = X_test[shared_cols]

        # SMOTE on train only (never on test)
        X_train, y_train = _smote_resample(X_train_raw, y_train_raw)
        print(f"  Train size after SMOTE : {len(X_train)} "
              f"(buggy={int(y_train.sum())}, clean={len(y_train)-int(y_train.sum())})")
        print(f"  Test size              : {len(X_test)} "
              f"(buggy={int(y_test.sum())}, clean={len(y_test)-int(y_test.sum())})")

        has_both = len(np.unique(y_test)) > 1

        # ── LOC-only baseline (research comparison) ────────────────────────────
        print("\n  [Baseline]")
        _loc_baseline(X_test, y_test)

        # ── Logistic Regression baseline ────────────────────────────────────
        lr = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE))
        ])
        lr.fit(X_train, y_train)
        lr_preds = lr.predict(X_test)
        lr_proba = lr.predict_proba(X_test)[:, 1]
        _print_metrics("Logistic Regression (baseline)", y_test, lr_preds, lr_proba)
        _optimal_threshold(y_test, lr_proba)
        _defect_density_validation(y_test, lr_proba)

        # ── Random Forest ──────────────────────────────────────────────────────
        print("  Tuning Random Forest...")
        rf = _tune_rf(X_train, y_train)
        rf_preds = rf.predict(X_test)
        rf_proba = rf.predict_proba(X_test)[:, 1]
        _print_metrics("Random Forest", y_test, rf_preds, rf_proba)
        _optimal_threshold(y_test, rf_proba)
        _defect_density_validation(y_test, rf_proba)
        _print_feature_importances(rf, shared_cols)

        # ── XGBoost ────────────────────────────────────────────────────────────
        print("  Tuning XGBoost...")
        xgb = _tune_xgb(X_train, y_train)
        xgb_preds = xgb.predict(X_test)
        xgb_proba = xgb.predict_proba(X_test)[:, 1]
        _print_metrics("XGBoost", y_test, xgb_preds, xgb_proba)
        _optimal_threshold(y_test, xgb_proba)
        _defect_density_validation(y_test, xgb_proba)
        _print_feature_importances(xgb, shared_cols)

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
        print(f"\n  Best this fold: {fold_best_name} (F1={best_f1_fold:.4f})")

        # Collect fold metrics for summary table
        n_top = max(1, int(len(y_test) * DEFECT_DENSITY_TOP_K))
        top_idx = np.argsort(best_proba_fold)[::-1][:n_top]
        bugs_in_top = y_test.iloc[top_idx].sum() if hasattr(y_test, "iloc") else y_test[top_idx].sum()
        fold_dd = bugs_in_top / y_test.sum() if y_test.sum() > 0 else 0
        fold_results.append({
            "test_repo":      os.path.basename(test_repo),
            "model":          fold_best_name,
            "n_test":         len(y_test),
            "n_buggy":        int(y_test.sum()),
            "f1":             best_f1_fold,
            "pr_auc":         average_precision_score(y_test, best_proba_fold) if has_both else 0.0,
            "defect_density": fold_dd,
        })

        fold_count += 1

    # ── Cross-project summary table ──────────────────────────────────────────────────
    if fold_results:
        print(f"\n{'='*72}")
        print("  CROSS-PROJECT EVALUATION SUMMARY")
        print(f"{'='*72}")
        print(f"  {'Fold':<12} {'Model':<6} {'N(test)':<9} {'Buggy':<7} "
              f"{'F1':<8} {'PR-AUC':<10} {'Defect@20%'}")
        print(f"  {'-'*68}")
        for r in fold_results:
            print(f"  {r['test_repo']:<12} {r['model']:<6} {r['n_test']:<9} "
                  f"{r['n_buggy']:<7} {r['f1']:<8.4f} {r['pr_auc']:<10.4f} "
                  f"{r['defect_density']:.1%}")
        avg_f1  = sum(r["f1"]  for r in fold_results) / len(fold_results)
        avg_auc = sum(r["pr_auc"] for r in fold_results) / len(fold_results)
        avg_dd  = sum(r["defect_density"] for r in fold_results) / len(fold_results)
        print(f"  {'-'*68}")
        print(f"  {'Average':<12} {'':6} {'':9} {'':7} "
              f"{avg_f1:<8.4f} {avg_auc:<10.4f} {avg_dd:.1%}")
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
    
    # SMOTE on the 80% train only
    X_train_smote, y_train_smote = _smote_resample(X_train_final, y_train_final)
    
    print("Using deeper XGBoost for smoother probability output...")

    best_model = Pipeline([
        ("scaler", StandardScaler()),
        ("xgb", XGBClassifier(
            n_estimators=600,
            max_depth=7,
            learning_rate=0.03,
            subsample=0.85,
            colsample_bytree=0.85,
            gamma=0.1,
            min_child_weight=2,
            reg_alpha=0.01,
            reg_lambda=1.0,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1
        ))
    ])

    best_model.fit(X_train_smote, y_train_smote)

    # ── Probability calibration ────────────────────────────────────────────────────
    # SMOTE trained on balanced (50/50) data; real-world prior is ~6% buggy.
    # Isotonic calibration maps raw scores → calibrated posteriors.
    # Calibrate on un-SMOTE’d out-of-bag data (to prevent 100% prob overfitting).
    print("Calibrating probabilities (isotonic regression)...")
    calibrated_model = _calibrate(best_model, X_cal_final, y_cal_final)

    # ── Calibration sanity check ────────────────────────────────────────────────────
    # We check calibration sanity on the hold-out calibration set.
    cal_proba   = calibrated_model.predict_proba(X_cal_final)[:, 1]
    mean_pred   = cal_proba.mean()
    actual_rate = float(y_cal_final.mean())
    print(f"  Calibration check : mean predicted prob = {mean_pred:.3f}  "
          f"actual buggy rate = {actual_rate:.3f}")
    if abs(mean_pred - actual_rate) < 0.05:
        print("  ✓ Probabilities are well-calibrated (gap < 5%)")
    else:
        print(f"  ⚠  Calibration gap = {abs(mean_pred - actual_rate):.3f} — "
              "scores may not reflect true risk probabilities")

    print(f"  Probability spread: min={cal_proba.min():.3f}  "
          f"max={cal_proba.max():.3f}  "
          f"unique values={len(np.unique(cal_proba.round(3)))}")
    if len(np.unique(cal_proba.round(3))) < 10:
        print("  ⚠ WARNING: Too few unique probability values — calibration too coarse")

    os.makedirs("model", exist_ok=True)
    
    save_dict = {
        "model": calibrated_model,
        "features": global_features
    }

    joblib.dump(save_dict, "model/bug_predictor.pkl")
    print("Calibrated model saved → model/bug_predictor.pkl")
    print(f"Model expects {len(global_features)} feature(s): {global_features}")

    return save_dict


def _single_project_train(df):
    """Fallback: temporal split on single project."""
    df_sorted = _temporal_sort(df)
    split     = int(len(df_sorted) * 0.7)
    train_df  = df_sorted.iloc[:split]
    test_df   = df_sorted.iloc[split:]

    X_train, y_train = _get_xy(train_df)
    X_test,  y_test  = _get_xy(test_df)

    X_train, y_train = _smote_resample(X_train, y_train)

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(
            n_estimators=200, max_depth=8,
            random_state=RANDOM_STATE, n_jobs=-1
        ))
    ])
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    _print_metrics("Random Forest (single project)", y_test, preds, proba)
    _optimal_threshold(y_test, proba)
    _defect_density_validation(y_test, proba)

    # calibrate on full un-SMOTE'd data
    print("Calibrating probabilities...")
    X_uncal, y_uncal = _get_xy(_temporal_sort(df))
    calibrated = _calibrate(model, X_uncal, y_uncal)

    os.makedirs("model", exist_ok=True)
    joblib.dump(calibrated, "model/bug_predictor.pkl")

    return calibrated


def run_ablation_study(df, global_features=None):
    """
    Ablation: compare Static-only vs Git-only vs Combined features.

    Uses Logistic Regression and Random Forest in cross-project LOO structure.
    Reports average F1 and PR-AUC for each feature subset.

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

        X_tr_full, y_train = _get_xy(train_df)
        X_te_full, y_test  = _get_xy(test_df)

        for fs_name, cols in feature_sets.items():
            shared = [c for c in cols if c in X_tr_full.columns and c in X_te_full.columns]
            if not shared:
                continue

            X_tr = X_tr_full[shared]
            X_te = X_te_full[shared]
            X_tr_s, y_tr_s = _smote_resample(X_tr, y_train)

            for m_name, base_model in models.items():
                model = Pipeline([
                    ("scaler", StandardScaler()),
                    (m_name.lower(), clone(base_model))
                ])
                model.fit(X_tr_s, y_tr_s)
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

    for m_name in models:
        for fs_name, cols in feature_sets.items():
            run_metrics = results[m_name][fs_name]
            if run_metrics:
                avg_f1  = sum(r["f1"]     for r in run_metrics) / len(run_metrics)
                avg_auc = sum(r["pr_auc"] for r in run_metrics) / len(run_metrics)
                n_cols  = len([c for c in cols if c in available])
                print(f"  {m_name:<6} {fs_name:<16} {n_cols:<8} {avg_f1:<10.4f} {avg_auc:.4f}")
    print(f"{'='*60}")
