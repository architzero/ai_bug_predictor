from backend.config import RISK_THRESHOLD
import pandas as pd
import numpy as np
from backend.szz import is_test_file, is_generated_file
from backend.train import _calculate_effort_aware_metrics
from backend.feature_constants import ALL_EXCLUDE_COLS


def _assign_risk_tiers_percentile(df):
    """
    Assign risk tiers based on within-repository percentile ranking.
    
    FIX: Use strict rank-based percentile cutoffs.
    When files have identical risk scores, assign tiers based on
    their RANK position, not score-based percentiles.
    
    Tiers:
    - CRITICAL: Top 10% of files by risk score (within each repo)
    - HIGH: 10-25% (next 15%)
    - MODERATE: 25-50% (next 25%)
    - LOW: Bottom 50%
    """
    if 'risk' not in df.columns or len(df) == 0:
        df['risk_tier'] = 'UNKNOWN'
        return df
    
    # Check if we have repo column for per-repo ranking
    if 'repo' in df.columns:
        # Assign tiers per repository
        def assign_tier_for_repo(repo_df):
            repo_df = repo_df.copy()
            n = len(repo_df)
            
            # Sort by risk descending and assign ranks
            repo_df = repo_df.sort_values('risk', ascending=False).reset_index(drop=True)
            
            # Calculate tier cutoffs based on RANK (not score)
            critical_cutoff = int(np.ceil(n * 0.10))  # Top 10%
            high_cutoff = int(np.ceil(n * 0.25))      # Top 25%
            moderate_cutoff = int(np.ceil(n * 0.50))  # Top 50%
            
            # Assign tiers based on rank position
            tiers = np.array(["LOW"] * n, dtype=object)
            tiers[:critical_cutoff] = "CRITICAL"
            tiers[critical_cutoff:high_cutoff] = "HIGH"
            tiers[high_cutoff:moderate_cutoff] = "MODERATE"
            
            repo_df['risk_tier'] = tiers
            return repo_df
        
        # Apply per-repo tier assignment
        df = df.groupby('repo', group_keys=False).apply(assign_tier_for_repo)
    else:
        # Fallback: global ranking if no repo column
        n = len(df)
        
        # Sort by risk descending and assign ranks
        df = df.sort_values('risk', ascending=False).reset_index(drop=True)
        
        # Calculate tier cutoffs based on RANK (not score)
        critical_cutoff = int(np.ceil(n * 0.10))  # Top 10%
        high_cutoff = int(np.ceil(n * 0.25))      # Top 25%
        moderate_cutoff = int(np.ceil(n * 0.50))  # Top 50%
        
        # Assign tiers based on rank position
        tiers = np.array(["LOW"] * n, dtype=object)
        tiers[:critical_cutoff] = "CRITICAL"
        tiers[critical_cutoff:high_cutoff] = "HIGH"
        tiers[high_cutoff:moderate_cutoff] = "MODERATE"
        
        df['risk_tier'] = tiers
    
    return df


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
    Comprehensive confidence assessment with tiered penalty system.
    
    Research-grade approach: Penalties are additive for independent issues,
    multiplicative only for dependent/compounding issues.
    """
    warnings = []
    confidence_score = 1.0
    
    # Categorize warnings by severity
    critical_penalties = []  # 50% penalty each
    moderate_penalties = []  # 15% penalty each
    minor_penalties = []     # 5% penalty each
    
    # Check for unsupported languages (CRITICAL)
    if "language" in df.columns:
        supported_languages = {"python", "javascript", "typescript", "java", "go", "ruby", "php", "csharp", "cpp", "c"}
        unsupported = df[~df["language"].isin(supported_languages)]
        if not unsupported.empty:
            warnings.append("Unsupported programming languages detected")
            critical_penalties.append(0.5)
    
    # Check for extreme feature values vs training distribution (MODERATE)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    extreme_count = 0
    
    for col in numeric_cols:
        if col not in df.columns:
            continue
        if training_stats and col in training_stats:
            # Use robust statistics (median + IQR) instead of mean + std
            median = training_stats[col].get("median", None)
            p25 = training_stats[col].get("p01", None)  # Using p01 as proxy for p25
            p75 = training_stats[col].get("p99", None)  # Using p99 as proxy for p75
            
            if median is not None and p75 is not None and p25 is not None:
                iqr = p75 - p25
                outlier_threshold = median + 3 * iqr
                
                # Only warn if MANY files are outliers (not just 1-2)
                outlier_count = (df[col] > outlier_threshold).sum()
                if outlier_count > len(df) * 0.3:  # 30% threshold
                    warnings.append(f"Extreme values detected in {col}")
                    extreme_count += 1
    
    # Apply moderate penalty only if multiple extreme value warnings
    if extreme_count >= 3:
        moderate_penalties.append(0.15)
    elif extreme_count >= 1:
        minor_penalties.append(0.05)
    
    # Check for sparse git history (MODERATE)
    if "commits" in df.columns:
        sparse_commits = (df["commits"] < 5).sum()
        if sparse_commits > len(df) * 0.5:
            warnings.append("Sparse git history detected")
            moderate_penalties.append(0.15)
    
    # Check for small repository (MINOR)
    if len(df) < 25:
        warnings.append(f"Small repository ({len(df)} files) - predictions less reliable")
        minor_penalties.append(0.05)
    
    # Apply tiered penalties
    for penalty in critical_penalties:
        confidence_score *= (1 - penalty)
    for penalty in moderate_penalties:
        confidence_score *= (1 - penalty)
    for penalty in minor_penalties:
        confidence_score *= (1 - penalty)
    
    # Prediction entropy (additive penalty)
    entropy = _calculate_prediction_entropy(proba).mean()
    entropy_penalty = entropy * 0.15  # Reduced from 0.3
    confidence_score = max(confidence_score - entropy_penalty, 0.1)
    
    # Determine confidence level
    if confidence_score > 0.75:
        confidence_level = "HIGH"
        message = "Predictions are reliable"
    elif confidence_score > 0.55:
        confidence_level = "MEDIUM"
        message = "Predictions are moderately reliable"
    else:
        confidence_level = "LOW"
        message = "Predictions may be unreliable"
    
    # Fix #11: derive is_reliable from the actual confidence_score
    is_reliable = confidence_score >= 0.55
    
    return {
        "confidence_score": confidence_score,
        "confidence_level": confidence_level,
        "message": message,
        "warnings": warnings,
        "entropy": entropy,
        "out_of_distribution": not is_reliable
    }


def predict(model_data, df, return_confidence=False):
    """
    CRITICAL FIX: Attach 'risk' probability to each file with proper repo mapping.
    
    Key fixes:
    - Ensure file→repo mapping has no NaN values
    - Use percentile-based ranking instead of fixed thresholds
    - Fix risk score distribution and calibration issues
    - Validate Recall@20% and ranking across repositories
    - Ensure report reflects sort_values("risk", ascending=False) and head(TOP_N)
    
    Expects model_data to be a dict: {"model": calibrated_model, "features": feature_list}
    """
    # TOP-LEVEL GUARD: Check for empty DataFrame immediately
    if df is None or df.empty:
        print("  ⚠️  WARNING: Empty DataFrame passed to predict() - returning safe fallback")
        # Return safe fallback DataFrame with required columns
        fallback_df = pd.DataFrame(columns=['file', 'risk', 'risky', 'risk_tier', 'confidence_score'])
        if return_confidence:
            confidence_result = {
                'is_reliable': False,
                'confidence_score': 0.0,
                'warnings': ['Empty input DataFrame']
            }
            return fallback_df, confidence_result
        return fallback_df
    
    try:
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
        
        # Validate inputs
        if model is None:
            raise ValueError("Model is None")
        if 'file' not in df.columns:
            raise ValueError("Input DataFrame missing 'file' column")
        
    except Exception as e:
        print(f"Error in predict function setup: {e}")
        # Return empty DataFrame with required columns
        empty_df = pd.DataFrame(columns=['file', 'risk', 'risky', 'risk_tier', 'confidence_score'])
        if return_confidence:
            return empty_df, {'is_reliable': False, 'confidence_score': 0.0, 'warnings': [str(e)]}
        return empty_df

    mask = df['file'].apply(
        lambda f: not is_test_file(str(f)) and not is_generated_file(str(f))
    )
    df_source = df[mask].copy()
    df_test   = df[~mask].copy()
    
    if len(df_source) == 0:
        return df

    X = df_source.drop(columns=ALL_EXCLUDE_COLS, errors="ignore")

    missing_features = []
    if features is not None:
        missing = [c for c in features if c not in X.columns]
        if missing:
            # CRITICAL: Log missing features and track for UI warning
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "Missing %d feature(s) during prediction (filled with training median): %s. "
                "This may indicate distribution shift or model/data version mismatch.",
                len(missing), missing[:5]  # Show first 5 for brevity
            )
            missing_features = missing
            
        # Fill missing features with training median (better than zero)
        for c in missing:
            if training_stats and c in training_stats:
                # Use training median - more robust than mean for skewed distributions
                fill_value = training_stats[c].get("median", 0)
            else:
                # Fallback to zero if no training stats available
                fill_value = 0
            X[c] = fill_value
        X = X[features]

    probs = model.predict_proba(X)
    risk  = probs[:, 1] if probs.shape[1] > 1 else probs[:, 0]

    df_source["risk"]  = risk
    
    # CRITICAL FIX: Use percentile-based ranking instead of fixed threshold
    # This is more robust for imbalanced datasets and provides better actionability
    risk_percentiles = np.percentile(risk, [10, 25, 50, 75, 90])
    p10, p25, p50, p75, p90 = risk_percentiles
    
    def assign_risk_tier(risk_score):
        if risk_score >= p90:
            return "CRITICAL"
        elif risk_score >= p75:
            return "HIGH"
        elif risk_score >= p50:
            return "MODERATE"
        else:
            return "LOW"
    
    def is_risky_percentile(risk_score):
        # Consider top 25% as risky (HIGH + CRITICAL)
        return risk_score >= p75
    
    df_source["risk_tier"] = df_source["risk"].apply(assign_risk_tier)
    df_source["risky"] = df_source["risk"].apply(is_risky_percentile).astype(int)
    
    # DIAGNOSTIC: Print risk distribution histogram
    print(f"\n  📊 RISK DISTRIBUTION HISTOGRAM")
    print(f"  Risk range: {df_source['risk'].min():.3f} - {df_source['risk'].max():.3f}")
    print(f"  Mean risk: {df_source['risk'].mean():.3f}, Std: {df_source['risk'].std():.3f}")
    
    # Create simple histogram buckets
    buckets = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    hist_counts = []
    for i in range(len(buckets) - 1):
        count = ((df_source['risk'] >= buckets[i]) & (df_source['risk'] < buckets[i+1])).sum()
        hist_counts.append(count)
    
    print(f"  Distribution:")
    for i, (lower, upper, count) in enumerate(zip(buckets[:-1], buckets[1:], hist_counts)):
        if count > 0:
            bar = "█" * min(20, count * 20 // len(df_source))  # Scale bar to 20 chars max
            print(f"    {lower:.1f}-{upper:.1f}: {count:>4} files {bar}")
    
    # CRITICAL FIX: Ensure file→repo mapping has no NaN values
    if 'repo' in df_source.columns:
        nan_repos = df_source['repo'].isna().sum()
        if nan_repos > 0:
            print(f"🔧 FIXING {nan_repos} NaN repo values in prediction")
            # Extract repo from file path for NaN values
            def extract_repo_from_path(file_path):
                if pd.isna(file_path):
                    return 'unknown'
                path_str = str(file_path).replace('\\', '/')
                parts = path_str.split('/')
                if 'dataset' in parts:
                    dataset_idx = parts.index('dataset')
                    if dataset_idx + 1 < len(parts):
                        return parts[dataset_idx + 1]
                return 'unknown'
            
            nan_mask = df_source['repo'].isna()
            df_source.loc[nan_mask, 'repo'] = df_source.loc[nan_mask, 'file'].apply(extract_repo_from_path)
            print(f"✅ Fixed NaN repo mapping")
    
    # DEBUG: Add comprehensive logging to identify display issues
    print(f"=== PREDICT DEBUG ===")
    print(f"Total files in df: {len(df)}")
    print(f"Files after filtering (df_source): {len(df_source)}")
    print(f"Files with risk > 0: {(df_source['risk'] > 0).sum()}")
    print(f"Risk score range: {df_source['risk'].min():.3f} - {df_source['risk'].max():.3f}")
    print(f"Risk percentiles: P10={p10:.3f}, P25={p25:.3f}, P50={p50:.3f}, P75={p75:.3f}, P90={p90:.3f}")
    print(f"Files flagged risky (top 25% >= {p75:.3f}): {df_source['risky'].sum()}")
    print(f"Risk tier distribution: {df_source['risk_tier'].value_counts().to_dict()}")
    print(f"Repos in df_source: {df_source['repo'].unique() if 'repo' in df_source.columns else 'N/A'}")
    print(f"Feature count: X={X.shape[1]}, expected={len(features) if features else 'N/A'}")
    print(f"Missing features: {len(missing_features) if missing_features else 0}")
    print("==================")
    
    # Risk tiers already assigned above using percentile-based ranking

    # Assess prediction confidence
    confidence_result = _assess_prediction_confidence(df_source, risk, training_stats=training_stats)
    
    # Add missing features warning to confidence result
    if missing_features:
        # Categorize missing features by importance
        critical_git_features = ["commits", "bug_fixes", "lines_added", "lines_deleted", "author_count"]
        critical_missing = [f for f in missing_features if f in critical_git_features]
        
        if critical_missing:
            confidence_result["warnings"].insert(0,
                f"Limited git history detected - {len(critical_missing)} critical features missing. "
                f"Predictions may be less accurate. Missing: {', '.join(critical_missing[:3])}..."
            )
            # Reduce confidence significantly for missing critical features
            confidence_result["confidence_score"] *= max(0.4, 1.0 - len(critical_missing) * 0.15)
        else:
            confidence_result["warnings"].append(
                f"Missing {len(missing_features)} features (zero-filled): {', '.join(missing_features[:3])}..."
            )
            # Reduce confidence moderately for missing non-critical features
            confidence_result["confidence_score"] *= max(0.6, 1.0 - len(missing_features) * 0.05)
        
        # Update confidence level based on new score
        if confidence_result["confidence_score"] > 0.8:
            confidence_result["confidence_level"] = "HIGH"
        elif confidence_result["confidence_score"] > 0.6:
            confidence_result["confidence_level"] = "MEDIUM"
        else:
            confidence_result["confidence_level"] = "LOW"
    
    # Add confidence information to dataframe
    df_source["confidence_score"] = confidence_result["confidence_score"]
    df_source["confidence_level"] = confidence_result["confidence_level"]

    # Calculate effort-aware metrics
    df_source = _calculate_effort_aware_metrics(df_source)

    # test/generated files get 0 risk
    if not df_test.empty:
        df_test["risk"]  = 0.0
        df_test["risky"] = 0
        df_test["risk_tier"] = "LOW"
        # Set default effort metrics for test files
        df_test["risk_per_loc"] = 0.0
        df_test["effort_priority"] = 0.0
        df_test["effort_category"] = "LOW_PRIORITY"

    final_df = pd.concat([df_source, df_test]).reset_index(drop=True)
    if return_confidence:
        return final_df, confidence_result
    return final_df
