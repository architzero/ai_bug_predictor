# Frontend Deployment Guide

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your values

# 3. Train the model (first time only)
python main.py

# 4. Start the server
python wsgi.py
```

Visit http://localhost:5000

## Environment Variables

### Required

- `FLASK_SECRET_KEY`: Generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- `GITHUB_CLIENT_ID`: From GitHub OAuth app
- `GITHUB_CLIENT_SECRET`: From GitHub OAuth app

### Optional

- `GITHUB_TOKEN`: Personal access token for webhook PR comments
- `GITHUB_WEBHOOK_SECRET`: For webhook signature verification
- `FLASK_ENV`: Set to `production` for HTTPS-only cookies

## GitHub OAuth Setup

1. Go to https://github.com/settings/developers
2. Click "New OAuth App"
3. Fill in:
   - Application name: AI Bug Predictor
   - Homepage URL: http://localhost:5000
   - Authorization callback URL: http://localhost:5000/auth/github/callback
4. Copy Client ID and Client Secret to .env

## Production Deployment

### Using Gunicorn

```bash
gunicorn wsgi:app --workers 4 --timeout 120 --bind 0.0.0.0:5000
```

### Using Heroku

```bash
heroku create your-app-name
heroku config:set FLASK_SECRET_KEY=your_secret_key
heroku config:set GITHUB_CLIENT_ID=your_client_id
heroku config:set GITHUB_CLIENT_SECRET=your_client_secret
heroku config:set FLASK_ENV=production
git push heroku main
```

### Using Docker

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "wsgi:app", "--workers", "4", "--timeout", "120", "--bind", "0.0.0.0:5000"]
```

## Security Checklist

- [x] CSRF protection on all POST endpoints
- [x] Security headers (X-Frame-Options, X-Content-Type-Options, etc.)
- [x] Rate limiting on scan endpoint (5 per hour)
- [x] Input validation (path traversal, URL validation)
- [x] Session security (HttpOnly, SameSite cookies)
- [x] OAuth state parameter validation
- [x] No debug mode in production

## Troubleshooting

### Model not found

Run `python main.py` to train the model first.

### Import errors

Ensure all dependencies are installed: `pip install -r requirements.txt`

### OAuth callback fails

Check that the callback URL in GitHub matches exactly: `http://localhost:5000/auth/github/callback`

### Charts not rendering

Check browser console for JavaScript errors. Ensure Chart.js CDN is accessible.

## Architecture

```
Frontend (Jinja2 + HTMX + Alpine.js + Tailwind)
    ↓
Flask Routes (app_ui.py)
    ↓
Backend Logic (backend/*.py)
    ↓
ML Model (ml/models/bug_predictor_latest.pkl)
    ↓
Database (SQLite - bug_predictor.db)
```

## API Endpoints

### Public
- `GET /` - Landing page
- `GET /about` - About page
- `GET /health` - Health check

### Authenticated
- `GET /dashboard` - User repositories
- `GET /auth/github/login` - OAuth login
- `GET /auth/github/callback` - OAuth callback
- `GET /auth/logout` - Logout

### Scan
- `POST /api/scan_repo` - Start scan (rate limited)
- `GET /api/scan_progress/<scan_id>` - SSE progress stream
- `GET /scan/<scan_id>` - Progress page
- `GET /results/<scan_id>` - Results page

### Data
- `GET /api/recent_scans` - Recent scans table
- `GET /api/repos` - User GitHub repos
- `GET /api/files` - File list
- `GET /api/file?id=<path>` - File details

## Performance

- Caching enabled for expensive endpoints (5 min TTL)
- SHAP values pre-computed on scan
- Chart data injected server-side
- Client-side filtering (no re-fetch)

## Monitoring

Logs are written to:
- `bug_predictor.log` (rotating, 5MB max, 3 backups)
- Console output

Log levels:
- INFO: Normal operations
- WARNING: Recoverable errors
- ERROR: Unexpected failures
- CRITICAL: Fatal errors

## License

MIT
