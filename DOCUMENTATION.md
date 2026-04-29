# GitSentinel — Complete Technical Documentation

**Version**: 1.0  
**Last Updated**: 2026-04-29  
**Status**: Production Ready ✅

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Performance Metrics](#performance-metrics)
4. [Installation & Setup](#installation--setup)
5. [Usage Guide](#usage-guide)
6. [Technical Implementation](#technical-implementation)
7. [Security & Scalability](#security--scalability)
8. [Development History](#development-history)
9. [API Reference](#api-reference)
10. [Troubleshooting](#troubleshooting)

---

## Executive Summary

GitSentinel is an AI-powered bug risk prediction system that analyzes Git repositories to identify files most likely to contain defects. Using machine learning trained on 9 open-source projects (1,654 files, 126K commits), it achieves:

- **PR-AUC**: 0.940 (elite ranking quality)
- **ROC-AUC**: 0.932 (strong discrimination)
- **F1 Score**: 0.855 (honest benchmark, 5 repos ≥30 files)
- **Recall@20%**: 34% of bugs caught by reviewing top 20% of files

### Key Features

✅ **ML Models**: Random Forest with isotonic calibration  
✅ **SZZ Algorithm**: Line-level git blame for bug labeling  
✅ **SHAP Explanations**: Human-readable risk explanations  
✅ **Per-Repo Ranking**: Tiers assigned within each repository  
✅ **Bug Classification**: 6 bug types (performance, security, exception, etc.)  
✅ **Web Dashboard**: Flask UI with GitHub OAuth (optional)  
✅ **CLI Tool**: Fast single-repo analysis

---

## System Architecture

```
ai-bug-predictor/
├── backend/              # Core ML & analysis modules
│   ├── analysis.py       # Static code analysis (Lizard)
│   ├── git_mining.py     # Git history extraction (PyDriller)
│   ├── features.py       # Feature engineering (42 features)
│   ├── labeling.py       # SZZ bug labeling
│   ├── train.py          # Model training pipeline
│   ├── predict.py        # Risk prediction & tier assignment
│   ├── explainer.py      # SHAP explanations
│   ├── bug_classifier.py # Bug type classification
│   └── config.py         # Configuration constants
├── frontend/             # Web UI (Flask)
│   ├── templates/        # HTML templates
│   └── assets/           # CSS, JS, images
├── ml/                   # Trained models & outputs
│   ├── models/           # Serialized models (.pkl)
│   ├── plots/            # SHAP visualizations
│   ├── cache/            # Git mining cache
│   ├── benchmarks.json   # Performance benchmarks
│   └── training_log.jsonl # Training history
├── dataset/              # Training repositories
├── main.py               # Training pipeline (multi-repo)
├── bug_predictor.py      # CLI tool (single-repo)
├── app_ui.py             # Flask web app
└── test_imports.py       # Dependency verification
```

### Data Flow

```
1. Static Analysis (Lizard)
   ↓
2. Git Mining (PyDriller + SZZ)
   ↓
3. Feature Engineering (42 features)
   ↓
4. Model Prediction (Random Forest)
   ↓
5. Calibration (Isotonic Regression)
   ↓
6. Tier Assignment (Per-Repo Percentiles)
   ↓
7. SHAP Explanations (Human-Readable)
```

---

## Performance Metrics

### Cross-Project Validation (9 Repos, Leave-One-Out)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Weighted F1** | 0.745 | >0.70 | ✅ PASS |
| **PR-AUC** | 0.940 | >0.85 | ✅ ELITE |
| **ROC-AUC** | 0.932 | >0.90 | ✅ STRONG |
| **Recall@20%** | 0.331 | >0.30 | ✅ PASS |

### Reliable Benchmark (5 Repos ≥30 Files)

Excludes tiny repos (httpx, flask, requests, express) for honest evaluation:

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Honest F1** | 0.855 | Excellent classification |
| **Honest PR-AUC** | 0.920 | Elite ranking quality |
| **Honest Recall@20%** | 0.340 | 34% of bugs in top 20% |
| **Honest Precision** | 0.873 | 87% of predictions correct |
| **Honest Recall** | 0.866 | 87% of bugs caught |

### Per-Repository Results

| Repo | Files | Bugs | F1 | PR-AUC | Recall@20% |
|------|-------|------|-----|--------|------------|
| httpx | 9 | 6 | 1.000 | 1.000 | 0.167 |
| flask | 23 | 20 | 0.974 | 0.998 | 0.200 |
| requests | 17 | 4 | 0.545 | 0.861 | 0.750 |
| fastapi | 47 | 23 | 0.909 | 0.977 | 0.391 |
| axios | 70 | 48 | 0.795 | 0.941 | 0.292 |
| express | 7 | 6 | 1.000 | 1.000 | 0.167 |
| celery | 214 | 127 | 0.908 | 0.959 | 0.315 |
| guava | 1031 | 411 | 0.663 | 0.786 | 0.433 |
| sqlalchemy | 236 | 171 | 0.883 | 0.938 | 0.269 |

---

## Installation & Setup

### Prerequisites

- Python 3.8+
- Git 2.0+
- 4GB RAM minimum (8GB recommended for training)
- Windows/Linux/macOS

### Quick Start

```bash
# 1. Clone repository
git clone <repo-url>
cd ai-bug-predictor

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify installation
python test_imports.py

# 5. Download training datasets (optional, for retraining)
git clone https://github.com/psf/requests dataset/requests
git clone https://github.com/pallets/flask dataset/flask
# ... (see dataset/README.md for full list)

# 6. Use pre-trained model (CLI)
python bug_predictor.py dataset/requests

# 7. Or retrain model (takes ~87 minutes)
python main.py

# 8. Run web UI (optional)
python app_ui.py
# Visit http://localhost:5000
```

### Dependencies

**Core ML**:
- scikit-learn 1.8.0
- xgboost 3.2.0
- imbalanced-learn 0.14.1
- shap 0.51.0

**Analysis**:
- GitPython 3.1.46
- PyDriller 2.9
- lizard 1.21.3

**Web UI** (optional):
- Flask 3.1.3
- Authlib 1.7.0 (GitHub OAuth)
- Flask-Limiter 3.5.0 (rate limiting)

See `requirements.txt` for complete list.

---

## Usage Guide

### CLI Tool (Single Repository)

```bash
# Analyze local repository
python bug_predictor.py /path/to/repo

# Analyze remote repository (auto-clones)
python bug_predictor.py https://github.com/user/repo

# Example output:
# ======================================================================
#   TOP 10 RISK FILES (with explanations)
# ======================================================================
#
#   #1. adapters.py
#       Risk: 89.6% | Tier: CRITICAL | LOC: 379
#       Why risky: · Modified 4.7× more than repo median (14 commits), 
#                    indicating high churn
#                  · Strong bug memory (1.013), which increases defect risk
#                  · Contains very long functions (107 lines)
```

### Training Pipeline (Multiple Repositories)

```bash
# Train on all datasets in dataset/ folder
python main.py

# Training stages:
# Stage 0: File filtering audit
# Stage 1: Data collection (parallel, 4 workers)
# Stage 2: Feature engineering (42 features)
# Stage 3: Cross-project training (9 folds)
# Stage 4: Risk prediction
# Stage 5: SHAP explanations
# Stage 6: Commit risk simulation
# Stage 7: Ablation study

# Output:
# - ml/models/bug_predictor_latest.pkl (model)
# - ml/plots/*.png (SHAP visualizations)
# - ml/benchmarks.json (performance metrics)
# - ml/training_log.jsonl (training history)
```

### Web UI (Optional)

```bash
# Start Flask server
python app_ui.py

# Features:
# - GitHub OAuth login
# - Real-time repository scanning
# - Interactive SHAP plots
# - PR risk analysis
# - Bug type classification
# - Rate limiting (5 scans/hour)
```

---

## Technical Implementation

### Feature Engineering (42 Features)

**Static Complexity** (10 features):
- `loc`: Lines of code
- `avg_complexity`, `max_complexity`: Cyclomatic complexity
- `functions`: Function count
- `avg_params`, `max_function_length`: Function metrics
- `complexity_density`, `complexity_per_function`: Normalized metrics
- `complexity_vs_baseline`: Language-relative complexity
- `has_test_file`: Test coverage indicator

**Git Activity** (18 features):
- `commits`, `lines_added`, `lines_deleted`: Change volume
- `commits_2w`, `commits_1m`, `commits_3m`: Recent activity
- `recent_churn_ratio`, `recent_activity_score`: Temporal patterns
- `author_count`, `ownership`: Developer metrics
- `instability_score`, `avg_commit_size`: Change patterns
- `days_since_last_change`, `recency_ratio`: Temporal metrics

**Bug History** (6 features):
- `bug_fixes`: Historical bug count
- `bug_recency_score`: Recent bug activity
- `temporal_bug_risk`, `temporal_bug_memory`: Bug patterns
- `recent_bug_flag`: Recent bug indicator

**File Coupling** (4 features):
- `max_coupling_strength`: Strongest coupling
- `coupled_file_count`: Number of coupled files
- `coupled_recent_missing`: Missing recent changes
- `coupling_risk`: Overall coupling risk

**Commit Bursts** (4 features):
- `commit_burst_score`: Burst intensity
- `recent_commit_burst`: Recent burst count
- `burst_ratio`: Burst concentration
- `burst_risk`: Overall burst risk

### Model Architecture

**Algorithm**: Random Forest (winner of composite metric)
- **n_estimators**: 300
- **max_depth**: 8
- **min_samples_split**: 10
- **min_samples_leaf**: 4
- **max_samples**: 0.7
- **class_weight**: balanced

**Resampling**: SMOTETomek
- Oversamples minority class (buggy files)
- Removes Tomek links (noisy boundary samples)
- Applied only to training data (80% split)

**Calibration**: Isotonic Regression
- Trained on 20% holdout set
- Minimal capping (0.001-0.999) to preserve discrimination
- Prevents probability clustering at ceiling

**Feature Selection**: RFE (Recursive Feature Elimination)
- Median threshold
- 26 features selected from 42 candidates
- Sparse features rescued (coupling, burst, temporal bug)

### Risk Tier Assignment

**Methodology**: Per-Repository Percentile Ranking

- **CRITICAL**: Top 10% of files by risk score
- **HIGH**: 10-25% (next 15%)
- **MODERATE**: 25-50% (next 25%)
- **LOW**: Bottom 50%

**Why Per-Repository?**
1. Base rate robustness (training: 49.3% buggy, real: 15-25%)
2. Actionable results (every scan produces CRITICAL files)
3. Fair comparison (small repos not dominated by large repos)
4. Calibration drift resilience (percentiles stable, absolutes shift)

**Tie-Breaking**: Files with identical risk scores get identical tiers (uses `np.unique()` grouping, not `argsort()`)

### SHAP Explanations

**Global Explanations**:
- Bar plot: Mean absolute SHAP per feature (top 15)
- Beeswarm plot: Feature impact distribution (top 20)

**Local Explanations** (per file):
- Waterfall plot: Additive feature contributions (top 10)
- Force plot: Push/pull visualization (top 10)
- Human-readable text: Top 3 features with context

**Example Explanation**:
```
· Modified 4.7× more than repo median (14 commits), indicating high churn
· Strong bug memory (1.013), which increases defect risk
· Contains very long functions (107 lines), which increases defect risk
```

### SZZ Algorithm (Bug Labeling)

**Process**:
1. Identify bug-fixing commits (keywords: "fix", "bug", "issue")
2. Use `git blame` to find bug-inducing commits
3. Label files modified in bug-inducing commits as buggy
4. Cache results for performance (ml/cache/szz/)

**Confidence Scoring**:
- High confidence: Explicit bug keywords + issue tracker links
- Medium confidence: Implicit bug keywords
- Low confidence: Heuristic patterns

---

## Security & Scalability

### Security Features

**Input Validation**:
- Path traversal prevention (no `..` in paths)
- Repository URL validation (whitelist: github.com, gitlab.com)
- File extension whitelist (supported languages only)

**Web UI Security**:
- CSRF protection on all POST endpoints
- Rate limiting (5 scans/hour, 200 requests/hour)
- OAuth 2.0 GitHub authentication
- Session management with secure cookies
- SQL injection prevention (parameterized queries)

**Secrets Management**:
- `.env` file for sensitive config (not in git)
- `.env.example` template provided
- GitHub OAuth tokens encrypted

### Scalability

**Performance Optimizations**:
- **Git mining cache**: Subsequent runs instant (first run: 1-5 min)
- **Parallel processing**: 4 workers for multi-repo training
- **SHAP sampling**: 60% sample for large repos (10× faster)
- **Lizard threading**: ThreadPoolExecutor for static analysis
- **Checkpoint system**: Resume training after interruption

**Resource Usage**:
- **Memory**: 2-4GB for training, 500MB for inference
- **Disk**: 100MB model + 50MB cache per repo
- **CPU**: Multi-core support (4 workers default)

**Horizontal Scaling** (future):
- Celery task queue for async scanning
- Redis cache for SHAP results
- PostgreSQL for multi-user support
- Docker containerization

---

## Development History

### Critical Bug Fixes (2026-04-29)

**1. Calibration Clustering** (CRITICAL)
- **Problem**: 64.7% of files clustered at risk > 0.95 due to aggressive capping (0.01-0.99)
- **Fix**: Changed to minimal capping (0.001-0.999) in `_IsotonicWrapper`
- **Impact**: Better probability discrimination, no ceiling clustering

**2. Per-Repo Tier Assignment** (CRITICAL)
- **Problem**: Tiers assigned globally, causing high-risk files in low-bug repos to show as LOW
- **Fix**: Changed `_assign_risk_tiers_percentile()` to use `groupby('repo')`
- **Impact**: Every repository gets actionable CRITICAL/HIGH/MODERATE/LOW distribution

**3. Tie-Breaking Consistency** (CRITICAL)
- **Problem**: Files with identical risk scores got different tiers due to arbitrary `argsort()` ordering
- **Fix**: Use `np.unique()` with `return_counts=True` to group tied scores
- **Impact**: Identical risk scores always get identical tiers

**4. String Truncation** (CRITICAL)
- **Problem**: `np.array(["LOW"] * n)` inferred dtype='<U3', truncating "CRITICAL" to "CRI"
- **Fix**: Use `dtype=object` for variable-length strings
- **Impact**: Tier labels display correctly in UI

**5. Training Stats Persistence** (ENHANCEMENT)
- **Problem**: No feature distribution stats saved for OOD detection
- **Fix**: Save per-feature mean/std/median/p01/p99 in model artifact
- **Impact**: Better confidence assessment for new repositories

### Training History

| Date | Version | F1 | PR-AUC | ROC-AUC | Notes |
|------|---------|-----|--------|---------|-------|
| 2026-04-29 | v1.0 | 0.855 | 0.920 | 0.932 | Production release |
| 2026-04-28 | v0.9 | 0.820 | 0.910 | 0.925 | Pre-fix baseline |

---

## API Reference

### Core Functions

#### `analyze_repository(repo_path, verbose=False)`
Static code analysis using Lizard.

**Parameters**:
- `repo_path` (str): Path to Git repository
- `verbose` (bool): Print analysis audit

**Returns**: List of dicts with static metrics

---

#### `mine_git_data(repo_path)`
Extract Git history using PyDriller.

**Parameters**:
- `repo_path` (str): Path to Git repository

**Returns**: Dict of file → git metrics

---

#### `build_features(static_results, git_results)`
Combine static + git metrics into feature matrix.

**Parameters**:
- `static_results` (list): Output from `analyze_repository()`
- `git_results` (dict): Output from `mine_git_data()`

**Returns**: pandas DataFrame with 42 features

---

#### `predict(model_data, df, return_confidence=False)`
Predict bug risk for files.

**Parameters**:
- `model_data` (dict): Model artifact from `load_model_version()`
- `df` (DataFrame): Feature matrix from `build_features()`
- `return_confidence` (bool): Return confidence assessment

**Returns**: DataFrame with `risk`, `risky`, `risk_tier` columns

---

#### `explain_prediction(model_data, df, save_plots=True, top_local=5)`
Generate SHAP explanations.

**Parameters**:
- `model_data` (dict): Model artifact
- `df` (DataFrame): Predictions from `predict()`
- `save_plots` (bool): Save SHAP plots to ml/plots/
- `top_local` (int): Number of local plots to generate

**Returns**: DataFrame with `explanation` column

---

### Configuration

Edit `backend/config.py` to customize:

```python
# Model parameters
RISK_THRESHOLD = 0.5          # Binary classification threshold
TUNING_N_ITER = 10            # Hyperparameter search iterations
TSCV_N_SPLITS = 3             # Time series CV splits

# Performance
DEFECT_DENSITY_TOP_K = 0.20   # Top 20% for Recall@K metric
SHAP_SAMPLE_SIZE = 0.60       # Sample 60% for SHAP (large repos)

# Paths
MODEL_DIR = "ml/models"
PLOTS_DIR = "ml/plots"
CACHE_DIR = "ml/cache"
```

---

## Troubleshooting

### Common Issues

**1. "No trained model found!"**
```bash
# Solution: Train model first
python main.py
```

**2. "No source files found in repository!"**
```bash
# Check supported languages:
# Python, JavaScript, TypeScript, Java, Go, Ruby, PHP, C#, C++, Rust

# Verify repository structure:
ls -R /path/to/repo
```

**3. "Git mining takes too long"**
```bash
# First run: 1-5 minutes (normal)
# Subsequent runs: instant (cached)

# To clear cache:
rm -rf ml/cache/miner/*
rm -rf ml/cache/szz/*
```

**4. "SHAP computation fails"**
```bash
# For large repos (>1000 files), SHAP samples 60% automatically
# To adjust sampling:
# Edit backend/explainer.py: sample_for_shap=500
```

**5. "Predictions seem unreliable"**
```bash
# Check confidence warnings:
python bug_predictor.py /path/to/repo

# Common warnings:
# - Small repository (<25 files) → directional only
# - Non-Python language → lower accuracy
# - Sparse git history → limited features
```

### Performance Tuning

**Speed up training**:
```python
# backend/config.py
TUNING_N_ITER = 5  # Reduce from 10 (2× faster)
TSCV_N_SPLITS = 2  # Reduce from 3 (1.5× faster)
```

**Speed up SHAP**:
```python
# backend/explainer.py
sample_for_shap = 500  # Reduce from 60% (2-3× faster)
```

**Reduce memory usage**:
```python
# main.py
# Comment out ablation study (saves 1GB RAM)
# run_ablation_study(df, global_features)
```

### Debugging

**Enable verbose logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Check model internals**:
```python
import joblib
model = joblib.load('ml/models/bug_predictor_latest.pkl')
print(f"Features: {model['features']}")
print(f"Training stats: {model['training_stats'].keys()}")
```

**Verify cache**:
```bash
ls -lh ml/cache/miner/  # Git mining cache
ls -lh ml/cache/szz/    # SZZ labeling cache
```

---

## License

MIT License - See LICENSE file for details

---

## Citation

If you use GitSentinel in research, please cite:

```bibtex
@software{gitsentinel2026,
  title={GitSentinel: AI-Powered Bug Risk Prediction},
  author={Your Name},
  year={2026},
  url={https://github.com/yourusername/ai-bug-predictor}
}
```

---

## Support

- **Issues**: GitHub Issues
- **Documentation**: This file + inline code comments
- **Contact**: your.email@example.com

---

**Last Updated**: 2026-04-29  
**Version**: 1.0  
**Status**: Production Ready ✅
