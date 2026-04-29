import os
import textwrap
from collections import defaultdict

import pandas as pd

from static_analysis.analyzer import analyze_repository, get_top_functions
from git_mining.git_miner import mine_git_data
from feature_engineering.feature_builder import build_features, filter_correlated_features
from feature_engineering.labeler import create_labels
from model.train_model import train_model, run_ablation_study
from model.predict import predict
from explainability.explainer import explain_prediction
from model.commit_predictor import predict_commit_risk
from config import REPOS, TOP_LOCAL_PLOTS, SZZ_CACHE_DIR

# ── 1. Data collection ────────────────────────────────────────────────────────
all_data = []

for repo_path in REPOS:
    print(f"\nProcessing {repo_path}")

    static_results = analyze_repository(repo_path)
    git_results    = mine_git_data(repo_path)

    df = build_features(static_results, git_results)
    df = create_labels(df, repo_path, cache_dir=SZZ_CACHE_DIR)
    df["repo"] = repo_path

    all_data.append(df)

# ── 2. Feature pipeline ───────────────────────────────────────────────────────
from sklearn.preprocessing import StandardScaler

GIT_FEATURES_TO_NORMALIZE = [
    'commits', 'lines_added', 'lines_deleted',
    'commits_2w', 'commits_1m', 'commits_3m',
    'recent_churn_ratio', 'recent_activity_score',
    'instability_score', 'avg_commit_size',
    'max_commit_size', 'max_commit_ratio',
    'max_added', 'author_count',
    'minor_contributor_ratio'
]

normalized_dfs = []
for repo_df in all_data:
    df_copy = repo_df.copy()
    cols_present = [c for c in GIT_FEATURES_TO_NORMALIZE if c in df_copy.columns]
    if cols_present:
        scaler = StandardScaler()
        df_copy[cols_present] = scaler.fit_transform(df_copy[cols_present])
    normalized_dfs.append(df_copy)

df = pd.concat(normalized_dfs, ignore_index=True)
df = filter_correlated_features(df)

print("\nTOTAL FILES:", len(df))
print("CLASS DISTRIBUTION:")
print(df["buggy"].value_counts())

# ── 2b. Data integrity check — filename overlap between repos ─────────────────
basename_repos = defaultdict(set)
for _, row in df.iterrows():
    basename_repos[os.path.basename(str(row["file"]))].add(
        os.path.basename(str(row["repo"]))
    )
overlapping = {k: v for k, v in basename_repos.items() if len(v) > 1}
if overlapping:
    print(f"\n⚠  {len(overlapping)} filename(s) appear in multiple repos "
          "(common names like 'utils.py' are expected — verify no test/label leak):")
    for fname in sorted(overlapping)[:8]:
        print(f"   {fname:<35} → {overlapping[fname]}")
else:
    print("\n✓ No filename overlap between repos")

# ── 3. Training ───────────────────────────────────────────────────────────────
print("\nTRAINING MODEL")
# Keep a clean copy for ablation (before predict() adds risk/risky/explanation cols)
df_for_ablation = df.copy()
model = train_model(df, REPOS)

# ── 4. Prediction + SHAP ─────────────────────────────────────────────────────
print("\nPREDICTING RISK")
df = predict(model, df)
df = explain_prediction(model, df, save_plots=True, top_local=TOP_LOCAL_PLOTS)

# ── 5. Final risk report ──────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  GITSENTINEL — FINAL RISK REPORT")
print("=" * 70)

TOP_N = 10

for repo_path in REPOS:
    repo_name = os.path.basename(repo_path)
    repo_df   = df[df["repo"] == repo_path].copy()

    buggy_count = int(repo_df["buggy"].sum())
    risky_count = int(repo_df["risky"].sum())
    total       = len(repo_df)

    print(f"\n{'─'*70}")
    print(f"  PROJECT : {repo_name}  ({total} files | {buggy_count} labelled buggy | {risky_count} flagged risky)")
    print(f"{'─'*70}")

    top_risky = (
        repo_df
        .sort_values("risk", ascending=False)
        .head(TOP_N)
        [["file", "risk", "buggy", "explanation"]]
        .reset_index(drop=True)
    )

    for _, row in top_risky.iterrows():
        fname    = os.path.relpath(str(row["file"]), repo_path)
        risk_pct = f"{row['risk']:.1%}"
        label    = "BUGGY" if row["buggy"] == 1 else "clean"
        expl     = str(row["explanation"])
        reason   = textwrap.shorten(expl, width=50, placeholder="...")
        print(f"  {risk_pct:>7}  [{label:^5}]  {fname:<40}  {reason}")

        # ── Function-level risk (top-3 most complex functions) ────────────
        funcs = get_top_functions(str(row["file"]), top_n=3)
        for fn in funcs:
            print(f"           ↳  {fn['name']:<32}  "
                  f"cx={fn['complexity']:>3}  len={fn['length']:>4}  "
                  f"params={fn['params']}")

print(f"\n{'='*70}")

# ── 6. Commit simulation ──────────────────────────────────────────────────────
print("\nSIMULATED COMMIT RISK CHECK")
print("─" * 40)

# sample 3 real source files (skip test files)
source_files = df[~df["file"].str.lower().str.contains("test")]["file"]
changed = source_files.sample(min(3, len(source_files)), random_state=42).tolist()

risk_score, risky_df = predict_commit_risk(df, changed)

print(f"Changed files ({len(changed)}):")
for f in changed:
    print(f"  • {os.path.basename(f)}")

print(f"\nCommit risk score : {risk_score:.2f}")

if not risky_df.empty:
    print("Highest-risk file in commit:")
    top = risky_df.sort_values("risk", ascending=False).iloc[0]
    print(f"  {os.path.basename(str(top['file']))}  →  {top['risk']:.1%}")

# ── 7. Ablation study ──────────────────────────────────────────────────────────────
print("\nABLATION STUDY")
# Use the clean pre-prediction df (predict() adds string columns that break SMOTE)
global_feats = model.get("features", None) if isinstance(model, dict) else None
run_ablation_study(df_for_ablation, global_features=global_feats)

