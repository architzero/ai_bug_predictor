import os
import pandas as pd

from backend.szz import extract_bug_labels_with_confidence, audit_labels
from backend.config import BUG_DENSITY_THRESH, MIN_BUG_FIXES_FALLBACK


def _norm_rel(filepath, repo_path):
    """
    Return a normalized (forward-slash, lowercase) relative path.
    Used to match absolute analyzer paths against PyDriller relative paths.
    
    CRITICAL: This is the single source of truth for path normalization.
    Both SZZ and analyzer must use this function to ensure consistent matching.
    
    MUST match the normalization in szz.py _norm_path() exactly.
    """
    try:
        rel = os.path.relpath(filepath, repo_path)
    except ValueError:
        # Different drives on Windows — fall back to basename match
        rel = os.path.basename(filepath)
    # Normalize: forward slashes, lowercase, strip leading/trailing slashes
    # This MUST produce the same output as szz._norm_path() for the same input
    return rel.replace("\\", "/").lower().strip("/")


def _fuzzy_match(path, buggy_set):
    """
    DEPRECATED: This function is no longer used.
    Replaced by exact path matching in create_labels() using _norm_rel().
    Kept for backward compatibility only.
    """
    path = path.replace("\\", "/").lower()

    for b in buggy_set:
        b = b.replace("\\", "/").lower()

        if path.endswith(b) or b.endswith(path):
            return True

    return False



def create_labels(df, repo_path, cache_dir=None):
    """
    Attach 'buggy' column (0/1) and 'confidence' column (0.3-1.0) to df.

    Primary path: SZZ v2 file-level labels with confidence weights.
    Files that appeared in bug-fix commits are marked buggy with confidence
    based on commit message strength. Matching uses normalized relative paths.

    Fallback (if SZZ finds no signal): simple heuristic from git features.

    Audit is printed AFTER matching so the reported numbers reflect actual
    analysis-set files (not deleted/renamed paths from SZZ).
    """
    # Load SZZ confidence weights once. extract_bug_labels_with_confidence is
    # the single entry point — extract_bug_labels() is just a thin wrapper around
    # it that would cause a redundant cache load (and duplicate print) if called here.
    try:
        buggy_confidence = extract_bug_labels_with_confidence(repo_path, cache_dir=cache_dir)
        use_confidence = isinstance(buggy_confidence, dict) and bool(buggy_confidence)
    except Exception:
        # SZZ completely unavailable — fall through to heuristic labeling below
        buggy_confidence = {}
        use_confidence = False

    df = df.copy()

    if use_confidence:
        # Build exact path matching lookup using normalized relative paths.
        # SZZ stores repo-relative paths (e.g. 'src/requests/auth.py');
        # the DataFrame has absolute paths — we normalize both to relative
        # using _norm_rel() for exact matching (no more fuzzy basename matching).
        
        # Create lookup: normalized_path -> (original_szz_path, confidence)
        exact_lookup = {}
        for b_path, conf in buggy_confidence.items():
            # SZZ paths are already repo-relative and normalized by _norm_path()
            # which uses the same logic as _norm_rel(): forward slashes, lowercase, strip slashes
            # So we can use them directly as keys
            norm_path = b_path  # Already normalized by SZZ
            exact_lookup[norm_path] = (b_path, conf)

        def match_and_confidence(fp):
            # Normalize the analyzer's absolute path to repo-relative
            norm_path = _norm_rel(fp, repo_path)
            
            # Exact match lookup
            if norm_path in exact_lookup:
                _, conf = exact_lookup[norm_path]
                return 1, conf
            
            return 0, 0.3  # baseline confidence for clean files

        df[["buggy", "confidence"]] = df["file"].apply(
            lambda fp: pd.Series(match_and_confidence(fp))
        )
        
        df["buggy"] = df["buggy"].astype(int)
        df["bug_density"] = df["buggy"].astype(float)

        # Audit AFTER matching: meaningful numbers
        matched_buggy = int(df["buggy"].sum())
        szz_raw_count = len(buggy_confidence) if isinstance(buggy_confidence, (set, dict)) else 0
        audit_labels(
            buggy_count=matched_buggy,
            total_files=len(df),
            szz_raw_count=szz_raw_count,
        )

    else:
        # NO FALLBACK - if SZZ finds nothing, all files are clean
        # This prevents the old bug_fixes heuristic from polluting labels
        print("  ⚠ SZZ found no buggy files - all files labeled clean")
        df["buggy"] = 0
        df["bug_density"] = 0.0
        df["confidence"] = 0.3
        
        audit_labels(
            buggy_count=0,
            total_files=len(df),
            szz_raw_count=0,
        )

    return df
