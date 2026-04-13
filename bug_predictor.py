import sys
import pandas as pd

from static_analysis.analyzer import analyze_repository
from git_mining.git_miner import mine_git_data
from feature_engineering.feature_builder import build_features, filter_correlated_features
from feature_engineering.labeler import create_labels
from model.train_model import train_model
from model.predict import predict
from explainability.explainer import explain_prediction
from config import SZZ_CACHE_DIR


def run(repo_path):

    print(f"\nAnalyzing repository: {repo_path}")

    static_results = analyze_repository(repo_path)
    git_results    = mine_git_data(repo_path)

    df = build_features(static_results, git_results)
    df = create_labels(df, repo_path, cache_dir=SZZ_CACHE_DIR)
    df["repo"] = repo_path

    df = filter_correlated_features(df)

    print(f"\nFiles analyzed : {len(df)}")
    print(f"Buggy files    : {df['buggy'].sum()}")

    print("\nTraining model...")
    model = train_model(df, [repo_path])

    print("\nPredicting risk...")
    df = predict(model, df)
    df = explain_prediction(model, df, save_plots=True)

    df = df.sort_values("risk", ascending=False)

    print("\nTop Risk Files:\n")
    for _, row in df.head(15).iterrows():
        print(
            f"{row['file']}  "
            f"risk={row['risk']:.2f}  "
            f"({row['explanation']})"
        )


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python bug_predictor.py <repo_path>")
        sys.exit(1)

    run(sys.argv[1])
