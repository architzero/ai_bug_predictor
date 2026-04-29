import sys
import pandas as pd
from backend.analysis import analyze_repository
from backend.git_mining import mine_git_data
from backend.features import build_features
from backend.labeling import create_labels
from backend.train import load_model_version
from backend.predict import predict
from backend.config import SZZ_CACHE_DIR

repo_path = sys.argv[1] if len(sys.argv) > 1 else "dataset/requests"

model = load_model_version()
static_results = analyze_repository(repo_path)
git_results = mine_git_data(repo_path)
df = build_features(static_results, git_results)
df = create_labels(df, repo_path, cache_dir=SZZ_CACHE_DIR)
df["repo"] = repo_path
df = predict(model, df)

# Check for exact duplicates
df_sorted = df.sort_values("risk", ascending=False).head(15)
print("\nTop 15 files - FULL PRECISION:")
print(f"{'Rank':<6} {'Risk (full precision)':<25} {'Risk (1 decimal)':<15} {'File':<30}")
print("-" * 80)

for rank, (_, row) in enumerate(df_sorted.iterrows(), 1):
    risk_full = row['risk']
    risk_1dec = f"{row['risk']:.1%}"
    filename = row['file'].split('/')[-1]
    print(f"#{rank:<5} {risk_full:<25.15f} {risk_1dec:<15} {filename:<30}")

# Count exact duplicates
from collections import Counter
risk_counts = Counter(df['risk'].round(10))  # Round to 10 decimals
exact_dupes = {k: v for k, v in risk_counts.items() if v > 1}

print(f"\n\nExact duplicate probabilities (rounded to 10 decimals):")
if exact_dupes:
    for prob, count in sorted(exact_dupes.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {prob:.10f}: {count} files")
else:
    print("  None found - all probabilities are unique")
