#!/usr/bin/env python3
"""
Commit Risk Simulation Fixes Implementation

Comprehensive fixes for Stage 6 to produce realistic and meaningful commit-level risk scores.
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from backend.szz import is_test_file, is_generated_file

def calculate_file_importance_weights(file_data: pd.DataFrame) -> pd.Series:
    """
    Calculate file importance weights based on LOC, churn, complexity, and coupling.
    
    Args:
        file_data: DataFrame with file-level features
        
    Returns:
        Series of importance weights for each file
    """
    print(f"🔍 CALCULATING FILE IMPORTANCE WEIGHTS")
    
    weights = pd.Series(index=file_data.index, dtype=float)
    
    # Initialize with equal weights
    weights[:] = 1.0
    
    # 1. LOC weighting (larger files are more important)
    if 'loc' in file_data.columns:
        loc_weights = np.log1p(file_data['loc'])  # Log transform to reduce extreme values
        loc_weights = loc_weights / loc_weights.max() if loc_weights.max() > 0 else loc_weights
        weights *= (0.5 + 0.5 * loc_weights)  # Scale between 0.5 and 1.0
        print(f"  Applied LOC weighting (range: {loc_weights.min():.3f} - {loc_weights.max():.3f})")
    
    # 2. Churn weighting (frequently changed files are more important)
    if 'commits' in file_data.columns:
        churn_weights = np.log1p(file_data['commits'])
        churn_weights = churn_weights / churn_weights.max() if churn_weights.max() > 0 else churn_weights
        weights *= (0.5 + 0.5 * churn_weights)
        print(f"  Applied churn weighting (range: {churn_weights.min():.3f} - {churn_weights.max():.3f})")
    
    # 3. Complexity weighting (more complex files are more important)
    if 'avg_complexity' in file_data.columns:
        complexity_weights = file_data['avg_complexity']
        complexity_weights = complexity_weights / complexity_weights.max() if complexity_weights.max() > 0 else complexity_weights
        weights *= (0.5 + 0.5 * complexity_weights)
        print(f"  Applied complexity weighting (range: {complexity_weights.min():.3f} - {complexity_weights.max():.3f})")
    
    # 4. Coupling weighting (highly coupled files are more important)
    if 'coupled_file_count' in file_data.columns:
        coupling_weights = np.log1p(file_data['coupled_file_count'])
        coupling_weights = coupling_weights / coupling_weights.max() if coupling_weights.max() > 0 else coupling_weights
        weights *= (0.5 + 0.5 * coupling_weights)
        print(f"  Applied coupling weighting (range: {coupling_weights.min():.3f} - {coupling_weights.max():.3f})")
    
    # Normalize weights to sum to 1
    if weights.sum() > 0:
        weights = weights / weights.sum()
    
    print(f"  Final weight range: {weights.min():.3f} - {weights.max():.3f}")
    
    return weights

def aggregate_file_risks_improved(file_data: pd.DataFrame, aggregation_method: str = 'hybrid') -> float:
    """
    Aggregate file-level risks correctly using max or weighted aggregation.
    
    Args:
        file_data: DataFrame with file-level risk scores
        aggregation_method: 'max', 'weighted_mean', 'hybrid'
        
    Returns:
        Aggregated commit risk score
    """
    print(f"🔍 AGGREGATING FILE RISKS (method: {aggregation_method})")
    
    if 'risk' not in file_data.columns:
        print(f"  ⚠️  No 'risk' column found")
        return 0.0
    
    if len(file_data) == 0:
        print(f"  ⚠️  No files to aggregate")
        return 0.0
    
    risk_scores = file_data['risk']
    
    # Calculate basic statistics
    max_risk = risk_scores.max()
    mean_risk = risk_scores.mean()
    weighted_mean_risk = 0.0
    
    # Calculate weighted mean using importance weights
    if aggregation_method in ['weighted_mean', 'hybrid']:
        weights = calculate_file_importance_weights(file_data)
        weighted_mean_risk = (risk_scores * weights).sum()
        print(f"  Weighted mean risk: {weighted_mean_risk:.3f}")
    
    print(f"  Max risk: {max_risk:.3f}")
    print(f"  Mean risk: {mean_risk:.3f}")
    
    # Apply aggregation method
    if aggregation_method == 'max':
        commit_risk = max_risk
        print(f"  Using max risk: {commit_risk:.3f}")
        
    elif aggregation_method == 'weighted_mean':
        commit_risk = weighted_mean_risk
        print(f"  Using weighted mean risk: {commit_risk:.3f}")
        
    elif aggregation_method == 'hybrid':
        # Hybrid: 60% max + 40% weighted mean
        # This ensures high-risk files strongly influence commit risk
        commit_risk = 0.6 * max_risk + 0.4 * weighted_mean_risk
        print(f"  Using hybrid risk (0.6*max + 0.4*weighted_mean): {commit_risk:.3f}")
        
    else:
        commit_risk = max_risk  # Default to max
        print(f"  Using default max risk: {commit_risk:.3f}")
    
    return commit_risk

def ensure_high_risk_influence(file_data: pd.DataFrame, commit_risk: float) -> Tuple[float, List[str]]:
    """
    Ensure high-risk files strongly influence commit risk.
    
    Args:
        file_data: DataFrame with file-level risk scores
        commit_risk: Current aggregated commit risk
        
    Returns:
        Tuple of (adjusted_commit_risk, high_risk_files)
    """
    print(f"🔍 ENSURING HIGH-RISK FILE INFLUENCE")
    
    if 'risk' not in file_data.columns:
        return commit_risk, []
    
    # Identify high-risk files (>0.4)
    high_risk_threshold = 0.4
    high_risk_files = file_data[file_data['risk'] > high_risk_threshold]
    
    if len(high_risk_files) == 0:
        print(f"  No high-risk files found (>0.4)")
        return commit_risk, []
    
    print(f"  Found {len(high_risk_files)} high-risk files (>0.4):")
    for _, file in high_risk_files.iterrows():
        file_name = file['file'].split('/')[-1] if 'file' in file else 'unknown'
        print(f"    {file_name}: {file['risk']:.3f}")
    
    # Calculate maximum risk among high-risk files
    max_high_risk = high_risk_files['risk'].max()
    
    # If commit risk is significantly lower than max high-risk file, boost it
    if commit_risk < max_high_risk * 0.8:
        print(f"  ⚠️  Commit risk ({commit_risk:.3f}) is much lower than max high-risk file ({max_high_risk:.3f})")
        
        # Boost commit risk to reflect high-risk file influence
        adjusted_risk = max(commit_risk, max_high_risk * 0.9)
        print(f"  🔧 Adjusted commit risk: {adjusted_risk:.3f}")
        
        return adjusted_risk, high_risk_files['file'].tolist()
    
    print(f"  ✅ Commit risk appropriately reflects high-risk files")
    return commit_risk, high_risk_files['file'].tolist()

def show_top_contributing_files(file_data: pd.DataFrame, top_k: int = 3) -> List[Dict]:
    """
    Show top contributing files with feature-based explanations.
    
    Args:
        file_data: DataFrame with file-level data
        top_k: Number of top files to show
        
    Returns:
        List of top contributing files with explanations
    """
    print(f"🔍 SHOWING TOP {top_k} CONTRIBUTING FILES")
    
    if 'risk' not in file_data.columns:
        return []
    
    # Sort by risk descending
    top_files = file_data.sort_values('risk', ascending=False).head(top_k)
    
    contributing_files = []
    
    for _, file_row in top_files.iterrows():
        file_name = os.path.basename(str(file_row['file']))
        risk_score = file_row['risk']
        risk_tier = file_row.get('risk_tier', 'UNKNOWN')
        
        # Generate feature-based explanation
        explanations = []
        
        # LOC explanation
        if 'loc' in file_row and file_row['loc'] > 0:
            loc_desc = f"large ({file_row['loc']} LOC)" if file_row['loc'] > 100 else f"moderate ({file_row['loc']} LOC)"
            explanations.append(f"{loc_desc}")
        
        # Churn explanation
        if 'commits' in file_row and file_row['commits'] > 0:
            churn_desc = f"high churn ({file_row['commits']} commits)" if file_row['commits'] > 10 else f"moderate churn ({file_row['commits']} commits)"
            explanations.append(f"{churn_desc}")
        
        # Complexity explanation
        if 'avg_complexity' in file_row and file_row['avg_complexity'] > 0:
            complexity_desc = f"complex ({file_row['avg_complexity']:.1f})" if file_row['avg_complexity'] > 5 else f"moderate complexity ({file_row['avg_complexity']:.1f})"
            explanations.append(f"{complexity_desc}")
        
        # Coupling explanation
        if 'coupled_file_count' in file_row and file_row['coupled_file_count'] > 0:
            coupling_desc = f"highly coupled ({file_row['coupled_file_count']} files)" if file_row['coupled_file_count'] > 5 else f"moderately coupled ({file_row['coupled_file_count']} files)"
            explanations.append(f"{coupling_desc}")
        
        # Bug status explanation
        if 'buggy' in file_row and file_row['buggy'] == 1:
            explanations.append("previously buggy")
        
        explanation_str = ", ".join(explanations) if explanations else "standard file"
        
        contributing_files.append({
            'file': file_name,
            'risk': risk_score,
            'tier': risk_tier,
            'explanation': explanation_str
        })
    
    print(f"  Top {len(contributing_files)} contributing files:")
    for i, file_info in enumerate(contributing_files):
        print(f"    {i+1}. {file_info['file']:<25} {file_info['risk']:.3f} ({file_info['tier']}) - {file_info['explanation']}")
    
    return contributing_files

def validate_commit_correlation(file_data: pd.DataFrame, commit_risk: float) -> Dict:
    """
    Validate commit risk correlates with highest-risk file.
    
    Args:
        file_data: DataFrame with file-level risk scores
        commit_risk: Aggregated commit risk score
        
    Returns:
        Validation results
    """
    print(f"🔍 VALIDATING COMMIT CORRELATION")
    
    validation_results = {
        'commit_risk': commit_risk,
        'max_file_risk': 0.0,
        'mean_file_risk': 0.0,
        'correlation_ratio': 0.0,
        'high_risk_files': 0,
        'validation_passed': False,
        'issues': []
    }
    
    if 'risk' not in file_data.columns or len(file_data) == 0:
        validation_results['issues'].append("No risk data available")
        return validation_results
    
    file_risks = file_data['risk']
    validation_results['max_file_risk'] = file_risks.max()
    validation_results['mean_file_risk'] = file_risks.mean()
    validation_results['high_risk_files'] = (file_risks > 0.4).sum()
    
    # Calculate correlation ratio (commit_risk / max_file_risk)
    if validation_results['max_file_risk'] > 0:
        validation_results['correlation_ratio'] = commit_risk / validation_results['max_file_risk']
    
    print(f"  Commit risk: {commit_risk:.3f}")
    print(f"  Max file risk: {validation_results['max_file_risk']:.3f}")
    print(f"  Mean file risk: {validation_results['mean_file_risk']:.3f}")
    print(f"  Correlation ratio: {validation_results['correlation_ratio']:.3f}")
    print(f"  High-risk files: {validation_results['high_risk_files']}")
    
    # Validation checks
    issues = []
    
    # Check 1: Commit risk should not be much lower than max file risk
    if validation_results['correlation_ratio'] < 0.5:
        issues.append(f"Commit risk too low compared to max file risk (ratio: {validation_results['correlation_ratio']:.3f})")
    
    # Check 2: If there are high-risk files, commit risk should be high
    if validation_results['high_risk_files'] > 0 and commit_risk < 0.3:
        issues.append(f"High-risk files present but commit risk is low ({commit_risk:.3f})")
    
    # Check 3: Commit risk should be at least as high as mean file risk
    if commit_risk < validation_results['mean_file_risk']:
        issues.append(f"Commit risk ({commit_risk:.3f}) lower than mean file risk ({validation_results['mean_file_risk']:.3f})")
    
    validation_results['issues'] = issues
    validation_results['validation_passed'] = len(issues) == 0
    
    if validation_results['validation_passed']:
        print(f"  ✅ Commit correlation validation passed")
    else:
        print(f"  ⚠️  Commit correlation validation failed:")
        for issue in issues:
            print(f"     - {issue}")
    
    return validation_results

def improved_predict_commit_risk(df: pd.DataFrame, changed_files: List[str], 
                                   aggregation_method: str = 'hybrid', 
                                   top_k: int = 3) -> Dict:
    """
    Improved commit risk prediction with realistic and meaningful scores.
    
    Args:
        df: DataFrame with file-level risk predictions
        changed_files: List of changed file paths
        aggregation_method: 'max', 'weighted_mean', 'hybrid'
        top_k: Number of top contributing files to show
        
    Returns:
        Comprehensive commit risk prediction results
    """
    print(f"🚀 IMPROVED COMMIT RISK PREDICTION")
    print(f"  ══════════════════════════════════════════════════════════════")
    
    # Filter out test and generated files
    filtered_files = [
        f for f in changed_files
        if not is_test_file(f) and not is_generated_file(f)
    ]
    
    print(f"  Changed files: {len(changed_files)}")
    print(f"  After filtering: {len(filtered_files)}")
    
    if not filtered_files:
        return {
            'commit_risk': 0.0,
            'top_files': [],
            'validation': {'validation_passed': False, 'issues': ['No valid files to analyze']},
            'aggregation_method': aggregation_method
        }
    
    # Get file data for changed files
    subset = df[df["file"].isin(filtered_files)].copy()
    
    if len(subset) == 0:
        return {
            'commit_risk': 0.0,
            'top_files': [],
            'validation': {'validation_passed': False, 'issues': ['No matching files in dataset']},
            'aggregation_method': aggregation_method
        }
    
    print(f"  Files in dataset: {len(subset)}")
    
    # Step 1: Aggregate file risks
    commit_risk = aggregate_file_risks_improved(subset, aggregation_method)
    
    # Step 2: Ensure high-risk files influence commit risk
    adjusted_risk, high_risk_files = ensure_high_risk_influence(subset, commit_risk)
    
    # Step 3: Show top contributing files
    top_files = show_top_contributing_files(subset, top_k)
    
    # Step 4: Validate commit correlation
    validation_results = validate_commit_correlation(subset, adjusted_risk)
    
    # Prepare results
    results = {
        'commit_risk': adjusted_risk,
        'top_files': top_files,
        'high_risk_files': high_risk_files,
        'validation': validation_results,
        'aggregation_method': aggregation_method,
        'file_count': len(subset),
        'filtered_file_count': len(filtered_files)
    }
    
    # Summary
    print(f"\n📊 COMMIT RISK SUMMARY:")
    print(f"  Final commit risk: {adjusted_risk:.3f}")
    print(f"  Aggregation method: {aggregation_method}")
    print(f"  Files analyzed: {len(subset)}")
    print(f"  High-risk files: {len(high_risk_files)}")
    print(f"  Validation passed: {validation_results['validation_passed']}")
    
    if validation_results['issues']:
        print(f"  Issues: {len(validation_results['issues'])}")
    
    print(f"  ══════════════════════════════════════════════════════════════")
    
    return results

# Backward compatibility function
def predict_commit_risk(df, changed_files):
    """
    Backward compatibility wrapper for the original function.
    Uses improved prediction with hybrid aggregation.
    """
    results = improved_predict_commit_risk(df, changed_files, aggregation_method='hybrid')
    top_files_df = df[df["file"].isin([f['file'] for f in results['top_files']])].copy()
    
    return results['commit_risk'], top_files_df
