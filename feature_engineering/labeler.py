import os

from git_mining.szz_labeler import extract_bug_labels, audit_labels
from config import BUG_DENSITY_THRESH, MIN_BUG_FIXES_FALLBACK


def _norm_rel(filepath, repo_path):
    """
    Return a normalized (forward-slash, lowercase) relative path.
    Used to match absolute analyzer paths against PyDriller relative paths.
    """
    try:
        rel = os.path.relpath(filepath, repo_path)
    except ValueError:
        # Different drives on Windows — fall back to basename match
        rel = os.path.basename(filepath)
    return rel.replace("\\", "/").lower()


def create_labels(df, repo_path, cache_dir=None):
    """
    Attach a 'buggy' column (0/1) to df.

    Primary path: SZZ file-level labels — files that appeared in bug-fix
    commits are marked buggy. Matching uses normalized relative paths to
    work correctly on Windows (where analyzer returns absolute paths and
    PyDriller returns forward-slash relative paths).

    Fallback (if SZZ finds no signal): simple heuristic from git features.

    Audit is printed AFTER matching so the reported numbers reflect actual
    analysis-set files (not deleted/renamed paths from SZZ).
    """
    buggy_files = extract_bug_labels(repo_path, cache_dir=cache_dir)

    df = df.copy()

    if buggy_files:
        df["buggy"] = df["file"].apply(
            lambda fp: 1 if _norm_rel(fp, repo_path) in buggy_files else 0
        ).astype(int)
        df["bug_density"] = df["buggy"].astype(float)

        # Audit AFTER matching: meaningful numbers
        matched_buggy = int(df["buggy"].sum())
        audit_labels(
            buggy_count=matched_buggy,
            total_files=len(df),
            szz_raw_count=len(buggy_files),
        )

    else:
        # fallback: structural heuristic — no SZZ signal available
        df["bug_density"] = df["bug_fixes"] / df["commits"].clip(lower=1)
        df["buggy"] = (
            (df["bug_density"] > BUG_DENSITY_THRESH)
            | (df["bug_fixes"] >= MIN_BUG_FIXES_FALLBACK)
        ).astype(int)

        matched_buggy = int(df["buggy"].sum())
        audit_labels(
            buggy_count=matched_buggy,
            total_files=len(df),
            szz_raw_count=0,
        )

    return df
