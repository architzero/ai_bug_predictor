import os
import textwrap
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

from backend.analysis import analyze_repository, get_top_functions
from backend.git_mining import mine_git_data
from backend.features import build_features, filter_correlated_features
from backend.labeling import create_labels
from backend.train import train_model, run_ablation_study
from backend.predict import predict
from backend.explainer import explain_prediction
from backend.commit_risk import predict_commit_risk
from backend.bug_integrator import train_bug_type_classifier, classify_file_bugs
from backend.config import REPOS, TOP_LOCAL_PLOTS, SZZ_CACHE_DIR, GIT_FEATURES_TO_NORMALIZE
from backend.szz import is_test_file, is_generated_file
from sklearn.preprocessing import StandardScaler

# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 0 — File Filtering Audit
# ══════════════════════════════════════════════════════════════════════════════

def audit_file_filtering(repo_path):
    """Generate detailed file filtering report."""
    all_files = []
    for root, dirs, files in os.walk(repo_path):
        # Skip .git directory
        if '.git' in root:
            continue
        for f in files:
            if f.endswith(('.py', '.js', '.ts', '.java', '.go', '.rb', '.php', '.cs', '.cpp', '.c', '.rs')):
                full_path = os.path.join(root, f)
                all_files.append(full_path)
    
    included = []
    excluded_test = []
    excluded_generated = []
    
    for f in all_files:
        if is_test_file(f):
            excluded_test.append(f)
        elif is_generated_file(f):
            excluded_generated.append(f)
        else:
            included.append(f)
    
    test_dirs = set()
    for f in excluded_test:
        parts = os.path.dirname(f).split(os.sep)
        for part in parts:
            if 'test' in part.lower() or 'spec' in part.lower():
                test_dirs.add(part)
                break
    
    gen_dirs = set()
    for f in excluded_generated:
        parts = os.path.dirname(f).split(os.sep)
        for part in parts:
            if part in ['node_modules', 'dist', 'build', 'vendor', '.venv', 'venv']:
                gen_dirs.add(part)
                break
    
    return {
        'total': len(all_files),
        'included': len(included),
        'excluded_test': len(excluded_test),
        'excluded_generated': len(excluded_generated),
        'test_dirs': test_dirs,
        'generated_dirs': gen_dirs
    }

# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 1 — Data Collection (PARALLELIZED)
# ══════════════════════════════════════════════════════════════════════════════

def process_repo(repo_path):
    """Process a single repository (for parallel execution)."""
    repo_name = os.path.basename(repo_path)
    # Enable parallel Lizard analysis (thread-safe, I/O bound)
    static_results = analyze_repository(repo_path, parallel=True, max_workers=4)
    git_results    = mine_git_data(repo_path)
    df = build_features(static_results, git_results)
    df = create_labels(df, repo_path, cache_dir=SZZ_CACHE_DIR)
    df["repo"] = repo_path
    buggy = int(df["buggy"].sum())
    return (repo_name, df, buggy)

if __name__ == '__main__':
    print("\n" + "═" * 72)
    print("  STAGE 0  ·  FILE FILTERING AUDIT")
    print("═" * 72)
    print(f"  {'Repo':<20} {'Total':<8} {'Included':<10} {'Excluded':<10} {'Drop %':<8} {'Key Excluded Dirs'}")
    print(f"  {'-'*90}")

    for repo_path in REPOS:
        audit = audit_file_filtering(repo_path)
        repo_name = os.path.basename(repo_path)
        drop_pct = (1 - audit['included'] / audit['total']) * 100 if audit['total'] > 0 else 0
        excluded_dirs = ', '.join(list(audit['test_dirs'] | audit['generated_dirs'])[:3])
        
        print(f"  {repo_name:<20} {audit['total']:<8} {audit['included']:<10} "
              f"{audit['total'] - audit['included']:<10} {drop_pct:>6.1f}%  {excluded_dirs}")

    print(f"\n  ✓ File filtering audit complete")
    print(f"  ✓ Verify excluded dirs are test/docs/generated (not src/core/lib)")

    print("\n" + "═" * 72)
    print("  STAGE 1  ·  DATA COLLECTION (Parallel Processing)")
    print("═" * 72)
    all_data = []
    max_workers = min(4, len(REPOS))  # Use up to 4 parallel workers

    print(f"  Using {max_workers} parallel workers for {len(REPOS)} repositories...")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_repo, repo): repo for repo in REPOS}
        
        for future in as_completed(futures):
            try:
                repo_name, df, buggy = future.result()
                print(f"  ✓  {repo_name:<20}  {len(df):>5} files  |  {buggy:>4} labelled buggy")
                all_data.append(df)
            except Exception as e:
                repo = futures[future]
                print(f"  ✗  {os.path.basename(repo):<20}  FAILED: {e}")

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
        joblib.dump(model, os.path.join("ml", "models", "bug_predictor_latest.pkl"))
        print(f"  Scaler persisted inside model artifact")

    # ══════════════════════════════════════════════════════════════════════════════
    #  STAGE 4 — Prediction + Explanations
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 72)
    print("  STAGE 4  ·  RISK PREDICTION")
    print("═" * 72)

    df = predict(model, df)

    # OPTIMIZATION: Use SHAP sampling for large datasets (>1000 files)
    # Compute SHAP on top 50% risk files + random 50% sample = 500-1000 files max
    # This reduces SHAP time from 15 min to ~5 min with minimal accuracy loss
    total_files = len(df)
    if total_files > 1000:
        shap_sample_size = min(1000, int(total_files * 0.6))  # 60% sample, max 1000
        print(f"  Large dataset detected ({total_files} files)")
        print(f"  Using SHAP sampling: {shap_sample_size} files for explanations")
        df = explain_prediction(model, df, save_plots=True, top_local=TOP_LOCAL_PLOTS, sample_for_shap=shap_sample_size)
    else:
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
            [["file", "risk", "risk_tier", "buggy", "bug_type", "explanation"]]
            .reset_index(drop=True)
        )

        for i, row in top_risky.iterrows():
            fname    = os.path.relpath(str(row["file"]), repo_path)
            risk_pct = f"{row['risk']:.0%}"
            tier     = row.get("risk_tier", "UNKNOWN")
            label    = "BUG" if row["buggy"] == 1 else "   "
            btype    = str(row.get("bug_type", "unknown"))
            expl     = textwrap.shorten(str(row["explanation"]), width=45, placeholder="…")

            # Map tier to severity for display
            if tier == "CRITICAL":
                sev = "CRITICAL"
            elif tier == "HIGH":
                sev = "HIGH    "
            elif tier == "MODERATE":
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
    #  STAGE 7 — Ablation Study (Optional)
    # ══════════════════════════════════════════════════════════════════════════════
    if os.getenv("RUN_ABLATION", "0") == "1":
        print("\n" + "═" * 72)
        print("  STAGE 7  ·  ABLATION STUDY")
        print("═" * 72)
        
        global_feats = model.get("features", None) if isinstance(model, dict) else None
        run_ablation_study(df_for_ablation, global_features=global_feats)
    else:
        print("\n" + "═" * 72)
        print("  STAGE 7  ·  ABLATION STUDY (Skipped)")
        print("═" * 72)
        print("  To run ablation study, set environment variable: RUN_ABLATION=1")

    print("\n" + "═" * 72)
    print("  PIPELINE COMPLETE")
    print("═" * 72)

    print("\n" + "═" * 72)
    print("  RISK TIER METHODOLOGY")
    print("═" * 72)
    print("  Risk tiers are assigned based on within-repository percentile ranking:")
    print("    CRITICAL: Top 10% of files by risk score")
    print("    HIGH:     10-25% (next 15%)")
    print("    MODERATE: 25-50% (next 25%)")
    print("    LOW:      Bottom 50%")
    print("")
    print("  This approach is robust to base rate shifts and ensures every scan")
    print("  produces actionable results regardless of absolute probability values.")
    print("  Absolute probabilities are shown for reference but should not be")
    print("  interpreted as literal bug probabilities across different repositories.")
    print("")
    print("  Base rate context: Training data has 49.3% buggy files after filtering.")
    print("  Real-world repos typically have 15-25% buggy files, so absolute")
    print("  probabilities will be systematically higher than true bug rates.")
    print("═" * 72 + "\n")
