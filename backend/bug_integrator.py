"""
Bug Type Classification Integration

Integrates bug type classification with the main pipeline.
"""

import pandas as pd
from typing import List, Dict, Optional
from pydriller import Repository
from backend.szz import extract_bug_labels_with_confidence
from backend.bug_classifier import BugTypeClassifier, extract_bug_type_from_message
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
    from backend.szz import extract_file_bug_messages
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
    Classify bug types for files in the dataset using robust matching.
    """
    if not classifier.is_trained:
        print("  Warning: Bug type classifier not trained")
        df['bug_type'] = 'unknown'
        df['bug_type_confidence'] = 0.0
        return df
    
    # Only classify buggy files
    if df[df['buggy'] == 1].empty:
        df['bug_type'] = 'unknown'
        df['bug_type_confidence'] = 0.0
        return df
    
    file_bug_types = {}
    file_confidences = {}

    from backend.szz import extract_file_bug_messages
    from backend.config import DATASET_DIR

    # Group by repo
    for repo_name in df['repo'].unique():
        # RECONSTRUCT full repo path
        actual_repo_path = os.path.join(DATASET_DIR, repo_name)
        
        repo_df = df[(df['repo'] == repo_name) & (df['buggy'] == 1)]
        
        # dict of form {norm_path: [msg1, msg2]}
        buggy_messages_cache = extract_file_bug_messages(actual_repo_path, cache_dir)
        if not buggy_messages_cache:
            continue

        # Prepare for robust matching
        def _clean_p(p):
            p = p.replace("src/", "").replace("lib/", "")
            parts = p.split('/')
            return "/".join(parts[-2:]) if len(parts) >= 2 else p
            
        clean_cache = {_clean_p(k): msgs for k, msgs in buggy_messages_cache.items()}
        base_cache = {os.path.basename(k): msgs for k, msgs in buggy_messages_cache.items() if len(os.path.basename(k)) > 6}

        for _, row in repo_df.iterrows():
            f_path = row['file']
            try:
                f_rel = os.path.relpath(f_path, actual_repo_path)
                f_norm = f_rel.replace("\\", "/").lower().strip("/")
            except ValueError:
                f_norm = f_path.replace("\\", "/").lower().strip("/")
            
            # Multi-stage match for messages
            msgs = []
            # 1. Exact
            if f_norm in buggy_messages_cache:
                msgs = buggy_messages_cache[f_norm]
            # 2. Suffix
            elif _clean_p(f_norm) in clean_cache:
                msgs = clean_cache[_clean_p(f_norm)]
            # 3. Filename
            elif os.path.basename(f_norm) in base_cache:
                msgs = base_cache[os.path.basename(f_norm)]

            if msgs:
                predictions = classifier.predict(msgs)
                if len(predictions) > 0:
                    counts = pd.Series(predictions).value_counts()
                    file_bug_types[f_path] = counts.index[0]
                    file_confidences[f_path] = 0.8
                    continue
                    
            file_bug_types[f_path] = 'unknown'
            file_confidences[f_path] = 0.0

    # Map back
    df['bug_type'] = df['file'].map(lambda fp: file_bug_types.get(fp, 'unknown'))
    df['bug_type_confidence'] = df['file'].map(lambda fp: file_confidences.get(fp, 0.0))
    
    return df
