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
# This forces a cache miss and triggers a fresh SZZ / miner run automatically.
CACHE_VERSION = "v5"

# ── Model versioning ───────────────────────────────────────────────────────────
MODEL_VERSION = "v1"
MODEL_PATH    = os.path.join(MODEL_DIR, f"bug_predictor_{MODEL_VERSION}.pkl")
FEATURES_PATH = os.path.join(CACHE_DIR, f"features_{MODEL_VERSION}.csv")

# ── Repositories ───────────────────────────────────────────────────────────────
REPOS = [
    os.path.join(DATASET_DIR, "requests"),
    os.path.join(DATASET_DIR, "flask"),
    os.path.join(DATASET_DIR, "fastapi"),
    os.path.join(DATASET_DIR, "httpx"),
]

# ── Git mining ─────────────────────────────────────────────────────────────────
RECENT_DAYS_2W = 14
RECENT_DAYS_1M = 30
RECENT_DAYS_3M = 90

# ── Labeling ───────────────────────────────────────────────────────────────────
BUG_FIX_KEYWORDS   = ["fix", "bug", "error", "crash", "resolve", "defect"]
NON_BUG_KEYWORDS   = ["typo", "docs", "readme", "refactor", "format", "style"]
BUG_DENSITY_THRESH = 0.15   # fallback heuristic: bug_density > this → buggy=1
MIN_BUG_FIXES_FALLBACK = 2  # fallback: bug_fixes >= this → buggy=1

# ── Feature engineering ────────────────────────────────────────────────────────
CORR_DROP_THRESHOLD       = 0.97   # drop one of any pair with |corr| > this
MIN_COMMITS_FOR_OWNERSHIP = 5      # ownership only computed if commits >= this

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
