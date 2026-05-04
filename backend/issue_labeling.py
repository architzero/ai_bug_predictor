#!/usr/bin/env python3
"""
Issue-based labeling system using GitHub API.
Extracts bug-fix commits from GitHub issue references.
"""

import os
import re
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime, timedelta

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
API_RATE_LIMIT_DELAY = 1.0  # seconds between requests
CACHE_MAX_AGE_HOURS = 24

# Issue reference patterns
ISSUE_PATTERNS = [
    r'(?:fixes?|closes?|resolves?|addresses?)\s+#(\d+)',
    r'(?:fixes?|closes?|resolves?|addresses?)\s+(?:https?://)?(?:www\.)?github\.com/[^/]+/[^/]+/issues/(\d+)',
    r'#(\d+)',  # Generic issue reference (lower confidence)
]

# Bug-related issue labels
BUG_LABELS = ['bug', 'defect', 'error', 'failure', 'crash', 'issue', 'problem']

class GitHubIssueLabeler:
    """GitHub issue-based bug fix labeler."""
    
    def __init__(self, cache_dir: str = None, github_token: str = None):
        """
        Initialize GitHub issue labeler.
        
        Args:
            cache_dir: Directory for caching issue data
            github_token: GitHub API token (optional but recommended)
        """
        self.cache_dir = cache_dir
        self.github_token = github_token
        self.session = requests.Session()
        
        if github_token:
            self.session.headers.update({
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github.v3+json'
            })
        
        self.api_delay = API_RATE_LIMIT_DELAY
        self.last_api_call = 0
    
    def _rate_limit_wait(self):
        """Wait to respect GitHub API rate limits."""
        current_time = time.time()
        time_since_last = current_time - self.last_api_call
        
        if time_since_last < self.api_delay:
            time.sleep(self.api_delay - time_since_last)
        
        self.last_api_call = time.time()
    
    def _get_cache_path(self, repo_path: str) -> str:
        """Get cache file path for repository."""
        repo_name = os.path.basename(repo_path.rstrip('/'))
        cache_filename = f"github_issues_{repo_name}.json"
        
        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)
            return os.path.join(self.cache_dir, cache_filename)
        else:
            return cache_filename
    
    def _load_cached_issues(self, repo_path: str) -> Optional[Dict]:
        """Load cached issue data."""
        cache_path = self._get_cache_path(repo_path)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
            
            # Check cache age
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time > timedelta(hours=CACHE_MAX_AGE_HOURS):
                return None
            
            print(f"  📂 Loaded cached GitHub issues for {repo_path}")
            return cache_data
        except Exception as e:
            print(f"  ⚠️  Failed to load cached issues: {e}")
            return None
    
    def _save_cached_issues(self, repo_path: str, issues_data: Dict):
        """Save issue data to cache."""
        cache_path = self._get_cache_path(repo_path)
        
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'issues': issues_data
        }
        
        try:
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
            print(f"  💾 Cached GitHub issues to {cache_path}")
        except Exception as e:
            print(f"  ⚠️  Failed to cache issues: {e}")
    
    def _extract_repo_info(self, repo_path: str) -> Optional[Tuple[str, str]]:
        """Extract GitHub owner and repo from git remote URL."""
        try:
            import subprocess
            
            # Get git remote URL
            result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return None
            
            remote_url = result.stdout.strip()
            
            # Parse GitHub URL
            # Handle both HTTPS and SSH URLs
            patterns = [
                r'https?://(?:www\.)?github\.com/([^/]+)/([^/]+)(?:\.git)?',
                r'git@github\.com:([^/]+)/([^/]+)(?:\.git)?',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, remote_url)
                if match:
                    owner, repo = match.groups()
                    repo = repo.replace('.git', '')
                    return owner, repo
            
            return None
        except Exception as e:
            print(f"  ⚠️  Failed to extract repo info: {e}")
            return None
    
    def _fetch_issue_data(self, owner: str, repo: str, issue_number: int) -> Optional[Dict]:
        """Fetch issue data from GitHub API."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"
        
        try:
            self._rate_limit_wait()
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 404:
                print(f"  ❌ Issue #{issue_number} not found")
                return None
            elif response.status_code == 403:
                print(f"  ❌ API rate limit exceeded for issue #{issue_number}")
                return None
            elif response.status_code != 200:
                print(f"  ❌ Failed to fetch issue #{issue_number}: {response.status_code}")
                return None
            
            return response.json()
        except Exception as e:
            print(f"  ❌ Error fetching issue #{issue_number}: {e}")
            return None
    
    def _is_bug_issue(self, issue_data: Dict) -> bool:
        """Determine if issue is a bug based on labels and content."""
        # Check labels
        labels = [label.get('name', '').lower() for label in issue_data.get('labels', [])]
        
        if any(bug_label in labels for bug_label in BUG_LABELS):
            return True
        
        # Check title and body for bug keywords
        title = issue_data.get('title', '').lower()
        body = issue_data.get('body', '').lower()
        
        bug_keywords = ['bug', 'error', 'crash', 'failure', 'defect', 'issue', 'problem']
        
        if any(keyword in title for keyword in bug_keywords):
            return True
        
        if any(keyword in body for keyword in bug_keywords):
            return True
        
        return False
    
    def extract_issue_references(self, commit_message: str) -> List[int]:
        """
        Extract issue numbers from commit message.
        
        Args:
            commit_message: Git commit message
            
        Returns:
            List of issue numbers
        """
        issue_numbers = []
        
        for pattern in ISSUE_PATTERNS:
            matches = re.findall(pattern, commit_message, re.IGNORECASE)
            issue_numbers.extend([int(match) for match in matches])
        
        return list(set(issue_numbers))  # Remove duplicates
    
    def get_bug_fix_commits(self, repo_path: str) -> Dict[str, float]:
        """
        Get bug-fix commits based on GitHub issue references.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Dictionary of commit_hash -> confidence
        """
        print(f"🔍 Extracting GitHub issue labels from {repo_path}")
        
        # Try cached data first
        cached_data = self._load_cached_issues(repo_path)
        if cached_data:
            return cached_data['issues']
        
        # Extract repo info
        repo_info = self._extract_repo_info(repo_path)
        if not repo_info:
            print("  ❌ Could not extract GitHub repository information")
            print("      This may be a private repository or not hosted on GitHub")
            return {}
        
        owner, repo = repo_info
        print(f"  📋 GitHub repository: {owner}/{repo}")
        
        # Get commit history
        try:
            import subprocess
            
            result = subprocess.run(
                ['git', 'log', '--pretty=format:%H|%s'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print("  ❌ Failed to get commit history")
                return {}
            
            commits = result.stdout.strip().split('\n')
        except Exception as e:
            print(f"  ❌ Failed to get commit history: {e}")
            return {}
        
        # Process commits for issue references
        bug_fix_commits = {}
        processed_issues = set()
        
        for commit_line in commits:
            if not commit_line:
                continue
            
            commit_hash, commit_message = commit_line.split('|', 1)
            
            # Extract issue references
            issue_numbers = self.extract_issue_references(commit_message)
            
            if not issue_numbers:
                continue
            
            # Process each issue
            is_bug_fix = False
            confidence = 0.8  # High confidence for issue-linked fixes
            
            for issue_number in issue_numbers:
                if issue_number in processed_issues:
                    continue
                
                processed_issues.add(issue_number)
                
                # Fetch issue data
                issue_data = self._fetch_issue_data(owner, repo, issue_number)
                
                if issue_data and self._is_bug_issue(issue_data):
                    is_bug_fix = True
                    print(f"  ✅ Issue #{issue_number}: {issue_data.get('title', 'No title')}")
                elif issue_data:
                    print(f"  ⚪ Issue #{issue_number}: Not a bug issue")
                else:
                    print(f"  ❓ Issue #{issue_number}: Could not fetch data")
            
            if is_bug_fix:
                bug_fix_commits[commit_hash] = confidence
        
        # Cache results
        self._save_cached_issues(repo_path, bug_fix_commits)
        
        print(f"  📊 Issue labeling results:")
        print(f"     Total commits processed: {len(commits)}")
        print(f"     Bug-fix commits found: {len(bug_fix_commits)}")
        print(f"     Issues processed: {len(processed_issues)}")
        
        return bug_fix_commits
    
    def get_files_changed_in_commits(self, repo_path: str, commit_hashes: List[str]) -> Dict[str, float]:
        """
        Get files changed in specific commits.
        
        Args:
            repo_path: Path to repository
            commit_hashes: List of commit hashes
            
        Returns:
            Dictionary of file_path -> confidence
        """
        file_changes = {}
        
        for commit_hash in commit_hashes:
            try:
                import subprocess
                
                # Get files changed in commit
                result = subprocess.run(
                    ['git', 'show', '--name-only', '--pretty=format:', commit_hash],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    continue
                
                files = result.stdout.strip().split('\n')
                
                for file_path in files:
                    if not file_path or file_path.startswith(' '):
                        continue
                    
                    full_path = os.path.join(repo_path, file_path)
                    
                    if os.path.exists(full_path):
                        # Use confidence from the commit
                        confidence = 0.8  # High confidence for issue-linked fixes
                        
                        # Keep highest confidence if file appears multiple times
                        current_confidence = file_changes.get(full_path, 0)
                        file_changes[full_path] = max(current_confidence, confidence)
                
            except Exception as e:
                print(f"  ⚠️  Failed to get files for commit {commit_hash}: {e}")
        
        return file_changes
    
    def extract_issue_labels(self, repo_path: str) -> Dict[str, float]:
        """
        Extract issue-based labels for all files in repository.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Dictionary of file_path -> confidence
        """
        # Get bug-fix commits
        bug_fix_commits = self.get_bug_fix_commits(repo_path)
        
        if not bug_fix_commits:
            print("  ⚠️  No bug-fix commits found via issue references")
            return {}
        
        # Get files changed in those commits
        file_labels = self.get_files_changed_in_commits(repo_path, list(bug_fix_commits.keys()))
        
        print(f"  📊 Issue-based labeling results:")
        print(f"     Files labeled as buggy: {len(file_labels)}")
        
        return file_labels

def extract_issue_labels(repo_path: str, cache_dir: str = None, github_token: str = None) -> Dict[str, float]:
    """
    Extract issue-based labels using GitHub API.
    
    Args:
        repo_path: Path to repository
        cache_dir: Cache directory
        github_token: GitHub API token
        
    Returns:
        Dictionary of file_path -> confidence
    """
    labeler = GitHubIssueLabeler(cache_dir=cache_dir, github_token=github_token)
    return labeler.extract_issue_labels(repo_path)
