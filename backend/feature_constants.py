"""
Centralized feature column definitions.

Single source of truth for NON_FEATURE_COLS and LEAKAGE_COLS
to prevent inconsistencies across modules.
"""

# Columns that are NOT features (metadata, labels, predictions)
NON_FEATURE_COLS = [
    "file",           # File path (metadata)
    "buggy",          # Label (target variable)
    "bug_fixes",      # Raw git metric (not a derived feature)
    "bug_density",    # Derived from label (not a feature)
    "buggy_commit",   # SZZ metadata
    "commit_hash",    # Git metadata
    "repo",           # Repository identifier
    "language",       # String language name (replaced by language_id)
    "confidence",     # Label confidence weight
    "risk",           # Prediction output
    "risky",          # Binary prediction output
    "explanation",    # SHAP explanation text
    "confidence_score",     # Prediction confidence
    "confidence_level",     # Prediction confidence level
    "risk_per_loc",         # Derived metric (not a feature)
    "effort_priority",      # Derived metric (not a feature)
    "effort_category",      # Derived metric (not a feature)
    "bug_type",             # Bug classification output
    "bug_type_confidence",  # Bug classification confidence
]

# Columns that are DATA LEAKAGE (derived from labels, must never be used as features)
# These features were removed from feature engineering but may exist in old cached data
LEAKAGE_COLS = [
    "bug_fix_ratio",        # REMOVED: ratio of bug-fix commits (derived from label)
    "past_bug_count",       # REMOVED: count of historical bugs (derived from label)
    "days_since_last_bug",  # REMOVED: recency of last bug (derived from label)
]

# All columns to exclude when building feature matrix
ALL_EXCLUDE_COLS = NON_FEATURE_COLS + LEAKAGE_COLS
