from backend.szz import is_test_file, is_generated_file


def predict_commit_risk(df, changed_files):
    """
    Compute average risk for a set of changed files.
    Filters out test and generated files before scoring —
    those are not bug-prone by definition.
    Returns (avg_risk, top_risky_files_df).
    """
    filtered = [
        f for f in changed_files
        if not is_test_file(f) and not is_generated_file(f)
    ]

    if not filtered:
        return 0.0, df.head(0)

    subset = df[df["file"].isin(filtered)]

    if len(subset) == 0:
        return 0.0, df.head(0)

    avg_risk    = subset["risk"].mean()
    risky_files = subset.sort_values("risk", ascending=False).head(5)

    return avg_risk, risky_files
