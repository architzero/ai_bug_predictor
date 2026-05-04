#!/usr/bin/env python3
"""
Feature Engineering Validation System

Ensures correct, reliable, and leakage-free ML inputs through comprehensive validation.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import Counter
import warnings

def validate_feature_distribution(df: pd.DataFrame, feature_cols: List[str]) -> Dict:
    """
    Validate feature distributions for diversity and non-degeneracy.
    
    Args:
        df: DataFrame with features
        feature_cols: List of feature column names
        
    Returns:
        Validation results dictionary
    """
    print(f"🔍 Validating feature distributions...")
    
    results = {
        'total_features': len(feature_cols),
        'valid_features': 0,
        'degenerate_features': [],
        'high_variance_features': [],
        'low_variance_features': [],
        'missing_values': {},
        'feature_types': {}
    }
    
    for col in feature_cols:
        if col not in df.columns:
            continue
            
        series = df[col]
        
        # Check for missing values
        missing_pct = series.isna().sum() / len(series)
        if missing_pct > 0.1:  # >10% missing
            results['missing_values'][col] = missing_pct
        
        # Check variance
        if series.dtype in ['int64', 'float64']:
            variance = series.var()
            if variance < 1e-6:  # Near-zero variance
                results['degenerate_features'].append(col)
            elif variance > series.std() * 10:  # High variance
                results['high_variance_features'].append(col)
            elif variance < series.std() * 0.1:  # Low variance
                results['low_variance_features'].append(col)
        
        # Track feature types
        results['feature_types'][col] = str(series.dtype)
        results['valid_features'] += 1
    
    # Validation warnings
    if results['degenerate_features']:
        print(f"  ⚠️  Found {len(results['degenerate_features'])} degenerate features")
        print(f"      {results['degenerate_features'][:5]}")
    
    if results['missing_values']:
        print(f"  ⚠️  Found {len(results['missing_values'])} features with high missing values")
    
    return results

def validate_leakage_prevention(df: pd.DataFrame) -> Dict:
    """
    Validate that leakage prevention is working correctly.
    
    Args:
        df: DataFrame to validate
        
    Returns:
        Validation results dictionary
    """
    print(f"🔍 Validating leakage prevention...")
    
    from backend.feature_constants import NON_FEATURE_COLS, LEAKAGE_COLS, ALL_EXCLUDE_COLS
    
    results = {
        'total_columns': len(df.columns),
        'non_feature_cols_found': [],
        'leakage_cols_found': [],
        'filename_based_features': [],
        'repo_based_features': [],
        'suspicious_correlations': []
    }
    
    # Check for non-feature columns
    for col in ALL_EXCLUDE_COLS:
        if col in df.columns:
            if col in NON_FEATURE_COLS:
                results['non_feature_cols_found'].append(col)
            elif col in LEAKAGE_COLS:
                results['leakage_cols_found'].append(col)
    
    # Check for filename-based features (potential leakage)
    filename_patterns = ['filename', 'file', 'path', 'hash', 'basename', 'dirname']
    for col in df.columns:
        if any(pattern in col.lower() for pattern in filename_patterns):
            results['filename_based_features'].append(col)
    
    # Check for repository-based features (potential leakage)
    repo_patterns = ['repo', 'project', 'repository']
    for col in df.columns:
        if any(pattern in col.lower() for pattern in repo_patterns):
            results['repo_based_features'].append(col)
    
    # Check for suspicious correlations with label
    if 'buggy' in df.columns:
        for col in df.columns:
            if col != 'buggy' and col not in ALL_EXCLUDE_COLS:
                try:
                    corr = abs(df[col].corr(df['buggy']))
                    if corr > 0.9:  # Very high correlation (potential leakage)
                        results['suspicious_correlations'].append((col, corr))
                except:
                    pass
    
    # Validation warnings
    if results['leakage_cols_found']:
        print(f"  🚨 CRITICAL: Found {len(results['leakage_cols_found'])} leakage columns!")
        print(f"      {results['leakage_cols_found']}")
    
    if results['filename_based_features']:
        print(f"  ⚠️  Found {len(results['filename_based_features'])} filename-based features")
    
    if results['suspicious_correlations']:
        print(f"  ⚠️  Found {len(results['suspicious_correlations'])} suspicious correlations")
    
    return results

def validate_bug_type_distribution(bug_types: List[str]) -> Dict:
    """
    Validate bug type distribution for class dominance.
    
    Args:
        bug_types: List of bug type labels
        
    Returns:
        Validation results dictionary
    """
    print(f"🔍 Validating bug type distribution...")
    
    if not bug_types:
        return {
            'total_samples': 0,
            'unique_types': 0,
            'dominant_class': None,
            'dominant_percentage': 0.0,
            'is_balanced': True,
            'status': 'NO_DATA'
        }
    
    counts = Counter(bug_types)
    total = len(bug_types)
    
    # Find dominant class
    dominant_class, dominant_count = max(counts.items(), key=lambda x: x[1])
    dominant_percentage = dominant_count / total
    
    # Check for dominance (>90%)
    is_balanced = dominant_percentage <= 0.9
    
    results = {
        'total_samples': total,
        'unique_types': len(counts),
        'class_distribution': dict(counts),
        'dominant_class': dominant_class,
        'dominant_percentage': dominant_percentage,
        'is_balanced': is_balanced,
        'status': 'BALANCED' if is_balanced else 'DOMINANT'
    }
    
    # Validation warnings
    if not is_balanced:
        print(f"  🚨 CRITICAL: Bug type class dominance detected!")
        print(f"     Class '{dominant_class}' is {dominant_percentage:.1%} of all samples")
        print(f"     This destroys interpretability and signal quality")
        print(f"     DISCARDING bug type feature entirely")
    else:
        print(f"  ✅ Bug type distribution is balanced")
    
    return results

def validate_cache_suspicion(df: pd.DataFrame, cache_path: Optional[str] = None) -> Dict:
    """
    Validate if cached data looks suspicious and should be recomputed.
    
    Args:
        df: DataFrame to validate
        cache_path: Optional cache file path
        
    Returns:
        Validation results dictionary
    """
    print(f"🔍 Validating cache suspicion...")
    
    results = {
        'suspicious_indicators': [],
        'recompute_recommended': False,
        'total_samples': len(df),
        'feature_count': len([col for col in df.columns if col not in ['file', 'buggy', 'repo']]),
        'cache_age_hours': None
    }
    
    # Check for suspiciously low sample count
    if results['total_samples'] < 50:
        results['suspicious_indicators'].append('Very low sample count')
        results['recompute_recommended'] = True
    
    # Check for suspiciously high bug rate
    if 'buggy' in df.columns:
        bug_rate = df['buggy'].mean()
        if bug_rate > 0.8:  # >80% buggy
            results['suspicious_indicators'].append('Very high bug rate')
            results['recompute_recommended'] = True
        elif bug_rate < 0.01:  # <1% buggy
            results['suspicious_indicators'].append('Very low bug rate')
            results['recompute_recommended'] = True
    
    # Check for suspicious feature count
    if results['feature_count'] < 5:
        results['suspicious_indicators'].append('Very low feature count')
        results['recompute_recommended'] = True
    elif results['feature_count'] > 100:
        results['suspicious_indicators'].append('Very high feature count (possible leakage)')
    
    # Check cache age if provided
    if cache_path:
        try:
            import os
            from datetime import datetime
            mtime = os.path.getmtime(cache_path)
            cache_age = (datetime.now().timestamp() - mtime) / 3600  # hours
            results['cache_age_hours'] = cache_age
            
            if cache_age > 48:  # >48 hours old
                results['suspicious_indicators'].append('Cache is very old')
                results['recompute_recommended'] = True
        except:
            pass
    
    # Validation warnings
    if results['suspicious_indicators']:
        print(f"  ⚠️  Found {len(results['suspicious_indicators'])} suspicious indicators:")
        for indicator in results['suspicious_indicators']:
            print(f"      - {indicator}")
        
        if results['recompute_recommended']:
            print(f"  🔄 RECOMMENDATION: Recompute features from scratch")
    else:
        print(f"  ✅ Cache looks fresh and valid")
    
    return results

def comprehensive_feature_validation(df: pd.DataFrame, bug_types: Optional[List[str]] = None, 
                                     cache_path: Optional[str] = None) -> Dict:
    """
    Run comprehensive feature validation.
    
    Args:
        df: DataFrame with features and labels
        bug_types: Optional list of bug type labels
        cache_path: Optional cache file path
        
    Returns:
        Comprehensive validation results
    """
    print(f"🔍 COMPREHENSIVE FEATURE VALIDATION")
    print(f"  ══════════════════════════════════════════════════════════════")
    
    # Get feature columns
    from backend.feature_constants import ALL_EXCLUDE_COLS
    feature_cols = [col for col in df.columns if col not in ALL_EXCLUDE_COLS]
    
    # Run all validations
    results = {
        'feature_distribution': validate_feature_distribution(df, feature_cols),
        'leakage_prevention': validate_leakage_prevention(df),
        'cache_suspicion': validate_cache_suspicion(df, cache_path),
        'overall_status': 'PASS',
        'critical_issues': [],
        'warnings': []
    }
    
    # Add bug type validation if provided
    if bug_types:
        results['bug_type_distribution'] = validate_bug_type_distribution(bug_types)
    
    # Determine overall status
    if results['leakage_prevention']['leakage_cols_found']:
        results['overall_status'] = 'FAIL'
        results['critical_issues'].append('Data leakage detected')
    
    if results['feature_distribution']['degenerate_features']:
        results['overall_status'] = 'FAIL'
        results['critical_issues'].append('Degenerate features detected')
    
    if bug_types and not results['bug_type_distribution']['is_balanced']:
        results['overall_status'] = 'FAIL'
        results['critical_issues'].append('Bug type class dominance')
    
    if results['cache_suspicion']['recompute_recommended']:
        results['warnings'].append('Cache recompute recommended')
    
    # Final status
    print(f"\n  📊 VALIDATION SUMMARY:")
    print(f"     Overall Status: {results['overall_status']}")
    print(f"     Critical Issues: {len(results['critical_issues'])}")
    print(f"     Warnings: {len(results['warnings'])}")
    
    if results['overall_status'] == 'PASS':
        print(f"     ✅ Features are ready for ML training")
    else:
        print(f"     ❌ Features need fixes before training")
    
    print(f"  ══════════════════════════════════════════════════════════════")
    
    return results
