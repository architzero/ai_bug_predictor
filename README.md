# GitSentinel — AI-Powered Bug Risk Prediction

Predicts which files in a Git repository are most likely to contain bugs using ML + SHAP explainability.

## ✅ Project Structure (Clean & Simple)

```
ai-bug-predictor/
├── backend/           # All Python modules (analysis, ML, features, etc.)
├── frontend/          # Web UI (templates + assets)
├── ml/                # Trained models + SHAP plots
├── dataset/           # Training repositories
├── main.py            # Training pipeline
├── bug_predictor.py   # CLI tool
├── app_ui.py          # Flask web app
└── test_imports.py    # Import verification script
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Clone Training Datasets
```bash
git clone https://github.com/psf/requests dataset/requests
git clone https://github.com/pallets/flask dataset/flask
```

### 3. Verify Setup
```bash
python test_imports.py
```

### 4. Train Model
```bash
python main.py
```

### 5. Run Web UI
```bash
python app_ui.py
```
Visit http://localhost:5000 (Press Ctrl+C to stop)

## 📊 CLI Usage

Analyze a single repository:
```bash
python bug_predictor.py dataset/requests
```

## 🎯 Features

- **ML Models**: LR → Random Forest → XGBoost with cross-project validation
- **SZZ Algorithm**: Line-level git blame for bug labeling
- **SHAP Explanations**: Global + local feature importance
- **Web Dashboard**: GitHub OAuth, real-time scanning, PR analysis
- **Bug Classification**: Categorizes bugs by type (logic, performance, security, etc.)

## 📈 Performance

Average F1: 0.74 | Average PR-AUC: 0.84 (cross-project validation)

## 🔒 Security

- CSRF protection on all POST endpoints
- Rate limiting (5 scans/hour, 200 requests/hour)
- OAuth 2.0 GitHub authentication
- Input validation & path traversal prevention

## 📝 License

MIT License
