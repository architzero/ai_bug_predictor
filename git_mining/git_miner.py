"""
Git history miner.

Extracts per-file metrics from a git repository.
Caches results by HEAD hash so re-runs are near-instant.
"""

from pydriller import Repository
from collections import defaultdict
from datetime import datetime, timezone
import os
import pickle
import subprocess

from config import CHECKPOINT_DIR as _CHECKPOINT_DIR, MINER_CACHE_DIR as _MINER_CACHE_DIR
from git_mining.szz_labeler import is_bug_fix   # single authoritative implementation
from static_analysis.analyzer import SUPPORTED_EXTENSIONS

CHECKPOINT_DIR  = _CHECKPOINT_DIR
MINER_CACHE_DIR = _MINER_CACHE_DIR


# ── HEAD hash (cache key) ──────────────────────────────────────────────────────

def _get_head_hash(repo_path):
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip() or None
    except Exception:
        return None


# ── Result cache (persists between runs) ───────────────────────────────────────

def _repo_key(repo_path):
    return repo_path.replace("/", "_").replace("\\", "_").replace(":", "_")


def _miner_cache_path(repo_path):
    return os.path.join(MINER_CACHE_DIR, f"{_repo_key(repo_path)}.pkl")


def _load_miner_cache(repo_path):
    path = _miner_cache_path(repo_path)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            cached = pickle.load(f)
        head = _get_head_hash(repo_path)
        if head and cached.get("head_hash") == head:
            print(f"  Loaded mining cache for {os.path.basename(repo_path)}")
            # restore as defaultdict so new keys can be added later
            file_metrics = defaultdict(lambda: {
                "commits": 0, "lines_added": 0, "lines_deleted": 0,
                "bug_fixes": 0, "authors": set(), "author_commits": defaultdict(int),
                "first_commit": None, "last_commit": None, "last_commit_hash": None,
                "max_added": 0, "commits_2w": 0, "commits_1m": 0, "commits_3m": 0,
                "last_bug_date": None, "past_bug_count": 0, "co_changes": defaultdict(int),
            })
            file_metrics.update(cached["file_metrics"])
            return file_metrics
    except Exception:
        pass
    return None


def _save_miner_cache(repo_path, file_metrics):
    os.makedirs(MINER_CACHE_DIR, exist_ok=True)
    head = _get_head_hash(repo_path)
    path = _miner_cache_path(repo_path)
    serializable = {
        file: {
            k: (list(v) if isinstance(v, set)
                else dict(v) if isinstance(v, defaultdict)
                else v)
            for k, v in data.items()
        }
        for file, data in file_metrics.items()
    }
    with open(path, "wb") as f:
        pickle.dump({"file_metrics": serializable, "head_hash": head}, f)


# ── Checkpoint helpers (for resuming interrupted runs) ─────────────────────────

def _checkpoint_path(repo_path):
    safe = repo_path.replace("/", "_").replace("\\", "_")
    return os.path.join(CHECKPOINT_DIR, f"{safe}.pkl")


def _load_checkpoint(repo_path):
    path = _checkpoint_path(repo_path)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
        except (EOFError, pickle.UnpicklingError):
            print("  Corrupted checkpoint — starting fresh")
            os.remove(path)
            return None, set()
        print(f"  Resuming from checkpoint: {data['processed']} commits processed")
        file_metrics = defaultdict(lambda: {
            "commits": 0, "lines_added": 0, "lines_deleted": 0,
            "bug_fixes": 0, "authors": set(), "author_commits": defaultdict(int),
            "first_commit": None, "last_commit": None, "last_commit_hash": None,
            "max_added": 0, "commits_2w": 0, "commits_1m": 0, "commits_3m": 0,
            "last_bug_date": None, "past_bug_count": 0, "co_changes": defaultdict(int),
        })
        for file, metrics in data["file_metrics"].items():
            if "co_changes" in metrics and isinstance(metrics["co_changes"], dict):
                co_ch = defaultdict(int)
                co_ch.update(metrics["co_changes"])
                metrics["co_changes"] = co_ch
            file_metrics[file].update(metrics)
        return file_metrics, data["processed_hashes"]
    return None, set()


def _save_checkpoint(repo_path, file_metrics, processed_hashes):
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    path = _checkpoint_path(repo_path)
    serializable = {
        file: {
            k: (set(v) if isinstance(v, set)
                else dict(v) if isinstance(v, defaultdict)
                else v)
            for k, v in data.items()
        }
        for file, data in file_metrics.items()
    }
    with open(path, "wb") as f:
        pickle.dump({
            "file_metrics": serializable,
            "processed_hashes": processed_hashes,
            "processed": len(processed_hashes)
        }, f)


def _clear_checkpoint(repo_path):
    path = _checkpoint_path(repo_path)
    if os.path.exists(path):
        os.remove(path)


# ── Main entry point ───────────────────────────────────────────────────────────

def mine_git_data(repo_path, use_checkpoint=True, use_cache=True):
    """
    Extract per-file git metrics from repo_path.

    use_cache=True (default): load from .cache/miner/ if HEAD unchanged.
    use_checkpoint=True: resume interrupted mining from last checkpoint.
    """
    # ── Fast path: result cache ────────────────────────────────────────────────
    if use_cache:
        cached = _load_miner_cache(repo_path)
        if cached is not None:
            return cached

    now       = datetime.now(timezone.utc)
    cutoff_2w = 14
    cutoff_1m = 30
    cutoff_3m = 90

    file_metrics, processed_hashes = (
        _load_checkpoint(repo_path) if use_checkpoint else (None, set())
    )

    if file_metrics is None:
        file_metrics = defaultdict(lambda: {
            "commits": 0,
            "lines_added": 0,
            "lines_deleted": 0,
            "bug_fixes": 0,
            "authors": set(),
            "author_commits": defaultdict(int),
            "first_commit": None,
            "last_commit": None,
            "last_commit_hash": None,
            "max_added": 0,
            "commits_2w": 0,
            "commits_1m": 0,
            "commits_3m": 0,
            "last_bug_date": None,
            "past_bug_count": 0,
            "co_changes": defaultdict(int),
        })

    count           = 0
    CHECKPOINT_EVERY = 1000

    try:
        for commit in Repository(repo_path, only_no_merge=True).traverse_commits():

            if commit.hash in processed_hashes:
                continue

            # use the shared, authoritative is_bug_fix from szz_labeler
            commit_is_bug_fix = is_bug_fix(commit.msg)

            commit_time = commit.committer_date
            if commit_time.tzinfo is None:
                commit_time = commit_time.replace(tzinfo=timezone.utc)

            age_days = (now - commit_time).days

            # Max Files Guard
            valid_paths = []
            for modified_file in commit.modified_files:
                path = modified_file.new_path or modified_file.old_path
                if not path:
                    continue
                if not path.endswith(SUPPORTED_EXTENSIONS):
                    continue
                valid_paths.append(os.path.normpath(os.path.join(repo_path, path)))

            track_co_changes = 1 < len(valid_paths) <= 30
            commit_paths = valid_paths

            for modified_file in commit.modified_files:

                path = modified_file.new_path
                if path is None:
                    continue

                full_path = os.path.normpath(
                    os.path.join(repo_path, path)
                )
                d = file_metrics[full_path]

                d["commits"]       += 1
                d["lines_added"]   += modified_file.added_lines
                d["lines_deleted"] += modified_file.deleted_lines
                d["max_added"]      = max(d["max_added"], modified_file.added_lines)

                author = commit.author.name
                d["authors"].add(author)
                d["author_commits"][author] += 1

                if d["first_commit"] is None:
                    d["first_commit"] = commit_time
                d["last_commit"]      = commit_time
                d["last_commit_hash"] = commit.hash

                if age_days < cutoff_2w:
                    d["commits_2w"] += 1
                if age_days < cutoff_1m:
                    d["commits_1m"] += 1
                if age_days < cutoff_3m:
                    d["commits_3m"] += 1

                if commit_is_bug_fix:
                    d["bug_fixes"]      += 1
                    d["past_bug_count"] += 1
                    d["last_bug_date"]   = commit_time

                if track_co_changes:
                    for other_path in commit_paths:
                        if other_path != full_path:
                            d["co_changes"][other_path] += 1

            processed_hashes.add(commit.hash)
            count += 1

            if use_checkpoint and count % CHECKPOINT_EVERY == 0:
                _save_checkpoint(repo_path, file_metrics, processed_hashes)
                print(f"  Checkpoint saved ({count} commits)")

    except Exception as e:
        print(f"  Mining interrupted: {e}")
        if use_checkpoint:
            _save_checkpoint(repo_path, file_metrics, processed_hashes)
            print(f"  Progress saved — re-run to resume from commit {len(processed_hashes)}")
        raise

    # ── Finalize: derived metrics ──────────────────────────────────────────────
    for full_path, d in file_metrics.items():

        commits = d["commits"] if d["commits"] > 0 else 1

        d["author_count"] = len(d["authors"])
        
        # ── Logical Coupling ──
        max_coupled_file = None
        max_coupled_count = 0
        if "co_changes" in d:
            for other_path, count in d["co_changes"].items():
                if count > max_coupled_count:
                    max_coupled_count = count
                    max_coupled_file = other_path
            
            if max_coupled_file and max_coupled_file in file_metrics and commits > 0:
                d["max_coupling_strength"] = max_coupled_count / commits
                d["coupled_file_count"] = len(d["co_changes"])
                
                partner_last_commit = file_metrics[max_coupled_file].get("last_commit")
                if d.get("last_commit") and partner_last_commit and d.get("last_commit") > partner_last_commit:
                    d["coupled_recent_missing"] = 1
                else:
                    d["coupled_recent_missing"] = 0
                    
                d["coupling_risk"] = d["max_coupling_strength"] * d["coupled_recent_missing"]
            else:
                d["max_coupling_strength"] = 0.0
                d["coupled_file_count"] = 0
                d["coupled_recent_missing"] = 0
                d["coupling_risk"] = 0.0
                
            del d["co_changes"]

        if commits >= 5 and d["author_commits"]:
            d["ownership"]       = max(d["author_commits"].values()) / commits
            d["low_history_flag"] = 0
        else:
            d["ownership"]       = 0
            d["low_history_flag"] = 1

        if d["author_count"] > 0:
            minor = sum(1 for c in d["author_commits"].values() if c == 1)
            d["minor_contributor_ratio"] = minor / d["author_count"]
        else:
            d["minor_contributor_ratio"] = 0

        if d["first_commit"] and d["last_commit"]:
            d["file_age_days"]          = (d["last_commit"] - d["first_commit"]).days
            d["days_since_last_change"] = (now - d["last_commit"]).days
        else:
            d["file_age_days"]          = 0
            d["days_since_last_change"] = 0

        d["days_since_last_bug"] = (
            (now - d["last_bug_date"]).days if d["last_bug_date"] else -1
        )

        d["bug_fix_ratio"] = d["past_bug_count"] / commits

        # clean up intermediate state
        del d["authors"]
        del d["author_commits"]
        del d["first_commit"]
        del d["last_commit"]
        del d["last_bug_date"]

    # clear interrupted-run checkpoint; save result cache
    if use_checkpoint:
        _clear_checkpoint(repo_path)
    if use_cache:
        _save_miner_cache(repo_path, file_metrics)

    return file_metrics
