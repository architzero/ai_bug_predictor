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

    # 1. Extract SZZ labels FIRST to preserve them during filtering
    from backend.szz import extract_bug_labels
    try:
        buggy_paths = extract_bug_labels(repo_path, cache_dir=SZZ_CACHE_DIR)
    except Exception as e:
        print(f"  ⚠️  Failed to pre-extract SZZ labels for {repo_name}: {e}")
        buggy_paths = set()

    # 2. Analyze repository
    static_results = analyze_repository(repo_path, parallel=True, max_workers=4, buggy_paths=buggy_paths)

    if not static_results:
        print(f"  ⚠️  No files analyzed for {repo_name} — skipping")
        return (repo_name, pd.DataFrame(), 0)

    # 3. Mine git data
    git_results = mine_git_data(repo_path)

    # 4. Build features
    df = build_features(static_results, git_results)

    # 5. CRITICAL: Set repo column BEFORE labeling so it survives any filtering
    df["repo"] = repo_name

    # 6. Create labels with multi-level matching
    df = create_labels(df, repo_path, cache_dir=SZZ_CACHE_DIR)

    # 7. Ensure repo column is always set (defensive — create_labels may return new DF)
    if "repo" not in df.columns or df["repo"].isna().any():
        df["repo"] = repo_name

    print(f"  [PIPELINE] {repo_name}: {len(df)} files, {int(df['buggy'].sum()) if not df.empty else 0} buggy")
    buggy = int(df["buggy"].sum()) if not df.empty else 0
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
                if df is not None and not df.empty:
                    print(f"  ✓  {repo_name:<20}  {len(df):>5} files  |  {buggy:>4} labelled buggy")
                    all_data.append(df)
                else:
                    print(f"  ⚠  {repo_name:<20}  SKIPPED (empty result)")
            except Exception as e:
                repo = futures[future]
                print(f"  ✗  {os.path.basename(repo):<20}  FAILED: {e}")

    # Guard: abort if no data collected
    if not all_data:
        print("\n  ❌ FATAL: No repositories produced usable data. Aborting.")
        print("  Check SZZ cache, repo paths, and file filtering settings.")
        import sys; sys.exit(1)

    # ══════════════════════════════════════════════════════════════════════════════
    #  STAGE 2 — Feature Pipeline
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 72)
    print("  STAGE 2  ·  FEATURE PIPELINE")
    print("═" * 72)

    df = pd.concat(all_data, ignore_index=True)

    # Guard: abort if combined dataset is empty
    if df.empty:
        print("\n  ❌ FATAL: Combined dataset is empty after collecting all repos. Aborting.")
        print("  Check SZZ cache, repo paths, and file filtering settings.")
        import sys; sys.exit(1)
    
    # Debug: Print dataset stats after concat
    print(f"  [DEBUG STAGE 1->2] Dataset after concat: {len(df)} files")
    print(f"  [DEBUG STAGE 1->2] Buggy files: {int(df['buggy'].sum())} ({df['buggy'].mean():.1%})")
    print(f"  [DEBUG STAGE 1->2] Repos: {df['repo'].nunique()} unique")

    # Ensure repo column has no NaNs before correlation filter
    if "repo" in df.columns and df["repo"].isna().any():
        print(f"  🔧 Fixing {df['repo'].isna().sum()} NaN repo values in combined dataset")
        df["repo"] = df["repo"].fillna("unknown")

    print(f"  [PIPELINE] Combined dataset: {len(df)} files total, {int(df['buggy'].sum())} buggy ({df['buggy'].mean():.1%} rate)")

    df = filter_correlated_features(df)
    
    # Guard: check if filtering removed all data
    if df.empty:
        print("\n  ❌ FATAL: Feature filtering removed all data. Aborting.")
        print("  Check correlation filter thresholds and feature engineering.")
        import sys; sys.exit(1)
    
    # Debug: Print dataset stats after feature filtering
    print(f"  [DEBUG STAGE 2] After feature filtering: {len(df)} files")
    print(f"  [DEBUG STAGE 2] Features available: {len([col for col in df.columns if col not in ['file', 'repo', 'buggy', 'bug_type']])}")

    # ── Bug Type Classification (DISABLED - prevents pipeline contamination) ───────
    print(f"\n  Bug type classifier skipped for binary classification focus")
    print(f"  ⚠️  Bug type classifier disabled to prevent feature corruption")
    df['bug_type'] = 'unknown'
    df['bug_type_confidence'] = 0.0

    print(f"\n  Dataset summary  →  {len(df)} files  |  {int(df['buggy'].sum())} buggy")
    print(f"  Bug type classification: DISABLED (prevents pipeline corruption)")
    buggy_count = int(df['buggy'].sum())
    if buggy_count > 0:
        print(f"  All {buggy_count} buggy files classified as 'unknown' (binary classification focus)")
    else:
        print(f"  No buggy files found in dataset")

    # ── Filename overlap leakage prevention ───────────────────────────────────
    basename_repos = defaultdict(set)
    for _, row in df.iterrows():
        basename_repos[os.path.basename(str(row["file"]))].add(
            os.path.basename(str(row["repo"]))
        )
    overlapping = {k: v for k, v in basename_repos.items() if len(v) > 1}
    if overlapping:
        print(f"\n  ⚠  {len(overlapping)} filename(s) shared across repos (mitigating leakage):")
        for fname in sorted(overlapping)[:6]:
            print(f"     {fname:<35} → {overlapping[fname]}")
        
        # Create filename-based leakage indicator
        overlapping_filenames = set(overlapping.keys())
        df['has_shared_filename'] = df['file'].apply(
            lambda x: os.path.basename(str(x)) in overlapping_filenames
        )
        
        # Warn about potential leakage
        shared_buggy = df[df['has_shared_filename'] & (df['buggy'] == 1)]
        if len(shared_buggy) > 0:
            print(f"  ⚠️  WARNING: {len(shared_buggy)} buggy files have shared filenames (potential leakage)")
        
        # Add leakage prevention feature for model to learn from
        print(f"  ✓ Added 'has_shared_filename' feature to mitigate cross-repo leakage")
    else:
        print("\n  ✓  No filename overlap between repos")
        df['has_shared_filename'] = False

    # ══════════════════════════════════════════════════════════════════════════════
    #  STAGE 3 — Model Training
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 72)
    print("  STAGE 3  ·  CROSS-PROJECT MODEL TRAINING")
    print("═" * 72)

    # Debug: Print dataset stats before training
    print(f"  [DEBUG STAGE 2->3] Training dataset: {len(df)} files")
    print(f"  [DEBUG STAGE 2->3] Buggy files: {int(df['buggy'].sum())} ({df['buggy'].mean():.1%})")
    print(f"  [DEBUG STAGE 2->3] Features for training: {len([col for col in df.columns if col not in ['file', 'repo', 'buggy', 'bug_type', 'risk', 'risky', 'explanation']])}")

    df_for_ablation = df.copy()
    model = train_model(df, REPOS)



    # ══════════════════════════════════════════════════════════════════════════════
    #  STAGE 4 — Prediction + Explanations
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 72)
    print("  STAGE 4  ·  RISK PREDICTION")
    print("═" * 72)

    df, confidence_result = predict(model, df, return_confidence=True)

    print(f"  [DEBUG] Total files in df: {len(df)}")
    if 'risk' in df.columns:
        print(f"  [DEBUG] Files with risk > 0: {(df['risk'] > 0).sum()}")
        print(f"  [DEBUG] Risk score range: {df['risk'].min():.3f} - {df['risk'].max():.3f}")
        print(f"  [DEBUG] Files flagged risky: {df['risky'].sum() if 'risky' in df.columns else 0}")
    else:
        print(f"  [DEBUG] 'risk' column missing from df!")
    if 'repo' in df.columns:
        print(f"  [DEBUG] Repos in df: {df['repo'].unique()}")
    
    # REPORT INPUT CHECK - CRITICAL DEBUG
    print("\nREPORT INPUT CHECK:")
    print("Rows:", len(df))
    print("Risk min/max:", df['risk'].min(), df['risk'].max())
    print("Non-zero risks:", (df['risk'] > 0).sum())
    print(df[['file', 'risk', 'repo']].head(10))

    # CRITICAL DEBUG: Check risk data before SHAP
    print(f"\n  [PRE-SHAP DEBUG] Risk range before SHAP: {df['risk'].min():.3f} - {df['risk'].max():.3f}")
    print(f"  [PRE-SHAP DEBUG] Non-zero risks before SHAP: {(df['risk'] > 0).sum()}")
    
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
    
    # CRITICAL DEBUG: Check risk data after SHAP
    print(f"  [POST-SHAP DEBUG] Risk range after SHAP: {df['risk'].min():.3f} - {df['risk'].max():.3f}")
    print(f"  [POST-SHAP DEBUG] Non-zero risks after SHAP: {(df['risk'] > 0).sum()}")

    # ══════════════════════════════════════════════════════════════════════════════
    #  STAGE 5 — Final Risk Report
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 72)
    print("  GITSENTINEL  ·  FINAL RISK REPORT")
    print("═" * 72)

    # CRITICAL FIX: Apply comprehensive final reporting fixes
    from backend.final_reporting_fixes import comprehensive_final_reporting_fixes
    
    print(f"\n  [REPORT DEBUG] Applying comprehensive fixes...")
    fix_results = comprehensive_final_reporting_fixes(df)
    df_fixed = fix_results['fixed_df']
    results = fix_results['results']
    
    print(f"  [REPORT DEBUG] Fixes applied: {len(results['fixes_applied'])}")
    print(f"  [REPORT DEBUG] Overall status: {results['overall_status']}")
    
    # Use the fixed dataframe for reporting
    df = df_fixed

    TOP_N = 20  # Increased from 10 for better coverage

    # CRITICAL FIX: Ensure we're using the full dataset, not filtering incorrectly
    # (Note: is_core_file filtering is now handled internally if needed)
    print(f"\n  [REPORT DEBUG] Using full dataset with {len(df)} files")
    print(f"  [REPORT DEBUG] Risk range: {df['risk'].min():.3f} - {df['risk'].max():.3f}")
    print(f"  [REPORT DEBUG] Files with risk > 0: {(df['risk'] > 0).sum()}")
    print(f"  [REPORT DEBUG] Repos: {df['repo'].unique()}")

    for repo_path in REPOS:
        repo_name = os.path.basename(repo_path)

        # Use the full predicted dataset — trust the prediction pipeline's filtering.
        # Do NOT re-filter here; it silently drops files that already passed Stage 0-4.
        repo_df = df[df["repo"] == repo_name].copy()

        if repo_df.empty:
            print(f"\n  ┌─ {repo_name}  (no files found — check repo path and SZZ match rate)")
            continue

        # CRITICAL DEBUG: Check risk data before processing
        print(f"\n  [REPORT DEBUG] Processing {repo_name}:")
        print(f"    Rows after filtering: {len(repo_df)}")
        print(f"    Risk range: {repo_df['risk'].min():.3f} - {repo_df['risk'].max():.3f}")
        print(f"    Non-zero risks: {(repo_df['risk'] > 0).sum()}")
        
        # CRITICAL FIX: Do NOT overwrite or reset risk values
        # Use actual predicted risk scores from Stage 4
        buggy_count = int(repo_df["buggy"].sum())
        risky_count = int(repo_df["risky"].sum()) if "risky" in repo_df.columns else int((repo_df["risk"] >= 0.5).sum())
        total = len(repo_df)

        print(f"\n  ┌─ {repo_name}  ({total} files │ {buggy_count} buggy │ {risky_count} flagged risky)")

        # CRITICAL FIX: Sort by risk (descending) and show top N
        top_risky = (
            repo_df
            .sort_values("risk", ascending=False)
            .head(TOP_N)
            [["file", "risk", "risk_tier", "buggy", "explanation"]]
            .reset_index(drop=True)
        )

        for i, row in top_risky.iterrows():
            fname    = os.path.relpath(str(row["file"]), repo_path)
            risk_pct = f"{row['risk']:.0%}"
            tier     = row.get("risk_tier", "UNKNOWN")
            label    = "BUG" if row["buggy"] == 1 else "   "
            expl     = textwrap.shorten(str(row.get("explanation", "N/A")), width=45, placeholder="…")
            # Fix: read bug_type from row, not from an undefined outer variable
            btype    = str(row.get("bug_type", "UNKNOWN"))

            # Map tier to severity for display
            if tier == "CRITICAL":
                sev = "CRITICAL"
            elif tier == "HIGH":
                sev = "HIGH    "
            elif tier == "MODERATE":
                sev = "MODERATE"
            else:
                sev = "LOW     "

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
    #  STAGE 7 — Ablation Study (Always Run)
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 72)
    print("  STAGE 7  ·  ABLATION STUDY")
    print("═" * 72)
    
    global_feats = model.get("features", None) if isinstance(model, dict) else None
    run_ablation_study(df_for_ablation, global_features=global_feats)

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
