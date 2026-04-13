import os
from static_analysis.analyzer import analyze_repository
from git_mining.szz_labeler import extract_bug_labels

repo_path = "dataset/requests"

print(f"Diagnosing Data Bleed for: {repo_path}")

# 1. SZZ paths
buggy_files = extract_bug_labels(repo_path, cache_dir=".cache/szz")
print(f"\nTotal SZZ Buggy Paths: {len(buggy_files)}")

print("\nSample SZZ Paths:")
for f in list(buggy_files)[:10]:
    print("  ", f)

# 2. Analyzer paths
results = analyze_repository(repo_path)
analyzer_paths = [
    r["file"].replace("\\", "/").lower()
    for r in results
]

print(f"\nTotal Analyzer Paths: {len(analyzer_paths)}")

# 3. find missing
szz = set(buggy_files)
ana = set(analyzer_paths)

missing = szz - ana

print("\n==============================")
print("FILES MISSED BY ANALYZER")
print("==============================")

for f in list(missing)[:20]:
    print(f)

print("\nMissed count:", len(missing))