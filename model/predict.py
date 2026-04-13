from config import RISK_THRESHOLD
import pandas as pd
from git_mining.szz_labeler import is_test_file, is_generated_file


def predict(model_data, df):
    """
    Attach 'risk' probability to each file.
    Uses RISK_THRESHOLD from config to determine binary 'risky' flag.
    Expects model_data to be a dict: {"model": calibrated_model, "features": feature_list}
    """
    if isinstance(model_data, dict) and "features" in model_data:
        model    = model_data["model"]
        features = model_data["features"]
    else:
        # Fallback for old/saved formats
        model    = model_data
        features = getattr(model, "feature_names_in_", None)

    mask = df['file'].apply(
        lambda f: not is_test_file(str(f)) and not is_generated_file(str(f))
    )
    df_source = df[mask].copy()
    df_test   = df[~mask].copy()
    
    if len(df_source) == 0:
        return df

    X = df_source.drop(columns=[
        "file", "buggy", "bug_fixes", "bug_density",
        "buggy_commit", "commit_hash", "repo",
        "bug_fix_ratio", "past_bug_count", "days_since_last_bug"
    ], errors="ignore")

    if features is not None:
        missing = [c for c in features if c not in X.columns]
        for c in missing:
            X[c] = 0
        X = X[features]

    probs = model.predict_proba(X)
    risk  = probs[:, 1] if probs.shape[1] > 1 else probs[:, 0]

    df_source["risk"]  = risk
    df_source["risky"] = (risk >= RISK_THRESHOLD).astype(int)

    # test/generated files get 0 risk
    if not df_test.empty:
        df_test["risk"]  = 0.0
        df_test["risky"] = 0

    return pd.concat([df_source, df_test]).sort_index()

