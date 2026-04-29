# GitSentinel — AI-Powered Bug Risk Prediction

Predicts which files in a Git repository are most likely to contain bugs using ML + SHAP explainability.

## ✅ Project Structure

```
ai-bug-predictor/
├── backend/           # Core ML & analysis modules
├── frontend/          # Web UI (templates + assets)
├── ml/                # Trained models + SHAP plots
├── dataset/           # Training repositories
├── main.py            # Training pipeline
├── bug_predictor.py   # CLI tool
├── app_ui.py          # Flask web app
└── DOCUMENTATION.md   # Complete technical docs
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Verify Setup
```bash
python test_imports.py
```

### 3. Analyze a Repository (CLI)
```bash
python bug_predictor.py dataset/requests
```

### 4. Run Web UI (Optional)
```bash
python app_ui.py
```
Visit http://localhost:5000

## 📊 Example Output

```
  #1. adapters.py
      Risk: 89.6% | Tier: CRITICAL | LOC: 379
      Why risky: · Modified 4.7× more than repo median (14 commits)
                 · Strong bug memory (1.013), increases defect risk
                 · Contains very long functions (107 lines)
```

## 🎯 Features

- **ML Models**: Random Forest with isotonic calibration
- **SZZ Algorithm**: Line-level git blame for bug labeling
- **SHAP Explanations**: Human-readable risk explanations
- **Per-Repo Ranking**: Tiers assigned within each repository
- **Bug Classification**: 6 bug types (performance, security, etc.)
- **Web Dashboard**: GitHub OAuth, real-time scanning, PR analysis

## 📈 Performance

- **PR-AUC**: 0.940 (elite ranking quality)
- **ROC-AUC**: 0.932 (strong discrimination)
- **F1 Score**: 0.855 (honest benchmark)
- **Recall@20%**: 34% of bugs in top 20% of files

## 📚 Documentation

See [DOCUMENTATION.md](DOCUMENTATION.md) for:
- Complete technical details
- API reference
- Training guide
- Troubleshooting
- Security & scalability

## 🔒 Security

- CSRF protection on all POST endpoints
- Rate limiting (5 scans/hour, 200 requests/hour)
- OAuth 2.0 GitHub authentication
- Input validation & path traversal prevention

