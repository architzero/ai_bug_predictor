# Quick Reference Guide

## 🚀 Getting Started

```bash
# First time setup
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GitHub OAuth credentials
python main.py  # Train model (optional, ~10 min)
python start.py # Start server
```

## 🔑 Environment Variables

Generate secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Get GitHub OAuth credentials:
1. Visit https://github.com/settings/developers
2. Create new OAuth app
3. Callback URL: `http://localhost:5000/auth/github/callback`

## 📝 Common Commands

```bash
# Start development server
python wsgi.py

# Start with checks
python start.py

# Run tests
python test_frontend.py

# Train model
python main.py

# Analyze single repo
python bug_predictor.py dataset/flask
```

## 🌐 URLs

- Landing: http://localhost:5000/
- About: http://localhost:5000/about
- Dashboard: http://localhost:5000/dashboard (requires login)
- Health: http://localhost:5000/health

## 🎨 Frontend Structure

```
frontend/
├── templates/
│   ├── base.html          # Base layout
│   ├── index.html         # Landing page
│   ├── scan.html          # Progress page
│   ├── results.html       # Results page
│   ├── dashboard.html     # GitHub repos
│   ├── about.html         # Methodology
│   ├── 404.html           # Not found
│   └── 500.html           # Server error
└── assets/
    ├── js/
    │   └── app.js         # Charts & helpers
    └── css/
        └── main.css       # Custom styles
```

## 🔧 Troubleshooting

### Server won't start
```bash
# Check imports
python test_imports.py

# Check environment
python start.py
```

### Model not found
```bash
# Train model
python main.py
```

### OAuth fails
- Check callback URL matches exactly
- Verify CLIENT_ID and CLIENT_SECRET in .env
- Check GitHub app is not suspended

### Charts not rendering
- Open browser console (F12)
- Check for JavaScript errors
- Verify Chart.js CDN is accessible

### CSRF errors
- Clear browser cookies
- Restart server
- Check FLASK_SECRET_KEY is set

## 📊 API Endpoints

### Public
```
GET  /                      Landing page
GET  /about                 About page
GET  /health                Health check
```

### Auth
```
GET  /auth/github/login     Start OAuth
GET  /auth/github/callback  OAuth callback
GET  /auth/logout           Logout
```

### Scan
```
POST /api/scan_repo         Start scan (rate limited)
GET  /api/scan_progress/:id SSE progress stream
GET  /scan/:id              Progress page
GET  /results/:id           Results page
```

### Data
```
GET  /api/recent_scans      Recent scans table
GET  /api/repos             User GitHub repos
GET  /api/files             File list
GET  /api/file?id=:path     File details
```

## 🎯 Risk Tiers

- **CRITICAL** (≥80%): Top 10% of files, immediate review
- **HIGH** (60-79%): 10-25%, prioritize for review
- **MODERATE** (40-59%): 25-50%, consider for review
- **LOW** (<40%): Bottom 50%, low priority

## 🔒 Security

- CSRF protection on all POST endpoints
- Rate limiting: 5 scans per hour
- Input validation: path traversal, URL validation
- Session security: HttpOnly, SameSite cookies
- Security headers: X-Frame-Options, X-Content-Type-Options

## 📈 Performance

- Caching: 5 min TTL on expensive endpoints
- SHAP: Pre-computed on scan
- Charts: Server-side data injection
- Filtering: Client-side (no re-fetch)

## 🐛 Known Issues

1. Results page needs actual scan data integration
2. Dashboard needs GitHub API integration
3. File detail panel needs real SHAP data

## 📚 Documentation

- `README.md` - Project overview
- `FRONTEND_DEPLOYMENT.md` - Deployment guide
- `FRONTEND_IMPLEMENTATION.md` - Implementation details
- `prompt_frontend.md` - Original requirements

## 💡 Tips

- Use `python start.py` for guided startup
- Run `python test_frontend.py` to verify setup
- Check `bug_predictor.log` for errors
- Use browser DevTools to debug frontend issues
- Clear cache if seeing stale data

## 🎓 Learning Resources

- HTMX: https://htmx.org/docs/
- Alpine.js: https://alpinejs.dev/start-here
- Chart.js: https://www.chartjs.org/docs/
- Tailwind: https://tailwindcss.com/docs
- Flask: https://flask.palletsprojects.com/

## 📞 Support

For issues:
1. Check logs: `bug_predictor.log`
2. Run tests: `python test_frontend.py`
3. Verify environment: `python start.py`
4. Check browser console (F12)

## 🎉 Quick Win

```bash
# Fastest way to see it working
python start.py
# Visit http://localhost:5000
# Enter: https://github.com/psf/requests
# Click Analyze
```
