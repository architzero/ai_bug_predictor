#!/usr/bin/env python3
"""
Test script to verify SZZ v2 implementation with filters and confidence weights.
"""

import os
import sys
import pandas as pd
from git_mining.szz_labeler import (
    extract_bug_labels_with_confidence, 
    get_commit_confidence,
    is_substantive_line,
    is_merge_commit
)
from feature_engineering.labeler import create_labels
from static_analysis.analyzer import analyze_repository
from git_mining.git_miner import mine_git_data
from config import REPOS, SZZ_CACHE_DIR

def test_confidence_scoring():
    """Test confidence weight scoring function."""
    print("Testing confidence weight scoring...")
    
    test_messages = [
        ("fix null pointer exception", 1.0),
        ("resolve issue #123", 0.8),
        ("handle edge case", 0.5),
        ("", 0.3),
        ("add documentation", 0.3),
        ("fix memory leak in parser", 1.0),
        ("prevent race condition", 0.5),
        ("crash on invalid input", 1.0),
    ]
    
    for message, expected_min in test_messages:
        confidence = get_commit_confidence(message)
        print(f"  '{message}' -> {confidence:.2f} (expected >= {expected_min})")
        assert confidence >= expected_min, f"Confidence too low for: {message}"
    
    print("  Confidence scoring: PASSED")

def test_comment_filtering():
    """Test comment/blank line filtering."""
    print("Testing comment/blank line filtering...")
    
    test_lines = [
        ("x = 5", "python", True),
        ("# This is a comment", "python", False),
        ("", "python", False),
        ("// JavaScript comment", "javascript", False),
        ("let x = 5;", "javascript", True),
        ("/* C-style comment */", "java", False),
        ("int x = 5;", "java", True),
    ]
    
    for line, language, expected in test_lines:
        result = is_substantive_line(line, language)
        print(f"  '{line}' ({language}) -> {result} (expected {expected})")
        assert result == expected, f"Filtering failed for: {line}"
    
    print("  Comment filtering: PASSED")

def test_szz_v2_integration():
    """Test SZZ v2 integration with a small repository."""
    print("Testing SZZ v2 integration...")
    
    # Test with requests repository (should exist)
    requests_repo = None
    for repo_path in REPOS:
        if "requests" in repo_path and os.path.exists(repo_path):
            requests_repo = repo_path
            break
    
    if not requests_repo:
        print("  Skipping integration test - requests repo not found")
        return
    
    try:
        # Test SZZ v2 with confidence weights
        buggy_confidence = extract_bug_labels_with_confidence(requests_repo, cache_dir=SZZ_CACHE_DIR)
        
        print(f"  Found {len(buggy_confidence)} buggy files with confidence weights")
        
        if buggy_confidence:
            # Check that we have confidence weights
            for file_path, confidence in list(buggy_confidence.items())[:3]:
                print(f"    {file_path}: {confidence:.2f}")
                assert 0.3 <= confidence <= 1.0, f"Invalid confidence: {confidence}"
        
        print("  SZZ v2 integration: PASSED")
        
    except Exception as e:
        print(f"  SZZ v2 integration: FAILED - {e}")
        raise

def test_labeler_integration():
    """Test labeler integration with confidence weights."""
    print("Testing labeler integration...")
    
    # Create a simple test DataFrame
    test_df = pd.DataFrame({
        'file': ['/test/file1.py', '/test/file2.py'],
        'repo': ['test_repo', 'test_repo'],
        'bug_fixes': [1, 0],
        'commits': [10, 5],
    })
    
    # Mock SZZ results
    from unittest.mock import patch
    mock_confidence = {'/test/file1.py': 0.8}
    
    with patch('feature_engineering.labeler.extract_bug_labels_with_confidence', return_value=mock_confidence):
        result_df = create_labels(test_df, 'test_repo', cache_dir=None)
    
    # Check results
    assert 'confidence' in result_df.columns, "Missing confidence column"
    assert result_df.loc[0, 'buggy'] == 1, "File should be marked buggy"
    assert result_df.loc[1, 'buggy'] == 0, "File should not be marked buggy"
    assert result_df.loc[0, 'confidence'] == 0.8, "Wrong confidence value"
    
    print("  Labeler integration: PASSED")

def test_bug_type_classification():
    """Test bug type classification components."""
    print("Testing bug type classification...")
    
    from bug_type_classification.classifier import extract_bug_type_from_message, BUG_TYPE_KEYWORDS
    
    test_cases = [
        ("fix null pointer exception", "null_pointer"),
        ("memory leak in parser", "memory_leak"),
        ("race condition in thread", "race_condition"),
        ("index out of bounds error", "index_error"),
        ("type conversion error", "type_error"),
        ("file not found exception", "resource"),
        ("logic error in calculation", "logic"),
        ("security vulnerability fix", "security"),
        ("performance optimization", "performance"),
        ("crash on invalid input", "crash"),
        ("add documentation", None),
        ("refactor code", None),
    ]
    
    for message, expected_type in test_cases:
        result = extract_bug_type_from_message(message)
        print(f"  '{message}' -> {result} (expected {expected_type})")
        assert result == expected_type, f"Wrong bug type for: {message}"
    
    print("  Bug type classification: PASSED")

def main():
    """Run all tests."""
    print("=" * 60)
    print("SZZ v2 Implementation Tests")
    print("=" * 60)
    
    tests = [
        test_confidence_scoring,
        test_comment_filtering,
        test_bug_type_classification,
        test_labeler_integration,
        test_szz_v2_integration,
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
        print()
    
    print("=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests PASSED! SZZ v2 implementation is working correctly.")
        return 0
    else:
        print("Some tests FAILED. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
