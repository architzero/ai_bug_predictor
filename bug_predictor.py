import sys
import os
import pandas as pd

from static_analysis.analyzer import analyze_repository
from git_mining.git_miner import mine_git_data
from feature_engineering.feature_builder import build_features, filter_correlated_features
from feature_engineering.labeler import create_labels
from model.train_model import load_model_version
from model.predict import predict
from explainability.explainer import explain_prediction
from config import SZZ_CACHE_DIR


def run(repo_path):
    """
    Analyze a single repository using pre-trained model.
    
    This is the CLI tool for quick analysis of a single repo.
    It loads the pre-trained model instead of training a new one.
    
    To train a new model on multiple repos, use main.py instead.
    """
    print(f"\nAnalyzing repository: {repo_path}")
    
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
    static_results = analyze_repository(repo_path)
    print(f"   ✓ Analyzed {len(static_results)} files")
    
    print(f"\n2. Git history mining...")
    git_results = mine_git_data(repo_path)
    print(f"   ✓ Mined {len(git_results)} files")

    print(f"\n3. Feature engineering...")
    df = build_features(static_results, git_results)
    df = create_labels(df, repo_path, cache_dir=SZZ_CACHE_DIR)
    df["repo"] = repo_path
    df = filter_correlated_features(df)
    print(f"   ✓ Built features for {len(df)} files")

    print(f"\n4. Risk prediction...")
    df, confidence_result = predict(model, df, return_confidence=True)
    print(f"   ✓ Predicted risk for {len(df)} files")
    print(f"   Confidence: {confidence_result['confidence_level']} ({confidence_result['confidence_score']:.2f})")
    if confidence_result['warnings']:
        print(f"   Warnings:")
        for warning in confidence_result['warnings']:
            print(f"     - {warning}")
    
    print(f"\n5. Generating explanations...")
    df = explain_prediction(model, df, save_plots=True, top_local=5)
    print(f"   ✓ Generated SHAP explanations")

    # Summary statistics
    print(f"\n{'='*70}")
    print(f"  ANALYSIS SUMMARY")
    print(f"{'='*70}")
    print(f"  Repository: {os.path.basename(repo_path)}")
    print(f"  Files analyzed: {len(df)}")
    print(f"  Buggy files (labeled): {int(df['buggy'].sum())}")
    print(f"  High-risk files (>0.7): {int((df['risk'] > 0.7).sum())}")
    print(f"  Medium-risk files (0.4-0.7): {int(((df['risk'] >= 0.4) & (df['risk'] <= 0.7)).sum())}")
    print(f"  Low-risk files (<0.4): {int((df['risk'] < 0.4).sum())}")
    print(f"  Average risk: {df['risk'].mean():.3f}")
    print(f"  Prediction confidence: {confidence_result['confidence_level']}")

    # Top risk files
    df_sorted = df.sort_values("risk", ascending=False)
    
    print(f"\n{'='*70}")
    print(f"  TOP 15 RISK FILES")
    print(f"{'='*70}")
    print(f"  {'Risk':<6} {'LOC':<6} {'Complexity':<12} {'File':<40}")
    print(f"  {'-'*70}")
    
    for _, row in df_sorted.head(15).iterrows():
        risk_pct = f"{row['risk']:.1%}"
        loc = int(row.get('loc', 0))
        complexity = f"{row.get('avg_complexity', 0):.1f}"
        filename = os.path.basename(str(row['file']))
        
        # Truncate long filenames
        if len(filename) > 40:
            filename = filename[:37] + "..."
        
        print(f"  {risk_pct:<6} {loc:<6} {complexity:<12} {filename:<40}")
    
    print(f"\n{'='*70}")
    print(f"\n✓ Analysis complete!")
    print(f"\nSHAP plots saved to: explainability/plots/")
    print(f"  - global_bar.png: Feature importance")
    print(f"  - global_beeswarm.png: Feature distribution")
    print(f"  - local_waterfall_*.png: Per-file explanations")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bug_predictor.py <repo_path>")
        print("\nExample:")
        print("  python bug_predictor.py dataset/requests")
        print("\nNote: You must train a model first using 'python main.py'")
        sys.exit(1)

    run(sys.argv[1])
