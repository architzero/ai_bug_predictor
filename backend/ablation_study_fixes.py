#!/usr/bin/env python3
"""
Ablation Study Fixes Implementation

Comprehensive fixes for Stage 7 to produce meaningful and research-valid insights.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import f1_score, average_precision_score
from imblearn.combine import SMOTETomek
import warnings

# Define clear feature groups
STATIC_FEATURES = [
    'loc', 'avg_complexity', 'max_complexity', 'functions', 'avg_params',
    'max_function_length', 'complexity_vs_baseline', 'complexity_density',
    'complexity_per_function', 'loc_per_function'
]

GIT_FEATURES = [
    'commits', 'lines_added', 'lines_deleted', 'max_added', 'churn_ratio',
    'recent_churn_ratio', 'recent_activity_score', 'instability_score',
    'avg_commit_size', 'max_commit_ratio'
]

DEVELOPER_FEATURES = [
    'author_count', 'ownership', 'low_history_flag', 'minor_contributor_ratio',
    'author_entropy', 'experience_score'
]

TEMPORAL_FEATURES = [
    'file_age_bucket', 'days_since_last_change', 'recency_ratio'
]

COUPLING_FEATURES = [
    'max_coupling_strength', 'coupled_file_count', 'coupled_recent_missing',
    'coupling_risk'
]

BURST_FEATURES = [
    'commit_burst_score', 'recent_commit_burst', 'burst_ratio', 'burst_risk'
]

# Core signals that must be preserved
CORE_SIGNALS = {
    'commits', 'churn_ratio', 'recent_churn_ratio', 'avg_complexity',
    'loc', 'author_count', 'ownership', 'days_since_last_change'
}

def construct_feature_sets(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Construct feature sets clearly and correctly, ensuring only numeric features.
    
    Args:
        df: Input DataFrame
        
    Returns:
        Dictionary of feature sets
    """
    print(f"🔍 CONSTRUCTING FEATURE SETS")
    
    # Get only numeric columns (exclude string/object columns)
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    available_features = set(numeric_columns)
    
    # Remove non-feature columns
    exclude_cols = {'buggy', 'repo', 'file', 'confidence'}
    available_features = available_features - exclude_cols
    
    print(f"  Available numeric features: {len(available_features)}")
    
    # Construct feature sets with validation
    feature_sets = {
        'Static-only': [f for f in STATIC_FEATURES if f in available_features],
        'Git-only': [f for f in GIT_FEATURES if f in available_features],
        'Developer-only': [f for f in DEVELOPER_FEATURES if f in available_features],
        'Temporal-only': [f for f in TEMPORAL_FEATURES if f in available_features],
        'Coupling-only': [f for f in COUPLING_FEATURES if f in available_features],
        'Burst-only': [f for f in BURST_FEATURES if f in available_features],
    }
    
    # Combined sets
    feature_sets['Static+Git'] = feature_sets['Static-only'] + feature_sets['Git-only']
    feature_sets['All-Combined'] = list(available_features)
    
    # Validate feature sets
    print(f"  Feature set construction:")
    for name, features in feature_sets.items():
        if features:
            print(f"    {name}: {len(features)} features")
        else:
            print(f"    {name}: No available features")
    
    return feature_sets

def fix_feature_selection_for_ablation(X_train, y_train, X_test, feature_set_name: str) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    """
    Fix feature selection (RFE) to preserve important signals and ensure numeric features only.
    
    Args:
        X_train: Training features
        y_train: Training labels
        X_test: Test features
        feature_set_name: Name of the feature set
        
    Returns:
        Tuple of (X_train_selected, X_test_selected, selected_features)
    """
    print(f"🔍 FIXING FEATURE SELECTION FOR {feature_set_name}")
    
    # CRITICAL FIX: Ensure only numeric features are used
    numeric_columns = X_train.select_dtypes(include=[np.number]).columns.tolist()
    X_train = X_train[numeric_columns]
    X_test = X_test[numeric_columns]
    
    print(f"  After numeric filtering: {len(X_train.columns)} features")
    
    # Always preserve core signals
    available_core = [f for f in CORE_SIGNALS if f in X_train.columns]
    
    # For small feature sets, don't apply RFE to avoid losing important signals
    if len(X_train.columns) <= 5:
        print(f"  Small feature set ({len(X_train.columns)}) - skipping RFE to preserve signals")
        return X_train, X_test, X_train.columns.tolist()
    
    # For specific feature sets, be more conservative
    conservative_sets = ['Static-only', 'Git-only', 'Developer-only']
    if feature_set_name in conservative_sets:
        print(f"  Conservative set ({feature_set_name}) - preserving all features")
        return X_train, X_test, X_train.columns.tolist()
    
    # Apply RFE but always preserve core signals
    from sklearn.feature_selection import SelectFromModel
    from sklearn.ensemble import RandomForestClassifier
    
    selector = SelectFromModel(
        RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            random_state=42,
            class_weight="balanced",
            n_jobs=-1,
        ),
        threshold='median',  # Conservative threshold
    )
    
    selector.fit(X_train, y_train)
    
    # Get selected features
    mask = selector.get_support()
    selected = X_train.columns[mask].tolist()
    
    # Always add back core signals if they were dropped
    final_selected = list(set(selected + available_core))
    
    print(f"  Original features: {len(X_train.columns)}")
    print(f"  RFE selected: {len(selected)}")
    print(f"  After preserving core signals: {len(final_selected)}")
    
    # Apply selection
    X_train_selected = X_train[final_selected]
    X_test_selected = X_test[final_selected]
    
    return X_train_selected, X_test_selected, final_selected

def adjust_training_distribution_realistic(X_train, y_train, target_buggy_rate: float = 0.20) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Adjust training distribution to realistic buggy rate (15-25%).
    
    Args:
        X_train: Training features
        y_train: Training labels
        target_buggy_rate: Target buggy rate (default 20%)
        
    Returns:
        Tuple of (balanced_X_train, balanced_y_train)
    """
    print(f"🔍 ADJUSTING TRAINING DISTRIBUTION TO REALISTIC BUGGY RATE")
    
    current_buggy_rate = y_train.mean()
    print(f"  Current buggy rate: {current_buggy_rate:.1%}")
    print(f"  Target buggy rate: {target_buggy_rate:.1%}")
    
    # If current rate is already realistic, don't over-balance
    if 0.15 <= current_buggy_rate <= 0.25:
        print(f"  ✅ Current rate is already realistic - no adjustment needed")
        return X_train, y_train
    
    # If current rate is too high, downsample majority class
    if current_buggy_rate > target_buggy_rate:
        print(f"  ⚠️  Current rate too high - downsampling majority class")
        
        # Calculate target majority class size
        current_buggy_count = int(y_train.sum())
        target_majority_count = int(current_buggy_count * (1 - target_buggy_rate) / target_buggy_rate)
        
        # Get indices for each class
        buggy_indices = np.where(y_train == 1)[0]
        clean_indices = np.where(y_train == 0)[0]
        
        # Downsample clean class — cap at available size to avoid ValueError
        np.random.seed(42)
        target_majority_count = min(target_majority_count, len(clean_indices))
        clean_downsampled = np.random.choice(clean_indices, target_majority_count, replace=False)
        
        # Combine indices
        balanced_indices = np.concatenate([buggy_indices, clean_downsampled])

        # Create balanced dataset
        X_balanced = X_train.iloc[balanced_indices]
        y_balanced = y_train.iloc[balanced_indices]
        
        new_buggy_rate = y_balanced.mean()
        print(f"  New buggy rate: {new_buggy_rate:.1%}")
        
        return X_balanced, y_balanced
    
    # If current rate is too low, use SMOTE but limit the target rate
    else:
        print(f"  ⚠️  Current rate too low - using limited SMOTE")
        
        # Calculate target minority class size
        current_clean_count = int((y_train == 0).sum())
        target_buggy_count = int(current_clean_count * target_buggy_rate / (1 - target_buggy_rate))
        
        # Use SMOTE but limit the number of synthetic samples
        current_buggy_count = int(y_train.sum())
        if target_buggy_count > current_buggy_count:
            synthetic_needed = target_buggy_count - current_buggy_count
            
            # Apply SMOTE with limited sampling
            smt = SMOTETomek(random_state=42, sampling_strategy={
                1: min(target_buggy_count, current_buggy_count * 3)  # Don't oversample too much
            })
            
            X_balanced, y_balanced = smt.fit_resample(X_train, y_train)
            
            new_buggy_rate = y_balanced.mean()
            print(f"  New buggy rate: {new_buggy_rate:.1%}")
            
            return X_balanced, y_balanced
        else:
            print(f"  ✅ No SMOTE needed - current rate acceptable")
            return X_train, y_train

def calculate_recall_at_20(y_true, y_proba) -> float:
    """
    Calculate Recall@20% for evaluation.
    
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

def evaluate_model_comprehensive(y_true, y_pred, y_proba, model_name: str, feature_set: str) -> Dict:
    """
    Evaluate model with focus on PR-AUC and Recall@20%.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        y_proba: Predicted probabilities
        model_name: Name of the model
        feature_set: Name of the feature set
        
    Returns:
        Comprehensive evaluation results
    """
    # Calculate metrics
    weighted_f1 = f1_score(y_true, y_pred, average='weighted')
    pr_auc = average_precision_score(y_true, y_proba)
    recall_20 = calculate_recall_at_20(y_true, y_proba)
    
    # Calculate additional metrics
    accuracy = np.mean(y_true == y_pred)
    
    results = {
        'model': model_name,
        'feature_set': feature_set,
        'weighted_f1': weighted_f1,
        'pr_auc': pr_auc,
        'recall_at_20': recall_20,
        'accuracy': accuracy
    }
    
    print(f"  {model_name} + {feature_set}:")
    print(f"    Weighted F1: {weighted_f1:.3f}")
    print(f"    PR-AUC: {pr_auc:.3f}")
    print(f"    Recall@20%: {recall_20:.3f}")
    print(f"    Accuracy: {accuracy:.3f}")
    
    return results

def run_improved_ablation_study(df: pd.DataFrame) -> Dict:
    """
    Run improved ablation study with meaningful and research-valid insights.
    
    Args:
        df: Input DataFrame
        
    Returns:
        Comprehensive ablation study results
    """
    print(f"🚀 IMPROVED ABLATION STUDY")
    print(f"  ══════════════════════════════════════════════════════════════")
    
    projects = df['repo'].unique() if 'repo' in df.columns else ['default']
    
    if len(projects) < 2:
        print(f"  ⚠️  Need ≥ 2 projects for cross-project validation")
        return {'status': 'INSUFFICIENT_PROJECTS'}
    
    # Construct feature sets
    feature_sets = construct_feature_sets(df)
    
    # Define models
    models = {
        'LR': LogisticRegression(max_iter=1000, random_state=42, class_weight='balanced'),
        'RF': RandomForestClassifier(n_estimators=200, random_state=42, class_weight='balanced', n_jobs=-1)
    }
    
    # Results storage
    all_results = []
    
    # Cross-project evaluation
    for test_repo in projects:
        print(f"\n{'='*60}")
        print(f"TEST PROJECT: {test_repo}")
        print(f"{'='*60}")
        
        # Split data
        train_df = df[df['repo'] != test_repo] if 'repo' in df.columns else df
        test_df = df[df['repo'] == test_repo] if 'repo' in df.columns else df
        
        if len(train_df) < 10 or len(test_df) < 5:
            continue
        
        # Get features and labels - ensure only numeric features
        all_columns = train_df.columns.tolist()
        exclude_cols = ['buggy', 'repo', 'file', 'confidence']
        
        # CRITICAL FIX: Only include numeric columns
        numeric_train_cols = train_df.select_dtypes(include=[np.number]).columns.tolist()
        numeric_test_cols = test_df.select_dtypes(include=[np.number]).columns.tolist()
        
        train_features = [col for col in numeric_train_cols if col not in exclude_cols]
        test_features = [col for col in numeric_test_cols if col not in exclude_cols]
        
        # Ensure train and test have the same features
        shared_features = list(set(train_features) & set(test_features))
        
        X_train_raw = train_df[shared_features]
        y_train_raw = train_df['buggy']
        X_test_raw = test_df[shared_features]
        y_test = test_df['buggy']
        
        # Evaluate each feature set
        for feature_set_name, feature_list in feature_sets.items():
            if not feature_list:
                continue
            
            # Get shared features
            shared_features = [f for f in feature_list if f in X_train_raw.columns and f in X_test_raw.columns]
            
            if len(shared_features) < 3:
                continue
            
            print(f"\n  Feature Set: {feature_set_name} ({len(shared_features)} features)")
            
            # Prepare data
            X_train = X_train_raw[shared_features]
            X_test = X_test_raw[shared_features]
            
            # Apply feature selection
            X_train_sel, X_test_sel, selected_features = fix_feature_selection_for_ablation(
                X_train, y_train_raw, X_test, feature_set_name
            )
            
            # Adjust training distribution
            X_train_bal, y_train_bal = adjust_training_distribution_realistic(X_train_sel, y_train_raw)
            
            # Train models
            for model_name, model in models.items():
                print(f"    Training {model_name}...")
                
                # Create pipeline
                pipeline = Pipeline([
                    ('scaler', StandardScaler()),
                    ('classifier', model)
                ])
                
                # Train model
                pipeline.fit(X_train_bal, y_train_bal)
                
                # Make predictions
                y_pred = pipeline.predict(X_test_sel)
                y_proba = pipeline.predict_proba(X_test_sel)[:, 1]
                
                # Evaluate
                results = evaluate_model_comprehensive(
                    y_test, y_pred, y_proba, model_name, feature_set_name
                )
                results['test_repo'] = test_repo
                results['selected_features'] = selected_features
                all_results.append(results)
    
    # Aggregate results
    if not all_results:
        return {'status': 'NO_VALID_RESULTS'}
    
    # Convert to DataFrame for analysis
    results_df = pd.DataFrame(all_results)
    
    # Calculate average metrics per model and feature set
    summary = results_df.groupby(['model', 'feature_set']).agg({
        'weighted_f1': 'mean',
        'pr_auc': 'mean',
        'recall_at_20': 'mean',
        'accuracy': 'mean'
    }).reset_index()
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"ABLATION STUDY SUMMARY")
    print(f"{'='*60}")
    
    print(f"{'Model':<6} {'Feature Set':<20} {'F1':<8} {'PR-AUC':<8} {'Recall@20%':<12}")
    print(f"{'-'*60}")
    
    for _, row in summary.iterrows():
        print(f"{row['model']:<6} {row['feature_set']:<20} {row['weighted_f1']:.3f}   {row['pr_auc']:.3f}   {row['recall_at_20']:.3f}")
    
    # Validate combined performance
    validation_results = validate_combined_performance(summary)
    
    print(f"\n📊 VALIDATION RESULTS:")
    print(f"  Combined outperforms individual: {validation_results['combined_outperforms']}")
    print(f"  PR-AUC target achieved: {validation_results['pr_auc_target_achieved']}")
    print(f"  Meaningful differences: {validation_results['meaningful_differences']}")
    
    return {
        'status': 'SUCCESS',
        'detailed_results': all_results,
        'summary': summary.to_dict('records'),
        'validation': validation_results
    }

def validate_combined_performance(summary_df: pd.DataFrame) -> Dict:
    """
    Validate that combined features outperform individual groups.
    
    Args:
        summary_df: Summary results DataFrame
        
    Returns:
        Validation results
    """
    print(f"🔍 VALIDATING COMBINED PERFORMANCE")
    
    validation_results = {
        'combined_outperforms': False,
        'pr_auc_target_achieved': False,
        'meaningful_differences': False,
        'best_individual': None,
        'best_combined': None,
        'issues': []
    }
    
    # Find best individual feature sets
    individual_sets = ['Static-only', 'Git-only', 'Developer-only']
    individual_results = summary_df[summary_df['feature_set'].isin(individual_sets)]
    
    if individual_results.empty:
        validation_results['issues'].append("No individual feature set results")
        return validation_results
    
    # Find best individual performance
    best_individual_idx = individual_results['pr_auc'].idxmax()
    best_individual = individual_results.loc[best_individual_idx]
    validation_results['best_individual'] = best_individual.to_dict()
    
    # Find best combined performance
    combined_sets = ['Static+Git', 'All-Combined']
    combined_results = summary_df[summary_df['feature_set'].isin(combined_sets)]
    
    if combined_results.empty:
        validation_results['issues'].append("No combined feature set results")
        return validation_results
    
    best_combined_idx = combined_results['pr_auc'].idxmax()
    best_combined = combined_results.loc[best_combined_idx]
    validation_results['best_combined'] = best_combined.to_dict()
    
    # Check if combined outperforms individual
    if best_combined['pr_auc'] > best_individual['pr_auc']:
        validation_results['combined_outperforms'] = True
        print(f"  ✅ Combined ({best_combined['pr_auc']:.3f}) outperforms individual ({best_individual['pr_auc']:.3f})")
    else:
        validation_results['issues'].append("Combined does not outperform individual")
        print(f"  ⚠️  Combined ({best_combined['pr_auc']:.3f}) does not outperform individual ({best_individual['pr_auc']:.3f})")
    
    # Check PR-AUC target
    if best_combined['pr_auc'] > 0.5:
        validation_results['pr_auc_target_achieved'] = True
        print(f"  ✅ PR-AUC target achieved (>0.5): {best_combined['pr_auc']:.3f}")
    else:
        validation_results['issues'].append(f"PR-AUC target not achieved: {best_combined['pr_auc']:.3f}")
    
    # Check for meaningful differences
    pr_auc_range = summary_df['pr_auc'].max() - summary_df['pr_auc'].min()
    if pr_auc_range > 0.1:
        validation_results['meaningful_differences'] = True
        print(f"  ✅ Meaningful differences in PR-AUC: {pr_auc_range:.3f}")
    else:
        validation_results['issues'].append(f"Small differences in PR-AUC: {pr_auc_range:.3f}")
    
    return validation_results
