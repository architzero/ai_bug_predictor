import pandas as pd
import numpy as np

from config import CORR_DROP_THRESHOLD


NON_FEATURE_COLS = [
    "file", "buggy", "bug_fixes", "bug_density",
    "buggy_commit", "commit_hash", "repo"
]

# leakage cols excluded from correlation analysis and model training
LEAKAGE_COLS = [
    "bug_fix_ratio",
    "past_bug_count",
    "days_since_last_bug",
]

EXCLUDE_FROM_CORR = set(NON_FEATURE_COLS + LEAKAGE_COLS)

# cap raw day values to 10 years to prevent extreme outliers skewing features
MAX_AGE_DAYS = 3650


def build_features(static_results, git_results):

    rows = []

    for static in static_results:

        file_path = static["file"]
        g = git_results.get(file_path, {})

        # safe base values — prevent division by zero
        commits    = max(g.get("commits", 0), 1)
        loc        = max(static["loc"], 1)
        functions  = max(static["functions"], 1)
        churn      = g.get("lines_added", 0) + g.get("lines_deleted", 0)
        avg_cx     = static["avg_complexity"]
        commits_3m = g.get("commits_3m", 0)
        avg_commit = churn / commits

        # file age — cap and bucket
        file_age_raw   = min(g.get("file_age_days", 0), MAX_AGE_DAYS)
        days_since_raw = min(g.get("days_since_last_change", 0), MAX_AGE_DAYS)

        if file_age_raw < 180:
            age_bucket = 0   # new
        elif file_age_raw < 365:
            age_bucket = 1   # young
        elif file_age_raw < 730:
            age_bucket = 2   # mature
        else:
            age_bucket = 3   # old

        recency_ratio = days_since_raw / (file_age_raw + 1)

        # new static features from lizard
        avg_params          = static.get("avg_params", 0)
        max_function_length = static.get("max_function_length", 0)

        row = {
            "file":        file_path,
            "commit_hash": g.get("last_commit_hash"),

            # static
            "loc":                  static["loc"],
            "avg_complexity":       avg_cx,
            "max_complexity":       static["max_complexity"],
            "functions":            static["functions"],
            "avg_params":           avg_params,
            "max_function_length":  max_function_length,

            # complexity ratios
            "complexity_density":      avg_cx / loc,
            "complexity_per_function": avg_cx / functions,
            "loc_per_function":        static["loc"] / functions,

            # git base
            "commits":       commits,
            "lines_added":   g.get("lines_added",   0),
            "lines_deleted": g.get("lines_deleted",  0),
            "max_added":     g.get("max_added",      0),
            "bug_fixes":     g.get("bug_fixes",      0),

            # time-window churn
            "commits_2w": g.get("commits_2w", 0),
            "commits_1m": g.get("commits_1m", 0),
            "commits_3m": commits_3m,

            "recent_churn_ratio":    g.get("commits_1m", 0) / commits,
            "recent_activity_score": g.get("commits_2w", 0) / commits_3m
                                     if commits_3m > 0 else 0.0,

            # developer experience
            "author_count":            g.get("author_count",            0),
            "ownership":               g.get("ownership",               0),
            "low_history_flag":        g.get("low_history_flag",        1),
            "minor_contributor_ratio": g.get("minor_contributor_ratio", 0),

            # stability / volatility
            "instability_score": churn / loc,
            "avg_commit_size":   avg_commit,
            "max_commit_ratio":  g.get("max_added", 0) / avg_commit
                                 if avg_commit > 0 else 0.0,

            # file age (bucketed + capped — never raw file_age_days)
            "file_age_bucket":        age_bucket,
            "days_since_last_change": days_since_raw,
            "recency_ratio":          recency_ratio,

            # logical coupling
            "max_coupling_strength":  g.get("max_coupling_strength", 0.0),
            "coupled_file_count":     g.get("coupled_file_count", 0),
            "coupled_recent_missing": g.get("coupled_recent_missing", 0),
            "coupling_risk":          g.get("coupling_risk", 0.0),

            # bug history (kept for analysis, excluded from model via LEAKAGE_COLS)
            "past_bug_count":      g.get("past_bug_count",      0),
            "bug_fix_ratio":       g.get("bug_fix_ratio",       0),
            "days_since_last_bug": g.get("days_since_last_bug", -1),
        }

        rows.append(row)

    return pd.DataFrame(rows)


def filter_correlated_features(df):
    """
    Drop features with pairwise |correlation| > CORR_DROP_THRESHOLD,
    keeping the one with higher correlation to the target label.
    Leakage cols and non-feature cols are excluded from analysis.
    """
    if "buggy" not in df.columns:
        return df

    feature_cols = [
        c for c in df.columns
        if c not in EXCLUDE_FROM_CORR
        and df[c].dtype in [np.float64, np.int64, float, int]
    ]

    feat_df     = df[feature_cols]
    corr_matrix = feat_df.corr().abs()
    target_corr = feat_df.corrwith(df["buggy"]).abs()

    to_drop = set()

    for i, col in enumerate(feature_cols):
        if col in to_drop:
            continue
        for j in range(i + 1, len(feature_cols)):
            other = feature_cols[j]
            if other in to_drop:
                continue
            if corr_matrix.loc[col, other] > CORR_DROP_THRESHOLD:
                drop = col if target_corr.get(col, 0) < target_corr.get(other, 0) else other
                to_drop.add(drop)

    if to_drop:
        print(f"Dropping {len(to_drop)} correlated feature(s)  "
              f"(|corr| > {CORR_DROP_THRESHOLD}, keeping higher target-corr):")
        for col in sorted(to_drop):
            tc = target_corr.get(col, 0)
            # find the partner it lost to (highest corr, not in to_drop)
            partner = max(
                (other for other in feature_cols
                 if other != col and other not in to_drop
                 and corr_matrix.loc[col, other] > CORR_DROP_THRESHOLD),
                key=lambda o: target_corr.get(o, 0),
                default="?"
            )
            ptc = target_corr.get(partner, 0) if partner != "?" else 0
            print(f"  \u2212 '{col}' (target_corr={tc:.3f}) "
                  f"\u2190 kept '{partner}' (target_corr={ptc:.3f})")
        df = df.drop(columns=list(to_drop))

    return df
