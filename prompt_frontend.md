Frontend Reimplementation Prompt
Context
Full ML bug prediction system. Backend is complete and working. Frontend needs
a complete rewrite — current one is broken and visually poor. Build it clean,
minimal, and human. Every UI decision should serve the user, not demonstrate
technology.

Step 0 — Read Before Building
Read these completely before writing a line of HTML:

app_ui.py — every route, every response shape, every session variable
database.py — schema, what scan results look like stored and retrieved
model/training_log.jsonl — actual structure of training metrics
explainability/plots/ — which files actually exist on disk
templates/ — understand what is broken and why
static/ — understand what JS is failing and why

Write a private audit listing every broken template variable, every failing
fetch call, and every missing route before touching any file.

Stack — No Exceptions
Flask + Jinja2       server-side rendering
HTMX                 dynamic updates, polling, form submission
Alpine.js            component state (panels, dropdowns, filters)
Chart.js via CDN     all data visualisation
Tailwind CSS via CDN styling — no custom CSS framework
No React. No Vue. No npm. No build step. No Webpack. Everything must run with
python wsgi.py and nothing else.

Design Principles
Minimal and human. This is a developer tool, not a marketing site. Every
element earns its place. No gradients on gradients. No animations for the sake
of it. No hero sections.
Typography does the work. Use font weight and size hierarchy instead of
colour for structure. Colour is reserved for status: red=risk, amber=warning,
green=safe, gray=neutral.
Consistent risk colours everywhere — never deviate:

CRITICAL: #DC2626 (red-600)
HIGH: #EA580C (orange-600)
MODERATE: #D97706 (amber-600)
LOW: #16A34A (green-600)
NEUTRAL / unknown: #6B7280 (gray-500)

Density over decoration. Show more useful information, less chrome.
Tables beat cards when there is data to compare. Inline context beats tooltips.

Pages
base.html

Navigation: Home · About · Dashboard (if logged in) · Sign in / Sign out
Flash message zone below nav
All CDN scripts loaded here: Tailwind, HTMX, Alpine.js, Chart.js
CSRF meta tag for JS fetch calls
No sidebar. Top nav only.


Page 1 — Landing /
Single focused screen. Two inputs:
Left (primary): URL or local path input + Analyze button.

Placeholder: https://github.com/owner/repo
Inline validation: if starts with https:// but not https://github.com/,
show error before submitting. Never let a bad URL hit the server.
Below input: small text listing supported languages as plain text, not badges.

Right (secondary, only if GITHUB_CLIENT_ID is set):

"Or sign in with GitHub to scan your own repositories" + OAuth button.
If env var is missing, hide this panel entirely.

Below both: Recent scans from GET /api/recent_scans.

Simple table: repo name, language, risk score (colored), scan date, View link.
If empty: "No scans yet."

No hero text. No illustrations. No animation on load.

Page 2 — Scan Progress /scan/<scan_id>
HTMX polling every 2 seconds against GET /api/scan_progress/<scan_id>.
Stop polling once status is complete or failed by omitting HTMX attributes
in the terminal response.
Show:

Repo name being analyzed
Progress bar (thin, percentage-driven, colored by current progress)
Step list with state: pending (gray dot), active (spinning indicator),
done (checkmark). Steps: Clone → Mine git history → Analyze code →
Build features → Predict → Generate explanations
If shallow_history_warning true: amber inline notice explaining that
limited git history means predictions rely mainly on code complexity.
On complete: "View Results →" link + auto redirect after 2 seconds.
On failure: red error box with the error message + "Try again" link back
to home. Never show a raw Python traceback.


Page 3 — Results /results/<scan_id>
Data loaded from GET /api/results/<scan_id> on page load. Show a loading
skeleton while fetching. Show a clear error state if fetch fails — not a
blank page.
Header row:
Repo name · language · file count · scan date · overall risk score (large
colored badge) · Rescan button.
If shallow_history_warning: amber banner under header, one line.
Three-column layout (desktop), single column (mobile):
Column 1 — Summary:

SVG gauge (pure inline SVG, no library): circular arc showing overall
risk score 0–100. Arc color matches risk tier. Number in center.
Below gauge: four stat rows. CRITICAL / HIGH / MODERATE / LOW with counts.

Column 2 — File list:

Sorted by risk score descending.
Each row: risk badge (colored, tier label), filename, percentage, top reason
(one line, gray text). Click → open file detail panel.
Filter bar above list: All · CRITICAL · HIGH · MODERATE · LOW.
Alpine.js client-side filter, no re-fetch.
Default: show top 20. "Show all N files" expander below.

Column 3 — File tree:

Build folder structure from files[].filepath.
Each folder: colored left border by max child risk. Click to expand/collapse
(Alpine.js x-show). Shows file count.
Each file: colored dot, name, percentage. Click → open same file detail panel.

Bottom row — Three charts (Chart.js):
Every chart uses this guard:
javascriptfunction initChart(id, buildFn) {
  const el = document.getElementById(id);
  if (!el) return;
  try { buildFn(el, JSON.parse(el.dataset.chartData)); }
  catch(e) {
    el.parentNode.innerHTML =
      '<p class="text-sm text-gray-400 p-4">No data available</p>';
  }
}
document.addEventListener('DOMContentLoaded', () => { /* init all charts */ });
Chart 1 — Risk distribution (bar). X: CRITICAL/HIGH/MODERATE/LOW. Y: count.
Chart 2 — Bug type distribution (doughnut). Only show types with count > 0.
Exclude "unknown". If nothing to show, display text message, not empty chart.
Chart 3 — Feature importance (horizontal bar). Top 8 features. Use human
labels from this mapping (only the 26 RFE-selected features appear):
  bug_recency_score → "Bug history"
  avg_complexity → "Code complexity (avg)"
  max_complexity → "Code complexity (peak)"
  temporal_bug_memory → "Long-term bug memory"
  instability_score → "File instability"
  commits → "Total commit history"
  author_count → "Contributor count"
  max_coupling_strength → "Coupling strength"
  recency_ratio → "Recent vs. historical activity"
  commit_burst_score → "Commit burst activity"
  coupling_risk → "Coupling risk"
  avg_params → "Avg function parameters"
  max_function_length → "Longest function"
  complexity_vs_baseline → "Complexity vs language baseline"
  loc_per_function → "Avg function size"
  lines_added → "Lines added (lifetime)"
  lines_deleted → "Lines deleted (lifetime)"
  max_added → "Largest single addition"
  avg_commit_size → "Avg commit size"
  max_commit_ratio → "Largest commit proportion"
  days_since_last_change → "Days since last change"
  coupled_file_count → "Coupled file count"
  coupled_recent_missing → "Co-changed files lagging"
  recent_commit_burst → "Recent activity burst"
  recent_bug_flag → "Recent bug indicator"
Never display raw feature names in the UI.
Inject chart data via data-chart-data attribute. Initialize in one
DOMContentLoaded listener.
File detail slide-in panel (Alpine.js, fixed right, full height):
html<div x-data="{ open:false, file:null }"
     @open-detail.window="open=true; file=$event.detail">
  <div x-show="open" x-transition class="fixed right-0 top-0 h-full w-96
       bg-white border-l overflow-y-auto z-50 p-6">
Panel contents:

Filename + language tag
Risk score (large) + tier badge + bug type badge with confidence
"Why risky" section: top 3 reasons as bullet list. Red bullet = increases
risk. Green bullet = decreases risk (negative SHAP).
Recommendation paragraph.
Top functions table: name, complexity, length, params. Sorted by complexity.
SHAP bars: horizontal, labeled with human feature names. Red = positive
contribution, green = negative. Show only top 6 features.
👍 / 👎 feedback buttons → POST /api/feedback with fetch, show confirmation
inline, no page reload.
Close button top right.

Trigger from file row:
javascriptwindow.dispatchEvent(new CustomEvent('open-detail', { detail: fileObj }));

Page 4 — GitHub Dashboard /dashboard
Only accessible when authenticated. Redirect to / if not logged in.
Fetch repos from GET /api/repos with HTMX on load. Show spinner while
loading.
Table layout (not cards):

Columns: Repository · Language · Last updated · Status · Action
Status: risk score badge if scanned, "Not scanned" (gray) if not,
"Language not supported" (gray, no action button) if unsupported.
Action: "Scan" button or "View results" link.
Supported languages: Python, JavaScript, TypeScript, Java, Go, Ruby,
PHP, C#, C++, C, Rust, Swift, Scala.


Page 5 — About /about
All dynamic data from GET /api/model_performance. If endpoint returns 404,
show: "No training data found. Run python main.py to train the model."
Do not show stale hardcoded numbers.
Sections in order:
What this is:
Two short paragraphs. Plain English. What problem it solves, what approach
it uses. No bullet points.
How the model works:
Step-by-step pipeline in plain text with thin horizontal rule separators.
No SVG diagram libraries. Pure HTML/CSS:
Source Code + Git History
        ↓  Feature extraction (26 metrics per file)
        ↓  SZZ labeling (bug-introducing commit identification)
        ↓  Cross-project training (leave-one-out, 9 repositories)
        ↓  Calibrated risk score + SHAP explanation
        ↓  Bug type prediction (TF-IDF + Logistic Regression)
Brief explanation of each step in 2–3 sentences below the diagram.
Labeling methodology:
Explain enhanced SZZ: merge-commit filter, 15-file commit cap, comment/blank
line exclusion, confidence-weighted sample weights. Be honest about label
noise (~30% estimated from literature).
Training datasets:
Table from training_datasets in API response. Columns: Repository, Language,
Files, Buggy files, Bug rate, Domain. Show totals row.
Evaluation results:
Full 9-fold table. Columns: Repository, Model, Files, Bugs, F1, PR-AUC,
Recall@Top20%, Note.

Flag folds with <20 test files with asterisk and footnote.
Show Full benchmark avg and Reliable benchmark avg as separate rows.
Add note: "Reliable benchmark excludes folds with <30 test files (requests,
httpx, express). Express F1=1.000 reflects a 6/7 positive test set, not
model quality."
Guava note: "Trained on zero Java examples. F1=0.742 on 1,031 Java files
demonstrates language-agnostic process metric generalization."

Ablation study:
Grouped bar chart (Chart.js). Feature sets on X axis. F1 and PR-AUC as two
grouped bars per set. Static-only / Git-only / RFE-combined.
Key finding below chart: "Git process metrics outperform static complexity
metrics in isolation (F1: 0.855 vs 0.708), confirming that how code changes
matters more than how complex it is."
Feature importance:
Horizontal bar chart. Top 8 features. Human labels. Brief explanation of the
top 3 features in plain English below the chart.
SHAP plots:
Fetch from GET /api/shap_plots. For each path returned, show the image with
a caption. If none: "SHAP visualizations are generated during model training.
Run python main.py to generate them." Never show a broken <img> tag.
What the risk score means:
Honest paragraph. Key points: scores are calibrated probabilities. Risk tiers
are assigned by within-repository percentile rank (top 10% = CRITICAL) not
by absolute thresholds. A score of 90% does not mean 90% certainty of a bug
— it means the file ranks in the highest risk tier based on signals that
historically preceded bugs.
Limitations:
Short numbered list. Git history required. SZZ label noise. Bug type
classification is approximate. Generalizes best to projects similar to training
data. Java predictions have higher uncertainty (less training data).

Security
Apply to every route and template:
python@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response
CSRF token in every form and in every JS fetch:
javascriptconst csrfToken = document.querySelector('meta[name="csrf-token"]').content;
fetch('/api/feedback', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
  body: JSON.stringify(payload)
});
Session config:
pythonapp.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600
)
All user-supplied file paths: validate length ≤ 500, reject .., reject
leading / before any filesystem operation.
Rate limit the scan endpoint: @limiter.limit("5 per hour").

Error Handling — Every Route
Every route:
pythontry:
    # logic
except Exception as e:
    logger.error("Route /x failed: %s", e, exc_info=True)
    if request.is_json:
        return jsonify({"error": "Something went wrong"}), 500
    flash("Something went wrong. Please try again.", "error")
    return redirect(url_for('index'))
Never return a Python traceback to the browser.
404 and 500 error pages must be custom HTML templates, not Flask defaults.
All /api/ routes must return JSON in every case including errors.

Deployment Readiness
wsgi.py:
pythonfrom app_ui import create_app
app = create_app()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
Procfile:
web: gunicorn wsgi:app --workers 4 --timeout 120 --bind 0.0.0.0:5000
logs/ directory must exist and be writable. Application log goes to
logs/app.log. No print() statements anywhere.
Remove any app.run(debug=True) from all files.
All paths use Path(__file__).parent — no hardcoded C:\Users\... paths.

Verification Checklist
Complete every item before finishing. Fix and re-run from the top if any fails.

 python wsgi.py starts with no import errors, startup checks logged
 GET /health returns 200 JSON with model_loaded status
 Landing page: no JS console errors, validation fires correctly
 Scan a GitHub URL: progress page polls, redirects on completion
 Results: three columns visible, gauge shows correct number, all charts
render (not blank canvases)
 Click a file: panel opens with SHAP bars using human labels
 Bug type chart: "unknown" never appears as a slice
 Filter buttons on file list work client-side without re-fetch
 About page: all metrics from training_log.jsonl not hardcoded
 Ablation chart renders correctly
 SHAP images appear on About if files exist; message if not
 GET /api/file_detail?id=../../etc/passwd → 400 rejected
 POST without CSRF token → 403 rejected
 Server error in any route → JSON error (API) or flash + redirect (page)
 Two simultaneous scans complete without race condition
 All pages readable on 375px mobile width


Deliverables
app_ui.py          fully working Flask application using create_app() pattern
wsgi.py            production entry point
templates/
  base.html
  index.html
  scan.html
  results.html
  dashboard.html
  about.html
  404.html
  500.html
static/
  js/app.js        all chart init + fetch helpers
.env.example       all env vars documented
requirements.txt   updated
Procfile           gunicorn config
Run with:
bashpip install -r requirements.txt
cp .env.example .env   # fill values
python main.py         # train model
python wsgi.py         # start server
All verification checks must pass.