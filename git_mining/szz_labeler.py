"""
SZZ Labeler — file-level bug attribution.

Strategy: iterate bug-fix commits and collect every non-test,
non-generated file they touch. Those files are labelled buggy.
This is fast (no git blame), correct for file-level prediction,
and cache-friendly.
"""

from pydriller import Repository
import os
import pickle
import sys

from config import CACHE_VERSION
from static_analysis.analyzer import SUPPORTED_EXTENSIONS
from pydriller import Repository, Git

# ── Keyword lists ──────────────────────────────────────────────────────────────

NEGATIVE_KEYWORDS = [
    "typo", "readme", "docs", "documentation",
    "format", "style", "comment", "rename",
    "refactor", "cleanup", "whitespace",
]

POSITIVE_KEYWORDS = [
    "fix", "bug", "error", "crash", "issue",
    "resolve", "defect", "failure", "hotfix",
    "incorrect", "exception",
]

TEST_PATH_KEYWORDS  = ["/test/", "/tests/", "/spec/", "/testing/"]

TEST_FILE_PATTERNS  = [
    "test_", "_test", "conftest", "fixture",
    "fixtures", "factory", "factories", "mock", "mocks",
]

TEST_FILE_EXTENSIONS = [".test.js", ".spec.js", ".test.ts", ".spec.ts"]

GENERATED_PATHS = [
    "/node_modules/", "/vendor/", "/dist/", "/build/",
    "/generated/", "/__generated__/", "/migrations/",
    "/coverage/", "/.venv/", "/venv/", "/env/",
    # ── Must mirror SKIP_DIR_PATTERNS in static_analysis/analyzer.py ────────────
    # Files in these dirs are excluded from analysis, so SZZ must also exclude
    # them — otherwise SZZ labels files the analyzer never scores, causing a
    # high SZZ-path count with near-zero match rate (e.g. FastAPI 5.1% → fix).
    "/docs_src/", "/docs/", "/examples/", "/example/",
]


# ── Path helpers ───────────────────────────────────────────────────────────────

def _norm_path(filepath):
    """Normalize to forward-slash + lowercase for cross-platform matching."""
    return filepath.replace("\\", "/").lower()


def _repo_key(repo_path):
    """Filesystem-safe key for cache filenames."""
    return repo_path.replace("/", "_").replace("\\", "_").replace(":", "_")


# ── Filter predicates ──────────────────────────────────────────────────────────

def is_bug_fix(message):
    """
    Return True iff the commit subject line signals a bug fix.
    Subject-line only (ignores multi-line body).
    Negative keywords take priority over positive keywords.
    """
    if not message:
        return False

    subject = message.strip().split("\n")[0].lower()

    if any(neg in subject for neg in NEGATIVE_KEYWORDS):
        return False

    return any(pos in subject for pos in POSITIVE_KEYWORDS)


def is_test_file(filepath):
    path = _norm_path(filepath)

    # match '/test/' in middle of path OR 'test/' at start
    for keyword in TEST_PATH_KEYWORDS:
        if keyword in path or path.startswith(keyword.lstrip("/")):
            return True

    filename = path.split("/")[-1]

    for pattern in TEST_FILE_PATTERNS:
        if pattern in filename:
            return True

    for ext in TEST_FILE_EXTENSIONS:
        if filename.endswith(ext):
            return True

    return False


def is_generated_file(filepath):
    path = _norm_path(filepath)
    # match both '/node_modules/' (middle of path) and 'node_modules/' (start)
    for keyword in GENERATED_PATHS:
        if keyword in path or path.startswith(keyword.lstrip("/")):
            return True
    return False


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _cache_file(repo_path, cache_dir):
    """Cache filename includes CACHE_VERSION — increment in config.py to bust stale caches."""
    return os.path.join(cache_dir, f"szz_{_repo_key(repo_path)}_{CACHE_VERSION}.pkl")


def _load_szz_cache(repo_path, cache_dir):
    if not cache_dir:
        return None
    path = _cache_file(repo_path, cache_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            buggy_files = pickle.load(f)
        print(f"  SZZ: loaded from cache ({len(buggy_files)} buggy files)")
        return buggy_files
    except Exception:
        return None


def _save_szz_cache(repo_path, buggy_files, cache_dir):
    if not cache_dir:
        return
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_file(repo_path, cache_dir)
    with open(path, "wb") as f:
        pickle.dump(buggy_files, f)


# ── Core labeling ──────────────────────────────────────────────────────────────

def extract_bug_labels(repo_path, cache_dir=None):
    """
    Hybrid TRUE SZZ (line-level + fallback file-level)

    Returns:
        set of normalized file paths that historically contained buggy code
    """

    cached = _load_szz_cache(repo_path, cache_dir)
    if cached is not None:
        print(f"  SZZ: loaded from cache ({len(cached)} buggy files)")
        return cached

    buggy_files = set()

    fix_commits = 0
    blame_hits = 0
    fallback_hits = 0

    repo = Repository(repo_path, only_no_merge=True)
    git_wrapper = Git(repo_path)

    for commit in repo.traverse_commits():

        if not is_bug_fix(commit.msg):
            continue

        fix_commits += 1

        for file in commit.modified_files:

            # prefer old_path (where bug existed)
            path = file.old_path or file.new_path
            if not path:
                continue

            fp_norm = _norm_path(path)

            # filter unwanted files
            if is_test_file(fp_norm):
                continue

            if is_generated_file(fp_norm):
                continue

            if not fp_norm.endswith(SUPPORTED_EXTENSIONS):
                continue

            # -------------------------------
            # TRUE LINE-LEVEL SZZ
            # -------------------------------

            deleted_lines = file.diff_parsed.get("deleted", [])
            if not deleted_lines:
                continue

            try:
                # CORRECT API USAGE: Pass the `file` object directly (it is a ModifiedFile object).
                # PyDriller automatically does the diff, finds the deleted lines, and runs git blame.
                blamed_dict = git_wrapper.get_commits_last_modified_lines(commit, modification=file)
                
                # blamed_dict returns { "filepath": {"commit_hash1", "commit_hash2"} }
                if blamed_dict:
                    buggy_files.add(fp_norm)
                    blame_hits += 1
                else:
                    # If blame found nothing, fallback to file-level
                    buggy_files.add(fp_norm)
                    fallback_hits += 1

            except Exception as e:
                # Print the first exception so we aren't flying blind!
                if fallback_hits == 0: 
                    print(f"  [Debug] Blame exception: {e}")
                buggy_files.add(fp_norm)
                fallback_hits += 1

    print(
        f"  SZZ (Hybrid): {fix_commits} fix-commits → "
        f"{len(buggy_files)} buggy paths"
    )

    print(
        f"  SZZ stats: "
        f"blame={blame_hits}, "
        f"fallback={fallback_hits}"
    )

    _save_szz_cache(repo_path, buggy_files, cache_dir)

    return buggy_files


# ── Audit ──────────────────────────────────────────────────────────────────────

def audit_labels(buggy_count, total_files, szz_raw_count):
    """
    Print file-level label distribution and warn if outside healthy range.

    buggy_count   = files actually matched and marked buggy
    total_files   = total files in this analysis (from static analyzer)
    szz_raw_count = total paths in SZZ set (includes deleted/renamed files)
    """
    ratio = buggy_count / total_files if total_files > 0 else 0

    matched_pct = buggy_count / szz_raw_count if szz_raw_count > 0 else 0

    print(f"\n  Label Audit:")
    print(f"  SZZ raw paths     : {szz_raw_count}")
    print(f"  Files in analysis : {total_files}")
    print(f"  Matched buggy     : {buggy_count} ({ratio:.1%} of analyzed files)")
    print(f"  SZZ match rate    : {matched_pct:.1%} of SZZ paths exist in analyzer")
    print(f"  Clean files       : {total_files - buggy_count} ({1 - ratio:.1%})")

    if ratio < 0.05:
        print("  ⚠ Very few buggy files — SZZ keyword filter may be too strict")
    elif ratio > 0.60:
        print("  ⚠ Many buggy files — SZZ filter may be too loose")
    else:
        print(f"  ✓ Label prevalence {ratio:.1%} looks healthy")
