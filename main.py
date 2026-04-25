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
from bug_type_classification.integrator import train_bug_type_classifier, classify_file_bugs
from config import REPOS, TOP_LOCAL_PLOTS, SZZ_CACHE_DIR, GIT_FEATURES_TO_NORMALIZE
from sklearn.preprocessing import StandardScaler

# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 1 — Data Collection
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 72)
print("  STAGE 1  ·  DATA COLLECTION")
print("═" * 72)

all_data = []
for repo_path in REPOS:
    repo_name = os.path.basename(repo_path)
    static_results = analyze_repository(repo_path)
    git_results    = mine_git_data(repo_path)
    df = build_features(static_results, git_results)
    df = create_labels(df, repo_path, cache_dir=SZZ_CACHE_DIR)
    df["repo"] = repo_path
    buggy = int(df["buggy"].sum())
    print(f"  ✓  {repo_name:<20}  {len(df):>5} files  |  {buggy:>4} labelled buggy")
    all_data.append(df)

# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 2 — Feature Pipeline
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 72)
print("  STAGE 2  ·  FEATURE PIPELINE")
print("═" * 72)

df = pd.concat(all_data, ignore_index=True)

cols_present = [c for c in GIT_FEATURES_TO_NORMALIZE if c in df.columns]
if cols_present:
    scaler = StandardScaler()
    df[cols_present] = scaler.fit_transform(df[cols_present])
    print(f"  Global StandardScaler applied  →  {len(cols_present)} git features  |  {len(df)} total files")
else:
    scaler = None

df = filter_correlated_features(df)

# ── Bug Type Classification ────────────────────────────────────────────────
print(f"\n  Bug type classifier ...")
bug_classifier = train_bug_type_classifier(REPOS, SZZ_CACHE_DIR)
df = classify_file_bugs(df, bug_classifier, SZZ_CACHE_DIR)

buggy_df = df[df["buggy"] == 1]
type_dist = buggy_df["bug_type"].value_counts()
print(f"\n  Dataset summary  →  {len(df)} files  |  {int(df['buggy'].sum())} buggy")
print(f"  Bug type distribution (buggy files only):")
for btype, cnt in type_dist.items():
    pct = cnt / len(buggy_df) * 100
    bar = "█" * max(1, int(pct / 2.5))
    print(f"    {btype:<20} {cnt:>5}  ({pct:5.1f}%)  {bar}")

# ── Filename overlap integrity check ──────────────────────────────────────
basename_repos = defaultdict(set)
for _, row in df.iterrows():
    basename_repos[os.path.basename(str(row["file"]))].add(
        os.path.basename(str(row["repo"]))
    )
overlapping = {k: v for k, v in basename_repos.items() if len(v) > 1}
if overlapping:
    print(f"\n  ⚠  {len(overlapping)} filename(s) shared across repos (verify no label leak):")
    for fname in sorted(overlapping)[:6]:
        print(f"     {fname:<35} → {overlapping[fname]}")
else:
    print("\n  ✓  No filename overlap between repos")

# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 3 — Model Training
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 72)
print("  STAGE 3  ·  CROSS-PROJECT MODEL TRAINING")
print("═" * 72)

df_for_ablation = df.copy()
model = train_model(df, REPOS)

# Attach the training scaler so inference (app_ui.py) applies identical scaling.
# XGBoost is scale-invariant so this has no effect on tree-based predictions, but
# it ensures LR/RF fallback paths and future linear layers stay consistent.
if scaler is not None and isinstance(model, dict):
    model["scaler"] = scaler
    import joblib, os
    joblib.dump(model, os.path.join("model", "bug_predictor_latest.pkl"))
    print(f"  Scaler persisted inside model artifact")

# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 4 — Prediction + Explanations
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 72)
print("  STAGE 4  ·  RISK PREDICTION")
print("═" * 72)

df = predict(model, df)
df = explain_prediction(model, df, save_plots=True, top_local=TOP_LOCAL_PLOTS)

# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 5 — Final Risk Report
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 72)
print("  GITSENTINEL  ·  FINAL RISK REPORT")
print("═" * 72)

TOP_N = 10

for repo_path in REPOS:
    repo_name = os.path.basename(repo_path)
    repo_df   = df[df["repo"] == repo_path].copy()

    if repo_df.empty:
        continue

    buggy_count = int(repo_df["buggy"].sum())
    risky_count = int(repo_df["risky"].sum())
    total       = len(repo_df)

    print(f"\n  ┌─ {repo_name}  ({total} files │ {buggy_count} buggy │ {risky_count} flagged risky)")

    top_risky = (
        repo_df
        .sort_values("risk", ascending=False)
        .head(TOP_N)
        [["file", "risk", "buggy", "bug_type", "explanation"]]
        .reset_index(drop=True)
    )

    for i, row in top_risky.iterrows():
        fname    = os.path.relpath(str(row["file"]), repo_path)
        risk_pct = f"{row['risk']:.0%}"
        label    = "BUG" if row["buggy"] == 1 else "   "
        btype    = str(row.get("bug_type", "unknown"))
        expl     = textwrap.shorten(str(row["explanation"]), width=45, placeholder="…")

        if row["risk"] >= 0.80:
            sev = "CRITICAL"
        elif row["risk"] >= 0.60:
            sev = "HIGH    "
        elif row["risk"] >= 0.40:
            sev = "MODERATE"
        else:
            sev = "LOW     "

        prefix = "  │" if i < len(top_risky) - 1 else "  └"
        print(f"  │  {risk_pct:>5}  [{label}]  {sev}  {fname:<38}  {btype:<16}  {expl}")

        # Function-level detail (top-2 most complex)
        funcs = get_top_functions(str(row["file"]), top_n=2)
        for fn in funcs:
            print(f"  │             ↳  {fn['name']:<30}  cx={fn['complexity']:>3}  len={fn['length']:>4}")

print(f"\n{'═' * 72}")

# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 6 — Commit Risk Simulation
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 72)
print("  STAGE 6  ·  COMMIT RISK SIMULATION")
print("═" * 72)

source_files = df[~df["file"].str.lower().str.contains("test")]["file"]
changed      = source_files.sample(min(3, len(source_files)), random_state=42).tolist()
risk_score, risky_df = predict_commit_risk(df, changed)

print(f"\n  Simulated changed files ({len(changed)}):")
for f in changed:
    print(f"    • {os.path.basename(f)}")

risk_label = "CRITICAL" if risk_score >= 0.8 else "HIGH" if risk_score >= 0.6 else "MODERATE" if risk_score >= 0.4 else "LOW"
print(f"\n  Commit risk score : {risk_score:.2f}  [{risk_label}]")

if not risky_df.empty:
    top = risky_df.sort_values("risk", ascending=False).iloc[0]
    print(f"  Highest-risk file : {os.path.basename(str(top['file']))}  →  {top['risk']:.1%}")

# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 7 — Ablation Study
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 72)
print("  STAGE 7  ·  ABLATION STUDY")
print("═" * 72)

global_feats = model.get("features", None) if isinstance(model, dict) else None
run_ablation_study(df_for_ablation, global_features=global_feats)

print("\n" + "═" * 72)
print("  PIPELINE COMPLETE")
print("═" * 72 + "\n")
