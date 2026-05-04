"""
Bug Type Classifier

Implements TF-IDF + Logistic Regression classification for bug types
based on commit message analysis.
"""

import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import pickle
import os
from typing import Dict, List, Tuple, Optional

# Bug type keyword mappings based on PRD specifications
# REFINED VERSION - Removed generic keywords that cause false positives
# Order matters - more specific keywords should come first
BUG_TYPE_KEYWORDS = {
    "logic": [
        "logic error", "incorrect logic", "wrong logic", "logic bug",
        "calculation error", "wrong calculation", "incorrect calculation",
        "algorithm bug", "wrong algorithm", "incorrect algorithm",
        "off by one", "boundary error", "edge case",
        "incorrect behavior", "wrong behavior", "unexpected behavior",
        "incorrect result", "wrong result", "wrong output",
        "wrong value", "incorrect value",
        "wrong condition", "inverted condition", "incorrect condition",
        "assertion failed", "assert fail"
    ],
    
    "memory_leak": [
        "memory leak", "leak memory", "leaking memory",
        "memory not freed", "memory not released",
        "memory allocation bug", "memory management bug",
        "heap leak", "memory corruption"
    ],
    
    "resource": [
        # REMOVED generic terms: "resource", "resources", "free resources", etc.
        # KEEP ONLY specific leak patterns:
        "resource leak", "fd leak", "file descriptor leak",
        "handle leak", "socket leak", "connection leak",
        "unclosed resource", "stream not closed", "file not closed",
        "connection not closed", "socket not closed",
        "resource exhaustion", "resource starvation"
    ],
    
    "race_condition": [
        # REMOVED generic async terms: "async", "lock", "thread", "concurrent", "await"
        # KEEP ONLY actual race condition bugs:
        "race condition", "data race", "race bug",
        "deadlock", "livelock",
        "thread safety violation", "thread safety bug",
        "concurrent modification", "concurrent access bug",
        "locking bug", "mutex issue", "mutex bug",
        "synchronization bug", "synchronization issue"
    ],
    
    "null_pointer": [
        "null pointer", "nullptr", "null reference",
        "nullpointerexception", "npe", "null dereference",
        "null check", "null value", "none type error",
        "attributeerror: 'nonetype'", "cannot read property of null",
        "cannot read property of undefined"
    ],
    
    "security": [
        "security", "vulnerability", "exploit", "injection",
        "xss", "csrf", "sql injection", "code injection",
        "privilege escalation", "buffer overflow"
    ],
    
    "performance": [
        "performance", "slow", "timeout", "hang",
        "optimization", "optimize", "inefficient",
        "bottleneck", "latency", "throughput"
    ],
    
    "crash": [
        "application crash", "process crash", "segfault", "segmentation fault",
        "crash on startup", "crash when", "crash if", "fatal error",
        "fatal crash", "hard crash", "abort", "panic"
    ],
    
    "exception": [
        "unhandled exception", "exception thrown", "raises exception",
        "keyerror", "valueerror", "typeerror", "indexerror",
        "runtimeerror", "attributeerror", "importerror",
        "zerodivisionerror"
    ],
    
    "api": [
        "api bug", "api error", "api issue",
        "wrong api", "incorrect api", "api mismatch",
        "api compatibility", "api breaking change",
        "api regression"
    ]
}

def extract_bug_type_from_message(message: str) -> Optional[str]:
    """
    Extract bug type from commit message using keyword matching.
    Returns the best matching bug type or None if no match.
    """
    if not message:
        return None
    
    message_lower = message.lower()
    
    # Score each bug type based on keyword matches
    bug_type_scores = {}
    
    for bug_type, keywords in BUG_TYPE_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            # Use word boundary matching to avoid substring false positives
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, message_lower):
                # Longer keywords get higher scores (more specific)
                score += len(keyword)
        if score > 0:
            bug_type_scores[bug_type] = score
    
    if not bug_type_scores:
        return None
    
    # Return the bug type with the highest score
    return max(bug_type_scores.items(), key=lambda x: x[1])[0]

def create_training_data(buggy_commits: List[Dict]) -> Tuple[List[str], List[str]]:
    """
    Create training data from bug-fix commits.
    
    Args:
        buggy_commits: List of dicts with 'message' and 'file_path' keys
        
    Returns:
        Tuple of (messages, bug_types)
    """
    messages = []
    bug_types = []
    
    for commit in buggy_commits:
        message = commit.get('message', '')
        bug_type = extract_bug_type_from_message(message)
        
        if bug_type:  # Only include commits with identifiable bug types
            messages.append(message)
            bug_types.append(bug_type)
    
    return messages, bug_types

class BugTypeClassifier:
    """
    TF-IDF + Logistic Regression classifier for bug type prediction.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir
        self.model_path = os.path.join(cache_dir, "bug_type_classifier.pkl") if cache_dir else None
        self.pipeline = None
        self.is_trained = False
        
    def train(self, messages: List[str], bug_types: List[str]) -> Dict:
        """
        Train the bug type classifier.
        
        Args:
            messages: List of commit messages
            bug_types: List of corresponding bug types
            
        Returns:
            Training statistics dictionary
        """
        if len(messages) < 10:
            raise ValueError("Need at least 10 training examples")
            
        # CRITICAL FIX: Check for class dominance before training
        from collections import Counter
        counts = Counter(bug_types)
        print(f"  Bug type counts before merge: {dict(counts)}")
        
        # Check for single class dominance (>90%)
        total_count = len(bug_types)
        dominant_class = max(counts.items(), key=lambda x: x[1])
        dominant_percentage = dominant_class[1] / total_count
        
        if dominant_percentage > 0.9:
            print(f"  🚨 CRITICAL: Single class dominance detected!")
            print(f"     Class '{dominant_class[0]}' is {dominant_percentage:.1%} of all samples")
            print(f"     This destroys interpretability and signal quality")
            print(f"     DISCARDING bug type feature entirely")
            
            # Return failure status to disable bug type features
            return {
                'training_samples': len(messages),
                'test_samples': 0,
                'accuracy': 0.0,
                'class_distribution': dict(counts),
                'unique_bug_types': len(set(bug_types)),
                'status': 'FAILED',
                'reason': 'Single class dominance >90%',
                'dominant_class': dominant_class[0],
                'dominant_percentage': dominant_percentage
            }
        
        # Merge rare classes (< 5 samples) into 'other'
        bug_types = [bt if counts[bt] >= 5 else 'other' for bt in bug_types]
        
        # Verify the merge
        new_counts = Counter(bug_types)
        print(f"  Bug type counts after merge: {dict(new_counts)}")
        
        # Check for dominance after merge
        total_after = len(bug_types)
        dominant_after = max(new_counts.items(), key=lambda x: x[1])
        dominant_after_percentage = dominant_after[1] / total_after
        
        if dominant_after_percentage > 0.9:
            print(f"  🚨 CRITICAL: Still dominant after merge!")
            print(f"     Class '{dominant_after[0]}' is {dominant_after_percentage:.1%} after merge")
            print(f"     DISCARDING bug type feature entirely")
            
            return {
                'training_samples': len(messages),
                'test_samples': 0,
                'accuracy': 0.0,
                'class_distribution': dict(new_counts),
                'unique_bug_types': len(set(bug_types)),
                'status': 'FAILED',
                'reason': 'Single class dominance >90% after merge',
                'dominant_class': dominant_after[0],
                'dominant_percentage': dominant_after_percentage
            }
        
        # Split data for evaluation
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                messages, bug_types, test_size=0.2, random_state=42, stratify=bug_types
            )
        except ValueError as e:
            print(f"  Warning: Stratified split failed: {e}")
            print("  Falling back to non-stratified split.")
            X_train, X_test, y_train, y_test = train_test_split(
                messages, bug_types, test_size=0.2, random_state=42
            )
        
        # Create pipeline
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2),
                lowercase=True
            )),
            ('classifier', LogisticRegression(
                random_state=42,
                max_iter=1000
            ))
        ])
        
        # Train model
        self.pipeline.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.pipeline.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        # Get class distribution
        class_counts = pd.Series(bug_types).value_counts().to_dict()
        
        stats = {
            'training_samples': len(messages),
            'test_samples': len(X_test),
            'accuracy': accuracy,
            'class_distribution': class_counts,
            'unique_bug_types': len(set(bug_types))
        }
        
        self.is_trained = True
        
        # Save model
        if self.model_path:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.pipeline, f)
        
        return stats
    
    def load(self) -> bool:
        """Load trained model from cache."""
        if self.model_path and os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    self.pipeline = pickle.load(f)
                self.is_trained = True
                return True
            except Exception:
                return False
        return False
    
    def predict(self, messages: List[str]) -> List[str]:
        """
        Predict bug types for commit messages.
        
        Args:
            messages: List of commit messages
            
        Returns:
            List of predicted bug types
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() or load() first.")
        
        return self.pipeline.predict(messages)
    
    def predict_proba(self, messages: List[str]) -> List[Dict]:
        """
        Predict bug type probabilities for commit messages.
        
        Args:
            messages: List of commit messages
            
        Returns:
            List of dictionaries with bug type probabilities
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() or load() first.")
        
        probas = self.pipeline.predict_proba(messages)
        classes = self.pipeline.classes_
        
        results = []
        for i, prob in enumerate(probas):
            prob_dict = {classes[j]: float(prob[j]) for j in range(len(classes))}
            results.append(prob_dict)
        
        return results
