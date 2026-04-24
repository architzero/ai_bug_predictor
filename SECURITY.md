# Security Configuration Guide

## Critical Security Fixes Applied

### 1. Secret Key Management ✅
**FIXED**: Removed hardcoded fallback secret key that was publicly visible in repository.

**Before**:
```python
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_fallback_secret_key_change_in_prod")
```

**After**:
```python
secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable must be set")
app.secret_key = secret_key
```

**Action Required**: Generate and set FLASK_SECRET_KEY before running the application.

---

### 2. OAuth Credentials ✅
**FIXED**: Removed dummy OAuth credentials that allowed application to start without proper authentication.

**Before**:
```python
client_id=os.environ.get("GITHUB_CLIENT_ID", "DUMMY_CLIENT_ID")
```

**After**:
```python
github_client_id = os.environ.get("GITHUB_CLIENT_ID")
if not github_client_id or not github_client_secret:
    raise RuntimeError("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set")
```

**Action Required**: Create GitHub OAuth app and set credentials.

---

### 3. Token Exposure Prevention ✅
**FIXED**: Git clone errors no longer expose GitHub access tokens in error messages.

**Before**:
```python
err_msg = e.stderr.decode('utf-8', errors='ignore')
err_msg = err_msg.replace(session["github_token"], "*****")  # Insufficient
```

**After**:
```python
# Generic error message, no token exposure possible
err_msg = "Git clone failed. Check repository URL and permissions."
```

---

### 4. CSRF Protection ✅
**ADDED**: Cross-Site Request Forgery protection on all POST endpoints.

```python
@csrf_protect
def api_scan_repo():
    # Protected endpoint
```

**Frontend Integration Required**: Include CSRF token in POST requests:
```javascript
headers: {
    'X-CSRF-Token': '{{ auth.csrf_token }}'
}
```

---

### 5. Rate Limiting ✅
**ADDED**: Prevents DoS attacks by limiting request rates.

- Global: 200 requests per hour per IP
- `/api/scan_repo`: 5 requests per hour (expensive operation)
- `/api/analyze_pr`: 20 requests per hour
- `/api/predict_commit`: 30 requests per minute

---

## Setup Instructions

### 1. Generate Secret Key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and add to `.env` file.

### 2. Create GitHub OAuth App

1. Go to: https://github.com/settings/developers
2. Click "New OAuth App"
3. Fill in:
   - **Application name**: GitSentinel Bug Predictor
   - **Homepage URL**: http://localhost:5000
   - **Authorization callback URL**: http://localhost:5000/auth/github/callback
4. Click "Register application"
5. Copy **Client ID** and generate **Client Secret**

### 3. Create .env File

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
FLASK_SECRET_KEY=<your_generated_secret_key>
GITHUB_CLIENT_ID=<your_github_client_id>
GITHUB_CLIENT_SECRET=<your_github_client_secret>
FLASK_ENV=development
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run Application

```bash
python app_ui.py
```

---

## Production Deployment Checklist

- [ ] Set `FLASK_ENV=production` in environment variables
- [ ] Use HTTPS (required for secure cookies)
- [ ] Set strong FLASK_SECRET_KEY (64+ characters)
- [ ] Rotate OAuth credentials regularly
- [ ] Enable firewall rules
- [ ] Use reverse proxy (nginx/Apache) with rate limiting
- [ ] Monitor rate limit violations
- [ ] Set up logging for security events
- [ ] Never commit `.env` file to repository
- [ ] Use environment-specific OAuth apps (dev/staging/prod)

---

## Security Best Practices

### Session Management
- Sessions expire after 1 hour
- Cookies are HttpOnly (prevents XSS)
- Cookies use SameSite=Lax (prevents CSRF)
- Secure flag enabled in production (HTTPS only)

### Token Validation
- GitHub tokens validated on each authenticated request
- Expired tokens automatically cleared from session
- Token refresh mechanism prevents stale sessions

### Error Handling
- Generic error messages to users
- Detailed errors logged server-side only
- No sensitive data in client-facing errors

### Input Validation
- Repository URLs validated before cloning
- File paths sanitized
- API parameters type-checked

---

## Remaining Security Considerations

### Not Yet Implemented (Future Work)

1. **Database Security**: Currently using in-memory storage
   - Add encrypted database for persistent storage
   - Implement proper user authentication/authorization

2. **Async Processing**: Blocking operations cause timeouts
   - Implement background task queue (Celery/Redis)
   - Add job status tracking

3. **Input Sanitization**: Limited validation on user inputs
   - Add comprehensive input validation
   - Implement file upload size limits

4. **Audit Logging**: No security event logging
   - Log authentication attempts
   - Track API usage per user
   - Monitor suspicious activity

5. **API Authentication**: No API key system
   - Implement API keys for programmatic access
   - Add OAuth scopes for fine-grained permissions

---

## Reporting Security Issues

If you discover a security vulnerability, please email: security@example.com

**Do NOT** open a public GitHub issue for security vulnerabilities.
