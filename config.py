import os

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MODEL_DIR   = os.path.join(BASE_DIR, "model")
PLOTS_DIR   = os.path.join(BASE_DIR, "explainability", "plots")
CACHE_DIR   = os.path.join(BASE_DIR, ".cache")

# ── Cache sub-directories ──────────────────────────────────────────────────────
CHECKPOINT_DIR  = os.path.join(CACHE_DIR, "checkpoints")
MINER_CACHE_DIR = os.path.join(CACHE_DIR, "miner")
SZZ_CACHE_DIR   = os.path.join(CACHE_DIR, "szz")

# ── Cache versioning ───────────────────────────────────────────────────────────
# Increment when filter logic, GENERATED_PATHS, or feature engineering changes.
CACHE_VERSION = "v10"

# ── Model versioning ───────────────────────────────────────────────────────────
MODEL_VERSION = "v1"

# MODEL_LATEST_PATH is always the stable pointer to the newest model.
# The timestamped per-run path is generated at training time inside
# train_model._save_model_with_metadata() so importing config at server
# startup does NOT create a phantom timestamped filename.
MODEL_LATEST_PATH = os.path.join(MODEL_DIR, "bug_predictor_latest.pkl")
FEATURES_PATH     = os.path.join(CACHE_DIR, f"features_{MODEL_VERSION}.csv")

# Lightweight training log – one JSON line appended per run (no MLflow needed).
TRAINING_LOG_PATH = os.path.join(MODEL_DIR, "training_log.jsonl")

# ── Repositories ───────────────────────────────────────────────────────────────
REPOS = [
    # Existing Python repos
    os.path.join(DATASET_DIR, "requests"),
    os.path.join(DATASET_DIR, "flask"),
    os.path.join(DATASET_DIR, "fastapi"),
    os.path.join(DATASET_DIR, "httpx"),
    # New repos for multi-language training set
    os.path.join(DATASET_DIR, "celery"),
    os.path.join(DATASET_DIR, "sqlalchemy"),
    os.path.join(DATASET_DIR, "express"),
    os.path.join(DATASET_DIR, "axios"),
    os.path.join(DATASET_DIR, "guava"),
]

# ── Skip Patterns (Shared across analyzer and SZZ) ────────────────────────────
# CRITICAL: Single source of truth for directories/files to exclude from analysis.
# Used by both static_analysis/analyzer.py and git_mining/szz_labeler.py to ensure
# consistent file filtering and prevent SZZ from labeling files that analyzer never scores.

SKIP_DIR_PATTERNS = [
    "docs_src", "docs", "examples", "example",
    "node_modules", "vendor", "dist", "build",
    ".venv", "venv", "env", "__pycache__",
    "migrations", "coverage", "generated", "__generated__",
    "scripts", "test", "tests", "spec", "testing",
    ".git", ".github", ".husky",
]

SKIP_FILE_PATTERNS = [
    ".min.js", ".min.css",  # Minified files
    "_pb2.py", ".pb.go",     # Protocol buffer generated files
    ".lock", ".log",         # Lock and log files
]

# ── Git mining ─────────────────────────────────────────────────────────────────
RECENT_DAYS_2W = 14
RECENT_DAYS_1M = 30
RECENT_DAYS_3M = 90

# ── Labeling ───────────────────────────────────────────────────────────────────
# NOTE: The primary bug-fix keyword list lives in git_mining/szz_labeler.py
# (POSITIVE_KEYWORDS / NEGATIVE_KEYWORDS) where it governs SZZ commit
# classification.  Only the heuristic fallback thresholds are kept here.
BUG_DENSITY_THRESH     = 0.15  # fallback: bug_density > this → buggy=1
MIN_BUG_FIXES_FALLBACK = 2     # fallback: bug_fixes >= this → buggy=1

# ── Feature engineering ────────────────────────────────────────────────────────
CORR_DROP_THRESHOLD       = 0.97   # drop one of any pair with |corr| > this
MIN_COMMITS_FOR_OWNERSHIP = 5      # ownership only computed if commits >= this

# Git metric columns normalised per-repo before training.
# Single source of truth — imported by both main.py and app_ui.py.
GIT_FEATURES_TO_NORMALIZE = [
    "commits", "lines_added", "lines_deleted",
    "commits_2w", "commits_1m", "commits_3m",
    "recent_churn_ratio", "recent_activity_score",
    "instability_score", "avg_commit_size",
    "max_commit_ratio", "max_added",
    "author_count", "minor_contributor_ratio",
]

# ── Model training ─────────────────────────────────────────────────────────────
RANDOM_STATE      = 42
TEST_SIZE         = 0.3
SMOTE_K_NEIGHBORS = 5
TUNING_N_ITER     = 50          # RandomizedSearchCV iterations
TSCV_N_SPLITS     = 5           # TimeSeriesSplit folds

# ── Risk threshold ─────────────────────────────────────────────────────────────
# Calibrate precision / recall trade-off.
RISK_THRESHOLD = 0.50
                        # 0.50 yields realistic F1 on imbalanced schemas

# ── Defect density validation ─────────────────────────────────────────────────
# What % of files to consider "high risk"? We check if they contain this many bugs:
DEFECT_DENSITY_TOP_K = 0.20   # top 20% risk files should contain ≥ 70% of bugs

# ── Explainability ─────────────────────────────────────────────────────────────
TOP_LOCAL_PLOTS = 5   # top-risk files to generate local SHAP plots
