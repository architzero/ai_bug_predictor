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

from backend.config import CACHE_VERSION, SKIP_DIR_PATTERNS, SKIP_FILE_PATTERNS
from backend.analysis import SUPPORTED_EXTENSIONS, get_language

# ── Keyword lists ──────────────────────────────────────────────────────────────

# Negative keywords that indicate NON-bug commits (higher priority)
NEGATIVE_KEYWORDS = [
    "typo", "readme", "docs", "documentation", "doc",
    "format", "style", "comment", "rename", "comments",
    "refactor", "cleanup", "whitespace", "lint", "linting",
    "update", "upgrade", "bump", "version",  # version bumps
    "merge", "rebase",  # merge commits
    "test", "tests", "testing",  # test-only changes
]

# Positive keywords that indicate bug fixes (require stronger evidence)
POSITIVE_KEYWORDS = [
    "fix", "bug", "error", "crash", "issue",
    "resolve", "defect", "failure", "hotfix",
    "incorrect", "exception", "broken",
    "leak", "null", "npe", "segfault", "overflow",
    "deadlock", "race", "timeout", "hang",
]

# Advanced NLP Phrasing matching exact intent:
NLP_PHRASES = [
    r"\bfix(?:es|ed)?\s+(?:bug|issue|error|crash)",  # "fixes bug", "fixed issue"
    r"\bresolve(?:s|d)?\s+(?:bug|issue|error)",  # "resolves bug"
    r"handle crash", r"prevent null", r"resolve timeout",
    r"memory leak", r"null pointer", r"edge case",
    r"regression", r"out of bounds", r"race condition",
    r"deadlock", r"security vulnerability", r"security fix",
    r"\brevert\b",  # revert commits are strong bug signals
]

# GitHub/Jira Issue Regex - STRICTER version
# Matches e.g. "fixes #123", "closes #45", "resolves JIRA-1234"
ISSUE_REGEX = re.compile(
    r"(?:fix(?:es|ed)?|resolv(?:es|ed)?|clos(?:es|ed)?|patch(?:es|ed)?)\s+(?:#\d+|[A-Z]+-\d+)",
    re.IGNORECASE
)

# Revert commit detection
REVERT_REGEX = re.compile(r"\brevert\b|\brollback\b|\bundo\b", re.IGNORECASE)

# Confidence weight scoring based on commit message strength
CONFIDENCE_WEIGHTS = {
    # High confidence (1.0) - explicit bug fixes with issue refs
    "fix": 0.9, "bug": 0.9, "error": 0.9, "crash": 1.0,
    "resolve": 0.85, "defect": 0.9, "failure": 0.9, "hotfix": 1.0,
    
    # Medium confidence (0.7) - issue references
    "issue": 0.7, "incorrect": 0.75, "exception": 0.8, "broken": 0.8,
    
    # Lower confidence (0.5) - general maintenance
    "handle": 0.5, "prevent": 0.5, "avoid": 0.5, "correct": 0.6,
    "missing": 0.5, "invalid": 0.6, "edge": 0.5, "case": 0.4,
}

def get_commit_confidence(message: str) -> float:
    """Calculate confidence weight based on commit message keywords.
    
    Research-based scoring:
    - Issue tracker refs: +0.25 boost (strong signal)
    - Revert commits: +0.35 boost (very strong signal)
    - NLP phrases: +0.15 boost
    - Multiple signals: additive boost
    """
    if not message:
        return 0.15  # very low confidence for empty messages
    
    subject = message.strip().split("\n")[0].lower()
    max_confidence = 0.25  # baseline confidence
    
    # Check for negative keywords first (disqualifiers)
    for neg in NEGATIVE_KEYWORDS:
        if neg in subject:
            return 0.1  # Very low confidence for non-bug commits
    
    # Check positive keywords
    for keyword, weight in CONFIDENCE_WEIGHTS.items():
        if keyword in subject:
            max_confidence = max(max_confidence, weight)
    
    # Bonus for issue references (strong signal)
    has_issue_ref = ISSUE_REGEX.search(subject)
    if has_issue_ref:
        max_confidence = min(max_confidence + 0.25, 1.0)
    
    # Bonus for revert commits (very strong bug signal)
    is_revert = REVERT_REGEX.search(subject)
    if is_revert:
        max_confidence = min(max_confidence + 0.35, 1.0)
    
    # Bonus for NLP phrases
    for phrase in NLP_PHRASES:
        if re.search(phrase, subject):
            max_confidence = min(max_confidence + 0.15, 1.0)
            break  # Only count once
    
    return min(max_confidence, 1.0)

def has_substantive_code_changes(file_mod, language: str, min_churn_ratio: float = 0.05) -> bool:
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
    
    # Only label if >10% of file was changed
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
    """Normalize to forward-slash + lowercase for cross-platform matching.
    
    CRITICAL: This must produce identical output to labeling._norm_rel() for the same input.
    Normalization steps:
    1. Replace backslashes with forward slashes
    2. Convert to lowercase
    3. Strip leading './' and trailing '/'
    """
    normalized = filepath.replace("\\", "/").lower()
    # Strip leading './' (relative path prefix)
    if normalized.startswith("./"):
        normalized = normalized[2:]
    # Strip trailing '/'
    normalized = normalized.rstrip("/")
    return normalized


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

    if any(pos in subject for pos in POSITIVE_KEYWORDS):
        return True
        
    for phrase in NLP_PHRASES:
        if re.search(phrase, subject):
            return True
            
    if ISSUE_REGEX.search(subject):
        return True

    return False


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

def extract_bug_labels_with_confidence(repo_path, cache_dir=None, label_window_days=730, min_confidence=0.35):
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
        dict: {file_path: confidence_weight} for buggy files
    """

    cached = _load_szz_cache(repo_path, cache_dir)
    if cached is not None:
        return cached

    buggy_files = {}  # dict with confidence weights
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
    
    print(f"  SZZ v2.6 (churn-weighted): Using {label_window_days}-day window, min_confidence={min_confidence:.1%}, min_churn=5%")
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

        # Filter 3: Size cap - skip commits touching more than 15 files
        if len(commit.modified_files) > 15:
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
            
            # Filter 5: Check for substantive code changes (>5% of file)
            lang = get_language(path)
            if not has_substantive_code_changes(file, lang, min_churn_ratio=0.05):
                skipped_trivial_changes += 1
                continue

            # FILE-LEVEL SZZ MAPPING with confidence
            if fp_norm not in buggy_files:
                buggy_files[fp_norm] = commit_confidence
                buggy_messages[fp_norm] = set()
            else:
                # Take maximum confidence across all bug-fix commits
                buggy_files[fp_norm] = max(buggy_files[fp_norm], commit_confidence)
            buggy_messages[fp_norm].add(commit.msg)
            blame_hits += 1

    print(
        f"  SZZ v2.6 (churn-weighted): {fix_commits} high-confidence fix-commits ("
        f"skipped: {skipped_old_commits} old, "
        f"{skipped_large_commits} large, "
        f"{skipped_merge_commits} merge, "
        f"{skipped_low_confidence} low-conf, "
        f"{skipped_trivial_changes} trivial <5% churn) -> "
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
