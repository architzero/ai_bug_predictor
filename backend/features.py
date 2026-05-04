import logging
import os
import pandas as pd
import numpy as np

from backend.config import CORR_DROP_THRESHOLD
from backend.feature_constants import ALL_EXCLUDE_COLS

logger = logging.getLogger(__name__)

# Import from feature_constants to ensure consistency
from backend.feature_constants import NON_FEATURE_COLS as IMPORTED_NON_FEATURE_COLS
NON_FEATURE_COLS = IMPORTED_NON_FEATURE_COLS

# Leakage columns - these are NO LONGER COMPUTED (removed from feature_builder.py)
# Kept here for reference in case old cached data still has them
LEAKAGE_COLS = [
    "bug_fix_ratio",      # REMOVED: derived from label
    "past_bug_count",     # REMOVED: derived from label  
    "days_since_last_bug", # REMOVED: derived from label
]

# Language encoding for multi-language support
# Each language gets a unique ID for categorical encoding
# CRITICAL: IDs must be unique and sequential (0-10) for XGBoost categorical support
LANGUAGE_ENCODING = {
    "python": 0,
    "javascript": 1,
    "typescript": 2,
    "java": 3,
    "go": 4,
    "ruby": 5,
    "php": 6,
    "csharp": 7,
    "cpp": 8,
    "rust": 9,
    "other": 10,
}


EXCLUDE_FROM_CORR = set(ALL_EXCLUDE_COLS)

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

        # PRE-COMPUTE ALL BASE VALUES ONCE (optimization)
        commits    = max(g.get("commits", 0), 1)
        loc        = max(static["loc"], 1)
        functions  = max(static["functions"], 1)
        lines_added = g.get("lines_added", 0)
        lines_deleted = g.get("lines_deleted", 0)
        churn      = lines_added + lines_deleted
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
            # Keep both language (string) and language_id (categorical) for compatibility
            "language":            language,  # String for CLI tool language detection
            "language_id":         LANGUAGE_ENCODING.get(language, 10),  # 0-10 for model
            "has_test_file":        int(static.get("has_test_file", False)),
            "complexity_vs_baseline": complexity_vs_baseline,

            # complexity ratios (use pre-computed values)
            "complexity_density":      avg_cx / loc,
            "complexity_per_function": avg_cx / functions,
            "loc_per_function":        loc / functions,

            # git base (use pre-computed values)
            "commits":       commits,
            "lines_added":   lines_added,
            "lines_deleted": lines_deleted,
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

            # stability / volatility (use pre-computed churn and avg_commit)
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

            # temporal bug memory REMOVED - these features leak target signal
            # "recent_bug_flag":        g.get("recent_bug_flag", 0),      # REMOVED: temporal leakage
            # "bug_recency_score":      g.get("bug_recency_score", 0.0),  # REMOVED: temporal leakage  
            # "temporal_bug_risk":      g.get("temporal_bug_risk", 0.0),  # REMOVED: temporal leakage
            # "temporal_bug_memory":    g.get("temporal_bug_memory", 0.0),  # REMOVED: temporal leakage

            # Bug history features REMOVED - they were derived from labels (data leakage)
            # These features are no longer computed to prevent circular logic
        }

        # Add missing high-value features
        
        # 1. churn_ratio = lines_added / loc (overall churn, not just recent)
        overall_churn_ratio = (lines_added + lines_deleted) / loc if loc > 0 else 0
        row["churn_ratio"] = overall_churn_ratio
        
        # 2. author_entropy - measure of contributor diversity
        # Using minor_contributor_ratio as proxy for entropy (higher = more diverse)
        row["author_entropy"] = g.get("minor_contributor_ratio", 0)
        
        # 3. experience_score - based on author_count and commit patterns
        # Higher experience = fewer authors with consistent commits (lower entropy)
        author_count = g.get("author_count", 1)
        if author_count == 1:
            experience_score = 1.0  # Single author = high experience
        elif author_count <= 3:
            experience_score = 0.7  # Small team = moderate experience
        else:
            experience_score = 0.3  # Large team = lower average experience
        row["experience_score"] = experience_score
        
        # CRITICAL FIX: Remove repo_id to prevent repository leakage
        # Repository identifiers should NOT be used as features
        # This prevents cross-repo bias and ensures generalization

        rows.append(row)

    df_built = pd.DataFrame(rows)
    if "language_id" in df_built.columns:
        df_built["language_id"] = df_built["language_id"].astype("category")
    # CRITICAL FIX: Remove repo_id entirely to prevent repository leakage
    if "repo_id" in df_built.columns:
        df_built = df_built.drop(columns=["repo_id"])
        
    return df_built


def filter_correlated_features(df):
    """
    Drop features with pairwise |correlation| > CORR_DROP_THRESHOLD,
    keeping the one with higher correlation to the target label.
    Leakage cols and non-feature cols are excluded from analysis.
    
    CRITICAL FEATURES (never dropped): avg_complexity, commits, functions
    LOC FEATURES: Keep both 'loc' and 'loc_per_function' if multicollinearity < 0.8
    """
    if "buggy" not in df.columns:
        return df

    # Critical features that should NEVER be dropped regardless of correlation
    # These are fundamental defect prediction features with strong theoretical backing
    FORCE_KEEP = {'loc', 'avg_complexity', 'commits', 'functions'}
    
    # LOC features - keep both if they're not too correlated with each other
    LOC_FEATURES = {'loc', 'loc_per_function'}

    feature_cols = [
        c for c in df.columns
        if c not in EXCLUDE_FROM_CORR
        and df[c].dtype in [np.float64, np.int64, float, int]
    ]

    feat_df     = df[feature_cols]
    
    # Remove constant columns (zero variance) to prevent correlation errors
    constant_cols = [col for col in feat_df.columns if feat_df[col].std() == 0]
    if constant_cols:
        logger.info("Removing %d constant feature(s) before correlation: %s", 
                   len(constant_cols), constant_cols)
        feat_df = feat_df.drop(columns=constant_cols)
        feature_cols = [c for c in feature_cols if c not in constant_cols]
    
    if len(feature_cols) < 2:
        return df  # Not enough features to compute correlation
    
    corr_matrix = feat_df.corr().abs()
    target_corr = feat_df.corrwith(df["buggy"]).abs()

    to_drop = set()

    for i, col in enumerate(feature_cols):
        if col in to_drop or col in FORCE_KEEP:
            continue
        for j in range(i + 1, len(feature_cols)):
            other = feature_cols[j]
            if other in to_drop:
                continue
            if corr_matrix.loc[col, other] > CORR_DROP_THRESHOLD:
                # Special handling for LOC features
                if col in LOC_FEATURES and other in LOC_FEATURES:
                    # Both are LOC features - check their mutual correlation
                    loc_corr = corr_matrix.loc[col, other]
                    if loc_corr < 0.8:
                        # Low multicollinearity - keep both
                        continue
                    else:
                        # High multicollinearity - drop the weaker one
                        drop = col if target_corr.get(col, 0) < target_corr.get(other, 0) else other
                        to_drop.add(drop)
                # If one is in FORCE_KEEP, drop the other
                elif col in FORCE_KEEP:
                    to_drop.add(other)
                elif other in FORCE_KEEP:
                    to_drop.add(col)
                else:
                    # Neither is critical, drop the one with lower target correlation
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
