#!/usr/bin/env python3
"""
Label validation and debugging system for hybrid labeling pipeline.
Provides comprehensive validation, debugging, and quality assessment.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
import pandas as pd

from backend.hybrid_labeling import HybridLabeler
from backend.szz_labeling import extract_enhanced_szz_labels_with_cache
from backend.issue_labeling import extract_issue_labels

class LabelValidator:
    """Comprehensive label validation and debugging system."""
    
    def __init__(self, cache_dir: str = None, github_token: str = None):
        """
        Initialize label validator.
        
        Args:
            cache_dir: Cache directory for labeling data
            github_token: GitHub API token for issue labeling
        """
        self.cache_dir = cache_dir
        self.github_token = github_token
        self.validation_results = {}
    
    def _calculate_szz_match_rate(self, repo_path: str) -> float:
        """Calculate SZZ match rate for repository."""
        try:
            from backend.analysis import analyze_repository
            analyzer_results = analyze_repository(repo_path, verbose=False, parallel=False)
            analyzer_files = [f['file'] for f in analyzer_results]
            
            szz_labels = extract_enhanced_szz_labels_with_cache(repo_path, self.cache_dir)
            
            if not szz_labels:
                return 0.0
            
            # Count matches
            from backend.szz_labeling import normalize_path
            analyzer_normalized = {normalize_path(f, repo_path) for f in analyzer_files}
            szz_normalized = {normalize_path(f, repo_path) for f in szz_labels.keys()}
            
            matches = len(analyzer_normalized & szz_normalized)
            match_rate = (matches / len(szz_normalized) * 100) if szz_normalized else 0.0
            
            return match_rate
        except Exception as e:
            print(f"  ❌ Error calculating SZZ match rate: {e}")
            return 0.0
    
    def _calculate_issue_match_rate(self, repo_path: str) -> float:
        """Calculate issue-based match rate for repository."""
        try:
            from backend.analysis import analyze_repository
            analyzer_results = analyze_repository(repo_path, verbose=False, parallel=False)
            analyzer_files = {f['file'] for f in analyzer_results}
            
            issue_labels = extract_issue_labels(repo_path, self.cache_dir, self.github_token)
            
            if not issue_labels:
                return 0.0
            
            matches = len(analyzer_files & set(issue_labels.keys()))
            match_rate = (matches / len(issue_labels) * 100) if issue_labels else 0.0
            
            return match_rate
        except Exception as e:
            print(f"  ❌ Error calculating issue match rate: {e}")
            return 0.0
    
    def _analyze_bug_prevalence(self, labels: Dict[str, Dict]) -> Dict:
        """Analyze bug prevalence statistics."""
        total_files = len(labels)
        buggy_files = sum(1 for label in labels.values() if label['is_buggy'])
        
        if total_files == 0:
            return {
                'total_files': 0,
                'buggy_files': 0,
                'bug_rate': 0.0,
                'status': 'no_files'
            }
        
        bug_rate = (buggy_files / total_files * 100)
        
        # Determine status
        if buggy_files == 0:
            status = 'critical'
        elif bug_rate > 50:
            status = 'high_bug_rate'
        elif bug_rate < 1:
            status = 'low_bug_rate'
        else:
            status = 'normal'
        
        return {
            'total_files': total_files,
            'buggy_files': buggy_files,
            'bug_rate': bug_rate,
            'status': status
        }
    
    def _analyze_confidence_distribution(self, labels: Dict[str, Dict]) -> Dict:
        """Analyze confidence distribution of bug labels."""
        buggy_labels = [label for label in labels.values() if label['is_buggy']]
        
        if not buggy_labels:
            return {
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0,
                'avg_confidence': 0.0
            }
        
        high_conf = sum(1 for label in buggy_labels if label['confidence'] >= 0.8)
        medium_conf = sum(1 for label in buggy_labels if 0.5 <= label['confidence'] < 0.8)
        low_conf = sum(1 for label in buggy_labels if label['confidence'] < 0.5)
        
        avg_confidence = sum(label['confidence'] for label in buggy_labels) / len(buggy_labels)
        
        return {
            'high_confidence': high_conf,
            'medium_confidence': medium_conf,
            'low_confidence': low_conf,
            'avg_confidence': avg_confidence
        }
    
    def _identify_lost_files(self, repo_path: str, szz_labels: Dict[str, float], issue_labels: Dict[str, float]) -> Dict:
        """Identify files lost due to filtering/mismatch."""
        try:
            from backend.analysis import analyze_repository
            analyzer_results = analyze_repository(repo_path, verbose=False, parallel=False)
            analyzer_files = {f['file'] for f in analyzer_results}
            
            lost_szz_files = set(szz_labels.keys()) - analyzer_files
            lost_issue_files = set(issue_labels.keys()) - analyzer_files
            
            return {
                'szz_lost_count': len(lost_szz_files),
                'issue_lost_count': len(lost_issue_files),
                'szz_lost_files': list(lost_szz_files)[:10],  # Show first 10
                'issue_lost_files': list(lost_issue_files)[:10]  # Show first 10
            }
        except Exception as e:
            print(f"  ❌ Error identifying lost files: {e}")
            return {
                'szz_lost_count': 0,
                'issue_lost_count': 0,
                'szz_lost_files': [],
                'issue_lost_files': []
            }
    
    def validate_repository(self, repo_path: str) -> Dict:
        """
        Perform comprehensive validation of labeling for a repository.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Dictionary with validation results
        """
        repo_name = os.path.basename(repo_path.rstrip('/'))
        print(f"🔍 Validating labels for {repo_name}")
        print("=" * 60)
        
        validation_result = {
            'repo_name': repo_name,
            'repo_path': repo_path,
            'timestamp': datetime.now().isoformat(),
            'warnings': [],
            'errors': []
        }
        
        try:
            # Step 1: Extract labels
            print("  📊 Step 1: Extracting hybrid labels...")
            labeler = HybridLabeler(cache_dir=self.cache_dir, github_token=self.github_token)
            hybrid_labels = labeler.extract_hybrid_labels(repo_path)
            
            validation_result['labels'] = hybrid_labels
            
            # Step 2: Bug prevalence analysis
            print("  📊 Step 2: Analyzing bug prevalence...")
            bug_analysis = self._analyze_bug_prevalence(hybrid_labels)
            validation_result['bug_analysis'] = bug_analysis
            
            # Add warnings based on bug analysis
            if bug_analysis['status'] == 'critical':
                validation_result['warnings'].append("No buggy files found - possible detection failure")
            elif bug_analysis['status'] == 'high_bug_rate':
                validation_result['warnings'].append(f"Very high bug rate ({bug_analysis['bug_rate']:.1f}%)")
            elif bug_analysis['status'] == 'low_bug_rate':
                validation_result['warnings'].append(f"Very low bug rate ({bug_analysis['bug_rate']:.1f}%)")
            
            # Step 3: Confidence analysis
            print("  📊 Step 3: Analyzing confidence distribution...")
            confidence_analysis = self._analyze_confidence_distribution(hybrid_labels)
            validation_result['confidence_analysis'] = confidence_analysis
            
            # Step 4: SZZ match rate
            print("  📊 Step 4: Calculating SZZ match rate...")
            szz_match_rate = self._calculate_szz_match_rate(repo_path)
            validation_result['szz_match_rate'] = szz_match_rate
            
            if szz_match_rate < 30:
                validation_result['warnings'].append(f"Low SZZ match rate ({szz_match_rate:.1f}%)")
            
            # Step 5: Issue match rate
            print("  📊 Step 5: Calculating issue match rate...")
            issue_match_rate = self._calculate_issue_match_rate(repo_path)
            validation_result['issue_match_rate'] = issue_match_rate
            
            # Step 6: Lost files analysis
            print("  📊 Step 6: Identifying lost files...")
            szz_labels = extract_enhanced_szz_labels_with_cache(repo_path, self.cache_dir)
            issue_labels = extract_issue_labels(repo_path, self.cache_dir, self.github_token)
            lost_files = self._identify_lost_files(repo_path, szz_labels, issue_labels)
            validation_result['lost_files'] = lost_files
            
            if lost_files['szz_lost_count'] > 0:
                validation_result['warnings'].append(f"Lost {lost_files['szz_lost_count']} SZZ-labeled files")
            
            if lost_files['issue_lost_count'] > 0:
                validation_result['warnings'].append(f"Lost {lost_files['issue_lost_count']} issue-labeled files")
            
            # Step 7: Summary
            self._print_validation_summary(validation_result)
            
        except Exception as e:
            validation_result['errors'].append(f"Validation failed: {e}")
            print(f"  ❌ Validation failed: {e}")
        
        return validation_result
    
    def _print_validation_summary(self, validation_result: Dict):
        """Print validation summary."""
        print(f"\n📋 VALIDATION SUMMARY for {validation_result['repo_name']}")
        print("-" * 50)
        
        # Bug prevalence
        bug_analysis = validation_result['bug_analysis']
        print(f"📊 Bug Prevalence:")
        print(f"   Total files: {bug_analysis['total_files']}")
        print(f"   Buggy files: {bug_analysis['buggy_files']}")
        print(f"   Bug rate: {bug_analysis['bug_rate']:.1f}%")
        print(f"   Status: {bug_analysis['status']}")
        
        # Confidence analysis
        confidence = validation_result['confidence_analysis']
        if confidence['avg_confidence'] > 0:
            print(f"\n🎯 Confidence Distribution:")
            print(f"   High (≥0.8): {confidence['high_confidence']}")
            print(f"   Medium (0.5-0.8): {confidence['medium_confidence']}")
            print(f"   Low (<0.5): {confidence['low_confidence']}")
            print(f"   Average: {confidence['avg_confidence']:.3f}")
        
        # Match rates
        print(f"\n🔗 Match Rates:")
        print(f"   SZZ: {validation_result['szz_match_rate']:.1f}%")
        print(f"   Issue: {validation_result['issue_match_rate']:.1f}%")
        
        # Lost files
        lost_files = validation_result['lost_files']
        if lost_files['szz_lost_count'] > 0 or lost_files['issue_lost_count'] > 0:
            print(f"\n⚠️  Lost Files:")
            print(f"   SZZ: {lost_files['szz_lost_count']} files")
            print(f"   Issue: {lost_files['issue_lost_count']} files")
        
        # Warnings
        if validation_result['warnings']:
            print(f"\n⚠️  WARNINGS:")
            for warning in validation_result['warnings']:
                print(f"   • {warning}")
        
        # Errors
        if validation_result['errors']:
            print(f"\n❌ ERRORS:")
            for error in validation_result['errors']:
                print(f"   • {error}")
    
    def validate_multiple_repositories(self, repo_paths: List[str]) -> Dict:
        """
        Validate multiple repositories and generate comprehensive report.
        
        Args:
            repo_paths: List of repository paths
            
        Returns:
            Dictionary with multi-repo validation results
        """
        print("🔍 MULTI-REPOSITORY VALIDATION")
        print("=" * 80)
        
        multi_validation = {
            'timestamp': datetime.now().isoformat(),
            'repositories': {},
            'summary': {
                'total_repos': len(repo_paths),
                'successful_validations': 0,
                'failed_validations': 0,
                'total_files': 0,
                'total_buggy_files': 0,
                'average_bug_rate': 0.0,
                'average_szz_match_rate': 0.0,
                'average_issue_match_rate': 0.0
            }
        }
        
        bug_rates = []
        szz_match_rates = []
        issue_match_rates = []
        
        for repo_path in repo_paths:
            try:
                result = self.validate_repository(repo_path)
                repo_name = result['repo_name']
                multi_validation['repositories'][repo_name] = result
                
                if not result.get('errors'):
                    multi_validation['summary']['successful_validations'] += 1
                    
                    # Aggregate statistics
                    bug_analysis = result['bug_analysis']
                    multi_validation['summary']['total_files'] += bug_analysis['total_files']
                    multi_validation['summary']['total_buggy_files'] += bug_analysis['buggy_files']
                    
                    if bug_analysis['bug_rate'] > 0:
                        bug_rates.append(bug_analysis['bug_rate'])
                    
                    szz_match_rates.append(result['szz_match_rate'])
                    issue_match_rates.append(result['issue_match_rate'])
                else:
                    multi_validation['summary']['failed_validations'] += 1
                
            except Exception as e:
                repo_name = os.path.basename(repo_path.rstrip('/'))
                multi_validation['repositories'][repo_name] = {
                    'repo_name': repo_name,
                    'errors': [str(e)]
                }
                multi_validation['summary']['failed_validations'] += 1
            
            print()  # Add spacing between repositories
        
        # Calculate averages
        if bug_rates:
            multi_validation['summary']['average_bug_rate'] = sum(bug_rates) / len(bug_rates)
        
        if szz_match_rates:
            multi_validation['summary']['average_szz_match_rate'] = sum(szz_match_rates) / len(szz_match_rates)
        
        if issue_match_rates:
            multi_validation['summary']['average_issue_match_rate'] = sum(issue_match_rates) / len(issue_match_rates)
        
        # Print multi-repo summary
        self._print_multi_repo_summary(multi_validation)
        
        return multi_validation
    
    def _print_multi_repo_summary(self, validation_result: Dict):
        """Print multi-repository validation summary."""
        summary = validation_result['summary']
        
        print("📊 MULTI-REPOSITORY VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total repositories: {summary['total_repos']}")
        print(f"Successful validations: {summary['successful_validations']}")
        print(f"Failed validations: {summary['failed_validations']}")
        
        if summary['successful_validations'] > 0:
            print(f"\n📈 Aggregate Statistics:")
            print(f"   Total files: {summary['total_files']}")
            print(f"   Total buggy files: {summary['total_buggy_files']}")
            print(f"   Average bug rate: {summary['average_bug_rate']:.1f}%")
            print(f"   Average SZZ match rate: {summary['average_szz_match_rate']:.1f}%")
            print(f"   Average issue match rate: {summary['average_issue_match_rate']:.1f}%")
        
        print("\n📋 Repository Details:")
        for repo_name, result in validation_result['repositories'].items():
            if 'bug_analysis' in result:
                bug_rate = result['bug_analysis']['bug_rate']
                szz_match = result['szz_match_rate']
                issue_match = result['issue_match_rate']
                warnings = len(result.get('warnings', []))
                errors = len(result.get('errors', []))
                
                status = "✅" if errors == 0 else "❌"
                print(f"   {status} {repo_name}: {bug_rate:.1f}% buggy, SZZ: {szz_match:.1f}%, Issue: {issue_match:.1f}%")
                if warnings > 0:
                    print(f"      ⚠️  {warnings} warnings")
                if errors > 0:
                    print(f"      ❌ {errors} errors")
    
    def save_validation_report(self, validation_result: Dict, output_file: str = None):
        """Save validation report to JSON file."""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"label_validation_report_{timestamp}.json"
        
        try:
            with open(output_file, 'w') as f:
                json.dump(validation_result, f, indent=2)
            print(f"💾 Validation report saved to {output_file}")
        except Exception as e:
            print(f"❌ Failed to save validation report: {e}")

def validate_labeling_pipeline(repo_paths: List[str], cache_dir: str = None, github_token: str = None) -> Dict:
    """
    Validate labeling pipeline for multiple repositories.
    
    Args:
        repo_paths: List of repository paths
        cache_dir: Cache directory
        github_token: GitHub API token
        
    Returns:
        Validation results dictionary
    """
    validator = LabelValidator(cache_dir=cache_dir, github_token=github_token)
    return validator.validate_multiple_repositories(repo_paths)
