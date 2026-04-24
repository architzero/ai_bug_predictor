# GitSentinel — Explainable Bug Risk Prediction

Predicts which files in a Git repository are most likely to contain bugs, and explains why — before bugs reach production.

Analyzes static code complexity and full Git commit history to produce a ranked risk score per file, backed by SHAP explainability.

---

## What It Does

- Mines Git history using PyDriller (commits, churn, authors, ownership)
- Analyzes code complexity using Lizard (cyclomatic complexity, LOC, function count)
- Labels bug-introducing commits using the SZZ algorithm (line-level git blame)
- Trains LR → Random Forest → XGBoost with cross-project validation
- Explains predictions with SHAP (global feature importance + per-file waterfall plots)

## What It Does NOT Do

- Detect logical bugs or fix code
- Replace code review
- Work on repos with no commit history

---

## Project Structure

```
ai-bug-predictor/
├── bug_type_classification/  # Bug type classifier
├── explainability/           # SHAP plots
├── feature_engineering/      # Feature builder + labeler
├── git_mining/              # PyDriller + SZZ
├── model/                   # Training + prediction
├── static/                  # CSS + JS
├── static_analysis/         # Lizard analyzer
├── templates/               # HTML templates
├── tests/                   # Unit tests
├── dataset/                 # Clone repos here (gitignored)
├── app_ui.py               # Flask web UI
├── bug_predictor.py        # CLI tool
├── config.py               # Configuration
├── database.py             # SQLAlchemy models
└── main.py                 # Full pipeline
```

---

## Setup

**1. Clone the project**
```bash
git clone https://github.com/<your-username>/ai-bug-predictor.git
cd ai-bug-predictor
```

**2. Create virtual environment**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables (REQUIRED for web UI)**
```bash
cp .env.example .env
```

Edit `.env` and set:
- **FLASK_SECRET_KEY**: Generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- **GITHUB_CLIENT_ID** & **GITHUB_CLIENT_SECRET**: Create OAuth app at https://github.com/settings/developers
  - Authorization callback URL: `http://localhost:5000/auth/github/callback`

See [SECURITY.md](SECURITY.md) for detailed security setup instructions.

**5. Clone dataset repos** (into `dataset/` folder)
```bash
git clone https://github.com/psf/requests      dataset/requests
git clone https://github.com/pallets/flask     dataset/flask
git clone https://github.com/tiangolo/fastapi  dataset/fastapi
```

---

## Run

**Full pipeline (train + predict + explain):**
```bash
python main.py
```

**Single repo CLI tool:**
```bash
python bug_predictor.py dataset/requests
```

**Web UI Dashboard:**
```bash
python app_ui.py
# Visit http://localhost:5000
```

⚠️ **Security Note**: Web UI requires environment variables to be set. See [SECURITY.md](SECURITY.md).

---

## Output

```
Top Risk Files:

requests/auth.py          risk=0.91  (instability_score, complexity_density, recent_churn_ratio)
requests/adapters.py      risk=0.87  (avg_commit_size, minor_contributor_ratio, ownership)
requests/models.py        risk=0.82  (complexity_per_function, commits_1m, recency_ratio)
```

SHAP plots saved to `explainability/plots/`:
- `global_bar.png` — top features across all predictions
- `global_beeswarm.png` — feature direction and distribution
- `local_waterfall_<file>.png` — per-file explanation
- `local_force_<file>.png` — force plot for demos

---

## ML Pipeline

| Step | Detail |
|------|--------|
| Labeling | SZZ algorithm — line-level git blame on bug-fix commits |
| Validation | Cross-project leave-one-out (train on 2 repos, test on 3rd) |
| Imbalance | SMOTE applied per fold on training data only |
| Models | Logistic Regression → Random Forest → XGBoost |
| Tuning | RandomizedSearchCV with TimeSeriesSplit (F1 scoring) |
| Metrics | F1, Precision, Recall, ROC-AUC, PR-AUC, Confusion Matrix |

---

## Key Features Used

| Category | Features |
|----------|----------|
| Static | `avg_complexity`, `complexity_density`, `loc_per_function` |
| Git history | `commits`, `churn`, `max_added`, `author_count` |
| Time-window | `commits_2w`, `commits_1m`, `recent_churn_ratio` |
| Developer | `ownership`, `minor_contributor_ratio`, `low_history_flag` |
| Stability | `instability_score`, `avg_commit_size`, `max_commit_ratio` |
| File age | `file_age_bucket`, `days_since_last_change`, `recency_ratio` |

---

## Run Tests

```bash
pytest tests/
```

---

## Requirements

See `requirements.txt`. Key dependencies:
- `pydriller` — Git history mining
- `lizard` — Static code analysis
- `scikit-learn` — ML models
- `xgboost` — Gradient boosting
- `imbalanced-learn` — SMOTE
- `shap` — Explainability
- `sqlalchemy` — Database ORM
- `flask-caching` — Response caching
- `flask-login` — Authentication

---

## Database & Performance

**Database**: All scans persist to SQLite database (`bug_predictor.db`)
- 90% memory reduction (500MB → 50MB)
- Data survives restarts
- Connection pooling for concurrent requests

**Caching**: Flask-Caching for 10-100x faster API responses
- Cached responses: ~50ms
- Automatic cache invalidation after scans

See [CHANGELOG.md](CHANGELOG.md) for detailed improvements.
