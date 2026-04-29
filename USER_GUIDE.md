# 🎯 GitSentinel - User Guide

## Quick Start (3 Steps)

### 1️⃣ Install
```bash
pip install -r requirements.txt
```

### 2️⃣ Scan Your Repository
```bash
# Scan local repository
python bug_predictor.py /path/to/your/repo

# Scan GitHub repository
python bug_predictor.py https://github.com/username/repo
```

### 3️⃣ View Results
```
✓ Analysis complete!

TOP 15 RISK FILES
═══════════════════════════════════════════════════════════════════
Risk   LOC    Complexity   File
───────────────────────────────────────────────────────────────────
95%    450    12.5         api/authentication.py
87%    320    8.3          core/database.py
76%    210    6.7          utils/parser.py
...
```

---

## 🌐 Web Interface (Alternative)

### Start Web Server
```bash
python app_ui.py
```

### Open Browser
```
http://localhost:5000
```

### Features
- 📊 Interactive dashboard
- 🔍 Real-time scanning
- 📈 Risk visualizations
- 🎯 PR analysis
- 💾 Scan history

---

## 📊 Understanding Results

### Risk Levels

| Risk Score | Level | Action |
|------------|-------|--------|
| 80-100% | 🔴 CRITICAL | Immediate review required |
| 60-79% | 🟠 HIGH | Prioritize for review |
| 40-59% | 🟡 MODERATE | Consider for review |
| 20-39% | 🟢 LOW | Monitor if changes planned |
| 0-19% | ⚪ MINIMAL | Low priority |

### What the Model Predicts

The model predicts **which files are most likely to contain bugs** based on:
- **Code complexity** - Cyclomatic complexity, function length
- **Git history** - Commit frequency, author count, churn
- **Temporal patterns** - Recent changes, bug recency
- **Coupling** - File dependencies and co-changes

---

## 🎯 Common Use Cases

### 1. Pre-Commit Review
```bash
# Scan before committing
python bug_predictor.py .

# Focus on high-risk files
# Review top 10 files shown in output
```

### 2. PR Risk Assessment
```bash
# Start web UI
python app_ui.py

# Navigate to PR Analysis
# Paste PR URL
# Get risk score and recommendations
```

### 3. Codebase Health Check
```bash
# Scan entire repository
python bug_predictor.py /path/to/repo

# Review summary statistics:
# - Total files analyzed
# - High-risk files count
# - Average risk score
```

### 4. Continuous Monitoring
```bash
# Setup GitHub webhook
# Automatic PR analysis on every PR
# Risk comments posted automatically
```

---

## 🔧 Configuration

### Environment Variables

Create `.env` file:
```bash
# Required for Web UI
FLASK_SECRET_KEY=your-secret-key-here

# Required for GitHub OAuth
GITHUB_CLIENT_ID=your-client-id
GITHUB_CLIENT_SECRET=your-client-secret

# Optional for webhooks
GITHUB_WEBHOOK_SECRET=your-webhook-secret
GITHUB_TOKEN=your-personal-access-token
```

### Generate Secret Key
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 📈 Interpreting Metrics

### Model Performance
- **F1 Score: 0.74** - Good balance of precision and recall
- **PR-AUC: 0.84** - Strong ranking ability
- **Defects@20%: 70-90%** - Catches most bugs in top 20% of files

### Confidence Levels
- **HIGH** - Predictions are reliable
- **MEDIUM** - Predictions may be less reliable
- **LOW** - Predictions may be unreliable (e.g., unsupported language)

### Warnings
- **Unsupported language** - Model trained primarily on Python
- **Limited git history** - Fewer than 10 commits
- **Very small repository** - Less than 10 files
- **Extreme complexity** - Many files with complexity > 30

---

## 🚨 Troubleshooting

### Error: "No trained model found"
**Solution:** The model file is missing. Contact the administrator to get the pre-trained model.

### Error: "No source files found"
**Solution:** Repository contains no supported source files. Supported languages:
- Python (.py)
- JavaScript (.js)
- TypeScript (.ts)
- Java (.java)
- Go (.go)
- Ruby (.rb)
- PHP (.php)
- C# (.cs)
- C++ (.cpp)
- C (.c)
- Rust (.rs)

### Error: "Failed to clone repository"
**Solution:** 
- Check repository URL is correct
- For private repos, authenticate with GitHub OAuth (Web UI)
- Ensure git is installed: `git --version`

### Slow Scanning
**Solution:**
- Large repositories (>1000 files) take longer
- Deep git history (>500 commits) increases scan time
- Expected: ~30 seconds for 100-file repo

### Low Confidence Score
**Solution:**
- Model trained primarily on Python - other languages may have lower accuracy
- Limited git history reduces prediction quality
- Very small repos (<10 files) are harder to assess

---

## 🎓 Best Practices

### 1. Focus on Top 10-20 Files
Don't try to fix everything at once. Focus on the highest-risk files first.

### 2. Combine with Code Review
Use predictions as a guide, not a replacement for human review.

### 3. Track Trends Over Time
Monitor how risk scores change as you fix bugs and refactor code.

### 4. Prioritize by Effort
Use the effort-aware recommendations to maximize impact:
```bash
# Web UI: /api/effort_recommendations?top_n=10
```

### 5. Review Before Major Releases
Scan before releases to catch high-risk files early.

---

## 📊 Example Output Explained

```
═══════════════════════════════════════════════════════════════════
ANALYSIS SUMMARY
═══════════════════════════════════════════════════════════════════
Repository: my-project
Files analyzed: 150
Buggy files (labeled): 12
High-risk files (>0.7): 8
Medium-risk files (0.4-0.7): 25
Low-risk files (<0.4): 117
Average risk: 0.342
Prediction confidence: HIGH
```

**What this means:**
- **150 files** were analyzed
- **12 files** have historical bug labels (from git history)
- **8 files** are predicted to be high-risk (>70% probability)
- **25 files** are medium-risk (40-70% probability)
- **117 files** are low-risk (<40% probability)
- **Average risk 0.342** means overall codebase is relatively healthy
- **HIGH confidence** means predictions are reliable

---

## 🔍 Feature Importance

The model considers these factors (in order of importance):

1. **Temporal Bug Memory** - Files with recent bugs are more likely to have bugs again
2. **Code Complexity** - Higher complexity = higher risk
3. **Recent Activity** - Files changed frequently in last 3 months
4. **Coupling Risk** - Files that change together with buggy files
5. **Lines of Code** - Larger files have more bug surface area
6. **Author Count** - More authors = more coordination issues
7. **Commit Frequency** - Very high or very low is risky
8. **Max Complexity** - Highest complexity function in file
9. **Ownership** - Low ownership (many small contributors) is risky
10. **File Age** - Very old or very new files are risky

---

## 🎯 Advanced Features

### 1. Commit Risk Prediction
```bash
# Web UI: /api/predict_commit
# POST: {"files": ["file1.py", "file2.py"]}
# Returns: Overall commit risk score
```

### 2. PR Risk Analysis
```bash
# Web UI: /api/analyze_pr
# POST: {"pr_url": "https://github.com/user/repo/pull/123"}
# Returns: Detailed PR risk assessment
```

### 3. Effort-Aware Recommendations
```bash
# Web UI: /api/effort_recommendations?top_n=10
# Returns: Files prioritized by risk/effort ratio
```

### 4. SHAP Explanations
```bash
# CLI automatically generates SHAP plots
# Web UI shows per-file explanations
# Explains WHY each file is risky
```

---

## 📞 Support

### Getting Help
1. Check this guide first
2. Review error messages carefully
3. Check logs: `bug_predictor.log`
4. Contact administrator

### Reporting Issues
Include:
- Error message
- Command used
- Repository size and language
- Python version: `python --version`
- Log file: `bug_predictor.log`

---

## 🎉 Tips for Success

### ✅ DO
- Focus on high-risk files first
- Review top 10-20 files regularly
- Use predictions as a guide
- Track trends over time
- Combine with code review

### ❌ DON'T
- Try to fix everything at once
- Ignore low-confidence warnings
- Skip code review for "low-risk" files
- Rely solely on predictions
- Ignore context and domain knowledge

---

## 📚 Additional Resources

### Documentation
- `README.md` - Project overview
- `DEPLOYMENT_GUIDE.md` - Technical details
- `VERIFICATION_CHECKLIST.md` - Implementation verification

### Web UI Endpoints
- `/` - Dashboard
- `/api/overview` - Metrics summary
- `/api/files` - File list with risks
- `/api/scan_repo` - Scan new repository
- `/api/analyze_pr` - PR risk analysis

---

**Version:** 1.0  
**Last Updated:** 2025-01-XX  
**Status:** Production Ready

**Happy Bug Hunting! 🐛🔍**
