from config import RISK_THRESHOLD
import pandas as pd
import numpy as np
from git_mining.szz_labeler import is_test_file, is_generated_file
from model.train_model import _calculate_effort_aware_metrics


def _detect_out_of_distribution(df, training_stats=None):
    """
    Detect out-of-distribution inputs that may lead to unreliable predictions.

    training_stats: optional dict of {col: {"mean": .., "std": .., "p99": ..}}
    saved from training time.  When absent we fall back to intra-scan stats
    which can only detect internal extremes, not distribution shift.
    """
    warnings = []
    confidence_score = 1.0

    # Check for supported languages
    if "language" in df.columns:
        supported_languages = {"python", "javascript", "typescript", "java", "go", "ruby", "php", "csharp", "cpp", "c"}
        unsupported = df[~df["language"].isin(supported_languages)]
        if not unsupported.empty:
            warnings.append("Unsupported programming languages detected")
            confidence_score *= 0.7

    # Check for extreme feature values vs training distribution
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if col not in df.columns:
            continue
        if training_stats and col in training_stats:
            # Compare against saved training distribution (Fix #22)
            ref_p99  = training_stats[col].get("p99", None)
            ref_mean = training_stats[col].get("mean", None)
            ref_std  = training_stats[col].get("std", 1.0)
            if ref_p99 is not None and (df[col] > ref_p99 * 3).sum() > 0:
                warnings.append(f"Extreme values detected in {col}")
                confidence_score *= 0.8
            elif ref_mean is not None and ref_std > 0:
                z_scores = ((df[col] - ref_mean) / ref_std).abs()
                if (z_scores > 5).sum() > 0:
                    warnings.append(f"Values >5σ from training mean in {col}")
                    confidence_score *= 0.85
        # No training_stats available — skip extreme check to avoid false positives

    # Check for sparse git history
    if "commits" in df.columns:
        sparse_commits = (df["commits"] < 5).sum()
        if sparse_commits > len(df) * 0.5:
            warnings.append("Sparse git history detected")
            confidence_score *= 0.6

    # Fix #11: derive is_reliable from the actual confidence_score
    is_reliable = confidence_score >= 0.6

    return {
        "is_reliable": is_reliable,
        "confidence_score": confidence_score,
        "warnings": warnings
    }


def _calculate_prediction_entropy(proba):
    """
    Calculate entropy of probability predictions as uncertainty measure.
    Higher entropy = more uncertainty.
    """
    # Calculate entropy for each prediction
    epsilon = 1e-10  # Avoid log(0)
    entropy = -proba * np.log(proba + epsilon) - (1 - proba) * np.log(1 - proba + epsilon)
    
    # Normalize entropy to [0, 1] range
    max_entropy = 0.693  # Maximum entropy for binary classification
    normalized_entropy = entropy / max_entropy
    
    return normalized_entropy


def _assess_prediction_confidence(df, proba, training_stats=None):
    """
    Comprehensive confidence assessment combining multiple uncertainty measures.
    """
    # Out-of-distribution detection
    ood_result = _detect_out_of_distribution(df, training_stats=training_stats)
    
    # Prediction entropy (mean across all predictions)
    entropy = _calculate_prediction_entropy(proba).mean()
    
    # Combine confidence scores
    base_confidence = ood_result["confidence_score"]
    entropy_penalty = entropy * 0.3  # Entropy reduces confidence
    
    final_confidence = max(base_confidence - entropy_penalty, 0.1)
    
    # Determine confidence level
    if final_confidence > 0.8:
        confidence_level = "HIGH"
        message = "Predictions are reliable"
    elif final_confidence > 0.6:
        confidence_level = "MEDIUM"
        message = "Predictions may be less reliable"
    else:
        confidence_level = "LOW"
        message = "Predictions may be unreliable"
    
    return {
        "confidence_score": final_confidence,
        "confidence_level": confidence_level,
        "message": message,
        "warnings": ood_result["warnings"],
        "entropy": entropy,
        "out_of_distribution": not ood_result["is_reliable"]
    }


def predict(model_data, df, return_confidence=False):
    """
    Attach 'risk' probability to each file.
    Uses RISK_THRESHOLD from config to determine binary 'risky' flag.
    Expects model_data to be a dict: {"model": calibrated_model, "features": feature_list}
    """
    if isinstance(model_data, dict) and "features" in model_data:
        model    = model_data["model"]
        features = model_data["features"]
        # training_stats saved by _save_model_with_metadata (Fix #22)
        training_stats = model_data.get("training_stats", None)
    else:
        # Fallback for old/saved formats
        model    = model_data
        features = getattr(model, "feature_names_in_", None)
        training_stats = None

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
        # Removed leakage features (no longer computed, but drop if present in old cached data)
        "bug_fix_ratio", "past_bug_count", "days_since_last_bug"
    ], errors="ignore")

    if features is not None:
        missing = [c for c in features if c not in X.columns]
        if missing:
            # CRITICAL: Log missing features and reduce confidence
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "Missing %d feature(s) during prediction (zero-filled): %s. "
                "This may indicate distribution shift or model/data version mismatch.",
                len(missing), missing[:5]  # Show first 5 for brevity
            )
            # Add warning to confidence result (will be populated later)
            # Store in df metadata for now
            df_source.attrs['missing_features'] = missing
            
        for c in missing:
            X[c] = 0
        X = X[features]

    probs = model.predict_proba(X)
    risk  = probs[:, 1] if probs.shape[1] > 1 else probs[:, 0]

    df_source["risk"]  = risk
    df_source["risky"] = (risk >= RISK_THRESHOLD).astype(int)

    # Assess prediction confidence
    confidence_result = _assess_prediction_confidence(df_source, risk, training_stats=training_stats)
    
    # Add missing features warning to confidence result if present
    if hasattr(df_source, 'attrs') and 'missing_features' in df_source.attrs:
        missing = df_source.attrs['missing_features']
        confidence_result["warnings"].append(
            f"Missing {len(missing)} features (zero-filled): {', '.join(missing[:3])}..."
        )
        # Reduce confidence score for missing features
        confidence_result["confidence_score"] *= max(0.5, 1.0 - len(missing) * 0.05)
    
    # Add confidence information to dataframe
    df_source["confidence_score"] = confidence_result["confidence_score"]
    df_source["confidence_level"] = confidence_result["confidence_level"]

    # Calculate effort-aware metrics
    df_source = _calculate_effort_aware_metrics(df_source)

    # test/generated files get 0 risk
    if not df_test.empty:
        df_test["risk"]  = 0.0
        df_test["risky"] = 0
        # Set default effort metrics for test files
        df_test["risk_per_loc"] = 0.0
        df_test["effort_priority"] = 0.0
        df_test["effort_category"] = "LOW_PRIORITY"

    final_df = pd.concat([df_source, df_test]).sort_index()
    if return_confidence:
        return final_df, confidence_result
    return final_df
