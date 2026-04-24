"""
Bug Type Classification Integration

Integrates bug type classification with the main pipeline.
"""

import pandas as pd
from typing import List, Dict, Optional
from pydriller import Repository
from git_mining.szz_labeler import extract_bug_labels_with_confidence
from bug_type_classification.classifier import BugTypeClassifier, extract_bug_type_from_message
import os

def train_bug_type_classifier(repos: List[str], cache_dir: Optional[str] = None) -> BugTypeClassifier:
    """
    Train bug type classifier on multiple repositories.
    
    Args:
        repos: List of repository paths
        cache_dir: Cache directory
        
    Returns:
        Trained BugTypeClassifier
    """
    from git_mining.szz_labeler import extract_file_bug_messages
    classifier = BugTypeClassifier(cache_dir)
    
    # Try to load existing model
    if classifier.load():
        print("  Bug type classifier: loaded from cache")
        return classifier
    
    print("  Bug type classifier: training new model...")
    
    # Collect training data from all repos
    all_messages = []
    all_bug_types = []
    
    for repo_path in repos:
        print(f"    Processing {os.path.basename(repo_path)}...")
        try:
            # Re-use SZZ O(1) cache
            buggy_messages_cache = extract_file_bug_messages(repo_path, cache_dir)
            
            for msgs in buggy_messages_cache.values():
                for msg in msgs:
                    bug_type = extract_bug_type_from_message(msg)
                    if bug_type:
                        all_messages.append(msg)
                        all_bug_types.append(bug_type)
        except Exception as e:
            print(f"    Warning: Failed to process {repo_path}: {e}")
            continue
    
    if len(all_messages) < 10:
        print("  Warning: Insufficient training data for bug type classifier")
        return classifier
    
    # Train classifier
    stats = classifier.train(all_messages, all_bug_types)
    
    print(f"  Bug type classifier trained:")
    print(f"    Training samples: {stats['training_samples']}")
    print(f"    Test accuracy: {stats['accuracy']:.3f}")
    print(f"    Bug types: {stats['unique_bug_types']}")
    print(f"    Class distribution: {stats['class_distribution']}")
    
    return classifier

def classify_file_bugs(df: pd.DataFrame, classifier: BugTypeClassifier, cache_dir: Optional[str] = None) -> pd.DataFrame:
    """
    Classify bug types for files in the dataset.
    
    Args:
        df: DataFrame with file information
        classifier: Trained BugTypeClassifier
        
    Returns:
        DataFrame with bug type predictions
    """
    if not classifier.is_trained:
        print("  Warning: Bug type classifier not trained")
        df['bug_type'] = 'unknown'
        df['bug_type_confidence'] = 0.0
        return df
    
    # Only classify buggy files
    buggy_files = df[df['buggy'] == 1].copy()
    
    if buggy_files.empty:
        df['bug_type'] = 'unknown'
        df['bug_type_confidence'] = 0.0
        return df
    
    file_bug_types = {}
    file_confidences = {}

    from git_mining.szz_labeler import extract_file_bug_messages

    # Group by repo so we only process each repo's cached messages ONE time
    for repo_path in df['repo'].unique():
        repo_files = df[(df['repo'] == repo_path) & (df['buggy'] == 1)]['file'].tolist()
        
        # O(1) access to pre-computed file messages from SZZ caching
        # dict of form {norm_path: [msg1, msg2]}
        buggy_messages_cache = extract_file_bug_messages(repo_path, cache_dir)
        
        # 1. Map messages to df files using full path matching
        for f_path in repo_files:
            try:
                # Convert absolute DataFrame path to repo-relative path to match SZZ cache
                f_rel = os.path.relpath(f_path, repo_path)
                f_norm = f_rel.replace("\\", "/").lower()
            except ValueError:
                # Fallback if path is somehow not relative to repo (e.g. cross-drive)
                f_norm = f_path.replace("\\", "/").lower()
            
            # Find matching paths in the cache using full path comparison
            messages = []
            for b_path, msgs in buggy_messages_cache.items():
                b_norm = b_path.replace("\\", "/").lower()
                # Match full paths or suffixes (avoid basename-only matching)
                if f_norm == b_norm or f_norm.endswith("/" + b_norm) or b_norm.endswith("/" + f_norm):
                    messages.extend(msgs)
                    
            # 2. Classify messages for each file mapped
            if messages:
                predictions = classifier.predict(messages)
                if len(predictions) > 0:
                    bug_type_counts = pd.Series(predictions).value_counts()
                    file_bug_types[f_path] = bug_type_counts.index[0]
                    file_confidences[f_path] = 0.8
                    continue
                    
            file_bug_types[f_path] = 'unknown'
            file_confidences[f_path] = 0.0

    # 3. Map back to DataFrame safely
    df['bug_type'] = df['file'].map(lambda fp: file_bug_types.get(fp, 'unknown'))
    df['bug_type_confidence'] = df['file'].map(lambda fp: file_confidences.get(fp, 0.0))
    
    return df
