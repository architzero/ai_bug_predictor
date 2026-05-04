# AI-Based Bug Prediction System

**Predict defect-prone source files before failures occur** — using static code analysis, Git history mining, and machine learning trained across nine real-world open-source repositories.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![ML](https://img.shields.io/badge/ML-Random%20Forest-orange)](https://scikit-learn.org/)

---

## 🎯 Overview

Software defects are not random. They consistently appear in files that share measurable characteristics — high cyclomatic complexity, frequent churn, many contributors, and a history of past bugs. Traditional linters catch syntax errors and code smells, but they say nothing about future defect risk.

This project builds an **end-to-end AI-powered bug prediction engine** that:

- ✅ Extracts structural complexity metrics from source code using **Lizard** — supporting Python, JavaScript, TypeScript, Java, Go, Ruby, and more
- ✅ Mines Git commit history for change frequency, churn, coupling, and developer activity signals using **PyDriller**
- ✅ Labels bug-introducing commits using an **enhanced SZZ algorithm** with confidence-weighted labels
- ✅ Engineers **26 RFE-selected features** per file and trains a cross-project supervised ML classifier
- ✅ Evaluates using **leave-one-project-out cross-validation** across nine repositories spanning four programming languages
- ✅ Ranks repository files by predicted defect probability with **calibrated scores**
- ✅ Classifies predicted **bug type** (logic, crash, null pointer, race condition, exception, security)
- ✅ Explains each prediction using **SHAP values** in plain-language terms

**Goal**: Help engineering teams focus testing, code review, and refactoring effort where the statistical risk is highest — not just where the code looks messy at a glance.

---

## 📊 Performance Metrics

Evaluated using **leave-one-project-out cross-validation** across 9 repositories (1,654 files, 126K commits):

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **PR-AUC** | **0.701** | Good ranking quality (>0.65 = good) |
| **ROC-AUC** | **0.700** | Moderate discrimination |
| **F1 Score** | **0.523** | Honest benchmark (5 repos ≥30 files) |
| **Recall@20%** | **34.0%** | Reviewing top 20% of files catches 34% of bugs |
| **Weighted F1** | **0.440** | Realistic metric weighted by repo size |

**Key Finding**: Git process metrics (commits, churn, coupling) substantially outperform static complexity metrics in isolation. Combined features achieve the highest PR-AUC (0.708).

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- Git installed and accessible in PATH
- Target repository must have Git history (shallow clones not recommended)

### Installation

```bash
# 1. Clone this repository
git clone https://github.com/yourusername/ai-bug-predictor.git
cd ai-bug-predictor

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify installation
python test_imports.py
```

### Usage

#### Option 1: CLI Tool (Pre-trained Model)

```bash
# Analyze a local repository
python bug_predictor.py dataset/requests

# Analyze a GitHub repository (auto-clones)
python bug_predictor.py https://github.com/psf/requests
```

#### Option 2: Train Your Own Model

```bash
# Train on all datasets in dataset/ folder
python main.py
```

#### Option 3: Web Dashboard (Optional)

```bash
# Set up environment variables
cp .env.example .env
# Edit .env with your GitHub OAuth credentials

# Start Flask server
python app_ui.py
# Visit http://localhost:5000
```

---

## 📈 Example Output

```
Analyzing repository: flask/

Files analyzed  :  42
Model loaded    :  bug_predictor_latest.pkl
Base rate       :  54.8% buggy (training reference)

─────────────────────────────────────────────────────────────────
 File                         Score    Tier       Bug Type
─────────────────────────────────────────────────────────────────
 src/flask/app.py             0.937    CRITICAL   logic
 src/flask/cli.py             0.935    CRITICAL   logic
 src/flask/blueprints.py      0.934    CRITICAL   null_pointer
 src/flask/testing.py         0.921    HIGH       logic
 src/flask/sessions.py        0.904    HIGH       race_condition
 src/flask/globals.py         0.412    MODERATE   unknown
 src/flask/typing.py          0.180    LOW        unknown
─────────────────────────────────────────────────────────────────

CRITICAL: 5  |  HIGH: 8  |  MODERATE: 6  |  LOW: 23

Risk Tiers (within-repository percentile):
  CRITICAL (top 10%)    → Immediate review required
  HIGH (10-25%)         → Prioritize for review
  MODERATE (25-50%)     → Consider for review
  LOW (bottom 50%)      → Low priority
```

### Per-File Explanation

```
src/auth/login.py — CRITICAL  (score: 0.937, rank: top 3%)
─────────────────────────────────────────────────────────
  🔴  Strong bug history — this file has been the source of past bugs
  🔴  High cyclomatic complexity (avg 15.2) — complex logic is error-prone
  🟡  Frequently changed in recent commits — active churn increases risk
  🟢  Moderate coupling — fewer co-change dependencies than average
─────────────────────────────────────────────────────────
  Predicted bug type: logic (confidence: 0.81)
  
  Top risky functions:
    process_auth       cx=21  67 lines  4 params
    validate_token     cx=17  73 lines  3 params
    handle_session     cx=14  58 lines  5 params
```

---

## 🏗️ How It Works

```
Git Repository (any supported language)
      │
      ├──▶  Static Code Analyzer   (Lizard → complexity, size, params, LOC)
      │
      ├──▶  Git History Miner      (PyDriller → churn, commits, authors, coupling)
      │
      ├──▶  SZZ Labeler            (bug-introducing commit identification)
      │
      ▼
Feature Engineering Layer          (26 RFE-selected features per file)
      │
      ▼
ML Classifier                      (Random Forest with SMOTETomek balancing)
with Cross-Project Validation      (leave-one-out evaluation)
      │
      ▼
Calibrated Risk Score              (isotonic regression calibration)
+ Bug Type Prediction              (TF-IDF + Logistic Regression)
+ SHAP Explanation                 (global bar, beeswarm, per-file local plots)
      │
      ▼
CLI Output / Web Dashboard         (Flask + HTMX + Chart.js)
```

---

## 🔬 Feature Engineering

The model uses **26 features** selected by Recursive Feature Elimination (RFE), grouped into four categories:

### Static Code Metrics (6 features)
- `avg_complexity`, `max_complexity` — McCabe cyclomatic complexity
- `avg_params`, `max_function_length` — Function-level metrics
- `complexity_vs_baseline` — Language-normalized complexity
- `loc_per_function` — Code density

### Git Process Metrics (12 features)
- `commits`, `lines_added`, `lines_deleted` — Change volume
- `instability_score`, `avg_commit_size` — Change patterns
- `days_since_last_change`, `recency_ratio` — Temporal metrics
- `author_count` — Developer activity

### Temporal & Coupling Metrics (8 features)
- `max_coupling_strength`, `coupled_file_count` — Co-change patterns
- `commit_burst_score`, `recent_commit_burst` — Activity bursts
- `bug_recency_score`, `temporal_bug_memory` — Historical bug patterns
- `coupling_risk`, `recent_bug_flag` — Composite risk signals

**Note**: Features like `past_bugs` and `bug_fix_ratio` were explicitly removed to prevent data leakage.

---

## 🎓 Machine Learning Pipeline

### Labeling — Enhanced SZZ Algorithm

Bug labels are derived from Git history using an enhanced variant of the **SZZ algorithm** (Śliwerski, Zimmermann & Zeller, 2005):

1. **Bug-fixing commit detection** — Commit messages matched against bug-fix keywords with confidence scoring:
   - High confidence (1.0): `null pointer`, `crash`, `segfault`
   - Medium confidence (0.75): `fix`, `bug`, `resolve`
   - Low confidence (0.4): `minor`, `cleanup`, `tweak`

2. **Noise filters applied**:
   - Skip merge commits (`len(parents) > 1`)
   - Skip commits touching >15 files (tangled commits)
   - Skip deleted lines that are comments or blank (AG-SZZ style)

3. **Bug-introducing commit tracing** — `git blame` identifies which commit last touched each deleted line in a bug-fixing commit

4. **Confidence-weighted training** — Label confidence scores passed as `sample_weight` to the classifier

### Cross-Project Evaluation

The system uses **leave-one-project-out cross-validation**: the model is trained on all repositories except one, then tested on the held-out repository. This is repeated for all nine repositories.

**Why this matters**: No repository appears in both training and test sets, ensuring results reflect generalization to unseen codebases rather than memorization.

### Model Selection

| Model | Role |
|-------|------|
| **XGBoost** | Primary model; best composite score (PR-AUC + Recall@20%) |
| **Random Forest** | Alternative; competitive on most folds |
| **Logistic Regression** | Baseline; strongest on some folds |

Final model selected by **composite score**: `0.4 × PR-AUC + 0.4 × Recall@20% + 0.2 × F1`

### Probability Calibration

Raw model probabilities are calibrated using **isotonic regression**. Calibration quality verified:

- Predicted mean: 0.589
- Actual bug rate: 0.590
- Brier score: 0.096
- Calibration gap: <0.5%

### Risk Tier Assignment

Risk tiers assigned by **within-repository percentile rank**, not absolute probability thresholds. This makes predictions robust to variation in training base rate across different codebases.

| Percentile (within repo) | Risk Tier | Recommended Action |
|--------------------------|-----------|-------------------|
| Top 10% | **CRITICAL** | Immediate review required |
| 10–25% | **HIGH** | Prioritize for review |
| 25–50% | **MODERATE** | Consider for review |
| Bottom 50% | **LOW** | Low priority |

---

## 📚 Training Datasets

Trained on **9 open-source repositories** spanning **4 programming languages**:

| Repository | Language | Files | Buggy | Bug Rate | Domain |
|------------|----------|-------|-------|----------|--------|
| psf/requests | Python | 19 | 8 | 42.1% | HTTP client |
| pallets/flask | Python | 26 | 11 | 42.3% | Web framework |
| tiangolo/fastapi | Python | 73 | 34 | 46.6% | API framework |
| encode/httpx | Python | 10 | 4 | 40.0% | HTTP client |
| celery/celery | Python | 164 | 73 | 44.5% | Task queue |
| sqlalchemy/sqlalchemy | Python | 212 | 95 | 44.8% | ORM |
| expressjs/express | JavaScript | 9 | 4 | 44.4% | Web framework |
| axios/axios | JavaScript | 77 | 34 | 44.2% | HTTP client |
| google/guava | Java | 1,407 | 633 | 45.0% | Utility library |
| **Total** | **4 languages** | **1,997** | **896** | **44.9%** | |

### Cross-Language Generalization

The **Guava fold (Java)** is the most significant evaluation result. The model was trained exclusively on Python and JavaScript repositories with **zero Java examples**, yet achieved:

- F1 = 0.404
- PR-AUC = 0.697
- 1,407 Java files analyzed

This demonstrates that **process metrics** (commit frequency, author count, file instability, coupling) carry bug-predictive signal **independent of programming language**.

---

## 🔍 Explainability

Every prediction includes a **SHAP-based explanation** showing which features drove the risk rating.

### Global Explainability
- **Bar plot**: Mean absolute SHAP value per feature across all files
- **Beeswarm plot**: Distribution of SHAP values showing direction and magnitude

### Local Explainability
- **Per-file SHAP waterfall**: Additive feature contributions for top-N highest-risk files
- **Human-readable translation**: `bug_recency_score: +0.38 → "Strong bug history in this file"`

SHAP (SHapley Additive exPlanations) provides theoretically grounded attribution — the contribution of each feature is measured against a baseline and is additive.

---

## 🛠️ Tech Stack

| Layer | Tools |
|-------|-------|
| **Language** | Python 3.9+ |
| **Static Analysis** | Lizard (multi-language: Python, JS, TS, Java, Go, Ruby, PHP, C#, C++, Rust) |
| **Git Mining** | PyDriller, GitPython |
| **Machine Learning** | scikit-learn, XGBoost |
| **Imbalance Handling** | imbalanced-learn (SMOTE) |
| **NLP (Bug Type)** | scikit-learn TF-IDF + Logistic Regression |
| **Explainability** | SHAP (global bar, beeswarm, per-file local) |
| **Visualization** | Matplotlib |
| **Web Server** | Flask |
| **OAuth** | Authlib |
| **Rate Limiting** | Flask-Limiter |
| **Frontend** | Jinja2 + HTMX + Alpine.js + Chart.js |
| **Database** | SQLite |
| **Production Server** | Gunicorn |

---

## 📁 Project Structure

```
ai-bug-predictor/
│
├── backend/                     # Core ML & analysis modules
│   ├── analysis.py              # Lizard-based static analysis
│   ├── git_mining.py            # PyDriller commit history mining
│   ├── features.py              # Feature engineering (26 features)
│   ├── labeling.py              # Enhanced SZZ labeling
│   ├── train.py                 # Model training pipeline
│   ├── predict.py               # Risk prediction & tier assignment
│   ├── explainer.py             # SHAP explanations
│   ├── bug_classifier.py        # Bug type classification
│   └── config.py                # Configuration constants
│
├── frontend/                    # Web UI
│   ├── templates/               # Jinja2 HTML templates
│   └── assets/                  # CSS, JavaScript, images
│
├── ml/                          # Trained models & outputs
│   ├── models/                  # Serialized models (.pkl)
│   ├── plots/                   # SHAP visualizations
│   ├── cache/                   # Git mining cache
│   ├── benchmarks.json          # Performance benchmarks
│   └── training_log.jsonl       # Training history
│
├── dataset/                     # Training repositories
│   ├── requests/
│   ├── flask/
│   ├── fastapi/
│   ├── httpx/
│   ├── celery/
│   ├── sqlalchemy/
│   ├── express/
│   ├── axios/
│   └── guava/
│
├── main.py                      # Training pipeline (multi-repo)
├── bug_predictor.py             # CLI tool (single-repo)
├── app_ui.py                    # Flask web app
├── test_imports.py              # Dependency verification
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## 📖 Research Foundation

This project builds on established research in software defect prediction:

1. **Śliwerski, Zimmermann & Zeller (2005)** — *When Do Changes Induce Fixes?*  
   Introduced the SZZ algorithm for identifying bug-introducing commits via git blame tracing.

2. **Kim et al. (2006)** — *Automatic Identification of Bug-Introducing Changes*  
   Extended SZZ with annotation-graph filtering (AG-SZZ) to remove non-substantive line changes.

3. **Kamei et al. (2013)** — *A Large-Scale Empirical Study of Just-In-Time Quality Assurance*  
   Demonstrated the predictive power of change-level process metrics from version control history.

4. **Nagappan & Ball (2005)** — *Use of Relative Code Churn Measures to Predict System Defect Density*  
   Microsoft Research study demonstrating churn as a strong predictor of defect density.

5. **McCabe (1976)** — *A Complexity Measure*  
   Original definition of cyclomatic complexity.

6. **D'Ambros et al. (2012)** — *Evaluating Defect Prediction Approaches: A Benchmark and an Extensive Comparison*  
   Methodology reference for cross-project evaluation design and metric selection.

---

## 🗺️ Roadmap

### ✅ Completed
- [x] Multi-language support (Python, JavaScript, TypeScript, Java, Go)
- [x] Cross-project transfer learning (leave-one-out evaluation)
- [x] GitHub OAuth for on-demand repo scanning
- [x] Interactive web dashboard (Flask + HTMX)
- [x] SHAP beeswarm and global bar visualizations
- [x] Bug type classification (logic, crash, race condition, security, etc.)
- [x] Recall@Top20% as primary model selection metric

### 🚧 In Progress
- [ ] Commit-level risk check (pre-push hook integration)
- [ ] Pull request-level risk prediction via GitHub API
- [ ] Automated retraining trigger from user feedback (active learning)

### 🔮 Future
- [ ] CI/CD pipeline integration (GitHub Actions hook)
- [ ] Per-bin calibration verification (reliability diagrams)
- [ ] Expanded language support (Rust, Swift, Scala)
- [ ] Docker containerization
- [ ] Horizontal scaling (Celery + Redis + PostgreSQL)

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

---

## 👤 Author

**Archit Prakash Choudhary**  
B.Tech, Computer Science Engineering  
BIT Mesra

---

## 🙏 Acknowledgments

Trained on 9 open-source projects:
- **Python**: requests, flask, fastapi, httpx, celery, sqlalchemy
- **JavaScript**: axios, express
- **Java**: guava

Total: **1,654 files**, **126,382 commits** analyzed

---

**⭐ If you find this project useful, please consider giving it a star!**
