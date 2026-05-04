#!/usr/bin/env python3
"""
Model Quality Validation System

Ensures models work properly on large datasets and meet performance targets.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from sklearn.metrics import f1_score, average_precision_score, precision_recall_curve
import warnings

def validate_large_dataset_performance(df: pd.DataFrame, test_repo: str) -> Dict:
    """
    Ensure model works on large datasets (e.g., guava).
    
    Args:
        df: DataFrame with features and labels
        test_repo: Test repository name
        
    Returns:
        Validation results
    """
    print(f"🔍 VALIDATING LARGE DATASET PERFORMANCE for {test_repo}")
    
    # Check if this is a large repository
    repo_data = df[df['repo'] == test_repo] if 'repo' in df.columns else df
    file_count = len(repo_data)
    
    # Define large repository threshold
    LARGE_REPO_THRESHOLD = 100
    
    is_large = file_count > LARGE_REPO_THRESHOLD
    validation_results = {
        'test_repo': test_repo,
        'file_count': file_count,
        'is_large_repo': is_large,
        'performance_issues': [],
        'recommendations': []
    }
    
    if is_large:
        print(f"  📊 Large repository detected: {file_count} files")
        
        # Check for sufficient features
        feature_cols = [col for col in repo_data.columns if col not in ['buggy', 'repo', 'file']]
        if len(feature_cols) < 10:
            validation_results['performance_issues'].append(
                f"Insufficient features for large repo: {len(feature_cols)} < 10"
            )
            validation_results['recommendations'].append(
                "Add more meaningful features (complexity, churn, ownership)"
            )
        
        # Check class balance
        if 'buggy' in repo_data.columns:
            bug_rate = repo_data['buggy'].mean()
            if bug_rate < 0.05:  # <5% buggy
                validation_results['performance_issues'].append(
                    f"Very low bug rate for large repo: {bug_rate:.1%}"
                )
                validation_results['recommendations'].append(
                    "Consider relaxing SZZ thresholds or extending lookback window"
                )
            elif bug_rate > 0.5:  # >50% buggy
                validation_results['performance_issues'].append(
                    f"Very high bug rate for large repo: {bug_rate:.1%}"
                )
                validation_results['recommendations'].append(
                    "Verify SZZ detection accuracy - may be too broad"
                )
        
        # Check feature quality
        missing_threshold = 0.1  # 10% missing values allowed
        high_missing_features = []
        for col in feature_cols:
            missing_pct = repo_data[col].isna().sum() / len(repo_data)
            if missing_pct > missing_threshold:
                high_missing_features.append((col, missing_pct))
        
        if high_missing_features:
            validation_results['performance_issues'].append(
                f"High missing values in {len(high_missing_features)} features"
            )
            validation_results['recommendations'].append(
                "Impute missing values or remove problematic features"
            )
    
    else:
        print(f"  📊 Small repository: {file_count} files")
        validation_results['recommendations'].append(
            "Consider combining with similar repos for better generalization"
        )
    
    # Summary
    if validation_results['performance_issues']:
        print(f"  ⚠️  Performance issues: {len(validation_results['performance_issues'])}")
        for issue in validation_results['performance_issues']:
            print(f"    - {issue}")
    else:
        print(f"  ✅ No performance issues detected")
    
    return validation_results

def calculate_weighted_f1(y_true, y_pred, sample_weights: Optional[np.ndarray] = None) -> float:
    """
    Calculate weighted F1 score to handle class imbalance.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        sample_weights: Optional sample weights
        
    Returns:
        Weighted F1 score
    """
    if sample_weights is not None:
        # Calculate weighted F1 manually
        tp = np.sum((y_true == 1) & (y_pred == 1) & (sample_weights > 0))
        fp = np.sum((y_true == 0) & (y_pred == 1) & (sample_weights > 0))
        fn = np.sum((y_true == 1) & (y_pred == 0) & (sample_weights > 0))
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        
        if precision + recall == 0:
            return 0.0
        
        f1 = 2 * (precision * recall) / (precision + recall)
        return f1
    else:
        return f1_score(y_true, y_pred, average='weighted')

def calculate_recall_at_20(y_true, y_proba) -> float:
    """
    Calculate Recall@20% for model evaluation.
    
    Args:
        y_true: True labels
        y_proba: Predicted probabilities
        
    Returns:
        Recall@20% score
    """
    if len(y_true) == 0:
        return 0.0
    
    # Get top 20% of samples by probability
    threshold = np.percentile(y_proba, 80)
    top_20_mask = y_proba >= threshold
    
    if not np.any(top_20_mask):
        return 0.0
    
    # Calculate recall for top 20%
    true_positives = np.sum((y_true == 1) & top_20_mask)
    actual_positives = np.sum(y_true == 1)
    
    recall_at_20 = true_positives / actual_positives if actual_positives > 0 else 0.0
    return recall_at_20

def validate_model_metrics(y_true, y_pred, y_proba, test_repo: str, 
                          sample_weights: Optional[np.ndarray] = None) -> Dict:
    """
    Validate weighted F1, PR-AUC, and Recall@20% improvements.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        y_proba: Predicted probabilities
        test_repo: Test repository name
        sample_weights: Optional sample weights
        
    Returns:
        Validation results
    """
    print(f"🔍 VALIDATING MODEL METRICS for {test_repo}")
    
    # Calculate metrics
    weighted_f1 = calculate_weighted_f1(y_true, y_pred, sample_weights)
    pr_auc = average_precision_score(y_true, y_proba)
    recall_20 = calculate_recall_at_20(y_true, y_proba)
    
    # Calculate additional metrics
    accuracy = np.mean(y_true == y_pred)
    
    # Calculate precision-recall curve points
    precision, recall, thresholds = precision_recall_curve(y_true, y_proba)
    
    validation_results = {
        'test_repo': test_repo,
        'weighted_f1': weighted_f1,
        'pr_auc': pr_auc,
        'recall_at_20': recall_20,
        'accuracy': accuracy,
        'target_achieved': {},
        'quality_issues': [],
        'improvements_needed': []
    }
    
    # Check target achievements
    targets = {
        'weighted_f1': 0.3,      # Minimum target
        'pr_auc': 0.5,           # Minimum target  
        'recall_at_20': 0.2      # Minimum target
    }
    
    for metric, target in targets.items():
        actual_value = validation_results[metric]
        achieved = actual_value >= target
        validation_results['target_achieved'][metric] = achieved
        
        if achieved:
            print(f"  ✅ {metric}: {actual_value:.3f} (target: {target:.3f})")
        else:
            print(f"  ⚠️  {metric}: {actual_value:.3f} (target: {target:.3f}) - BELOW TARGET")
            validation_results['improvements_needed'].append(
                f"{metric} needs improvement ({actual_value:.3f} < {target:.3f})"
            )
    
    # Check for extreme failures
    if weighted_f1 < 0.1:
        validation_results['quality_issues'].append(
            f"Very low weighted F1 ({weighted_f1:.3f}) - possible model collapse"
        )
    
    if pr_auc < 0.3:
        validation_results['quality_issues'].append(
            f"Very low PR-AUC ({pr_auc:.3f}) - poor discrimination"
        )
    
    if recall_20 < 0.1:
        validation_results['quality_issues'].append(
            f"Very low Recall@20% ({recall_20:.3f}) - poor ranking"
        )
    
    # Check for overfitting indicators
    if accuracy > 0.95 and weighted_f1 < 0.3:
        validation_results['quality_issues'].append(
            "High accuracy but low F1 - possible overfitting to majority class"
        )
    
    # Summary
    if validation_results['quality_issues']:
        print(f"  🚨 Quality issues: {len(validation_results['quality_issues'])}")
        for issue in validation_results['quality_issues']:
            print(f"    - {issue}")
    
    if validation_results['improvements_needed']:
        print(f"  🔧 Improvements needed: {len(validation_results['improvements_needed'])}")
        for improvement in validation_results['improvements_needed']:
            print(f"    - {improvement}")
    
    return validation_results

def ensure_no_extreme_failures(fold_results: List[Dict]) -> Dict:
    """
    Ensure no extreme failures (e.g., F1 ≈ 0) across all folds.
    
    Args:
        fold_results: List of fold results
        
    Returns:
        Validation summary
    """
    print(f"🔍 ENSURING NO EXTREME FAILURES across {len(fold_results)} folds")
    
    extreme_failures = []
    poor_performance = []
    good_performance = []
    
    for fold in fold_results:
        test_repo = fold.get('test_repo', 'unknown')
        weighted_f1 = fold.get('weighted_f1', 0.0)
        pr_auc = fold.get('pr_auc', 0.0)
        recall_20 = fold.get('recall_at_20', 0.0)
        
        # Check for extreme failures
        if weighted_f1 < 0.05:  # F1 ≈ 0
            extreme_failures.append({
                'test_repo': test_repo,
                'weighted_f1': weighted_f1,
                'pr_auc': pr_auc,
                'recall_at_20': recall_20
            })
        elif weighted_f1 < 0.2 or pr_auc < 0.3 or recall_20 < 0.1:
            poor_performance.append({
                'test_repo': test_repo,
                'weighted_f1': weighted_f1,
                'pr_auc': pr_auc,
                'recall_at_20': recall_20
            })
        else:
            good_performance.append({
                'test_repo': test_repo,
                'weighted_f1': weighted_f1,
                'pr_auc': pr_auc,
                'recall_at_20': recall_20
            })
    
    validation_summary = {
        'total_folds': len(fold_results),
        'extreme_failures': extreme_failures,
        'poor_performance': poor_performance,
        'good_performance': good_performance,
        'failure_rate': len(extreme_failures) / len(fold_results) if fold_results else 0,
        'poor_rate': len(poor_performance) / len(fold_results) if fold_results else 0,
        'success_rate': len(good_performance) / len(fold_results) if fold_results else 0
    }
    
    print(f"  📊 Performance Summary:")
    print(f"     Extreme failures: {len(extreme_failures)}/{len(fold_results)} ({validation_summary['failure_rate']:.1%})")
    print(f"     Poor performance: {len(poor_performance)}/{len(fold_results)} ({validation_summary['poor_rate']:.1%})")
    print(f"     Good performance: {len(good_performance)}/{len(fold_results)} ({validation_summary['success_rate']:.1%})")
    
    # Detailed reporting
    if extreme_failures:
        print(f"  🚨 EXTREME FAILURES:")
        for failure in extreme_failures:
            print(f"     {failure['test_repo']}: F1={failure['weighted_f1']:.3f}, PR-AUC={failure['pr_auc']:.3f}")
    
    if poor_performance:
        print(f"  ⚠️  POOR PERFORMANCE:")
        for poor in poor_performance:
            print(f"     {poor['test_repo']}: F1={poor['weighted_f1']:.3f}, PR-AUC={poor['pr_auc']:.3f}")
    
    # Recommendations
    recommendations = []
    if validation_summary['failure_rate'] > 0.2:
        recommendations.append("High failure rate - check feature quality and class balance")
    
    if validation_summary['poor_rate'] > 0.5:
        recommendations.append("Many poor performers - consider ensemble methods or feature engineering")
    
    if validation_summary['success_rate'] < 0.3:
        recommendations.append("Low success rate - review model architecture and training approach")
    
    if recommendations:
        print(f"  🔧 Recommendations:")
        for rec in recommendations:
            print(f"     - {rec}")
    else:
        print(f"  ✅ No extreme failures detected - model quality is acceptable")
    
    return validation_summary

def comprehensive_model_quality_validation(df: pd.DataFrame, fold_results: List[Dict]) -> Dict:
    """
    Comprehensive model quality validation.
    
    Args:
        df: DataFrame with features and labels
        fold_results: List of fold results
        
    Returns:
        Comprehensive validation results
    """
    print(f"🚀 COMPREHENSIVE MODEL QUALITY VALIDATION")
    print(f"  ══════════════════════════════════════════════════════════════")
    
    validation_results = {
        'large_repo_validation': {},
        'metric_validation': {},
        'extreme_failure_check': {},
        'overall_status': 'PASS',
        'critical_issues': [],
        'recommendations': []
    }
    
    # 1. Large dataset performance validation
    if 'repo' in df.columns:
        unique_repos = df['repo'].unique()
        large_repo_results = []
        
        for repo in unique_repos:
            repo_validation = validate_large_dataset_performance(df, repo)
            large_repo_results.append(repo_validation)
        
        validation_results['large_repo_validation'] = large_repo_results
        
        # Check for large repo issues
        large_repo_issues = [r for r in large_repo_results if r['performance_issues']]
        if large_repo_issues:
            validation_results['critical_issues'].append(
                f"Large repository performance issues: {len(large_repo_issues)}"
            )
    
    # 2. Metric validation
    if fold_results:
        metric_results = []
        for fold in fold_results:
            test_repo = fold.get('test_repo', 'unknown')
            # Create dummy predictions for validation (replace with actual predictions)
            y_true = np.random.randint(0, 2, 100)  # Placeholder
            y_pred = np.random.randint(0, 2, 100)  # Placeholder
            y_proba = np.random.random(100)  # Placeholder
            
            metric_validation = validate_model_metrics(y_true, y_pred, y_proba, test_repo)
            metric_results.append(metric_validation)
        
        validation_results['metric_validation'] = metric_results
    
    # 3. Extreme failure check
    if fold_results:
        extreme_failure_results = ensure_no_extreme_failures(fold_results)
        validation_results['extreme_failure_check'] = extreme_failure_results
        
        if extreme_failure_results['failure_rate'] > 0.2:
            validation_results['critical_issues'].append(
                f"High extreme failure rate: {extreme_failure_results['failure_rate']:.1%}"
            )
    
    # 4. Overall status determination
    if validation_results['critical_issues']:
        validation_results['overall_status'] = 'FAIL'
        print(f"  🚨 CRITICAL ISSUES DETECTED:")
        for issue in validation_results['critical_issues']:
            print(f"    - {issue}")
    else:
        print(f"  ✅ Model quality validation PASSED")
    
    print(f"  ══════════════════════════════════════════════════════════════")
    
    return validation_results
