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
CACHE_VERSION = "v16"  # Overhauled metadata format: {'confidence': float, 'bug_count': int}

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

# ── 3-LAYER FILTERING SYSTEM ────────────────────────────────────────────────────

# 🔹 LAYER 1: EXTENSION FILTER (COARSE FILTER)
ALLOWED_EXTENSIONS = {
    # Python
    ".py",
    
    # JavaScript / frontend/backend
    ".js", ".jsx", ".ts", ".tsx",
    
    # Java
    ".java",
    
    # Web / frontend
    ".html", ".css",
    
    # Configs (important ones only)
    ".json", ".yaml", ".yml"
}

EXCLUDED_EXTENSIONS = {
    ".md", ".txt", ".rst", ".log", ".csv",
    ".png", ".jpg", ".jpeg", ".svg",
    ".pdf"
}

# 🔹 LAYER 2: DIRECTORY INTELLIGENCE
EXCLUDED_DIRS = {
    # Test directories
    "test", "tests", "testing", "__tests__", "spec", "specs", "t",
    # Documentation
    "docs", "documentation", "docs_src",
    # Build artifacts
    "build", "dist", "out",
    # Version control
    ".git", ".github",
    # Dependencies
    "node_modules", "__pycache__", "coverage",
    # Static assets
    "static", "assets", "public", "vendor",
    # Examples and demos (CRITICAL: prevents noisy training data)
    "examples", "example", "sample", "samples",
    "demo", "demos", "benchmarks",
    # Virtual environments
    ".venv", "venv", "env",
    # Migrations (often auto-generated)
    "migrations"
}

CORE_DIRS = {
    "src", "lib", "app", "backend", "frontend", "api", "routers", "services", "db", "models", "database", "utils", "middleware", "controllers",
    # Add semantic directories often missed in large repos
    "routing", "dependencies", "security", "schemas", "endpoints", "views", "handlers"
}

# Conditional directories (need intelligence) - MORE INCLUSIVE
CONDITIONAL_DIRS = {
    "scripts", "config", "migrations"  # Allow with intelligent filtering
}

# Framework infrastructure keywords (research-clean approach)
FRAMEWORK_KEYWORDS = [
    "middleware", "routing", "security",
    "dependency", "template", "templating", "websocket",
    "openapi", "static", "auth"
]

# Legacy compatibility
SKIP_DIR_PATTERNS = EXCLUDED_DIRS  # Now excludes only truly non-code directories
ALWAYS_INCLUDE_DIRS = CORE_DIRS

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
    "instability_score", "avg_commit_score",
    "max_commit_ratio", "max_added",
    "author_count", "minor_contributor_ratio",
    "churn_ratio", "author_entropy", "experience_score",
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

# ── SZZ Algorithm Parameters ───────────────────────────────────────────────────
SZZ_MIN_CHURN_RATIO = 0.01  # 1% of file must change to be labeled buggy (more inclusive)
SZZ_MAX_FILES_PER_COMMIT = 20  # Skip commits touching >20 files (allow larger refactor commits)
SZZ_MIN_CONFIDENCE = 0.4  # 40% minimum confidence threshold (balanced for 'fix' keywords)
SZZ_LABEL_WINDOW_DAYS = 2555  # 7 years (essential for mature repositories)

# ── Explainability ─────────────────────────────────────────────────────────────
TOP_LOCAL_PLOTS = 5
SHAP_BACKGROUND_SAMPLES = 100  # k-means samples for SHAP background
