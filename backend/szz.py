"""
SZZ Labeler — file-level bug attribution.

Strategy: iterate bug-fix commits and collect every non-test,
non-generated file they touch. Those files are labelled buggy.
This is fast (no git blame), correct for file-level prediction,
and cache-friendly.
"""

import os
import re
import pickle
import sys
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple

import pandas as pd
from pydriller import Repository, Git

from backend.config import CACHE_VERSION, SKIP_DIR_PATTERNS, SKIP_FILE_PATTERNS, SZZ_MIN_CHURN_RATIO, SZZ_MAX_FILES_PER_COMMIT, SZZ_MIN_CONFIDENCE, SZZ_LABEL_WINDOW_DAYS
from backend.analysis import SUPPORTED_EXTENSIONS, get_language

# ── Keyword lists (Aligned with Correct Design Mandate) ─────────────────────────

# HIGH CONFIDENCE signals (Weight: 1.0)
HIGH_KEYWORDS = [
    "crash", "exception", "failure", "null", "panic", "segfault",
    "deadlock", "overflow", "memory leak"
]

# MEDIUM confidence signals (Weight: 0.7)
MEDIUM_KEYWORDS = [
    "fix", "bug", "issue", "resolve", "patch", "defect", "broken"
]

# IGNORE / Weak signals (Do not label as bug)
IGNORE_KEYWORDS = [
    # Code quality / style (not bugs)
    "refactor", "cleanup", "rename", "format", "style", "lint",
    "flake8", "pylint", "mypy", "pyright", "ruff", "black",
    # Type annotations (not bugs)
    "typing", "annotation", "type hint", "type check",
    # Documentation (not bugs)
    "typo", "docs", "documentation", "readme", "rst", "docstring",
    "grammar", "spelling", "comment",
    # Dependency / CI (not bugs)
    "update", "upgrade", "bump", "pre-commit", "ci", "release", "version"
]

def get_commit_confidence(message: str) -> float:
    """
    Calculate weight based on Correct Design Step 1.
    HIGH = 1.0, MEDIUM = 0.7, others effectively ignored.
    """
    if not message:
        return 0.0
    
    subject = message.strip().split("\n")[0].lower()
    
    # Priority 0: IGNORE weak keywords
    if any(kw in subject for kw in IGNORE_KEYWORDS):
        return 0.0
    
    # Priority 1: HIGH category
    if any(kw in subject for kw in HIGH_KEYWORDS):
        return 1.0
    
    # Priority 2: MEDIUM category
    if any(kw in subject for kw in MEDIUM_KEYWORDS):
        return 0.7
            
    return 0.0

def has_substantive_code_changes(file_mod, language: str, min_churn_ratio: float = SZZ_MIN_CHURN_RATIO) -> bool:
    """Check if file has substantive code changes using churn ratio.
    
    CHURN-WEIGHTED LABELING: Only label files where a significant portion
    of the file was changed in the bug-fix commit. This reduces false positives
    from minor typo fixes or incidental changes.
    
    Args:
        file_mod: PyDriller ModifiedFile object
        language: Programming language
        min_churn_ratio: Minimum ratio of file changed (default: 0.05 = 5%)
    
    Returns:
        True if file has substantive code changes (>5% of file modified)
    """
    if not file_mod.diff:
        return False
    
    # Get total lines changed in this commit
    lines_changed = (file_mod.added_lines or 0) + (file_mod.deleted_lines or 0)
    
    if lines_changed == 0:
        return False
    
    # Get file size (use source_code_before for deleted lines context)
    try:
        if file_mod.source_code_before:
            total_lines = len(file_mod.source_code_before.split('\n'))
        elif file_mod.source_code:
            total_lines = len(file_mod.source_code.split('\n'))
        else:
            # Fallback: if we can't determine file size, use absolute threshold
            return lines_changed >= 5  # At least 5 lines changed
    except Exception:
        return lines_changed >= 5
    
    if total_lines == 0:
        return False
    
    # Calculate churn ratio
    churn_ratio = lines_changed / total_lines
    
    # Only label if >10% of file was changed AND at least 3 substantive lines
    if lines_changed < 3:
        return False
    
    # Count substantive lines (not comments/whitespace)
    substantive_lines = 0
    if file_mod.source_code_before:
        for line in file_mod.source_code_before.split('\n')[:lines_changed]:
            if is_substantive_line(line, language):
                substantive_lines += 1
    
    # More relaxed substantive line requirement - allow 1 substantive line for small files
    min_substantive_lines = 1 if lines_changed <= 5 else 2
    if substantive_lines < min_substantive_lines:
        return False
    
    # Primary check: churn ratio (more inclusive)
    return churn_ratio >= min_churn_ratio


def is_substantive_line(line: str, language: str) -> bool:
    """Check if a deleted line is actual code (not comment/blank)."""
    stripped = line.strip()
    if not stripped:  # blank line
        return False
    
    # Language-specific comment detection
    if language == "python":
        if stripped.startswith("#"):  # Python comment
            return False
        if stripped.startswith('"""') or stripped.startswith("'''"):
            return False
    elif language in ("javascript", "typescript", "java", "go", "cpp", "csharp"):
        if stripped.startswith("//"):  # line comment
            return False
        if stripped.startswith("/*") or stripped.startswith("*"):
            return False
    
    return True

def is_merge_commit(commit) -> bool:
    """Check if commit is a merge commit."""
    return len(commit.parents) > 1

TEST_PATH_KEYWORDS  = ["/test/", "/tests/", "/spec/", "/testing/"]

TEST_FILE_PATTERNS  = [
    "test_", "_test", "conftest", "fixture",
    "fixtures", "factory", "factories", "mock", "mocks",
]

TEST_FILE_EXTENSIONS = [".test.js", ".spec.js", ".test.ts", ".spec.ts"]

# GENERATED_PATHS now uses shared SKIP_DIR_PATTERNS from config.py
# This ensures SZZ and analyzer exclude the same directories
GENERATED_PATHS = [f"/{pattern}/" for pattern in SKIP_DIR_PATTERNS]


# ── Path helpers ───────────────────────────────────────────────────────────────

def _norm_path(filepath):
    """Robust path normalization for matching.
    Requirement: lowercase, forward slashes, repo-relative, no leading './'
    """
    if not filepath:
        return ""
    # 1. Lowercase and replace backslashes
    norm = filepath.replace("\\", "/").lower()
    # 2. Remove leading './' or '/'
    norm = re.sub(r'^(\./|/)', '', norm)
    # 3. Strip trailing slashes
    norm = norm.strip("/")
    return norm


def _repo_key(repo_path):
    """Filesystem-safe key for cache filenames."""
    return repo_path.replace("/", "_").replace("\\", "_").replace(":", "_")


# ── Filter predicates ──────────────────────────────────────────────────────────

def is_bug_fix(message):
    """
    Identify bug-fix commits using strong keywords only.
    """
    return get_commit_confidence(message) > 0.0
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
        
        # VALIDATION: Ensure new format {'path': {'confidence': f, 'bug_count': i}}
        if not isinstance(buggy_files, dict):
            return None
        # Check a sample item if exists
        if buggy_files:
            sample = next(iter(buggy_files.values()))
            if not isinstance(sample, dict):
                print(f"  ⚠ Stale SZZ cache format detected for {os.path.basename(repo_path)} - ignoring.")
                return None

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


def _msg_cache_file(repo_path, cache_dir):
    return os.path.join(cache_dir, f"szz_msgs_{_repo_key(repo_path)}_{CACHE_VERSION}.pkl")

def _load_szz_msg_cache(repo_path, cache_dir):
    if not cache_dir: return None
    path = _msg_cache_file(repo_path, cache_dir)
    if not os.path.exists(path): return None
    try:
        with open(path, "rb") as f: return pickle.load(f)
    except Exception: return None

def _save_szz_msg_cache(repo_path, messages, cache_dir):
    if not cache_dir: return
    os.makedirs(cache_dir, exist_ok=True)
    with open(_msg_cache_file(repo_path, cache_dir), "wb") as f:
        pickle.dump(messages, f)

# ── Core labeling ──────────────────────────────────────────────────────────────

def extract_bug_labels_with_confidence(repo_path, cache_dir=None, label_window_days=SZZ_LABEL_WINDOW_DAYS, min_confidence=SZZ_MIN_CONFIDENCE):
    """
    SZZ v2.6 with churn-weighted labeling:
    - Balanced bug-fix detection (issue refs, reverts, strong keywords)
    - CHURN-WEIGHTED: Only label files where >10% of file was changed
    - Confidence-based thresholding (45% threshold)
    - Time-windowed labeling (18 months)
    - Merge commit filtering
    - Size cap filter (max 15 files)

    Args:
        label_window_days: Only label files as buggy if touched in bug-fix
                          commits within this many days from repo's latest commit.
                          Default 548 days = 18 months.
        min_confidence: Minimum confidence to label a file as buggy (0.45 = 45%)
                       Balanced to reduce false positives while keeping real bugs.

    Returns:
        dict: {file_path: {'confidence': float, 'bug_count': int}}
    """

    cached = _load_szz_cache(repo_path, cache_dir)
    if cached is not None:
        return cached

    buggy_files = {}  # dict with {'confidence': float, 'bug_count': int}
    buggy_messages = {} # dict of {fp_norm: set([commit.msg])}

    fix_commits = 0
    blame_hits = 0
    skipped_large_commits = 0
    skipped_merge_commits = 0
    skipped_old_commits = 0
    skipped_low_confidence = 0
    skipped_trivial_changes = 0

    repo = Repository(repo_path, only_no_merge=True)
    git_wrapper = Git(repo_path)
    
    # Find the latest commit date in the repo
    all_commits = list(repo.traverse_commits())
    if not all_commits:
        return buggy_files
    
    repo_latest_date = max(commit.committer_date for commit in all_commits)
    from datetime import timedelta
    cutoff_date = repo_latest_date - timedelta(days=label_window_days)
    
    print(f"  SZZ v2.6 (churn-weighted): Using {label_window_days}-day window, min_confidence={min_confidence:.1%}, min_churn={SZZ_MIN_CHURN_RATIO:.1%}")
    print(f"  Cutoff date: {cutoff_date.strftime('%Y-%m-%d')}")

    for commit in all_commits:

        # Filter 1: Skip merge commits
        if is_merge_commit(commit):
            skipped_merge_commits += 1
            continue

        if not is_bug_fix(commit.msg):
            continue
        
        # Filter 2: Time window - only count bug fixes within the window
        if commit.committer_date < cutoff_date:
            skipped_old_commits += 1
            continue

        # Filter 3: Size cap - skip commits touching more than SZZ_MAX_FILES_PER_COMMIT files
        if len(commit.modified_files) > SZZ_MAX_FILES_PER_COMMIT:
            skipped_large_commits += 1
            continue

        # Calculate commit-level confidence
        commit_confidence = get_commit_confidence(commit.msg)
        
        # Filter 4: Skip low-confidence commits
        if commit_confidence < min_confidence:
            skipped_low_confidence += 1
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

            if not fp_norm.endswith(tuple(SUPPORTED_EXTENSIONS.keys())):
                continue
            
            # Filter 5: Check for substantive code changes (>SZZ_MIN_CHURN_RATIO of file)
            lang = get_language(path)
            if not has_substantive_code_changes(file, lang, min_churn_ratio=SZZ_MIN_CHURN_RATIO):
                skipped_trivial_changes += 1
                continue

            # STAGE 1 REDESIGN: Use blame to find bug-introducing commits
            try:
                bug_intro_commits = git_wrapper.get_commits_last_modified_lines(commit, file)
            except Exception:
                bug_intro_commits = {}

            if not bug_intro_commits:
                continue

            # We found bug introducing commits. The file is definitely buggy.
            # FILE-LEVEL SZZ MAPPING with confidence and counts
            if fp_norm not in buggy_files:
                buggy_files[fp_norm] = {'confidence': commit_confidence, 'bug_count': 1}
                buggy_messages[fp_norm] = set()
            else:
                # Take maximum confidence across all bug-fix commits
                buggy_files[fp_norm]['confidence'] = max(buggy_files[fp_norm]['confidence'], commit_confidence)
                buggy_files[fp_norm]['bug_count'] += 1
            buggy_messages[fp_norm].add(commit.msg)
            blame_hits += 1

    print(
        f"  SZZ v2.6 (churn-weighted): {fix_commits} high-confidence fix-commits ("
        f"skipped: {skipped_old_commits} old, "
        f"{skipped_large_commits} large, "
        f"{skipped_merge_commits} merge, "
        f"{skipped_low_confidence} low-conf, "
        f"{skipped_trivial_changes} trivial <{SZZ_MIN_CHURN_RATIO:.1%} churn) -> "
        f"{len(buggy_files)} buggy files"
    )

    _save_szz_cache(repo_path, buggy_files, cache_dir)
    # Convert sets to lists before pickling
    serializable_msgs = {k: list(v) for k, v in buggy_messages.items()}
    _save_szz_msg_cache(repo_path, serializable_msgs, cache_dir)

    return buggy_files

def extract_file_bug_messages(repo_path, cache_dir=None):
    """
    Returns dict: {file_path: [commit_message1, commit_message2]}
    Relies on SZZ v2 execution/cache. If not available, returns empty dict.
    """
    cached_msgs = _load_szz_msg_cache(repo_path, cache_dir)
    if cached_msgs is not None:
        return cached_msgs
    # If not cached, we'd have to re-run SZZ. We assume it ran.
    return {}

def extract_bug_labels(repo_path, cache_dir=None):
    """
    SZZ v2.6 with churn-weighted labeling:
    - Merge commit filtering
    - CHURN-WEIGHTED: Only label files where >10% of file was changed
    - Size cap filter (max 15 files)
    - Confidence weight scoring (45% threshold)

    Returns:
        set of normalized file paths that historically contained buggy code
    """
    confidence_dict = extract_bug_labels_with_confidence(repo_path, cache_dir)
    return set(confidence_dict.keys())


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
