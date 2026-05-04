#!/usr/bin/env python3
"""
Hybrid labeling system combining SZZ and GitHub issue-based labeling.
Provides confidence-weighted labels with source attribution.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime

from backend.szz_labeling import extract_enhanced_szz_labels_with_cache
from backend.issue_labeling import extract_issue_labels

class HybridLabeler:
    """Hybrid labeling system combining SZZ and issue-based approaches."""
    
    def __init__(self, cache_dir: str = None, github_token: str = None):
        """
        Initialize hybrid labeler.
        
        Args:
            cache_dir: Cache directory for both SZZ and issue data
            github_token: GitHub API token for issue labeling
        """
        self.cache_dir = cache_dir
        self.github_token = github_token
    
    def _combine_labels(self, szz_labels: Dict[str, float], issue_labels: Dict[str, float]) -> Dict[str, Dict]:
        """
        Combine SZZ and issue labels with confidence weighting.
        
        Args:
            szz_labels: Dictionary of file_path -> confidence (SZZ)
            issue_labels: Dictionary of file_path -> confidence (issue)
            
        Returns:
            Dictionary of file_path -> {'is_buggy': bool, 'confidence': float, 'source': str}
        """
        combined_labels = {}
        all_files = set(szz_labels.keys()) | set(issue_labels.keys())
        
        for file_path in all_files:
            szz_confidence = szz_labels.get(file_path, 0.0)
            issue_confidence = issue_labels.get(file_path, 0.0)
            
            # Determine final label and confidence
            if issue_confidence > 0:
                # Issue-linked fixes have highest confidence
                final_confidence = max(issue_confidence, szz_confidence)
                source = "issue"
                is_buggy = True
            elif szz_confidence > 0:
                # SZZ-only labels
                final_confidence = szz_confidence
                source = "szz"
                is_buggy = True
            else:
                # No bug indicators
                final_confidence = 0.0
                source = "none"
                is_buggy = False
            
            combined_labels[file_path] = {
                'is_buggy': is_buggy,
                'confidence': final_confidence,
                'source': source,
                'szz_confidence': szz_confidence,
                'issue_confidence': issue_confidence
            }
        
        return combined_labels
    
    def _calculate_source_breakdown(self, combined_labels: Dict[str, Dict]) -> Dict[str, int]:
        """Calculate breakdown of labels by source."""
        breakdown = {
            'issue_only': 0,
            'szz_only': 0,
            'both_sources': 0,
            'total_buggy': 0
        }
        
        for file_path, label_info in combined_labels.items():
            if not label_info['is_buggy']:
                continue
            
            szz_conf = label_info['szz_confidence'] > 0
            issue_conf = label_info['issue_confidence'] > 0
            
            if szz_conf and issue_conf:
                breakdown['both_sources'] += 1
            elif issue_conf:
                breakdown['issue_only'] += 1
            elif szz_conf:
                breakdown['szz_only'] += 1
            
            breakdown['total_buggy'] += 1
        
        return breakdown
    
    def _validate_hybrid_labels(self, combined_labels: Dict[str, Dict], total_files: int) -> None:
        """
        Validate hybrid labeling results and print warnings.
        
        Args:
            combined_labels: Combined labeling results
            total_files: Total number of files analyzed
        """
        buggy_count = sum(1 for label in combined_labels.values() if label['is_buggy'])
        bug_rate = (buggy_count / total_files * 100) if total_files > 0 else 0
        
        source_breakdown = self._calculate_source_breakdown(combined_labels)
        
        print(f"  🔍 Hybrid Label Validation:")
        print(f"     Total files: {total_files}")
        print(f"     Buggy files: {buggy_count}")
        print(f"     Bug rate: {bug_rate:.1f}%")
        print(f"     Source breakdown:")
        print(f"       Issue-linked: {source_breakdown['issue_only']}")
        print(f"       SZZ-only: {source_breakdown['szz_only']}")
        print(f"       Both sources: {source_breakdown['both_sources']}")
        
        # Validation warnings
        if buggy_count == 0:
            print("  🚨 CRITICAL: No buggy files found!")
            print("      This may indicate issues with both SZZ and issue detection.")
        elif bug_rate > 50:
            print(f"  ⚠️  WARNING: Very high bug rate ({bug_rate:.1f}%)")
            print("      This may indicate overly broad bug detection.")
        elif bug_rate < 1:
            print(f"  ⚠️  WARNING: Very low bug rate ({bug_rate:.1f}%)")
            print("      This may indicate missed bug fixes.")
        
        # Source validation
        if source_breakdown['total_buggy'] > 0:
            issue_ratio = (source_breakdown['issue_only'] + source_breakdown['both_sources']) / source_breakdown['total_buggy'] * 100
            print(f"     Issue-linked ratio: {issue_ratio:.1f}%")
            
            if issue_ratio < 10:
                print("  ⚠️  WARNING: Low issue-linked ratio")
                print("      Consider checking GitHub API access or issue references.")
    
    def extract_hybrid_labels(self, repo_path: str) -> Dict[str, Dict]:
        """
        Extract hybrid labels combining SZZ and issue-based approaches.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Dictionary of file_path -> {'is_buggy': bool, 'confidence': float, 'source': str}
        """
        print(f"🔍 Extracting hybrid labels from {repo_path}")
        
        # Extract SZZ labels
        print("  📊 Step 1: Extracting SZZ labels...")
        szz_labels = extract_enhanced_szz_labels_with_cache(repo_path, self.cache_dir)
        
        # Extract issue labels
        print("  📊 Step 2: Extracting issue labels...")
        issue_labels = extract_issue_labels(repo_path, self.cache_dir, self.github_token)
        
        # Combine labels
        print("  📊 Step 3: Combining labels...")
        combined_labels = self._combine_labels(szz_labels, issue_labels)
        
        # Validate results
        total_files = len(szz_labels.keys()) + len(issue_labels.keys())
        self._validate_hybrid_labels(combined_labels, total_files)
        
        return combined_labels
    
    def apply_labels_to_dataframe(self, df, repo_path: str):
        """
        Apply hybrid labels to analyzer DataFrame.
        
        Args:
            df: Analyzer DataFrame with file information
            repo_path: Repository path
            
        Returns:
            DataFrame with hybrid labels applied
        """
        # Extract hybrid labels
        hybrid_labels = self.extract_hybrid_labels(repo_path)
        
        # Create lookup for file matching
        from backend.szz_labeling import normalize_path
        normalized_labels = {}
        
        for file_path, label_info in hybrid_labels.items():
            norm_path = normalize_path(file_path, repo_path)
            normalized_labels[norm_path] = label_info
        
        # Apply labels to DataFrame
        df_copy = df.copy()
        
        # Initialize label columns
        df_copy['is_buggy'] = False
        df_copy['confidence'] = 0.0
        df_copy['source'] = 'none'
        
        # Apply labels with path normalization
        for idx, row in df_copy.iterrows():
            file_path = row['file']
            norm_path = normalize_path(file_path, repo_path)
            
            if norm_path in normalized_labels:
                label_info = normalized_labels[norm_path]
                df_copy.at[idx, 'is_buggy'] = label_info['is_buggy']
                df_copy.at[idx, 'confidence'] = label_info['confidence']
                df_copy.at[idx, 'source'] = label_info['source']
        
        # Print final statistics
        buggy_count = df_copy['is_buggy'].sum()
        total_count = len(df_copy)
        bug_rate = (buggy_count / total_count * 100) if total_count > 0 else 0
        
        print(f"  📊 Final labeling results:")
        print(f"     Files in dataset: {total_count}")
        print(f"     Buggy files: {buggy_count}")
        print(f"     Bug rate: {bug_rate:.1f}%")
        
        return df_copy
    
    def save_labels_to_file(self, labels: Dict[str, Dict], repo_path: str, output_file: str = None):
        """
        Save hybrid labels to JSON file.
        
        Args:
            labels: Hybrid labels dictionary
            repo_path: Repository path
            output_file: Output file path (optional)
        """
        if not output_file:
            repo_name = os.path.basename(repo_path.rstrip('/'))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"hybrid_labels_{repo_name}_{timestamp}.json"
        
        # Prepare output data
        output_data = {
            'repo_path': repo_path,
            'timestamp': datetime.now().isoformat(),
            'total_files': len(labels),
            'buggy_files': sum(1 for label in labels.values() if label['is_buggy']),
            'source_breakdown': self._calculate_source_breakdown(labels),
            'labels': labels
        }
        
        try:
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"  💾 Saved hybrid labels to {output_file}")
        except Exception as e:
            print(f"  ❌ Failed to save labels: {e}")

def create_hybrid_labels(df, repo_path: str, cache_dir: str = None, github_token: str = None):
    """
    Create hybrid labels for analyzer DataFrame.
    
    Args:
        df: Analyzer DataFrame
        repo_path: Repository path
        cache_dir: Cache directory
        github_token: GitHub API token
        
    Returns:
        DataFrame with hybrid labels applied
    """
    labeler = HybridLabeler(cache_dir=cache_dir, github_token=github_token)
    return labeler.apply_labels_to_dataframe(df, repo_path)

def extract_hybrid_labels_standalone(repo_path: str, cache_dir: str = None, github_token: str = None) -> Dict[str, Dict]:
    """
    Extract hybrid labels as standalone function.
    
    Args:
        repo_path: Repository path
        cache_dir: Cache directory
        github_token: GitHub API token
        
    Returns:
        Dictionary of file_path -> {'is_buggy': bool, 'confidence': float, 'source': str}
    """
    labeler = HybridLabeler(cache_dir=cache_dir, github_token=github_token)
    return labeler.extract_hybrid_labels(repo_path)
