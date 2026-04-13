import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feature_engineering.feature_builder import build_features, filter_correlated_features
from feature_engineering.labeler import create_labels
from git_mining.szz_labeler import is_bug_fix, is_test_file, is_generated_file


# ── is_bug_fix ─────────────────────────────────────────────────────────────────

def test_is_bug_fix_positive():
    assert is_bug_fix("fix null pointer in auth.py") is True
    assert is_bug_fix("bug: crash on empty input") is True
    assert is_bug_fix("resolve memory leak") is True

def test_is_bug_fix_negative_keywords():
    # NEG keywords override POS
    assert is_bug_fix("refactor: fix naming") is False
    assert is_bug_fix("docs: fix typo in readme") is False

def test_is_bug_fix_no_keywords():
    assert is_bug_fix("update dependencies") is False
    assert is_bug_fix("add new feature") is False

def test_is_bug_fix_uses_subject_line_only():
    # second line has fix but subject doesn't
    assert is_bug_fix("update config\n\nfix: something") is False


# ── is_test_file ───────────────────────────────────────────────────────────────

def test_is_test_file_path():
    assert is_test_file("project/tests/auth.py") is True
    assert is_test_file("project/test/utils.py") is True

def test_is_test_file_prefix():
    assert is_test_file("src/test_auth.py") is True     # test_ prefix
    assert is_test_file("src/auth_test.py") is True     # _test suffix (also caught below)
    assert is_test_file("src/test_utils.py") is True    # test_ prefix with underscore

def test_is_test_file_suffix():
    assert is_test_file("src/auth_test.py") is True

def test_is_test_file_false():
    assert is_test_file("src/auth.py") is False
    assert is_test_file("src/utils.py") is False


# ── is_generated_file ──────────────────────────────────────────────────────────

def test_is_generated_file_true():
    assert is_generated_file("node_modules/lodash/index.js") is True
    assert is_generated_file("dist/bundle.js") is True
    assert is_generated_file("build/output.py") is True
    assert is_generated_file("migrations/0001_initial.py") is True

def test_is_generated_file_false():
    assert is_generated_file("src/auth.py") is False
    assert is_generated_file("feature_engineering/builder.py") is False


# ── build_features ─────────────────────────────────────────────────────────────

def _make_static(file="repo/auth.py", loc=100, avg_cx=5.0, max_cx=10, funcs=8,
                  avg_params=2.0, max_fn_len=30):
    return [{"file": file, "loc": loc, "avg_complexity": avg_cx,
             "max_complexity": max_cx, "functions": funcs,
             "avg_params": avg_params, "max_function_length": max_fn_len}]

def _make_git(file="repo/auth.py"):
    return {
        file: {
            "commits": 20, "lines_added": 300, "lines_deleted": 150,
            "bug_fixes": 4, "author_count": 3, "ownership": 0.6,
            "low_history_flag": 0, "minor_contributor_ratio": 0.33,
            "recent_commits": 5, "file_age_days": 400,
            "days_since_last_change": 10, "max_added": 80,
            "commits_2w": 2, "commits_1m": 5, "commits_3m": 10,
            "past_bug_count": 4, "bug_fix_ratio": 0.2,
            "days_since_last_bug": 30, "last_commit_hash": "abc123"
        }
    }

def test_build_features_columns():
    df = build_features(_make_static(), _make_git())
    assert "file" in df.columns
    assert "loc" in df.columns
    # 'churn' column was removed (= lines_added + lines_deleted, perfectly correlated)
    assert "churn" not in df.columns
    assert "complexity_density" in df.columns
    assert "recent_churn_ratio" in df.columns
    assert "instability_score" in df.columns
    assert "days_since_last_bug" in df.columns
    assert "commit_hash" in df.columns
    assert "file_age_bucket" in df.columns
    assert "recency_ratio" in df.columns
    assert "avg_params" in df.columns
    assert "max_function_length" in df.columns
    assert "file_age_days" not in df.columns

def test_build_features_instability_uses_churn():
    df = build_features(_make_static(loc=100), _make_git())
    # instability_score = (lines_added + lines_deleted) / loc
    assert abs(df.iloc[0]["instability_score"] - (300 + 150) / 100) < 1e-9

def test_build_features_no_division_by_zero():
    # loc=0, functions=0, commits=0 — should not raise
    static = [{"file": "x.py", "loc": 0, "avg_complexity": 0,
                "max_complexity": 0, "functions": 0,
                "avg_params": 0, "max_function_length": 0}]
    git = {}
    df = build_features(static, git)
    # commit_hash is None for files with no git history — that is expected
    numeric_cols = df.select_dtypes(include="number").columns
    assert not df[numeric_cols].isnull().any().any()

def test_build_features_missing_git_defaults():
    df = build_features(_make_static(), {})
    assert df.iloc[0]["commits"] == 1          # default 0 → clamped to 1
    assert df.iloc[0]["lines_added"] == 0      # no git history → zero churn
    assert df.iloc[0]["lines_deleted"] == 0    # churn col removed; check components

def test_build_features_complexity_density():
    df = build_features(_make_static(loc=100, avg_cx=10.0), _make_git())
    assert abs(df.iloc[0]["complexity_density"] - 10.0 / 100) < 1e-9


# ── filter_correlated_features ─────────────────────────────────────────────────

def test_filter_drops_highly_correlated():
    np.random.seed(0)
    base = np.random.rand(100)
    df = pd.DataFrame({
        "file": ["f.py"] * 100,
        "buggy": (base > 0.5).astype(int),
        "feat_a": base,
        "feat_b": base + np.random.rand(100) * 0.01,  # near-perfect correlation
        "feat_c": np.random.rand(100),                 # independent
    })
    result = filter_correlated_features(df)
    # one of feat_a / feat_b should be dropped
    assert not ("feat_a" in result.columns and "feat_b" in result.columns)
    assert "feat_c" in result.columns

def test_filter_keeps_all_if_no_high_corr():
    np.random.seed(1)
    df = pd.DataFrame({
        "file": ["f.py"] * 50,
        "buggy": np.random.randint(0, 2, 50),
        "feat_a": np.random.rand(50),
        "feat_b": np.random.rand(50),
        "feat_c": np.random.rand(50),
    })
    result = filter_correlated_features(df)
    assert "feat_a" in result.columns
    assert "feat_b" in result.columns
    assert "feat_c" in result.columns


# ── create_labels fallback heuristic ──────────────────────────────────────────

def test_create_labels_fallback_marks_buggy(monkeypatch):
    # patch extract_bug_labels to return empty set so fallback triggers
    import feature_engineering.labeler as labeler_mod
    monkeypatch.setattr(
        "feature_engineering.labeler.extract_bug_labels",
        lambda repo_path, cache_dir=None: set()
    )
    df = build_features(_make_static(), _make_git())
    df = labeler_mod.create_labels(df, "fake/repo")
    assert "buggy" in df.columns
    assert df["buggy"].isin([0, 1]).all()

def test_create_labels_fallback_clean_file(monkeypatch):
    import feature_engineering.labeler as labeler_mod
    monkeypatch.setattr(
        "feature_engineering.labeler.extract_bug_labels",
        lambda repo_path, cache_dir=None: set()
    )
    static = [{"file": "clean.py", "loc": 50, "avg_complexity": 1.0,
                "max_complexity": 2, "functions": 3,
                "avg_params": 1.0, "max_function_length": 10}]
    git = {
        "clean.py": {
            "commits": 100, "lines_added": 10, "lines_deleted": 5,
            "bug_fixes": 0, "author_count": 1, "ownership": 1.0,
            "low_history_flag": 0, "minor_contributor_ratio": 0.0,
            "file_age_days": 200,
            "days_since_last_change": 100, "max_added": 5,
            "commits_2w": 0, "commits_1m": 0, "commits_3m": 0,
            "past_bug_count": 0, "bug_fix_ratio": 0.0,
            "days_since_last_bug": -1, "last_commit_hash": "def456"
        }
    }
    df = build_features(static, git)
    df = labeler_mod.create_labels(df, "fake/repo")
    assert df.iloc[0]["buggy"] == 0
