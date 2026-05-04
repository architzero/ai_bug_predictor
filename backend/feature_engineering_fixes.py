#!/usr/bin/env python3
"""
Feature Engineering Fixes Implementation

Comprehensive fixes for Stage 2 to ensure correct, reliable, and leakage-free ML inputs.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from backend.feature_validation import comprehensive_feature_validation

def apply_feature_engineering_fixes(df: pd.DataFrame, cache_path: Optional[str] = None) -> pd.DataFrame:
    """
    Apply comprehensive feature engineering fixes.
    
    Args:
        df: Input DataFrame with features and labels
        cache_path: Optional cache file path for validation
        
    Returns:
        Fixed DataFrame with clean features
    """
    print(f"🔧 APPLYING FEATURE ENGINEERING FIXES")
    print(f"  ══════════════════════════════════════════════════════════════")
    
    original_shape = df.shape
    print(f"  Original shape: {original_shape}")
    
    # 1. CRITICAL FIX: Remove bug type features entirely
    if 'bug_type' in df.columns:
        print(f"  🗑️  Removing bug_type column (CRITICAL FIX: class dominance prevention)")
        df = df.drop(columns=['bug_type'])
    
    if 'bug_type_confidence' in df.columns:
        print(f"  🗑️  Removing bug_type_confidence column")
        df = df.drop(columns=['bug_type_confidence'])
    
    # 2. CRITICAL FIX: Remove filename-based features (leakage prevention)
    filename_cols = [col for col in df.columns if any(pattern in col.lower() for pattern in 
                    ['filename', 'file', 'path', 'hash', 'basename', 'dirname'])]
    if filename_cols:
        print(f"  🗑️  Removing filename-based features: {filename_cols}")
        df = df.drop(columns=filename_cols)
    
    # 3. CRITICAL FIX: Remove repository identifiers (leakage prevention)
    repo_cols = [col for col in df.columns if any(pattern in col.lower() for pattern in 
                ['repo', 'project', 'repository'])]
    if repo_cols:
        print(f"  🗑️  Removing repository identifiers: {repo_cols}")
        df = df.drop(columns=repo_cols)
    
    # 4. CRITICAL FIX: Remove data leakage columns
    from backend.feature_constants import LEAKAGE_COLS
    leakage_cols = [col for col in df.columns if col in LEAKAGE_COLS]
    if leakage_cols:
        print(f"  🗑️  Removing leakage columns: {leakage_cols}")
        df = df.drop(columns=leakage_cols)
    
    # 5. Remove non-feature columns
    from backend.feature_constants import NON_FEATURE_COLS
    non_feature_cols = [col for col in df.columns if col in NON_FEATURE_COLS]
    if non_feature_cols:
        print(f"  🗑️  Removing non-feature columns: {non_feature_cols}")
        df = df.drop(columns=non_feature_cols)
    
    # 6. Validate feature distributions
    feature_cols = [col for col in df.columns if col not in ['buggy']]
    if feature_cols:
        print(f"  ✅ Validating {len(feature_cols)} feature columns...")
        
        # Check for degenerate features
        degenerate_cols = []
        for col in feature_cols:
            if df[col].dtype in ['int64', 'float64']:
                if df[col].var() < 1e-6:  # Near-zero variance
                    degenerate_cols.append(col)
        
        if degenerate_cols:
            print(f"  🗑️  Removing degenerate features: {degenerate_cols}")
            df = df.drop(columns=degenerate_cols)
        
        # Check for high missing values
        high_missing_cols = []
        for col in feature_cols:
            if col in df.columns:
                missing_pct = df[col].isna().sum() / len(df)
                if missing_pct > 0.1:  # >10% missing
                    high_missing_cols.append(col)
        
        if high_missing_cols:
            print(f"  ⚠️  Features with high missing values: {high_missing_cols}")
            # Impute instead of dropping to preserve data
            for col in high_missing_cols:
                if df[col].dtype in ['int64', 'float64']:
                    df[col] = df[col].fillna(df[col].median())
                else:
                    df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else 'unknown')
    
    # 7. Add label back if it was removed
    if 'buggy' not in df.columns:
        print(f"  ⚠️  WARNING: 'buggy' label column missing - cannot proceed")
        return df
    
    # 8. Final validation
    print(f"  Final shape: {df.shape}")
    print(f"  Features removed: {original_shape[1] - df.shape[1]}")
    
    # Run comprehensive validation
    validation_results = comprehensive_feature_validation(df, cache_path=cache_path)
    
    if validation_results['overall_status'] == 'FAIL':
        print(f"  🚨 CRITICAL: Feature validation failed!")
        print(f"  Issues: {validation_results['critical_issues']}")
    else:
        print(f"  ✅ Feature validation passed")
    
    print(f"  ══════════════════════════════════════════════════════════════")
    
    return df

def extract_meaningful_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract only meaningful features for ML training.
    
    Args:
        df: Input DataFrame
        
    Returns:
        DataFrame with only meaningful features
    """
    print(f"🔍 EXTRACTING MEANINGFUL FEATURES")
    
    # Static features: complexity, LOC, function length
    static_features = [
        'loc', 'avg_complexity', 'max_complexity', 'functions',
        'avg_params', 'max_function_length', 'complexity_vs_baseline',
        'complexity_density', 'complexity_per_function', 'loc_per_function'
    ]
    
    # Git features: commits, churn, recency
    git_features = [
        'commits', 'lines_added', 'lines_deleted', 'max_added',
        'commits_2w', 'commits_1m', 'commits_3m',
        'recent_churn_ratio', 'recent_activity_score',
        'churn_ratio', 'instability_score', 'avg_commit_size',
        'max_commit_ratio'
    ]
    
    # Developer features: author count, ownership
    dev_features = [
        'author_count', 'ownership', 'low_history_flag',
        'minor_contributor_ratio', 'author_entropy', 'experience_score'
    ]
    
    # Temporal features (non-leaky)
    temporal_features = [
        'file_age_bucket', 'days_since_last_change', 'recency_ratio'
    ]
    
    # Coupling features
    coupling_features = [
        'max_coupling_strength', 'coupled_file_count',
        'coupled_recent_missing', 'coupling_risk'
    ]
    
    # Burst features
    burst_features = [
        'commit_burst_score', 'recent_commit_burst',
        'burst_ratio', 'burst_risk'
    ]
    
    # Language feature
    language_features = ['language_id']
    
    # Combine all meaningful features
    all_meaningful_features = (
        static_features + git_features + dev_features + 
        temporal_features + coupling_features + burst_features + 
        language_features
    )
    
    # Filter to only available columns
    available_features = [col for col in all_meaningful_features if col in df.columns]
    
    print(f"  Available meaningful features: {len(available_features)}")
    
    # Return DataFrame with only meaningful features plus label
    result_cols = available_features + ['buggy'] if 'buggy' in df.columns else available_features
    return df[result_cols]

def fix_bug_type_classifier_integration(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fix bug type classifier integration to prevent pipeline contamination.
    
    Args:
        df: Input DataFrame
        
    Returns:
        Fixed DataFrame without bug type features
    """
    print(f"🔧 FIXING BUG TYPE CLASSIFIER INTEGRATION")
    
    # Check if bug type features exist
    bug_type_cols = [col for col in df.columns if 'bug_type' in col.lower()]
    
    if bug_type_cols:
        print(f"  🗑️  Removing bug type features: {bug_type_cols}")
        df = df.drop(columns=bug_type_cols)
        print(f"  ✅ Bug type classifier integration fixed - features removed from pipeline")
    else:
        print(f"  ✅ No bug type features found - integration already clean")
    
    return df

def validate_feature_alignment(df: pd.DataFrame) -> Dict:
    """
    Validate that features are correctly aligned with labeled files.
    
    Args:
        df: DataFrame to validate
        
    Returns:
        Validation results
    """
    print(f"🔍 VALIDATING FEATURE ALIGNMENT")
    
    results = {
        'total_files': len(df),
        'labeled_files': 0,
        'unlabeled_files': 0,
        'feature_completeness': 0,
        'alignment_issues': []
    }
    
    if 'buggy' in df.columns:
        results['labeled_files'] = df['buggy'].notna().sum()
        results['unlabeled_files'] = len(df) - results['labeled_files']
    
    # Check feature completeness
    feature_cols = [col for col in df.columns if col not in ['buggy']]
    complete_features = 0
    
    for col in feature_cols:
        missing_pct = df[col].isna().sum() / len(df)
        if missing_pct < 0.1:  # <10% missing
            complete_features += 1
        elif missing_pct > 0.5:  # >50% missing
            results['alignment_issues'].append(f"High missing values in {col}: {missing_pct:.1%}")
    
    results['feature_completeness'] = complete_features / len(feature_cols) if feature_cols else 0
    
    print(f"  Total files: {results['total_files']}")
    print(f"  Labeled files: {results['labeled_files']}")
    print(f"  Feature completeness: {results['feature_completeness']:.1%}")
    
    if results['alignment_issues']:
        print(f"  Alignment issues: {len(results['alignment_issues'])}")
        for issue in results['alignment_issues']:
            print(f"    - {issue}")
    else:
        print(f"  ✅ No alignment issues detected")
    
    return results

def comprehensive_feature_engineering_fix(df: pd.DataFrame, cache_path: Optional[str] = None) -> pd.DataFrame:
    """
    Apply comprehensive feature engineering fixes from root to top.
    
    Args:
        df: Input DataFrame
        cache_path: Optional cache file path
        
    Returns:
        Fixed DataFrame ready for ML training
    """
    print(f"🚀 COMPREHENSIVE FEATURE ENGINEERING FIXES")
    print(f"  ══════════════════════════════════════════════════════════════")
    
    # Step 1: Apply core fixes
    df = apply_feature_engineering_fixes(df, cache_path)
    
    # Step 2: Extract meaningful features only
    df = extract_meaningful_features(df)
    
    # Step 3: Fix bug type classifier integration
    df = fix_bug_type_classifier_integration(df)
    
    # Step 4: Validate feature alignment
    alignment_results = validate_feature_alignment(df)
    
    # Step 5: Final validation
    print(f"\n📊 FINAL VALIDATION RESULTS:")
    print(f"  Final shape: {df.shape}")
    print(f"  Feature columns: {len([col for col in df.columns if col != 'buggy'])}")
    print(f"  Label completeness: {alignment_results['feature_completeness']:.1%}")
    
    if alignment_results['alignment_issues']:
        print(f"  ⚠️  {len(alignment_results['alignment_issues'])} alignment issues remain")
    else:
        print(f"  ✅ Features are properly aligned and ready for ML training")
    
    print(f"  ══════════════════════════════════════════════════════════════")
    
    return df
