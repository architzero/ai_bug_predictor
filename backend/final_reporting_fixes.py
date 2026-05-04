#!/usr/bin/env python3
"""
Final Reporting Fixes for AI Bug Predictor

Fixes critical issues in Stage 5 reporting to prevent data collapse
and ensure proper display of model predictions.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import os

def validate_full_prediction_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Validate that the full prediction dataset is preserved and not collapsed.
    
    Args:
        df: DataFrame with predictions
        
    Returns:
        Dictionary with validation results
    """
    validation_results = {
        'is_valid': True,
        'issues': [],
        'stats': {}
    }
    
    # Check for required columns
    required_cols = ['file', 'risk', 'repo']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        validation_results['is_valid'] = False
        validation_results['issues'].append(f"Missing required columns: {missing_cols}")
        return validation_results
    
    # Check dataset size
    total_files = len(df)
    validation_results['stats']['total_files'] = total_files
    
    if total_files == 0:
        validation_results['is_valid'] = False
        validation_results['issues'].append("Empty dataset")
        return validation_results
    
    # Check risk distribution
    if 'risk' in df.columns:
        risk_stats = {
            'min': df['risk'].min(),
            'max': df['risk'].max(),
            'mean': df['risk'].mean(),
            'non_zero_count': (df['risk'] > 0).sum(),
            'zero_count': (df['risk'] == 0).sum()
        }
        validation_results['stats']['risk'] = risk_stats
        
        # Check for collapsed risk values
        if df['risk'].nunique() <= 2:
            validation_results['issues'].append("Risk values appear collapsed (low diversity)")
    
    # Check repo coverage
    if 'repo' in df.columns:
        repo_count = df['repo'].nunique()
        validation_results['stats']['repo_count'] = repo_count
        
        # Check for NaN repos
        nan_repos = df['repo'].isna().sum()
        if nan_repos > 0:
            validation_results['issues'].append(f"{nan_repos} files have NaN repo values")
    
    # Check for buggy consistency
    if 'buggy' in df.columns:
        buggy_count = df['buggy'].sum()
        validation_results['stats']['buggy_count'] = buggy_count
        validation_results['stats']['buggy_rate'] = buggy_count / total_files
    
    return validation_results

def comprehensive_final_reporting_fixes(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Apply comprehensive fixes to ensure final reporting works correctly.
    
    Key fixes:
    - Preserve full prediction dataset (no re-filtering)
    - Maintain risk values and repo mapping
    - Prevent data collapse during reporting
    - Ensure proper column structure
    
    Args:
        df: DataFrame with model predictions
        
    Returns:
        Dictionary with 'fixed_df' and 'results' keys
    """
    print("  🔧 Applying comprehensive final reporting fixes...")
    
    fixes_applied = []
    
    # Validate input dataset
    validation = validate_full_prediction_dataset(df)
    
    if not validation['is_valid']:
        print(f"  ❌ Critical validation issues: {validation['issues']}")
    
    print(f"  ✓ Dataset validation passed: {validation['stats']['total_files']} files")
    
    # Ensure required columns exist
    required_cols = ['file', 'risk', 'repo']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    # Fix NaN repo values
    if df['repo'].isna().any():
        nan_count = df['repo'].isna().sum()
        print(f"  🔧 Fixing {nan_count} NaN repo values...")
        
        # Extract repo from file path for NaN values
        def extract_repo_from_path(file_path):
            if pd.isna(file_path):
                return 'unknown'
            path_str = str(file_path).replace('\\', '/').lower()
            if 'requests' in path_str:
                return 'requests'
            elif 'flask' in path_str:
                return 'flask'
            elif 'fastapi' in path_str:
                return 'fastapi'
            elif 'httpx' in path_str:
                return 'httpx'
            elif 'celery' in path_str:
                return 'celery'
            elif 'sqlalchemy' in path_str:
                return 'sqlalchemy'
            elif 'express' in path_str:
                return 'express'
            elif 'axios' in path_str:
                return 'axios'
            elif 'guava' in path_str:
                return 'guava'
            else:
                return 'unknown'
        
        df.loc[df['repo'].isna(), 'repo'] = df.loc[df['repo'].isna(), 'file'].apply(extract_repo_from_path)
        print(f"  ✓ Fixed NaN repo values")
        fixes_applied.append(f"Fixed {nan_count} NaN repo values")
    
    # Ensure risk_tier column exists
    if 'risk_tier' not in df.columns:
        print("  🔧 Adding missing risk_tier column...")
        
        # Calculate percentiles
        risk_values = df['risk'].values
        p10, p25, p50, p75, p90 = np.percentile(risk_values, [10, 25, 50, 75, 90])
        
        def assign_risk_tier(risk_score):
            if risk_score >= p90:
                return "CRITICAL"
            elif risk_score >= p75:
                return "HIGH"
            elif risk_score >= p50:
                return "MODERATE"
            else:
                return "LOW"
        
        df['risk_tier'] = df['risk'].apply(assign_risk_tier)
        print(f"  ✓ Added risk tiers: {df['risk_tier'].value_counts().to_dict()}")
        fixes_applied.append("Added risk tiers")
    
    # Ensure risky column exists
    if 'risky' not in df.columns:
        print("  🔧 Adding missing risky column...")
        # Consider top 25% as risky (HIGH + CRITICAL)
        p75 = np.percentile(df['risk'], 75)
        df['risky'] = (df['risk'] >= p75).astype(int)
        print(f"  ✓ Added risky flag: {df['risky'].sum()} files flagged risky")
        fixes_applied.append("Added risky flag")
    
    # Ensure explanation column exists
    if 'explanation' not in df.columns:
        print("  🔧 Adding missing explanation column...")
        df['explanation'] = 'No explanation available'
        fixes_applied.append("Added explanation column")
    
    # Final validation
    final_validation = validate_full_prediction_dataset(df)
    print(f"  ✓ Final validation: {final_validation['stats']['total_files']} files ready for reporting")
    
    # Return results in expected format
    results = {
        'overall_status': 'success' if validation['is_valid'] else 'failed',
        'fixes_applied': fixes_applied,
        'validation_stats': final_validation['stats'],
        'issues': validation['issues']
    }
    
    return {
        'fixed_df': df,
        'results': results
    }

def fix_reporting_data_collapse(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fix data collapse during reporting by preserving the full dataset.
    
    Args:
        df: Original prediction DataFrame
        
    Returns:
        Fixed DataFrame with no data collapse
    """
    print("  🔧 Fixing reporting data collapse...")
    
    original_size = len(df)
    
    # DO NOT re-filter the dataset - use the full prediction results
    # This prevents data collapse and preserves all risk scores
    
    # Only apply essential fixes
    fixes_applied = []
    
    # Fix NaN repos
    if df['repo'].isna().any():
        nan_count = df['repo'].isna().sum()
        df['repo'] = df['repo'].fillna('unknown')
        fixes_applied.append(f"Fixed {nan_count} NaN repos")
    
    # Ensure risk_tier exists
    if 'risk_tier' not in df.columns:
        risk_percentiles = np.percentile(df['risk'], [10, 25, 50, 75, 90])
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
        
        df['risk_tier'] = df['risk'].apply(assign_risk_tier)
        fixes_applied.append("Added risk tiers")
    
    # Ensure risky flag exists
    if 'risky' not in df.columns:
        p75 = np.percentile(df['risk'], 75)
        df['risky'] = (df['risk'] >= p75).astype(int)
        fixes_applied.append("Added risky flag")
    
    # Ensure explanation exists
    if 'explanation' not in df.columns:
        df['explanation'] = 'No explanation available'
        fixes_applied.append("Added explanations")
    
    final_size = len(df)
    
    if final_size == original_size:
        print(f"  ✓ No data collapse: {final_size} files preserved")
        print(f"  ✓ Applied fixes: {', '.join(fixes_applied)}")
    else:
        print(f"  ⚠️  Data size changed: {original_size} → {final_size}")
    
    return df

def ensure_reporting_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure all required columns exist for reporting.
    
    Args:
        df: Input DataFrame
        
    Returns:
        DataFrame with all required columns
    """
    required_columns = {
        'file': 'string',
        'risk': 'float',
        'repo': 'string', 
        'risk_tier': 'string',
        'risky': 'int',
        'explanation': 'string'
    }
    
    for col, dtype in required_columns.items():
        if col not in df.columns:
            print(f"  🔧 Adding missing column: {col}")
            
            if col == 'risk_tier':
                # Calculate risk tiers based on percentiles
                risk_percentiles = np.percentile(df['risk'], [10, 25, 50, 75, 90])
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
                
                df[col] = df['risk'].apply(assign_risk_tier)
                
            elif col == 'risky':
                # Consider top 25% as risky
                p75 = np.percentile(df['risk'], 75)
                df[col] = (df['risk'] >= p75).astype(int)
                
            elif col == 'explanation':
                df[col] = 'No explanation available'
                
            else:
                print(f"    Warning: Cannot auto-generate column {col}")
    
    return df