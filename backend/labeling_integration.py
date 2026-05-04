#!/usr/bin/env python3
"""
Integration module for hybrid labeling system with existing pipeline.
Provides drop-in replacement for current labeling functionality.
"""

import os
import pandas as pd
from typing import Dict, List, Optional
from pathlib import Path

from backend.hybrid_labeling import create_hybrid_labels
from backend.label_validation import validate_labeling_pipeline

def create_labels(df, repo_path, cache_dir=None, github_token=None, use_validation=True):
    """
    Enhanced version of create_labels function using hybrid labeling system.
    
    Args:
        df: Analyzer DataFrame with file information
        repo_path: Repository path
        cache_dir: Cache directory for SZZ and issue data
        github_token: GitHub API token for issue labeling
        use_validation: Whether to run validation checks
        
    Returns:
        DataFrame with hybrid labels applied
    """
    print(f"🏷️  Creating hybrid labels for {repo_path}")
    
    # Apply hybrid labels
    labeled_df = create_hybrid_labels(df, repo_path, cache_dir=cache_dir, github_token=github_token)
    
    # Optional validation
    if use_validation:
        print(f"\n🔍 Running label validation...")
        validation_results = validate_labeling_pipeline([repo_path], cache_dir=cache_dir, github_token=github_token)
        
        # Add validation metadata to DataFrame
        labeled_df.attrs['validation_results'] = validation_results
    
    return labeled_df

def audit_labels(buggy_count: int, total_files: int, szz_raw_count: int = 0, issue_raw_count: int = 0):
    """
    Enhanced audit function with hybrid labeling support.
    
    Args:
        buggy_count: Number of files labeled as buggy
        total_files: Total number of files
        szz_raw_count: Raw SZZ count (for backward compatibility)
        issue_raw_count: Raw issue count (new)
    """
    bug_rate = (buggy_count / total_files * 100) if total_files > 0 else 0
    
    print(f"  📊 Label Audit Results:")
    print(f"     Total files: {total_files}")
    print(f"     Buggy files: {buggy_count}")
    print(f"     Bug rate: {bug_rate:.1f}%")
    
    if szz_raw_count > 0:
        szz_match_rate = (buggy_count / szz_raw_count * 100) if szz_raw_count > 0 else 0
        print(f"     SZZ raw count: {szz_raw_count}")
        print(f"     SZZ match rate: {szz_match_rate:.1f}%")
    
    if issue_raw_count > 0:
        issue_match_rate = (buggy_count / issue_raw_count * 100) if issue_raw_count > 0 else 0
        print(f"     Issue raw count: {issue_raw_count}")
        print(f"     Issue match rate: {issue_match_rate:.1f}%")
    
    # Validation warnings
    if buggy_count == 0:
        print("  🚨 CRITICAL: No buggy files found!")
    elif bug_rate > 50:
        print(f"  ⚠️  WARNING: Very high bug rate ({bug_rate:.1f}%)")
    elif bug_rate < 1:
        print(f"  ⚠️  WARNING: Very low bug rate ({bug_rate:.1f}%)")

def analyze_repository_with_labels(repo_path: str, cache_dir: str = None, github_token: str = None, 
                                 use_validation: bool = True, parallel: bool = False, verbose: bool = True):
    """
    Complete repository analysis with enhanced labeling.
    
    Args:
        repo_path: Path to repository
        cache_dir: Cache directory for labeling data
        github_token: GitHub API token for issue labeling
        use_validation: Whether to run validation checks
        parallel: Whether to use parallel processing
        verbose: Whether to print verbose output
        
    Returns:
        DataFrame with analysis results and hybrid labels
    """
    from backend.analysis import analyze_repository
    
    # Step 1: Analyze repository (file filtering and metrics)
    if verbose:
        print(f"🔍 Analyzing repository: {repo_path}")
    
    analysis_results = analyze_repository(repo_path, verbose=verbose, parallel=parallel)
    
    # Convert to DataFrame if needed
    if isinstance(analysis_results, list):
        import pandas as pd
        df = pd.DataFrame(analysis_results)
    else:
        df = analysis_results
    
    if df.empty:
        print(f"  ⚠️  No files found after filtering for {repo_path}")
        return df
    
    # Step 2: Apply hybrid labels
    labeled_df = create_labels(df, repo_path, cache_dir=cache_dir, github_token=github_token, use_validation=use_validation)
    
    # Step 3: Print final summary
    if verbose:
        buggy_count = labeled_df['is_buggy'].sum()
        total_count = len(labeled_df)
        
        print(f"\n📊 Final Results for {os.path.basename(repo_path)}:")
        print(f"   Files analyzed: {total_count}")
        print(f"   Files labeled buggy: {buggy_count}")
        print(f"   Bug rate: {(buggy_count/total_count*100):.1f}%")
        
        # Source breakdown
        if 'source' in labeled_df.columns:
            source_counts = labeled_df[labeled_df['is_buggy']]['source'].value_counts()
            if not source_counts.empty:
                print(f"   Label sources: {dict(source_counts)}")
    
    return labeled_df

def batch_analyze_repositories(repo_paths: List[str], cache_dir: str = None, github_token: str = None,
                              use_validation: bool = True, parallel: bool = False, verbose: bool = True) -> Dict[str, pd.DataFrame]:
    """
    Analyze multiple repositories with hybrid labeling.
    
    Args:
        repo_paths: List of repository paths
        cache_dir: Cache directory for labeling data
        github_token: GitHub API token for issue labeling
        use_validation: Whether to run validation checks
        parallel: Whether to use parallel processing
        verbose: Whether to print verbose output
        
    Returns:
        Dictionary of repo_name -> DataFrame with labels
    """
    results = {}
    
    if verbose:
        print(f"🔍 Batch analyzing {len(repo_paths)} repositories")
        print("=" * 80)
    
    for repo_path in repo_paths:
        try:
            repo_name = os.path.basename(repo_path.rstrip('/'))
            
            if verbose:
                print(f"\n📁 Processing: {repo_name}")
                print("-" * 40)
            
            # Analyze repository with labels
            labeled_df = analyze_repository_with_labels(
                repo_path=repo_path,
                cache_dir=cache_dir,
                github_token=github_token,
                use_validation=use_validation,
                parallel=parallel,
                verbose=verbose
            )
            
            results[repo_name] = labeled_df
            
        except Exception as e:
            repo_name = os.path.basename(repo_path.rstrip('/'))
            print(f"  ❌ Failed to analyze {repo_name}: {e}")
            results[repo_name] = pd.DataFrame()  # Empty DataFrame for failed repos
    
    # Print batch summary
    if verbose:
        successful_repos = sum(1 for df in results.values() if not df.empty)
        total_repos = len(repo_paths)
        
        print(f"\n📊 Batch Analysis Summary:")
        print(f"   Total repositories: {total_repos}")
        print(f"   Successful: {successful_repos}")
        print(f"   Failed: {total_repos - successful_repos}")
        
        if successful_repos > 0:
            total_files = sum(len(df) for df in results.values() if not df.empty)
            total_buggy = sum(df['is_buggy'].sum() for df in results.values() if not df.empty)
            overall_bug_rate = (total_buggy / total_files * 100) if total_files > 0 else 0
            
            print(f"   Total files: {total_files}")
            print(f"   Total buggy files: {total_buggy}")
            print(f"   Overall bug rate: {overall_bug_rate:.1f}%")
    
    return results

def export_labeled_data(labeled_dfs: Dict[str, pd.DataFrame], output_dir: str = None, format: str = 'csv'):
    """
    Export labeled data to files.
    
    Args:
        labeled_dfs: Dictionary of repo_name -> labeled DataFrame
        output_dir: Output directory
        format: Export format ('csv', 'json', 'parquet')
    """
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    for repo_name, df in labeled_dfs.items():
        if df.empty:
            continue
        
        if output_dir:
            filename = f"{repo_name}_labeled.{format}"
            output_path = os.path.join(output_dir, filename)
        else:
            output_path = f"{repo_name}_labeled.{format}"
        
        try:
            if format == 'csv':
                df.to_csv(output_path, index=False)
            elif format == 'json':
                df.to_json(output_path, orient='records', indent=2)
            elif format == 'parquet':
                df.to_parquet(output_path, index=False)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            print(f"  💾 Exported {repo_name}: {len(df)} files to {output_path}")
            
        except Exception as e:
            print(f"  ❌ Failed to export {repo_name}: {e}")

# Backward compatibility aliases
def create_labels_enhanced(df, repo_path, cache_dir=None, github_token=None):
    """Enhanced version of create_labels with hybrid labeling."""
    return create_labels(df, repo_path, cache_dir=cache_dir, github_token=github_token, use_validation=True)

def analyze_repository_enhanced(repo_path, cache_dir=None, github_token=None, parallel=False, verbose=True):
    """Enhanced version of analyze_repository with hybrid labeling."""
    return analyze_repository_with_labels(repo_path, cache_dir=cache_dir, github_token=github_token, 
                                        use_validation=True, parallel=parallel, verbose=verbose)
