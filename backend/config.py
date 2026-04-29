import os

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MODEL_DIR   = os.path.join(BASE_DIR, "ml", "models")
PLOTS_DIR   = os.path.join(BASE_DIR, "ml", "plots")
CACHE_DIR   = os.path.join(BASE_DIR, "ml", "cache")

# ── Cache sub-directories ──────────────────────────────────────────────────────
CHECKPOINT_DIR  = os.path.join(CACHE_DIR, "checkpoints")
MINER_CACHE_DIR = os.path.join(CACHE_DIR, "miner")
SZZ_CACHE_DIR   = os.path.join(CACHE_DIR, "szz")

# ── Cache versioning ───────────────────────────────────────────────────────────
CACHE_VERSION = "v14"  # Incremented for SZZ v2.6 with relaxed thresholds (5% churn, 35% confidence, 24 months)

# ── Model versioning ───────────────────────────────────────────────────────────
MODEL_VERSION = "v1"
MODEL_LATEST_PATH = os.path.join(MODEL_DIR, "bug_predictor_latest.pkl")
FEATURES_PATH     = os.path.join(CACHE_DIR, f"features_{MODEL_VERSION}.csv")
TRAINING_LOG_PATH = os.path.join(BASE_DIR, "ml", "training_log.jsonl")

# ── Repositories ───────────────────────────────────────────────────────────────
REPOS = [
    os.path.join(DATASET_DIR, "requests"),
    os.path.join(DATASET_DIR, "flask"),
    os.path.join(DATASET_DIR, "fastapi"),
    os.path.join(DATASET_DIR, "httpx"),
    os.path.join(DATASET_DIR, "celery"),
    os.path.join(DATASET_DIR, "sqlalchemy"),
    os.path.join(DATASET_DIR, "express"),
    os.path.join(DATASET_DIR, "axios"),
    os.path.join(DATASET_DIR, "guava"),
]

# ── Skip Patterns ──────────────────────────────────────────────────────────────
# Skip directories that contain non-production code or generated files
SKIP_DIR_PATTERNS = [
    # Dependencies & build artifacts
    "node_modules", "vendor", "dist", "build",
    # Virtual environments
    ".venv", "venv", "env", "__pycache__",
    # Generated & coverage
    "coverage", "__generated__", ".pytest_cache", ".mypy_cache",
    # Version control
    ".git", ".github", ".husky", ".gitlab",
    # Test directories (test files in main code are filtered by name pattern)
    "tests", "test", "__tests__", "spec",
    # Documentation & examples (not production code)
    "docs", "docs_src", "documentation", "examples", "example",
    # Scripts & migrations (utility code, not core logic)
    "scripts", "migrations",
    # Guava Android variant (duplicate of guava/src/)
    "android",
]

SKIP_FILE_PATTERNS = [
    ".min.js", ".min.css",
    "_pb2.py", ".pb.go",
    ".lock", ".log",
]

# ── Git mining ─────────────────────────────────────────────────────────────────
RECENT_DAYS_2W = 14
RECENT_DAYS_1M = 30
RECENT_DAYS_3M = 90

# ── Labeling ───────────────────────────────────────────────────────────────────
BUG_DENSITY_THRESH     = 0.15
MIN_BUG_FIXES_FALLBACK = 2

# ── Feature engineering ────────────────────────────────────────────────────────
CORR_DROP_THRESHOLD       = 0.97
MIN_COMMITS_FOR_OWNERSHIP = 5

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
TUNING_N_ITER     = 50
TSCV_N_SPLITS     = 5

# ── Risk threshold ─────────────────────────────────────────────────────────────
RISK_THRESHOLD = 0.50

# ── Defect density validation ─────────────────────────────────────────────────
DEFECT_DENSITY_TOP_K = 0.20

# ── Explainability ─────────────────────────────────────────────────────────────
TOP_LOCAL_PLOTS = 5
