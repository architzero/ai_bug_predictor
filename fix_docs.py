import re

with open("c:/Users/archi/project/ai-bug-predictor/detail.md", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Title
text = text.replace("AI-Based Bug Prediction System: Complete Technical Documentation\nA Predictive Defect Detection Using Static Analysis, Git History Mining, and Cross-Project Machine Learning", 
                    "# AI-Based Bug Prediction System: Complete Technical Documentation\n> A Predictive Defect Detection Using Static Analysis, Git History Mining, and Cross-Project Machine Learning")

# 2. Add Headers
def add_headers(match):
    prefix = match.group(1)
    if '.' in prefix:
        return f"## {match.group(0)}"
    else:
        return f"# {match.group(0)}"

# Match things like "1. Abstract", "2.1 Formal Definition", etc. that are at the beginning of a line.
# Specifically match 1-11 since 12+ already have headers.
text = re.sub(r'^((?:[1-9]|10|11)(?:\.\d+)?\.)\s+[A-Za-z].*$', add_headers, text, flags=re.MULTILINE)

# 3. Remove "Copy", "bash", "python" artifacts
text = re.sub(r'^Copy\s*\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^bash\s*\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^python\s*\n', '', text, flags=re.MULTILINE)

# 4. Fix 11.5 section
bad_section = """Issue: Model operates on structural and process metrics,

complete it?


Context
### 11.5 No Semantic Code Understanding"""

good_section = """Issue: Model operates on structural and process metrics, not semantic code analysis."""

text = text.replace(bad_section, good_section)

# 5. Fix 9. Project Structure
old_structure = """├── backend/                     # Core ML & analysis modules
│   ├── analysis.py              # Lizard-based static analysis
│   ├── git_mining.py            # PyDriller commit history mining
│   ├── features.py              # Feature engineering (26 features)
│   ├── labeling.py              # Enhanced SZZ labeling
│   ├── train.py                 # Training pipeline with LOPOCV
│   ├── predict.py               # Risk prediction & tier assignment
│   ├── explainer.py             # SHAP explanations
│   ├── bug_classifier.py        # Bug type classification
│   └── config.py                # Configuration constants"""

new_structure = """├── backend/                     # Core ML & analysis modules
│   ├── analysis.py              # Lizard-based static analysis
│   ├── git_mining.py            # PyDriller commit history mining
│   ├── features.py              # Feature engineering
│   ├── feature_constants.py     # Centralized feature column definitions
│   ├── labeling.py              # Bug-introducing commit detection
│   ├── szz.py                   # Advanced SZZ algorithm implementation
│   ├── train.py                 # Training pipeline with LOPOCV
│   ├── predict.py               # Risk prediction & tier assignment
│   ├── explainer.py             # SHAP explanations
│   ├── bug_classifier.py        # Bug type classification
│   ├── bug_integrator.py        # Unified defect severity integration
│   ├── commit_risk.py           # Pre-commit risk evaluation
│   ├── visualizations.py        # Chart generation for dashboard
│   ├── database.py              # SQLite storage for scan persistence
│   └── config.py                # Configuration constants"""

text = text.replace(old_structure, new_structure)

# 6. Fix 8. Implementation Stack
old_stack = """Component	Technology	Purpose
Static Analysis	Lizard 1.17+	Multi-language complexity analysis
Git Mining	PyDriller 2.5+	Commit history traversal
ML Framework	scikit-learn 1.3+	Random Forest, calibration, metrics
Gradient Boosting	XGBoost 2.0+	Alternative classifier
Imbalance Handling	imbalanced-learn 0.11+	SMOTE, Tomek links
Explainability	SHAP 0.43+	Feature attribution
NLP (Bug Type)	scikit-learn TF-IDF	Text classification
Visualization	Matplotlib 3.7+	SHAP plots, calibration curves
Web Framework	Flask 3.0+	Dashboard backend
Frontend	HTMX + Alpine.js	Interactive UI
Database	SQLite	Analysis cache
Production Server	Gunicorn	WSGI server"""

new_stack = """| Component | Technology | Purpose |
|---|---|---|
| **Static Analysis** | Lizard 1.17+ | Multi-language complexity analysis |
| **Git Mining** | PyDriller 2.5+ | Commit history traversal |
| **ML Framework** | scikit-learn 1.3+ | Random Forest, calibration, metrics |
| **Gradient Boosting** | XGBoost 2.0+ | Alternative classifier |
| **Imbalance Handling** | imbalanced-learn 0.11+ | SMOTE, Tomek links |
| **Explainability** | SHAP 0.43+ | Feature attribution |
| **NLP (Bug Type)** | scikit-learn TF-IDF | Text classification |
| **Visualization** | Matplotlib 3.7+ | SHAP plots, calibration curves |
| **Web Framework** | Flask 3.0+ | Dashboard backend |
| **Frontend** | HTMX + Alpine.js | Interactive UI |
| **Auth** | GitHub OAuth | User authentication & repo access |
| **Caching/State** | Flask-Caching | Fast API serving |
| **Database** | SQLite | Scan persistence & rate limiting |
| **Production Server** | Gunicorn | WSGI server |"""

text = text.replace(old_stack, new_stack)

# Replace tabbed tables with markdown tables
text = text.replace("Pattern\tConfidence\tExamples\nHigh (1.0)\tCritical bugs\tnull pointer, crash, segfault, memory leak\nMedium (0.75)\tStandard fixes\tfix, bug, resolve, patch\nLow (0.4)\tMinor fixes\tminor, cleanup, tweak",
                    "| Pattern | Confidence | Examples |\n|---|---|---|\n| High (1.0) | Critical bugs | null pointer, crash, segfault, memory leak |\n| Medium (0.75) | Standard fixes | fix, bug, resolve, patch |\n| Low (0.4) | Minor fixes | minor, cleanup, tweak |")

text = text.replace("Percentile (within repo)\tTier\tAction\nTop 10%\tCRITICAL\tImmediate review required\n10-25%\tHIGH\tPrioritize for review\n25-50%\tMODERATE\tConsider for review\nBottom 50%\tLOW\tLow priority",
                    "| Percentile (within repo) | Tier | Action |\n|---|---|---|\n| Top 10% | CRITICAL | Immediate review required |\n| 10-25% | HIGH | Prioritize for review |\n| 25-50% | MODERATE | Consider for review |\n| Bottom 50% | LOW | Low priority |")

text = text.replace("Repository\tLanguage\tFiles\tF1\tPR-AUC\tROC-AUC\nguava\tJava\t1,031\t0.742\t0.801\t0.885\nsqlalchemy\tPython\t236\t0.891\t0.952\t0.948\ncelery\tPython\t214\t0.863\t0.928\t0.931\naxios\tJavaScript\t70\t0.812\t0.887\t0.902\nfastapi\tPython\t47\t0.879\t0.941\t0.936\nflask\tPython\t23\t0.901\t0.968\t0.957\nrequests\tPython\t17\t0.785\t0.856\t0.891\nhttpx\tPython\t9\t0.722\t0.813\t0.867\nexpress\tJavaScript\t7\t0.698\t0.789\t0.843",
                    "| Repository | Language | Files | F1 | PR-AUC | ROC-AUC |\n|---|---|---|---|---|---|\n| guava | Java | 1,031 | 0.742 | 0.801 | 0.885 |\n| sqlalchemy | Python | 236 | 0.891 | 0.952 | 0.948 |\n| celery | Python | 214 | 0.863 | 0.928 | 0.931 |\n| axios | JavaScript | 70 | 0.812 | 0.887 | 0.902 |\n| fastapi | Python | 47 | 0.879 | 0.941 | 0.936 |\n| flask | Python | 23 | 0.901 | 0.968 | 0.957 |\n| requests | Python | 17 | 0.785 | 0.856 | 0.891 |\n| httpx | Python | 9 | 0.722 | 0.813 | 0.867 |\n| express | JavaScript | 7 | 0.698 | 0.789 | 0.843 |")

text = text.replace("Feature Set\tPR-AUC\tΔ from Full\nFull (26 features)\t0.940\t—\nProcess only (12)\t0.891\t-0.049\nStatic only (6)\t0.742\t-0.198\nTemporal only (8)\t0.823\t-0.117\nStatic + Process\t0.928\t-0.012\nProcess + Temporal\t0.935\t-0.005",
                    "| Feature Set | PR-AUC | Δ from Full |\n|---|---|---|\n| Full (26 features) | 0.940 | — |\n| Process only (12) | 0.891 | -0.049 |\n| Static only (6) | 0.742 | -0.198 |\n| Temporal only (8) | 0.823 | -0.117 |\n| Static + Process | 0.928 | -0.012 |\n| Process + Temporal | 0.935 | -0.005 |")

text = text.replace("Repository\tLanguage\tFiles\tBuggy\tBug Rate\tCommits\tDomain\npsf/requests\tPython\t17\t4\t23.5%\t3,847\tHTTP client\npallets/flask\tPython\t23\t20\t87.0%\t5,291\tWeb framework\ntiangolo/fastapi\tPython\t47\t23\t48.9%\t4,102\tAPI framework\nencode/httpx\tPython\t9\t6\t66.7%\t2,156\tHTTP client\ncelery/celery\tPython\t214\t127\t59.3%\t18,743\tTask queue\nsqlalchemy/sqlalchemy\tPython\t236\t171\t72.5%\t21,089\tORM\nexpressjs/express\tJavaScript\t7\t6\t85.7%\t6,234\tWeb framework\naxios/axios\tJavaScript\t70\t48\t68.6%\t3,918\tHTTP client\ngoogle/guava\tJava\t1,031\t411\t39.8%\t61,002\tUtility library\nTotal\t4 languages\t1,654\t816\t49.3%\t126,382",
                    "| Repository | Language | Files | Buggy | Bug Rate | Commits | Domain |\n|---|---|---|---|---|---|---|\n| psf/requests | Python | 17 | 4 | 23.5% | 3,847 | HTTP client |\n| pallets/flask | Python | 23 | 20 | 87.0% | 5,291 | Web framework |\n| tiangolo/fastapi | Python | 47 | 23 | 48.9% | 4,102 | API framework |\n| encode/httpx | Python | 9 | 6 | 66.7% | 2,156 | HTTP client |\n| celery/celery | Python | 214 | 127 | 59.3% | 18,743 | Task queue |\n| sqlalchemy/sqlalchemy | Python | 236 | 171 | 72.5% | 21,089 | ORM |\n| expressjs/express | JavaScript | 7 | 6 | 85.7% | 6,234 | Web framework |\n| axios/axios | JavaScript | 70 | 48 | 68.6% | 3,918 | HTTP client |\n| google/guava | Java | 1,031 | 411 | 39.8% | 61,002 | Utility library |\n| **Total** | **4 languages** | **1,654** | **816** | **49.3%** | **126,382** | |")

# Make sure usage commands are in bash blocks
text = re.sub(r'(# Clone repository.*?\npython test_imports\.py\n)', r'```bash\n\1```\n', text, flags=re.DOTALL)
text = re.sub(r'(# Analyze local repository.*?\npython bug_predictor\.py https://github\.com/psf/requests\n)', r'```bash\n\1```\n', text, flags=re.DOTALL)
text = re.sub(r'(# Train on all datasets in dataset/ folder.*?\n# Output: ml/models/bug_predictor_latest\.pkl\n)', r'```bash\n\1```\n', text, flags=re.DOTALL)
text = re.sub(r'(# Configure environment.*?\n# Visit http://localhost:5000\n)', r'```bash\n\1```\n', text, flags=re.DOTALL)

with open("c:/Users/archi/project/ai-bug-predictor/detail.md", "w", encoding="utf-8") as f:
    f.write(text)

print("detail.md fixed successfully!")
