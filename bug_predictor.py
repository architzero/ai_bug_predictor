import sys
import os
import pandas as pd
import subprocess
import uuid

from backend.analysis import analyze_repository
from backend.git_mining import mine_git_data
from backend.features import build_features, filter_correlated_features
from backend.labeling import create_labels
from backend.train import load_model_version
from backend.predict import predict
from backend.explainer import explain_prediction
from backend.config import SZZ_CACHE_DIR, BASE_DIR
from backend.visualizations import create_risk_dashboard, create_tier_summary_table


def clone_if_needed(repo_input):
    """Clone repository if URL is provided, otherwise return the path."""
    if repo_input.startswith("http://") or repo_input.startswith("https://") or repo_input.startswith("git@"):
        # Extract repo name from URL
        repo_name = repo_input.rstrip('/').split('/')[-1].replace('.git', '')
        temp_dir = os.path.join(BASE_DIR, "dataset", f"temp_{repo_name}_{uuid.uuid4().hex[:6]}")
        
        print(f"Cloning {repo_input}...")
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "500", repo_input, temp_dir],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"✓ Cloned to {temp_dir}")
            return temp_dir, True  # Return path and is_temp flag
        except subprocess.CalledProcessError as e:
            if e.stderr and "Clone succeeded, but checkout failed" in e.stderr:
                print(f"\n⚠ WARNING: Git checkout partially failed (likely OS path constraints).")
                print(f"  Forcing checkout of valid files...")
                try:
                    subprocess.run(["git", "config", "core.protectNTFS", "false"], cwd=temp_dir, check=True)
                    subprocess.run(["git", "checkout", "-f", "HEAD"], cwd=temp_dir, check=False)
                except Exception as checkout_err:
                    print(f"  ⚠ Forced checkout failed: {checkout_err}")
                return temp_dir, True
            else:
                print(f"\n❌ ERROR: Failed to clone repository!")
                print(f"Git error: {e.stderr}")
                sys.exit(1)
    else:
        # Local path
        if not os.path.exists(repo_input):
            print(f"\n❌ ERROR: Directory not found: {repo_input}")
            sys.exit(1)
        return repo_input, False  # Return path and is_temp flag


def run(repo_input):
    """
    Analyze a single repository using pre-trained model.
    
    This is the CLI tool for quick analysis of a single repo.
    It loads the pre-trained model instead of training a new one.
    
    To train a new model on multiple repos, use main.py instead.
    """
    print(f"\nAnalyzing repository: {repo_input}")
    
    # Clone if URL, otherwise use local path
    repo_path, is_temp = clone_if_needed(repo_input)
    
    # Check if model exists
    try:
        model = load_model_version()
        print(f"✓ Loaded pre-trained model")
    except FileNotFoundError:
        print("\n❌ ERROR: No trained model found!")
        print("\nPlease train a model first by running:")
        print("  python main.py")
        print("\nThis will train a model on multiple repositories.")
        print("After training, you can use this CLI tool to analyze single repos.")
        sys.exit(1)

    # Analyze repository
    print(f"\n1. Static analysis...")
    static_results = analyze_repository(repo_path, verbose=True)  # Enable verbose mode
    print(f"   ✓ Analyzed {len(static_results)} files")
    
    if len(static_results) == 0:
        print(f"\n❌ ERROR: No source files found in repository!")
        print(f"\nPossible reasons:")
        print(f"  - Repository contains no supported source files (.py, .js, .java, etc.)")
        print(f"  - Repository path is incorrect")
        print(f"  - Files are in unsupported languages")
        print(f"\nSupported languages: Python, JavaScript, TypeScript, Java, Go, Ruby, PHP, C#, C++, Rust")
        sys.exit(1)
    
    print(f"\n2. Git history mining...")
    print(f"   (This may take 1-5 minutes for large repos on first run)")
    print(f"   (Subsequent runs will be instant due to caching)")
    git_results = mine_git_data(repo_path)
    print(f"   ✓ Mined {len(git_results)} files")

    print(f"\n3. Feature engineering...")
    df = build_features(static_results, git_results)
    
    if len(df) == 0:
        print(f"\n❌ ERROR: Failed to build features - no valid files!")
        sys.exit(1)
    
    # Small repo warning
    if len(df) < 25:
        print(f"\n⚠  WARNING: Small repository detected ({len(df)} files)")
        print(f"   Results are directional only. Predictions more reliable for repos with 25+ files.")
        print(f"   Confidence scores will reflect this limitation.")
        print(f"   Risk scores may be tightly clustered - focus on TIER rankings.")
    
    # Check for cross-language issues
    languages = df['language'].unique()
    if len(languages) > 1:
        print(f"\n⚠  WARNING: Multi-language repository detected")
        print(f"   Languages found: {', '.join(languages)}")
        print(f"   Model trained primarily on Python/JavaScript - predictions for other languages may be less reliable")
        print(f"   Risk scores may cluster - focus on TIER rankings for prioritization.")
        
        python_files = len(df[df['language'] == 'python'])
        total_files = len(df)
        
        if python_files > 0 and python_files < total_files:
            print(f"\n   Repository mix: {python_files} Python, {total_files - python_files} other languages")
            print(f"   Analyzing all files, but Python predictions will be most accurate")
    elif 'python' not in languages and 'javascript' not in languages:
        print(f"\n⚠  WARNING: Non-Python/JavaScript repository detected")
        print(f"   Language: {languages[0] if len(languages) > 0 else 'unknown'}")
        print(f"   Model trained primarily on Python/JavaScript - predictions may have lower accuracy")
        print(f"   Confidence scores will reflect this uncertainty")
        print(f"   Risk scores may cluster - focus on TIER rankings for prioritization.")
    
    df = create_labels(df, repo_path, cache_dir=SZZ_CACHE_DIR)
    df["repo"] = os.path.basename(repo_path)
    # NOTE: Do NOT call filter_correlated_features() here!
    # The model was trained with a fixed feature set.
    # Correlation filtering at inference time causes feature mismatch.
    print(f"   ✓ Built features for {len(df)} files")

    print(f"\n4. Risk prediction...")
    df, confidence_result = predict(model, df, return_confidence=True)
    print(f"   ✓ Predicted risk for {len(df)} files")
    print(f"   Confidence: {confidence_result['confidence_level']} ({confidence_result['confidence_score']:.2f})")
    
    # Check for probability clustering
    risk_std = df['risk'].std()
    risk_range = df['risk'].max() - df['risk'].min()
    if risk_std < 0.05 or risk_range < 0.1:
        print(f"   ⚠ Risk scores are tightly clustered (std={risk_std:.3f}, range={risk_range:.3f})")
        print(f"     This is common for repositories very different from training data.")
        print(f"     Focus on TIER rankings (CRITICAL/HIGH/MODERATE/LOW) for prioritization.")
    
    if confidence_result['warnings']:
        print(f"   Warnings:")
        for warning in confidence_result['warnings']:
            print(f"     - {warning}")
    
    print(f"\n5. Generating explanations...")
    df = explain_prediction(model, df, save_plots=True, top_local=5)
    print(f"   ✓ Generated SHAP explanations")
    
    # Generate easy-to-understand visualizations
    print(f"\n6. Creating visual dashboard...")
    try:
        dashboard_path = create_risk_dashboard(df, os.path.basename(repo_path))
        summary_path = create_tier_summary_table(df, os.path.basename(repo_path))
        print(f"   ✓ Created dashboard: {os.path.basename(dashboard_path)}")
        print(f"   ✓ Created summary table: {os.path.basename(summary_path)}")
    except Exception as e:
        print(f"   ⚠ Could not create dashboard: {e}")
    
    # Validate explanations are not empty
    empty_explanations = df[df['explanation'].str.strip() == ''].shape[0]
    if empty_explanations > 0:
        print(f"   ⚠ {empty_explanations} files have empty explanations (will show generic message)")

    # Summary statistics
    print(f"\n{'='*70}")
    print(f"  ANALYSIS SUMMARY")
    print(f"{'='*70}")
    print(f"  Repository: {os.path.basename(repo_path)}")
    print(f"  Files analyzed: {len(df)}")
    print(f"  Buggy files (labeled): {int(df['buggy'].sum())}")
    
    # Use tier-based summary instead of absolute thresholds
    tier_counts = df['risk_tier'].value_counts()
    print(f"  CRITICAL tier: {tier_counts.get('CRITICAL', 0)}")
    print(f"  HIGH tier: {tier_counts.get('HIGH', 0)}")
    print(f"  MODERATE tier: {tier_counts.get('MODERATE', 0)}")
    print(f"  LOW tier: {tier_counts.get('LOW', 0)}")
    print(f"  Risk score range: {df['risk'].min():.3f} - {df['risk'].max():.3f} (std: {df['risk'].std():.3f})")
    print(f"  Prediction confidence: {confidence_result['confidence_level']}")
    
    # Tier distribution summary
    print(f"\n  Risk Tier Distribution:")
    print(f"    CRITICAL (top 10%):    {tier_counts.get('CRITICAL', 0)} files → Immediate review required")
    print(f"    HIGH (10-25%):         {tier_counts.get('HIGH', 0)} files → Prioritize for review")
    print(f"    MODERATE (25-50%):     {tier_counts.get('MODERATE', 0)} files → Consider for review")
    print(f"    LOW (bottom 50%):      {tier_counts.get('LOW', 0)} files → Low priority")

    # Top risk files
    df_sorted = df.sort_values("risk", ascending=False)
    
    print(f"\n{'='*70}")
    print(f"  TOP 10 RISK FILES (with explanations)")
    print(f"{'='*70}")
    print(f"\n  ⚠️  IMPORTANT: Risk scores are RELATIVE rankings within this repository.")
    print(f"      Focus on TIER (CRITICAL/HIGH/MODERATE/LOW) for prioritization.")
    print(f"      Tiers: CRITICAL=top 10%, HIGH=10-25%, MODERATE=25-50%, LOW=bottom 50%")
    
    # Check for score clustering and warn user
    if risk_std < 0.05 or risk_range < 0.1:
        print(f"\n  ⚠️  NOTE: Risk scores are tightly clustered (range={risk_range:.3f}).")
        print(f"      This may indicate the repository is very different from training data.")
        print(f"      Focus on TIER rankings rather than absolute percentages.\n")
    else:
        print()
    
    for rank, (_, row) in enumerate(df_sorted.head(10).iterrows(), 1):
        risk_pct = f"{row['risk']:.1%}"
        tier = row.get('risk_tier', 'UNKNOWN')
        loc = int(row.get('loc', 0))
        
        # FIX: Show relative path to avoid confusion with duplicate filenames
        full_path = str(row['file'])
        if os.path.isabs(full_path) and repo_path in full_path:
            filename = os.path.relpath(full_path, repo_path)
        else:
            filename = os.path.basename(full_path)
        
        explanation = row.get('explanation', 'No explanation available')
        
        # Format risk percentage with better precision for clustered scores
        if risk_std < 0.05:
            risk_display = f"{row['risk']:.3f}"  # Show 3 decimals when clustered
        else:
            risk_display = risk_pct
        
        print(f"\n  #{rank}. {filename}")
        print(f"      Risk: {risk_display} | Tier: {tier} | LOC: {loc}")
        if explanation and explanation.strip():
            print(f"      Why risky: {explanation}")
        else:
            print(f"      Why risky: Flagged by model based on code patterns")
    
    print(f"\n{'='*70}")
    print(f"\n✓ Analysis complete!")
    print(f"\nInterpretation Guide:")
    print(f"  • Focus on TIER (CRITICAL/HIGH/MODERATE/LOW) for prioritization")
    print(f"  • CRITICAL = top 10% riskiest files in THIS repository")
    print(f"  • Risk scores are relative rankings, not absolute probabilities")
    print(f"  • Files with similar scores should be prioritized by tier, then by LOC")
    
    plots_dir = os.path.abspath('ml/plots')
    print(f"\nVisualizations saved to: {plots_dir}")
    print(f"  - dashboard_{os.path.basename(repo_path)}.png: Easy-to-understand overview")
    print(f"  - summary_table_{os.path.basename(repo_path)}.png: Tier statistics")
    print(f"  - global_bar.png: Feature importance (technical)")
    print(f"  - global_beeswarm.png: Feature distribution (technical)")
    print(f"  - local_waterfall_*.png: Per-file explanations (technical)")
    print(f"\nFor best results:")
    print(f"  - Review CRITICAL tier files first (top 10%)")
    print(f"  - Use tier rankings when risk scores are clustered")
    print(f"  - Consider LOC when prioritizing files within same tier")
    
    # Auto-open plots folder
    try:
        if os.name == 'nt':
            os.startfile(plots_dir)
            print(f"\n✓ Opened plots folder in Explorer")
        else:
            print(f"\nTo view plots, open: {plots_dir}")
    except Exception:
        print(f"\nTo view plots manually, open: {plots_dir}")
    
    # Cleanup temp directory if cloned
    if is_temp:
        import shutil
        import time
        try:
            # On Windows, git files can be locked. Try multiple times with delay.
            for attempt in range(3):
                try:
                    shutil.rmtree(repo_path)
                    print(f"\n✓ Cleaned up temporary clone")
                    break
                except PermissionError:
                    if attempt < 2:
                        time.sleep(0.5)
                    else:
                        print(f"\n⚠ Could not clean up temp directory (files locked by git)")
                        print(f"  You can manually delete: {repo_path}")
        except Exception as e:
            print(f"\n⚠ Could not clean up temp directory: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bug_predictor.py <repo_path>")
        print("\nExample:")
        print("  python bug_predictor.py dataset/requests")
        print("\nNote: You must train a model first using 'python main.py'")
        sys.exit(1)

    run(sys.argv[1])
