import logging
import pandas as pd
import numpy as np

from config import CORR_DROP_THRESHOLD

logger = logging.getLogger(__name__)

# Language encoding for multi-language support
LANGUAGE_ENCODING = {
    "python": 0, "javascript": 1, "typescript": 1,
    "java": 2, "go": 3, "ruby": 4, "php": 5,
    "csharp": 6, "cpp": 7, "rust": 8, "other": 9,
}


NON_FEATURE_COLS = [
    "file", "buggy", "bug_fixes", "bug_density",
    "buggy_commit", "commit_hash", "repo", "language", "confidence"
]

# leakage cols excluded from correlation analysis and model training
LEAKAGE_COLS = [
    "bug_fix_ratio",
    "past_bug_count",
    "days_since_last_bug",
    "bug_fixes",  # CRITICAL: This is derived from the label - circular logic
]

EXCLUDE_FROM_CORR = set(NON_FEATURE_COLS + LEAKAGE_COLS)

# cap raw day values to 10 years to prevent extreme outliers skewing features
MAX_AGE_DAYS = 3650

# Language-specific complexity baselines for normalization
LANGUAGE_COMPLEXITY_BASELINE = {
    "python": 3.5,
    "javascript": 3.8,
    "typescript": 3.8,
    "java": 5.5,   # higher baseline due to OOP boilerplate
    "go": 4.0,
    "ruby": 3.5,
    "other": 4.0,
}

def normalize_complexity(raw_complexity: float, language: str) -> float:
    """Normalize complexity by language baseline to account for structural differences."""
    baseline = LANGUAGE_COMPLEXITY_BASELINE.get(language, 4.0)
    # How many times above baseline is this file?
    return raw_complexity / baseline


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
        language            = static.get("language", "other")

        # language-normalized complexity
        complexity_vs_baseline = normalize_complexity(avg_cx, language)

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
            "language":             language,
            "language_id":         LANGUAGE_ENCODING.get(language, 9),  # Cast to categorical in train_model
            "has_test_file":        int(static.get("has_test_file", False)),
            "complexity_vs_baseline": complexity_vs_baseline,

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
            
            # change burst
            "commit_burst_score":     g.get("commit_burst_score", 0.0),
            "recent_commit_burst":    g.get("recent_commit_burst", 0),
            "burst_ratio":            g.get("burst_ratio", 0.0),
            "burst_risk":             g.get("burst_risk", 0.0),

            # temporal bug memory
            "recent_bug_flag":        g.get("recent_bug_flag", 0),
            "bug_recency_score":      g.get("bug_recency_score", 0.0),
            "temporal_bug_risk":      g.get("temporal_bug_risk", 0.0),
            "temporal_bug_memory":    g.get("temporal_bug_memory", 0.0),

            # bug history (kept for analysis, excluded from model via LEAKAGE_COLS)
            "past_bug_count":      g.get("past_bug_count",      0),
            "bug_fix_ratio":       g.get("bug_fix_ratio",       0),
            "days_since_last_bug": g.get("days_since_last_bug", -1),
        }

        rows.append(row)

    df_built = pd.DataFrame(rows)
    if "language_id" in df_built.columns:
        df_built["language_id"] = df_built["language_id"].astype("category")
        
    return df_built


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
        logger.info(
            "Dropping %d correlated feature(s) (|corr| > %s, keeping higher target-corr):",
            len(to_drop), CORR_DROP_THRESHOLD,
        )
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
            logger.info("  − '%s' (target_corr=%.3f) ← kept '%s' (target_corr=%.3f)",
                        col, tc, partner, ptc)
        df = df.drop(columns=list(to_drop))

    return df
