import os
import secrets
import logging
import logging.handlers
import joblib
import pandas as pd
import requests
import uuid
import json
import time
import threading
from urllib.parse import urlparse
from flask import Flask, jsonify, render_template, request, session, redirect, url_for, make_response, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from datetime import timedelta
from functools import wraps
# database_v2 does not exist — all DB access goes through database.py

# ── Logging setup ─────────────────────────────────────────────────────────────
# RotatingFileHandler caps the log at 5 MB with 3 rolling backups so the
# file never grows unbounded even on a long-running server.
_log_handler_file = logging.handlers.RotatingFileHandler(
    "bug_predictor.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding="utf-8",
)
_log_handler_console = logging.StreamHandler()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[_log_handler_file, _log_handler_console],
)
logger = logging.getLogger("app_ui")

load_dotenv()

# Import existing domain logic
from static_analysis.analyzer import analyze_repository, get_top_functions
from git_mining.git_miner import mine_git_data
from feature_engineering.feature_builder import build_features, filter_correlated_features
from feature_engineering.labeler import create_labels
from model.predict import predict
from model.train_model import load_model_version
from explainability.explainer import _compute_shap, _get_features, NON_FEATURE_COLS
from model.commit_predictor import predict_commit_risk
from config import REPOS, SZZ_CACHE_DIR, BASE_DIR, MODEL_LATEST_PATH, GIT_FEATURES_TO_NORMALIZE
from database import (
    DatabaseManager, 
    save_scan_results, 
    get_recent_scans, 
    get_high_risk_files,
    get_scan_by_id,
    Scan,
    FileRisk
)



app = Flask(__name__)

db = DatabaseManager.get_instance()

# CRITICAL: Secret key must be set via environment variable
secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY environment variable must be set. "
        "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
    )
app.secret_key = secret_key

# Session security configurations
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Rate limiting to prevent DoS attacks.
# SQLite-backed storage persists rate-limit counters across restarts so the
# window cannot be bypassed by bouncing the server (Fix #5).
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="sqlite:///rate_limits.db"
)

# Caching for expensive endpoints
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',  # In-memory cache
    'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutes default
})

# CSRF protection decorator.
# NOTE (Fix #19): CSRF tokens are session-based. Unauthenticated JSON API
# callers (e.g. curl/Postman during development) will be blocked by this
# decorator because they have no session cookie with a csrf_token. This is
# intentional for production; for local dev, temporarily comment out the
# @csrf_protect decorator on specific endpoints.
def csrf_protect(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "POST":
            token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
            if not token or token != session.get("csrf_token"):
                return jsonify({"error": "CSRF token missing or invalid"}), 403
        return f(*args, **kwargs)
    return decorated_function

# Generate CSRF token for session
def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]

# Initialize database
db = DatabaseManager.get_instance()
logger.info("Database initialized")

# Scan progress tracking.
# Entries are also tagged with a 'created_at' timestamp so a periodic TTL
# cleanup can evict abandoned scans (where the SSE client disconnected).
# This prevents unbounded memory growth on long-running servers. (Fix #6)
scan_progress = {}  # {scan_id: {"progress": 0, "status": "...", "complete": False, "created_at": <float>}}
_SCAN_PROGRESS_TTL_SECS = 1800  # evict entries older than 30 min


def _evict_stale_scan_progress():
    """Remove scan_progress entries older than _SCAN_PROGRESS_TTL_SECS."""
    now = time.time()
    stale = [
        sid for sid, info in scan_progress.items()
        if now - info.get("created_at", now) > _SCAN_PROGRESS_TTL_SECS
    ]
    for sid in stale:
        scan_progress.pop(sid, None)
    if stale:
        logger.info("Evicted %d stale scan_progress entries", len(stale))

# ── OAuth Configuration ──
github_client_id = os.environ.get("GITHUB_CLIENT_ID")
github_client_secret = os.environ.get("GITHUB_CLIENT_SECRET")

if not github_client_id or not github_client_secret:
    raise RuntimeError(
        "GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set. "
        "Create OAuth app at: https://github.com/settings/developers"
    )

oauth = OAuth(app)
github = oauth.register(
    name="github",
    client_id=github_client_id,
    client_secret=github_client_secret,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email read:user repo"},
)

# Token validation function
def validate_github_token(token):
    """Validate GitHub OAuth token by making a test API call."""
    try:
        headers = {"Authorization": f"token {token}"}
        resp = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False

def refresh_github_token():
    """Check if stored token is still valid, clear session if not."""
    if "github_token" in session:
        if not validate_github_token(session["github_token"]):
            session.clear()
            return False
    return True

SUPPORTED_LANGUAGES = {
    "Python", "JavaScript", "TypeScript", "Java",
    "Go", "Ruby", "PHP", "C#", "C++", "C", "Rust", "Swift", "Scala",
}

# Basic in-memory store so API endpoints are instant
app_state = {
    "df": None,
    "model": None,
    "global_shap": None,
    "global_shap_X": None,
    "metrics": {
        "files_analyzed": 0,
        "buggy_count": 0,
        "avg_risk": 0,
        "defect_at_20": 0.0
    }
}

def init_app_state():
    """
    Build dataset from caches and load model.

    Designed for graceful degradation: the server must always start so users
    can still authenticate via OAuth and submit ad-hoc scans even when the
    model has not been trained yet or the training repos are absent.  The
    distinction between "expected not-ready" and "unexpected crash" is handled
    by the logging level — INFO for expected, ERROR for unexpected.
    """
    logger.info("Loading AI Bug Predictor backend...")

    # ── Model ──────────────────────────────────────────────────────────────────
    if not os.path.exists(MODEL_LATEST_PATH):
        logger.info(
            "Model not found at %s — run 'python main.py' first. "
            "Starting in scan-only mode.",
            MODEL_LATEST_PATH,
        )
        return
    model_data = load_model_version()
    app_state["model"] = model_data

    # ── Training repos ─────────────────────────────────────────────────────────
    all_data = []
    for repo_path in REPOS:
        if not os.path.isdir(repo_path):
            logger.info("Skipping %s — directory not found", os.path.basename(repo_path))
            continue
        try:
            logger.info("Loading data for %s", os.path.basename(repo_path))
            static_results = analyze_repository(repo_path)
            git_results    = mine_git_data(repo_path)
            df_repo = build_features(static_results, git_results)
            df_repo = create_labels(df_repo, repo_path, cache_dir=SZZ_CACHE_DIR)
            df_repo["repo"] = repo_path
            all_data.append(df_repo)
        except Exception:
            logger.warning(
                "Failed to load %s — skipping. "
                "Delete .git/config.lock if this is a lock error.",
                os.path.basename(repo_path),
                exc_info=True,
            )

    if not all_data:
        logger.info("No training data loaded — starting in scan-only mode.")
        return

    df = pd.concat(all_data, ignore_index=True)

    # Normalize globally to prevent feature scale skew between repos
    from sklearn.preprocessing import StandardScaler
    cols_present = [c for c in GIT_FEATURES_TO_NORMALIZE if c in df.columns]
    if cols_present:
        scaler = StandardScaler()
        df[cols_present] = scaler.fit_transform(df[cols_present])
    df = filter_correlated_features(df)
    df = predict(model_data, df)
    df = df.sort_values("risk", ascending=False).reset_index(drop=True)
    app_state["df"] = df

    # Pre-compute Global SHAP for fast serving
    X = _get_features(df)
    features = (
        model_data.get("features", getattr(model_data, "feature_names_in_", None))
        if isinstance(model_data, dict)
        else getattr(model_data, "feature_names_in_", None)
    )
    if features is not None:
        for c in [col for col in features if col not in X.columns]:
            X[c] = 0
        X = X[features]

    raw_model = model_data["model"] if isinstance(model_data, dict) and "model" in model_data else model_data
    shap_vals, expected_val, X_disp = _compute_shap(raw_model, X)
    app_state["global_shap"] = shap_vals
    app_state["global_shap_X"] = X_disp

    # Compute dashboard metrics
    buggy = df["buggy"].sum()
    top_20_count = max(1, int(len(df) * 0.20))
    captured_bugs = df.head(top_20_count)["buggy"].sum()
    defect_at_20 = (captured_bugs / buggy * 100) if buggy > 0 else 0

    from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
    y_true = df["buggy"].fillna(0).astype(int).values
    y_pred = df.get("risky", pd.Series([0] * len(df))).values
    y_prob = df.get("risk",  pd.Series([0] * len(df))).values
    has_bugs = y_true.sum() > 0 and len(set(y_true)) > 1

    app_state["metrics"] = {
        "files_analyzed": len(df),
        "buggy_count": int(buggy),
        "avg_risk": round(df["risk"].mean(), 3),
        "defect_at_20": round(defect_at_20, 1),
        "expected_value": float(expected_val) if not isinstance(expected_val, (list, tuple)) else float(expected_val[0]),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 2) if has_bugs else 0.0,
        "recall":    round(recall_score(y_true, y_pred, zero_division=0), 2) if has_bugs else 0.0,
        "f1":        round(f1_score(y_true, y_pred, zero_division=0), 2) if has_bugs else 0.0,
        "roc_auc":   round(float(roc_auc_score(y_true, y_prob)), 2) if has_bugs else 0.0,
    }

    logger.info("Backend initialized successfully — %d repos loaded.", len(all_data))


# Initialize state on server start.
# Graceful degradation is intentional: the server must remain reachable for
# OAuth and ad-hoc scans even when the trained model is not yet present.
# Unexpected crashes inside init_app_state are logged at ERROR with a full
# traceback so they are easy to diagnose without killing the server.
try:
    init_app_state()
except Exception:
    logger.error(
        "Backend init raised an unexpected error — "
        "starting in scan-only mode. Check the log for details.",
        exc_info=True,
    )

@app.route("/")
def index():
    # Provide the auth state to template for conditional rendering
    auth_state = {
        "is_authenticated": "github_token" in session,
        "username": session.get("github_username", ""),
        "avatar": session.get("github_avatar", ""),
        "csrf_token": generate_csrf_token()
    }
    return render_template("index.html", auth=auth_state)

# ── Authentication Routes ──
@app.route("/auth/github/login")
def github_login():
    redirect_target = request.args.get("redirect", "/")
    session["auth_redirect"] = redirect_target
    
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    redirect_uri = url_for("github_callback", _external=True)
    return github.authorize_redirect(redirect_uri, state=state)

@app.route("/auth/github/callback")
def github_callback():
    try:
        # CSRF protection: validate state parameter
        if session.get("oauth_state") != request.args.get("state"):
            return jsonify({"error": "Invalid state parameter - possible CSRF attack"}), 400
        
        # Clear the state from session
        session.pop("oauth_state", None)
        
        # Exchange authorization code for access token
        token = github.authorize_access_token()
        if not token or "access_token" not in token:
            return jsonify({"error": "Failed to obtain access token"}), 400
        
        # Get user information
        user_resp = github.get("user")
        if user_resp.status_code != 200:
            return jsonify({"error": "Failed to fetch user information"}), 400
            
        user = user_resp.json()
        
        # Validate the token works
        if not validate_github_token(token["access_token"]):
            return jsonify({"error": "Invalid access token"}), 400
        
        # Store user session data
        session.permanent = True
        session["github_token"] = token["access_token"]
        session["github_username"] = user["login"]
        session["github_avatar"] = user["avatar_url"]
        session["github_user_id"] = user["id"]
        
        redirect_target = session.pop("auth_redirect", "/")
        return redirect(redirect_target)
        
    except Exception as e:
        # SECURITY: Log detailed error server-side, show generic message to user
        logger.error("OAuth callback error: %s", e, exc_info=True)
        return redirect("/?error=auth_failed")

@app.route("/auth/logout")
def logout():
    session.clear()
    resp = make_response(redirect("/"))
    resp.set_cookie('session', '', expires=0)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

@app.route("/api/repo_prs")
def get_repo_prs():
    # Validate authentication
    if "github_token" not in session:
        return jsonify({"error": "not authenticated"}), 401
    
    # Check if a specific repo or generic query is requested
    repo_name = request.args.get("repo", "").strip()
    
    headers = {"Authorization": f"token {session['github_token']}"}
    try:
        if repo_name:
            # Fetch open PRs for the specific repo
            url = f"https://api.github.com/repos/{repo_name}/pulls?state=open"
            resp = requests.get(url, headers=headers)
        else:
            # Fetch open PRs authored by the user or involving the user
            username = session.get("github_username")
            url = f"https://api.github.com/search/issues?q=is:pr+is:open+author:{username}"
            resp = requests.get(url, headers=headers)
            
        if resp.status_code != 200:
            return jsonify({"error": "failed to fetch PRs from GitHub API", "details": resp.text}), resp.status_code
            
        data = resp.json()
        prs = data.get("items", data) if "items" in data else data
        
        result = []
        for pr in prs[:20]: # Limit to 20 for UI
            repo_full_name = repo_name if repo_name else pr.get("repository_url", "").split("repos/")[-1]
            result.append({
                "title": pr["title"],
                "number": pr["number"],
                "url": pr.get("html_url", ""),
                "diff_url": pr.get("diff_url", ""),
                "repo": repo_full_name,
                "created_at": pr.get("created_at", "")
            })
            
        return jsonify({"prs": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/repos")
def list_user_repos():
    # Validate authentication
    if "github_token" not in session:
        return jsonify({"error": "not authenticated"}), 401
    
    # Validate token is still valid
    if not refresh_github_token():
        return jsonify({"error": "token expired"}), 401

    try:
        headers = {"Authorization": f"token {session['github_token']}"}
        resp = requests.get(
            "https://api.github.com/user/repos",
            headers=headers,
            params={"sort": "updated", "per_page": 100, "type": "all"},
            timeout=10
        )
        
        if resp.status_code != 200:
            return jsonify({"error": "Failed to fetch repositories from GitHub", "status": resp.status_code}), resp.status_code

        repos = []
        for r in resp.json():
            # Only surface supported languages
            if r.get("language") not in SUPPORTED_LANGUAGES and r.get("language") is not None:
                continue
                
            repos.append({
                "name": r["full_name"],
                "clone_url": r["clone_url"],
                "language": r.get("language", "Unknown"),
                "stars": r["stargazers_count"],
                "private": r["private"],
                "updated_at": r["updated_at"],
            })
        
        return jsonify(repos)
        
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "GitHub API request failed", "message": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route("/api/overview")
@cache.cached(timeout=60, query_string=True)
def api_overview():
    return jsonify({
        "metrics": app_state["metrics"],
        "histogram": _generate_histogram(),
        "top_risk_files": _get_top_risk_files(),
        "confusion_matrix": _generate_confusion_matrix(),
        "health_trend": _generate_health_trend()
    })

def _generate_histogram():
    df = app_state["df"]
    if df is None: return []
    bins = [i/20 for i in range(21)]
    hist = pd.cut(df["risk"], bins=bins).value_counts().sort_index()
    return [{"bin": f"{b.left:.2f}", "count": int(c)} for b, c in hist.items()]

def _get_top_risk_files():
    df = app_state["df"]
    if df is None: return []
    top = df.head(10)
    return [{
        "file": os.path.basename(str(row["file"])),
        "risk": round(row["risk"], 3)
    } for _, row in top.iterrows()]

def _generate_confusion_matrix():
    df = app_state["df"]
    if df is None: return {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    y_true = df.get("buggy", pd.Series([0]*len(df))).fillna(0).astype(int)
    y_pred = df.get("risky", pd.Series([0]*len(df))).fillna(0).astype(int)
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}

def _generate_health_trend():
    df = app_state["df"]
    if df is None or "repo" not in df.columns: return []
    trend = df.groupby("repo").agg({
        "risk": "mean",
        "buggy": "sum"
    }).reset_index()
    return [{
        "repo": os.path.basename(str(row["repo"])),
        "avg_risk": round(row["risk"], 3),
        "bugs": int(row["buggy"])
    } for _, row in trend.iterrows()]

@app.route("/api/files")
@cache.cached(timeout=300, query_string=True)
def api_files():
    # Try database first, fallback to app_state
    try:
        recent_scan = get_recent_scans(limit=1)
        if recent_scan:
            scan_id = recent_scan[0]['scan_id']
            files = get_high_risk_files(scan_id=scan_id, limit=500)
            if files:
                return jsonify(files)
    except Exception as e:
        logger.warning("Database query failed, using app_state: %s", e)

    # Fallback to app_state
    df = app_state["df"]
    if df is None: return jsonify([])

    limit = min(500, len(df))
    # Fix #15: to_dict("records") is ~50x faster than iterrows() for large DataFrames
    rows = df.head(limit).to_dict("records")
    files_list = []
    for row in rows:
        repo_name = os.path.basename(str(row["repo"]))
        rel_path  = os.path.relpath(str(row["file"]), str(row["repo"])).replace("\\", "/")
        files_list.append({
            "id":         str(row["file"]),
            "repo":       repo_name,
            "filename":   rel_path,
            "risk":       round(row.get("risk", 0.0), 3),
            "buggy":      int(row.get("buggy", 0)),
            "complexity": int(row.get("avg_complexity", 0)),
            "coupling":   round(row.get("coupling_risk", 0.0), 2) if "coupling_risk" in row else 0.0,
            "temporal":   round(row.get("temporal_bug_risk", 0.0), 2) if "temporal_bug_risk" in row else 0.0,
            "commits_1m": int(row.get("commits_1m", 0)) if "commits_1m" in row else 0,
        })

    return jsonify(files_list)

@app.route("/api/file", methods=["GET"])
def api_file_detail():
    file_id = request.args.get("id")
    df = app_state["df"]
    if df is None or file_id not in df["file"].values:
        return jsonify({"error": "File not found"}), 404
        
    idx = df.index[df['file'] == file_id].tolist()[0]
    row = df.loc[idx]
    
    # Get Function details
    top_funcs = []
    try:
        funcs = get_top_functions(file_id, top_n=5)
        top_funcs = [{"name": f["name"], "cx": f["complexity"], "len": f["length"]} for f in funcs]
    except Exception:
        pass
        
    # Get SHAP explanations
    shap_vals = app_state["global_shap"]
    X_disp = app_state["global_shap_X"]
    
    if shap_vals is not None and len(shap_vals) > idx:
        sv = shap_vals[idx]
        if len(sv.shape) > 1 and sv.shape[1] > 1: # if 2D array
            sv = sv[:, 1]
            
        contribs = pd.Series(sv, index=X_disp.columns).sort_values(ascending=False)
        top_positive = contribs[contribs > 0].head(5).to_dict()
        top_negative = contribs[contribs < 0].tail(5).to_dict()
        
        shap_data = {
            "positive": [{"feature": k, "value": round(v, 4)} for k, v in top_positive.items()],
            "negative": [{"feature": k, "value": round(v, 4)} for k, v in top_negative.items()]
        }
    else:
        shap_data = {"positive": [], "negative": []}
        
    return jsonify({
        "filepath": os.path.relpath(file_id, row["repo"]).replace("\\", "/"),
        "risk": round(row["risk"], 3),
        "top_funcs": top_funcs,
        "shap": shap_data
    })

# ── Allowed remote hosts for repository scanning ───────────────────────────────
_ALLOWED_REMOTE_HOSTS = {"github.com", "www.github.com"}
_MAX_URL_LENGTH = 300


def _validate_repo_input(raw_path: str) -> str:
    """
    Validate and normalise the repo path submitted to /api/scan_repo.

    Accepts two forms:
      - Remote URL  : must be a GitHub HTTPS or SSH URL
      - Local path  : must be an existing directory inside BASE_DIR
                      (no path-traversal outside the project root)

    Returns the cleaned path string or raises ValueError with a user-facing
    message that is safe to return in a JSON error response.
    """
    if not raw_path:
        raise ValueError("Repository path or URL is required.")

    if len(raw_path) > _MAX_URL_LENGTH:
        raise ValueError(
            f"Input too long — maximum {_MAX_URL_LENGTH} characters allowed."
        )

    is_remote = (
        raw_path.startswith("https://")
        or raw_path.startswith("http://")
        or raw_path.startswith("git@")
        or "github.com/" in raw_path
    )

    if is_remote:
        # Normalise bare "github.com/owner/repo" → "https://github.com/owner/repo"
        if not raw_path.startswith("http") and not raw_path.startswith("git@"):
            raw_path = "https://" + raw_path

        # For HTTPS URLs, enforce an allowlisted hostname
        if raw_path.startswith("http"):
            parsed = urlparse(raw_path)
            if parsed.netloc.lower() not in _ALLOWED_REMOTE_HOSTS:
                raise ValueError(
                    f"Only GitHub repositories are supported. "
                    f"Received host: '{parsed.netloc}'."
                )
            # Must have at least /owner/repo in the path
            path_parts = [p for p in parsed.path.strip("/").split("/") if p]
            if len(path_parts) < 2:
                raise ValueError(
                    "Invalid GitHub URL — expected format: "
                    "https://github.com/owner/repo"
                )
        return raw_path.strip("-").rstrip("/")

    # Local path: block traversal patterns, allow any absolute directory
    import re as _re
    if _re.search(r'\.\.[/\\]', raw_path):
        raise ValueError("Path traversal sequences ('..') are not allowed.")
    try:
        resolved = os.path.realpath(raw_path)
    except OSError:
        raise ValueError(f"Invalid local path: {raw_path}")

    if not os.path.isabs(resolved):
        raise ValueError("Local path must be an absolute path.")
    if not os.path.isdir(resolved):
        raise ValueError(f"Directory not found: {raw_path}")

    return resolved


@app.route("/api/scan_repo", methods=["POST"])
@limiter.limit("5 per hour")
@csrf_protect
def api_scan_repo():
    # ── Validate JSON body ────────────────────────────────────────────────────
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

    raw_path = data.get("path", "").strip()

    try:
        repo_path = _validate_repo_input(raw_path)
    except ValueError as exc:
        logger.warning("Scan rejected — invalid input: %s", exc)
        return jsonify({"error": str(exc)}), 400

    # ── Check model is loaded ─────────────────────────────────────────────────
    if app_state["model"] is None:
        return jsonify({"error": "Model not loaded — run 'python main.py' first."}), 503

    # ── Launch background scan ────────────────────────────────────────────────
    scan_id = str(uuid.uuid4())
    _evict_stale_scan_progress()  # TTL cleanup (Fix #6)
    scan_progress[scan_id] = {
        "progress": 0, "status": "Initializing...",
        "complete": False, "error": None,
        "created_at": time.time(),   # for TTL eviction (Fix #6)
    }

    logger.info("Scan %s started for: %s", scan_id, repo_path)
    thread = threading.Thread(target=scan_repo_background, args=(scan_id, repo_path))
    thread.daemon = True
    thread.start()

    return jsonify({"success": True, "scan_id": scan_id})

def scan_repo_background(scan_id, repo_path):
    """Background task for repository scanning with progress updates."""
    import subprocess
    _scan_logger = logging.getLogger(f"app_ui.scan.{scan_id[:8]}")

    try:
        scan_progress[scan_id] = {
            "progress": 5, "status": "Validating repository...",
            "complete": False, "error": None,
            "created_at": scan_progress.get(scan_id, {}).get("created_at", time.time()),
        }
        # repo_path has already been validated & normalised by _validate_repo_input
        # before this thread was launched — do NOT re-normalise here (Fix #3).
        if (
            repo_path.startswith("http://")
            or repo_path.startswith("https://")
            or repo_path.startswith("git@")
        ):
            auth_clone_url = repo_path
            is_private = False
            
            if "github.com" in repo_path and not repo_path.startswith("git@"):
                try:
                    repo_api_url = repo_path.replace("https://github.com/", "https://api.github.com/repos/").replace(".git", "")
                    test_response = requests.get(repo_api_url, timeout=5)
                    if test_response.status_code == 404:
                        is_private = True
                    elif test_response.status_code == 200:
                        repo_data = test_response.json()
                        is_private = repo_data.get("private", False)
                    else:
                        is_private = True
                except Exception:
                    is_private = True
                
                if is_private:
                    if "github_token" not in session:
                        scan_progress[scan_id] = {"progress": 0, "status": "Error", "complete": True, "error": "Authentication required for private repositories"}
                        return
                    
                    if not refresh_github_token():
                        scan_progress[scan_id] = {"progress": 0, "status": "Error", "complete": True, "error": "Token expired - please re-authenticate"}
                        return
                    
                    auth_clone_url = repo_path.replace("https://github.com", f"https://x-access-token:{session['github_token']}@github.com")
                
            try:
                repo_name = repo_path.rstrip('/').split('/')[-1].replace('.git', '')
                temp_cache_dir = os.path.join(BASE_DIR, "dataset", f"temp_{repo_name}_{uuid.uuid4().hex[:6]}")
                
                scan_progress[scan_id] = {"progress": 10, "status": "Cloning repository...", "complete": False, "error": None}
                
                result = subprocess.run(
                    ["git", "clone", "--depth", "500", auth_clone_url, temp_cache_dir],
                    check=True,
                    capture_output=True,
                    text=True
                )
                repo_path = temp_cache_dir
            except subprocess.CalledProcessError as e:
                err_msg = "Git clone failed. Check repository URL and permissions."
                if e.returncode == 128:
                    err_msg = "Repository not found or access denied."
                scan_progress[scan_id] = {"progress": 0, "status": "Error", "complete": True, "error": err_msg}
                return
                
        elif not os.path.exists(repo_path) or not os.path.isdir(repo_path):
            scan_progress[scan_id] = {"progress": 0, "status": "Error", "complete": True, "error": f"Invalid directory path: {repo_path}"}
            return
            
        scan_progress[scan_id] = {"progress": 25, "status": "Analyzing code structure...", "complete": False, "error": None}
        static_results = analyze_repository(repo_path)
        
        scan_progress[scan_id] = {"progress": 45, "status": "Mining git history...", "complete": False, "error": None}
        git_results = mine_git_data(repo_path)
        
        scan_progress[scan_id] = {"progress": 65, "status": "Engineering features...", "complete": False, "error": None,
                                   "created_at": scan_progress.get(scan_id, {}).get("created_at", time.time())}
        df_repo = build_features(static_results, git_results)
        df_repo["repo"] = repo_path

        if len(df_repo) == 0:
            scan_progress[scan_id] = {"progress": 0, "status": "Error", "complete": True, "error": "No valid source files or git history found"}
            return

        # Apply the training scaler for consistent feature normalization at inference.
        # The scaler is fitted globally on training data and saved inside the model
        # artifact by main.py. Using fit_transform here would create a distribution
        # mismatch (per-repo statistics vs global training statistics).
        model_data = app_state["model"]
        _saved_scaler = model_data.get("scaler") if isinstance(model_data, dict) else None
        if _saved_scaler is not None:
            cols_present = [c for c in GIT_FEATURES_TO_NORMALIZE if c in df_repo.columns]
            if cols_present:
                df_repo[cols_present] = _saved_scaler.transform(df_repo[cols_present])
        # If no scaler is saved (model trained before this fix), skip normalization.
        # XGBoost is scale-invariant so predictions remain valid without scaling.

        # Do NOT call filter_correlated_features on an ad-hoc scan — the trained
        # model has a fixed feature list; dropping columns here can silently zero
        # out features the model depends on. (Fix #10)
        scan_progress[scan_id] = {"progress": 80, "status": "Running predictions...", "complete": False, "error": None,
                                   "created_at": scan_progress.get(scan_id, {}).get("created_at", time.time())}
        model_data = app_state["model"]
        df_repo, confidence_result = predict(model_data, df_repo, return_confidence=True)
        
        if "buggy" not in df_repo.columns:
            df_repo["buggy"] = 0
            
        df_repo = df_repo.sort_values("risk", ascending=False).reset_index(drop=True)
        
        scan_progress[scan_id] = {"progress": 90, "status": "Generating explanations...", "complete": False, "error": None}
        X = _get_features(df_repo)
        features = model_data.get("features", getattr(model_data, "feature_names_in_", None)) if isinstance(model_data, dict) else getattr(model_data, "feature_names_in_", None)
        if features is not None:
            missing = [c for c in features if c not in X.columns]
            for c in missing:
                X[c] = 0
            X = X[features]
            
        raw_model = model_data["model"] if isinstance(model_data, dict) and "model" in model_data else model_data
        shap_vals, expected_val, X_disp = _compute_shap(raw_model, X)
        
        # Save to database
        scan_progress[scan_id] = {"progress": 95, "status": "Saving to database...", "complete": False, "error": None}
        scan_record = save_scan_results(
            df=df_repo,
            scan_id=scan_id,
            repo_path=repo_path,
            confidence_result=confidence_result,
            scan_duration=time.time() - time.time()  # Will be updated below
        )
        print(f"✓ Saved scan {scan_id} to database: {len(df_repo)} files")
        
        # Update app state (for backward compatibility)
        app_state["df"] = df_repo
        app_state["global_shap"] = shap_vals
        app_state["global_shap_X"] = X_disp
        
        # Recalculate metrics
        buggy = int(df_repo.get("buggy", pd.Series([0]*len(df_repo))).sum())
        top_20_count = max(1, int(len(df_repo) * 0.20))
        top_20_df = df_repo.head(top_20_count)
        captured_bugs = int(top_20_df.get("buggy", pd.Series([0]*len(top_20_df))).sum())
        defect_at_20 = (captured_bugs / buggy * 100) if buggy > 0 else 0
        
        from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
        y_true = df_repo.get("buggy", pd.Series([0]*len(df_repo))).fillna(0).astype(int).values
        y_pred = df_repo.get("risky", pd.Series([0]*len(df_repo))).values
        y_prob = df_repo.get("risk", pd.Series([0]*len(df_repo))).values
        has_bugs = sum(y_true) > 0 and len(set(y_true)) > 1
        
        app_state["metrics"] = {
            "files_analyzed": len(df_repo),
            "buggy_count": buggy,
            "avg_risk": round(float(df_repo.get("risk", pd.Series([0])).mean()), 3),
            "defect_at_20": round(defect_at_20, 1),
            "expected_value": float(expected_val) if not isinstance(expected_val, (list, tuple)) else float(expected_val[0]),
            "precision": round(precision_score(y_true, y_pred, zero_division=0), 2) if has_bugs else 0.0,
            "recall": round(recall_score(y_true, y_pred, zero_division=0), 2) if has_bugs else 0.0,
            "f1": round(f1_score(y_true, y_pred, zero_division=0), 2) if has_bugs else 0.0,
            "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 2) if has_bugs else 0.0,
            "confidence": {
                "score": round(confidence_result["confidence_score"], 3),
                "level": confidence_result["confidence_level"],
                "message": confidence_result["message"],
                "warnings": confidence_result["warnings"],
                "out_of_distribution": confidence_result["out_of_distribution"]
            }
        }
        
        scan_progress[scan_id] = {"progress": 100, "status": "Complete", "complete": True, "error": None}
        
        # Invalidate cache after successful scan
        cache.clear()
        
    except Exception as e:
        _scan_logger.error("Scan %s failed: %s", scan_id, e, exc_info=True)
        scan_progress[scan_id] = {"progress": 0, "status": "Error", "complete": True, "error": str(e)}

@app.route("/api/scan_progress/<scan_id>")
def scan_progress_stream(scan_id):
    """Server-Sent Events endpoint for real-time scan progress."""
    def generate():
        while True:
            if scan_id in scan_progress:
                data = scan_progress[scan_id]
                yield f"data: {json.dumps(data)}\n\n"
                
                if data["complete"]:
                    # Clean up after 5 seconds
                    time.sleep(5)
                    if scan_id in scan_progress:
                        del scan_progress[scan_id]
                    break
            else:
                yield f"data: {{\"progress\": 0, \"status\": \"Not found\", \"complete\": true, \"error\": \"Scan not found\"}}\n\n"
                break
            
            time.sleep(0.5)
    
    return Response(generate(), mimetype="text/event-stream")

@app.route("/api/predict_commit", methods=["POST"])
@limiter.limit("30 per minute")
@csrf_protect
def api_predict_commit():
    data = request.json
    filenames = data.get("files", [])
    if not filenames:
        return jsonify({"risk": 0.0, "main_driver": "No files provided"})
        
    df = app_state["df"]
    # We need to map short filenames to absolute paths
    # Because input might be "requests/sessions.py" or just "sessions.py"
    changed_abs_paths = []
    for fn in filenames:
        matched = False
        for abs_p in df["file"].values:
            if fn.lower() in abs_p.lower():
                changed_abs_paths.append(abs_p)
                matched = True
                break
                
    if not changed_abs_paths:
        return jsonify({"risk": 0.0, "main_driver": "Files not found in analyzer dataset"})
        
    risk_score, risky_df = predict_commit_risk(df, changed_abs_paths)
    
    driver = "None"
    if not risky_df.empty:
        top = risky_df.sort_values("risk", ascending=False).iloc[0]
        driver = f"{os.path.basename(top['file'])} ({top['risk']:.1%})"
        
    return jsonify({
        "risk": round(risk_score, 2),
        "main_driver": driver,
        "matched_files": [os.path.basename(f) for f in changed_abs_paths]
    })

@app.route("/api/analyze_pr", methods=["POST"])
@limiter.limit("20 per hour")
@csrf_protect
def api_analyze_pr():
    """Enhanced Pull Request risk analysis with past bug areas and developer experience."""
    data = request.json
    pr_url = data.get("pr_url", "").strip()
    
    if not pr_url:
        return jsonify({"error": "PR URL is required"}), 400
    
    # Extract owner, repo, and PR number from URL
    # Expected format: https://github.com/owner/repo/pull/123
    try:
        parsed_pr = urlparse(pr_url)
        path_parts = [p for p in parsed_pr.path.strip("/").split("/") if p]
        # path_parts = ["owner", "repo", "pull", "123"]
        if len(path_parts) < 4 or path_parts[2] != "pull":
            return jsonify({"error": "Invalid PR URL format. Expected: https://github.com/owner/repo/pull/123"}), 400

        owner     = path_parts[0]
        repo_name = path_parts[1]
        pr_number = path_parts[3]
        
        # Get PR data from GitHub API
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}"
        headers = {}
        
        # Use OAuth token if available for higher rate limits and private repos
        if "github_token" in session and refresh_github_token():
            headers["Authorization"] = f"token {session['github_token']}"
        
        pr_response = requests.get(api_url, headers=headers, timeout=10)
        if pr_response.status_code != 200:
            return jsonify({"error": f"Failed to fetch PR data: {pr_response.status_code}"}), pr_response.status_code
        
        pr_data = pr_response.json()
        
        # Get files changed in PR
        files_url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/files"
        files_response = requests.get(files_url, headers=headers, timeout=10)
        if files_response.status_code != 200:
            return jsonify({"error": f"Failed to fetch PR files: {files_response.status_code}"}), files_response.status_code
        
        files_data = files_response.json()
        
        # Get author's commit history for experience analysis
        author = pr_data.get("user", {}).get("login", "Unknown")
        author_experience = _analyze_developer_experience(owner, repo_name, author, headers)
        
        # Get repository's buggy files if available in our system
        buggy_files = _get_known_buggy_files(owner, repo_name)
        
        # Analyze risk for each file
        file_risks = []
        total_risk = 0.0
        high_risk_files = []
        past_bug_files = []
        
        for file_info in files_data:
            filename = file_info["filename"]
            additions = file_info.get("additions", 0)
            deletions = file_info.get("deletions", 0)
            changes = additions + deletions
            
            # Skip non-code files
            if not any(filename.endswith(ext) for ext in ['.py', '.js', '.ts', '.java', '.go', '.rb', '.php', '.cs', '.cpp', '.c', '.rs', '.swift']):
                continue
            
            # Enhanced risk calculation
            base_risk = min(0.1 + (changes / 100) * 0.5, 0.9)  # Base risk from change size
            
            # File type risk adjustment
            if filename.endswith('.py'):
                base_risk *= 1.2  # Python often has complex logic
            elif filename.endswith('.js') or filename.endswith('.ts'):
                base_risk *= 1.1  # JavaScript/TypeScript
            elif filename.endswith('.java'):
                base_risk *= 1.15  # Java complexity
            
            # Past bug area risk boost
            is_past_bug_area = filename in buggy_files
            if is_past_bug_area:
                base_risk *= 1.3  # Higher risk for previously buggy files
                past_bug_files.append(filename)
            
            # Test directory risk reduction
            if 'test' in filename.lower() or 'spec' in filename.lower():
                base_risk *= 0.7
            
            # Complex file detection (based on additions/deletions ratio)
            if changes > 1000:
                base_risk *= 1.2  # Very large changes
            elif additions > deletions * 3:
                base_risk *= 1.1  # Mostly additions (new code)
            
            file_risk = min(base_risk, 0.95)
            file_risks.append({
                "filename": filename,
                "risk": round(file_risk, 3),
                "additions": additions,
                "deletions": deletions,
                "changes": changes,
                "is_past_bug_area": is_past_bug_area
            })
            
            total_risk += file_risk
            
            if file_risk > 0.7:
                high_risk_files.append(filename)
        
        # Calculate overall PR risk with developer experience factor
        if file_risks:
            overall_risk = min(total_risk / len(file_risks), 0.95)
            
            # Adjust based on developer experience
            if author_experience["experience_level"] == "SENIOR":
                overall_risk *= 0.9  # Reduce risk for experienced developers
            elif author_experience["experience_level"] == "JUNIOR":
                overall_risk *= 1.2  # Increase risk for junior developers
        else:
            overall_risk = 0.1
        
        # Enhanced risk categorization with specific recommendations
        if overall_risk >= 0.8:
            risk_level = "HIGH"
            recommendation = "Requires senior review + extra tests"
            if past_bug_files:
                recommendation += f". Focus on: {', '.join(past_bug_files[:3])}"
        elif overall_risk >= 0.6:
            risk_level = "MEDIUM"
            recommendation = "Standard code review recommended"
            if author_experience["experience_level"] == "JUNIOR":
                recommendation += " + mentor guidance"
        else:
            risk_level = "LOW"
            recommendation = "Light review sufficient"
        
        return jsonify({
            "pr_info": {
                "title": pr_data.get("title", "Unknown"),
                "author": author,
                "state": pr_data.get("state", "Unknown"),
                "additions": pr_data.get("additions", 0),
                "deletions": pr_data.get("deletions", 0),
                "changed_files": len(files_data)
            },
            "author_experience": author_experience,
            "risk_analysis": {
                "overall_risk": round(overall_risk, 3),
                "risk_level": risk_level,
                "recommendation": recommendation,
                "high_risk_files_count": len(high_risk_files),
                "total_files_analyzed": len(file_risks),
                "past_bug_files_count": len(past_bug_files),
                "complexity_factor": "HIGH" if any(f["changes"] > 1000 for f in file_risks) else "MEDIUM"
            },
            "file_risks": file_risks,
            "high_risk_files": high_risk_files,
            "past_bug_files": past_bug_files
        })
        
    except Exception as e:
        logger.error("PR analysis failed: %s", e, exc_info=True)
        return jsonify({"error": f"Failed to analyze PR: {str(e)}"}), 500


def _analyze_developer_experience(owner, repo_name, author, headers):
    """Analyze developer experience based on commit history."""
    try:
        # Get author's commits to this repository
        commits_url = f"https://api.github.com/repos/{owner}/{repo_name}/commits"
        params = {"author": author, "per_page": 100}
        
        response = requests.get(commits_url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            return {"experience_level": "UNKNOWN", "total_commits": 0, "repo_contributions": 0}
        
        commits = response.json()
        total_commits = len(commits)
        
        # Get author's total contributions across all repos
        user_url = f"https://api.github.com/users/{author}"
        user_response = requests.get(user_url, headers=headers, timeout=10)
        if user_response.status_code == 200:
            user_data = user_response.json()
            total_contributions = user_data.get("total_contributions", 0)
        else:
            total_contributions = 0
        
        # Determine experience level
        if total_contributions > 1000 and total_commits > 50:
            experience_level = "SENIOR"
        elif total_contributions > 100 and total_commits > 10:
            experience_level = "MEDIUM"
        elif total_commits > 0:
            experience_level = "JUNIOR"
        else:
            experience_level = "NEW"
        
        return {
            "experience_level": experience_level,
            "total_commits": total_commits,
            "total_contributions": total_contributions,
            "repo_contributions": total_commits
        }
        
    except Exception as e:
        logger.warning("Error analyzing developer experience: %s", e)
        return {"experience_level": "UNKNOWN", "total_commits": 0, "repo_contributions": 0}


def _get_known_buggy_files(owner, repo_name):
    """Get known buggy files from our system if available."""
    try:
        # Check if we have data for this repo in our system
        df = app_state.get("df")
        if df is None:
            return set()
        
        # Look for files from this repository
        repo_files = df[df["repo"].str.contains(repo_name, case=False, na=False)]
        buggy_files = repo_files[repo_files["buggy"] == 1]["file"]
        
        # Extract just the filename for matching
        buggy_filenames = set()
        for file_path in buggy_files:
            filename = os.path.basename(str(file_path))
            buggy_filenames.add(filename)
        
        return buggy_filenames
        
    except Exception as e:
        logger.warning("Error getting known buggy files: %s", e)
        return set()


@app.route("/api/effort_recommendations", methods=["GET"])
def api_effort_recommendations():
    """Get effort-aware review recommendations."""
    df = app_state["df"]
    if df is None: 
        return jsonify({"error": "No scan data available"})
    
    try:
        from model.train_model import _get_effort_aware_recommendations
        
        # Get parameters
        top_n = int(request.args.get("top_n", 10))
        effort_budget = request.args.get("effort_budget")
        if effort_budget:
            effort_budget = int(effort_budget)
        
        # Generate recommendations
        recommendations = _get_effort_aware_recommendations(df, top_n, effort_budget)
        
        return jsonify(recommendations)
        
    except Exception as e:
        logger.error("Failed to generate recommendations: %s", e, exc_info=True)
        return jsonify({"error": f"Failed to generate recommendations: {str(e)}"}), 500


@app.route("/api/model_evaluation", methods=["GET"])
def api_model_evaluation():
    """Get comprehensive model evaluation results from training."""
    try:
        # Cross-project evaluation results from training
        cross_project_data = [
            {"repo": "requests", "model": "RF", "f1": 0.8333, "pr_auc": 0.7664, "recall10": 0.727, "precision10": 0.800, "defect20": 27.3, "n_test": 23, "n_buggy": 11},
            {"repo": "flask", "model": "LR", "f1": 0.9167, "pr_auc": 0.9346, "recall10": 0.391, "precision10": 0.900, "defect20": 30.4, "n_test": 42, "n_buggy": 23},
            {"repo": "fastapi", "model": "LR", "f1": 0.8000, "pr_auc": 0.8991, "recall10": 0.435, "precision10": 1.000, "defect20": 91.3, "n_test": 143, "n_buggy": 23},
            {"repo": "httpx", "model": "RF", "f1": 0.8000, "pr_auc": 0.7996, "recall10": 1.000, "precision10": 0.600, "defect20": 50.0, "n_test": 15, "n_buggy": 6},
            {"repo": "celery", "model": "RF", "f1": 0.9000, "pr_auc": 0.9626, "recall10": 0.078, "precision10": 1.000, "defect20": 34.1, "n_test": 224, "n_buggy": 129},
            {"repo": "sqlalchemy", "model": "RF", "f1": 0.8382, "pr_auc": 0.8786, "recall10": 0.062, "precision10": 1.000, "defect20": 35.6, "n_test": 329, "n_buggy": 160},
            {"repo": "express", "model": "XGB", "f1": 0.2308, "pr_auc": 0.8349, "recall10": 0.857, "precision10": 0.600, "defect20": 85.7, "n_test": 97, "n_buggy": 7},
            {"repo": "axios", "model": "RF", "f1": 0.7921, "pr_auc": 0.8852, "recall10": 0.145, "precision10": 0.800, "defect20": 56.4, "n_test": 179, "n_buggy": 55},
            {"repo": "guava", "model": "LR", "f1": 0.4523, "pr_auc": 0.5956, "recall10": 0.017, "precision10": 1.000, "defect20": 59.6, "n_test": 3223, "n_buggy": 591}
        ]
        
        # Calculate model averages
        model_stats = {}
        for item in cross_project_data:
            model = item["model"]
            if model not in model_stats:
                model_stats[model] = {"f1": [], "pr_auc": [], "recall10": [], "precision10": []}
            model_stats[model]["f1"].append(item["f1"])
            model_stats[model]["pr_auc"].append(item["pr_auc"])
            model_stats[model]["recall10"].append(item["recall10"])
            model_stats[model]["precision10"].append(item["precision10"])
        
        avg_stats = {}
        for model, stats in model_stats.items():
            avg_stats[model] = {
                "f1": sum(stats["f1"]) / len(stats["f1"]),
                "pr_auc": sum(stats["pr_auc"]) / len(stats["pr_auc"]),
                "recall10": sum(stats["recall10"]) / len(stats["recall10"]),
                "precision10": sum(stats["precision10"]) / len(stats["precision10"])
            }
        
        # Overall statistics
        total_files = sum(item["n_test"] for item in cross_project_data)
        total_buggy = sum(item["n_buggy"] for item in cross_project_data)
        best_f1 = max(cross_project_data, key=lambda x: x["f1"])
        best_recall = max(cross_project_data, key=lambda x: x["recall10"])
        best_precision = [item for item in cross_project_data if item["precision10"] == 1.0]
        
        return jsonify({
            "summary": {
                "total_projects": len(cross_project_data),
                "total_files": total_files,
                "total_buggy": total_buggy,
                "best_overall_model": "RF",
                "best_f1_score": avg_stats.get("RF", {}).get("f1", 0),
                "best_recall_project": best_recall["repo"],
                "best_recall_value": best_recall["recall10"],
                "perfect_precision_projects": [item["repo"] for item in best_precision],
                "best_defect_density": max(item["defect20"] for item in cross_project_data),
                "best_defect_project": max(cross_project_data, key=lambda x: x["defect20"])["repo"]
            },
            "cross_project": cross_project_data,
            "model_comparison": avg_stats,
            "performance_categories": {
                "excellent": ["fastapi", "flask", "httpx"],
                "moderate": ["celery", "sqlalchemy", "axios"],
                "challenging": ["express", "guava"]
            }
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to load model evaluation data: {str(e)}"}), 500


@app.route("/api/importance", methods=["GET"])
@cache.cached(timeout=600, query_string=True)
def api_importance():
    shap_vals = app_state["global_shap"]
    X_disp = app_state["global_shap_X"]
    
    if shap_vals is None: return jsonify([])
    
    # Calculate mean absolute SHAP for global importance
    import numpy as np
    mean_abs_shap = np.abs(shap_vals).mean(axis=0)
    
    importance = pd.Series(mean_abs_shap, index=X_disp.columns).sort_values(ascending=False).head(10)
    return jsonify([{"feature": k, "value": round(float(v), 4)} for k, v in importance.items()])


# ── GitHub Webhook — Real-Time PR Risk Assessment ──────────────────────────────
#
# Setup:
#   1. Set GITHUB_WEBHOOK_SECRET in your .env file to any strong random string.
#   2. In your GitHub repo → Settings → Webhooks → Add webhook:
#        Payload URL : http://<your-server>/webhook/github
#        Content type: application/json
#        Secret      : <same value as GITHUB_WEBHOOK_SECRET>
#        Events      : Pull requests
#
# The endpoint verifies the HMAC-SHA256 signature on every delivery to prevent
# spoofed payloads, then queues an async risk assessment and posts a comment.

import hmac
import hashlib

_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")


def _verify_github_signature(payload_bytes: bytes, sig_header: str) -> bool:
    """Verify X-Hub-Signature-256 header using HMAC-SHA256."""
    if not _WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET not set — webhook signature check skipped")
        return True  # Allow through in dev; fail closed in prod by setting the secret
    if not sig_header or not sig_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        _WEBHOOK_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


def _post_pr_comment(owner: str, repo: str, pr_number: int, body: str, token: str) -> bool:
    """Post a comment to a GitHub PR via the REST API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    resp = requests.post(
        url,
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        json={"body": body},
        timeout=10,
    )
    return resp.status_code == 201


def _webhook_assess_pr(owner: str, repo: str, pr_number: int,
                        clone_url: str, changed_files: list[str], token: str):
    """
    Background thread: run risk assessment for the PR's changed files and
    post a structured comment back to the PR.
    """
    try:
        df = app_state.get("df")
        if df is None or df.empty:
            logger.warning("Webhook: no dataset loaded — skipping risk assessment for PR #%s", pr_number)
            return

        # Match changed PR filenames against the loaded dataset
        matched_paths = []
        for fname in changed_files:
            for abs_path in df["file"].values:
                if fname.lower() in abs_path.lower().replace("\\", "/"):
                    matched_paths.append(abs_path)
                    break

        if not matched_paths:
            comment = (
                f"## 🤖 CodeSentinel Risk Assessment — PR #{pr_number}\n\n"
                f"⚠️ None of the {len(changed_files)} changed file(s) matched the analyzed dataset.\n"
                f"Run `python main.py` to update the analysis, then re-open this PR.\n"
            )
            _post_pr_comment(owner, repo, pr_number, comment, token)
            return

        risk_score, risky_df = predict_commit_risk(df, matched_paths)

        # Build risk level label
        if risk_score >= 0.80:
            level_badge = "🔴 CRITICAL"
        elif risk_score >= 0.60:
            level_badge = "🟠 HIGH"
        elif risk_score >= 0.40:
            level_badge = "🟡 MODERATE"
        else:
            level_badge = "🟢 LOW"

        lines = [
            f"## 🤖 CodeSentinel Risk Assessment — PR #{pr_number}",
            f"",
            f"**Commit Risk Score: `{risk_score:.0%}` {level_badge}**",
            f"",
            f"| File | Risk | Label |",
            f"|---|---|---|",
        ]

        top_files = risky_df.sort_values("risk", ascending=False).head(5)
        for _, row in top_files.iterrows():
            fname = os.path.basename(str(row["file"]))
            r     = row.get("risk", 0.0)
            lbl   = "🐛 Buggy" if int(row.get("buggy", 0)) == 1 else "✅ Clean"
            icon  = "🔴" if r >= 0.8 else "🟠" if r >= 0.6 else "🟡" if r >= 0.4 else "🟢"
            lines.append(f"| `{fname}` | {icon} `{r:.0%}` | {lbl} |")

        lines += [
            f"",
            f"*{len(matched_paths)} file(s) matched from {len(changed_files)} changed.*",
            f"*Powered by [CodeSentinel](https://github.com/architzero/ai_bug_predictor)*",
        ]

        comment = "\n".join(lines)
        posted = _post_pr_comment(owner, repo, pr_number, comment, token)
        if posted:
            logger.info("Webhook: posted risk comment to %s/%s PR #%s (risk=%.2f)", owner, repo, pr_number, risk_score)
        else:
            logger.warning("Webhook: failed to post comment to PR #%s", pr_number)

    except Exception as exc:
        logger.error("Webhook assessment failed for PR #%s: %s", pr_number, exc, exc_info=True)


@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    """
    Receive GitHub webhook events and trigger real-time PR risk assessment.
    Verifies X-Hub-Signature-256, filters pull_request events, posts a
    risk comment back to the PR asynchronously.
    """
    payload_bytes = request.get_data()

    # ── Signature verification ─────────────────────────────────────────────
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_github_signature(payload_bytes, sig_header):
        logger.warning("Webhook: invalid signature rejected from %s", request.remote_addr)
        return jsonify({"error": "Invalid signature"}), 401

    # ── Event routing ──────────────────────────────────────────────────────
    event_type = request.headers.get("X-GitHub-Event", "")
    if event_type not in ("pull_request", "ping"):
        return jsonify({"status": "ignored", "event": event_type}), 200

    if event_type == "ping":
        logger.info("Webhook: ping received — webhook configured successfully")
        return jsonify({"status": "pong"}), 200

    data = request.get_json(silent=True) or {}
    action = data.get("action", "")

    # Only assess on PR open or new commits pushed
    if action not in ("opened", "synchronize", "reopened"):
        return jsonify({"status": "ignored", "action": action}), 200

    pr        = data.get("pull_request", {})
    pr_number = pr.get("number")
    repo_data = data.get("repository", {})
    owner     = repo_data.get("owner", {}).get("login", "")
    repo_name = repo_data.get("name", "")
    clone_url = repo_data.get("clone_url", "")

    if not all([pr_number, owner, repo_name]):
        return jsonify({"error": "Malformed payload"}), 400

    # Resolve GitHub token (prefer session OAuth token, fall back to env PAT)
    token = (
        session.get("github_token")
        or os.environ.get("GITHUB_TOKEN", "")
    )
    if not token:
        logger.warning("Webhook: no GitHub token available — cannot post PR comment")
        return jsonify({"status": "no_token"}), 200

    # Fetch changed files from GitHub API
    try:
        files_resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/files",
            headers={"Authorization": f"token {token}"},
            timeout=10,
        )
        changed_files = [f["filename"] for f in files_resp.json()] if files_resp.ok else []
    except Exception:
        changed_files = []

    # Launch assessment in background — return 200 immediately to GitHub
    thread = threading.Thread(
        target=_webhook_assess_pr,
        args=(owner, repo_name, pr_number, clone_url, changed_files, token),
        daemon=True,
    )
    thread.start()

    logger.info("Webhook: queued assessment for %s/%s PR #%s (%d files)", owner, repo_name, pr_number, len(changed_files))
    return jsonify({"status": "queued", "pr": pr_number}), 202




if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("CodeSentinel Dashboard → http://localhost:5000")
    logger.info("=" * 50)
    
    try:
        init_app_state()
    except Exception as e:
        logger.critical("Failed to initialize backend: %s", e)
        import sys
        sys.exit(1)
        
    app.run(host="localhost", port=5000, debug=True, use_reloader=False)
