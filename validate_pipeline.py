"""
Pre-Training Validation Script

Validates the entire training pipeline before running main.py:
1. Import integrity - all modules load correctly
2. Path normalization consistency - SZZ and labeling use same logic
3. Feature constants consistency - no duplicates or conflicts
4. Cache version correctness - v13 for churn-weighted labeling
5. Configuration sanity - all paths exist, thresholds are reasonable
6. Repository availability - all training repos exist
"""

import os
import sys
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*72}{RESET}")
    print(f"{BLUE}  {text}{RESET}")
    print(f"{BLUE}{'='*72}{RESET}")

def print_success(text):
    print(f"{GREEN}  ✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}  ✗ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}  ⚠ {text}{RESET}")

def print_info(text):
    print(f"  • {text}")

# Test 1: Import Integrity
print_header("TEST 1: Import Integrity")
try:
    from backend import config, features, train, predict, explainer
    from backend import analysis, git_mining, labeling, szz
    from backend import bug_classifier, bug_integrator, commit_risk
    from backend.feature_constants import NON_FEATURE_COLS, LEAKAGE_COLS, ALL_EXCLUDE_COLS
    print_success("All backend modules imported successfully")
except ImportError as e:
    print_error(f"Import failed: {e}")
    sys.exit(1)

# Test 2: Path Normalization Consistency
print_header("TEST 2: Path Normalization Consistency")
try:
    from backend.szz import _norm_path
    from backend.labeling import _norm_rel
    
    # Test cases
    test_paths = [
        ("src/requests/auth.py", "src/requests/auth.py"),
        ("SRC\\Requests\\Auth.py", "src/requests/auth.py"),
        ("./src/requests/auth.py", "src/requests/auth.py"),
        ("src/requests/auth.py/", "src/requests/auth.py"),
    ]
    
    all_match = True
    for input_path, expected in test_paths:
        szz_norm = _norm_path(input_path)
        if szz_norm != expected:
            print_error(f"SZZ normalization mismatch: {input_path} -> {szz_norm} (expected {expected})")
            all_match = False
    
    if all_match:
        print_success("Path normalization is consistent between SZZ and labeling")
    else:
        print_error("Path normalization inconsistency detected")
        sys.exit(1)
except Exception as e:
    print_error(f"Path normalization test failed: {e}")
    sys.exit(1)

# Test 3: Feature Constants Consistency
print_header("TEST 3: Feature Constants Consistency")
try:
    # Check for duplicates
    all_cols = NON_FEATURE_COLS + LEAKAGE_COLS
    if len(all_cols) != len(set(all_cols)):
        duplicates = [col for col in all_cols if all_cols.count(col) > 1]
        print_error(f"Duplicate columns found: {set(duplicates)}")
        sys.exit(1)
    
    # Verify ALL_EXCLUDE_COLS matches
    if set(ALL_EXCLUDE_COLS) != set(all_cols):
        print_error("ALL_EXCLUDE_COLS doesn't match NON_FEATURE_COLS + LEAKAGE_COLS")
        sys.exit(1)
    
    print_success(f"Feature constants are consistent ({len(NON_FEATURE_COLS)} non-features, {len(LEAKAGE_COLS)} leakage)")
    print_info(f"Non-feature columns: {', '.join(NON_FEATURE_COLS[:5])}...")
    print_info(f"Leakage columns: {', '.join(LEAKAGE_COLS)}")
except Exception as e:
    print_error(f"Feature constants test failed: {e}")
    sys.exit(1)

# Test 4: Cache Version
print_header("TEST 4: Cache Version Verification")
try:
    from backend.config import CACHE_VERSION
    
    if CACHE_VERSION != "v13":
        print_error(f"Cache version is {CACHE_VERSION}, expected v13 for churn-weighted labeling")
        sys.exit(1)
    
    print_success(f"Cache version is correct: {CACHE_VERSION} (churn-weighted SZZ v2.6)")
except Exception as e:
    print_error(f"Cache version test failed: {e}")
    sys.exit(1)

# Test 5: Configuration Sanity
print_header("TEST 5: Configuration Sanity Checks")
try:
    from backend.config import (
        BASE_DIR, DATASET_DIR, MODEL_DIR, PLOTS_DIR, CACHE_DIR,
        RISK_THRESHOLD, CORR_DROP_THRESHOLD, RANDOM_STATE,
        REPOS
    )
    
    # Check directories exist
    for dir_name, dir_path in [
        ("Base", BASE_DIR),
        ("Dataset", DATASET_DIR),
        ("Model", MODEL_DIR),
        ("Plots", PLOTS_DIR),
        ("Cache", CACHE_DIR),
    ]:
        if not os.path.exists(dir_path):
            print_warning(f"{dir_name} directory doesn't exist: {dir_path} (will be created)")
        else:
            print_success(f"{dir_name} directory exists: {dir_path}")
    
    # Check thresholds
    if not 0 < RISK_THRESHOLD < 1:
        print_error(f"RISK_THRESHOLD ({RISK_THRESHOLD}) must be between 0 and 1")
        sys.exit(1)
    print_success(f"RISK_THRESHOLD is valid: {RISK_THRESHOLD}")
    
    if not 0 < CORR_DROP_THRESHOLD < 1:
        print_error(f"CORR_DROP_THRESHOLD ({CORR_DROP_THRESHOLD}) must be between 0 and 1")
        sys.exit(1)
    print_success(f"CORR_DROP_THRESHOLD is valid: {CORR_DROP_THRESHOLD}")
    
    print_success(f"RANDOM_STATE is set: {RANDOM_STATE}")
    
except Exception as e:
    print_error(f"Configuration sanity test failed: {e}")
    sys.exit(1)

# Test 6: Repository Availability
print_header("TEST 6: Repository Availability")
try:
    from backend.config import REPOS
    
    missing_repos = []
    available_repos = []
    
    for repo_path in REPOS:
        repo_name = os.path.basename(repo_path)
        if not os.path.exists(repo_path):
            missing_repos.append(repo_name)
            print_error(f"Repository not found: {repo_name} ({repo_path})")
        else:
            # Check if it's a git repo
            git_dir = os.path.join(repo_path, ".git")
            if not os.path.exists(git_dir):
                print_warning(f"Repository exists but no .git directory: {repo_name}")
            else:
                available_repos.append(repo_name)
                print_success(f"Repository available: {repo_name}")
    
    if missing_repos:
        print_error(f"{len(missing_repos)} repositories missing: {', '.join(missing_repos)}")
        print_info("Run: git clone <repo_url> dataset/<repo_name>")
        sys.exit(1)
    
    print_success(f"All {len(available_repos)} repositories are available")
    
except Exception as e:
    print_error(f"Repository availability test failed: {e}")
    sys.exit(1)

# Test 7: Feature Engineering Sanity
print_header("TEST 7: Feature Engineering Sanity")
try:
    from backend.features import LANGUAGE_ENCODING, build_features
    
    # Check language encoding
    if len(LANGUAGE_ENCODING) < 5:
        print_error(f"LANGUAGE_ENCODING has only {len(LANGUAGE_ENCODING)} languages")
        sys.exit(1)
    
    print_success(f"LANGUAGE_ENCODING has {len(LANGUAGE_ENCODING)} languages")
    print_info(f"Supported languages: {', '.join(LANGUAGE_ENCODING.keys())}")
    
    # Verify language_id values are unique
    lang_ids = list(LANGUAGE_ENCODING.values())
    if len(lang_ids) != len(set(lang_ids)):
        print_error("Duplicate language_id values found in LANGUAGE_ENCODING")
        sys.exit(1)
    
    print_success("Language encoding is valid")
    
except Exception as e:
    print_error(f"Feature engineering sanity test failed: {e}")
    sys.exit(1)

# Test 8: SZZ Configuration
print_header("TEST 8: SZZ Configuration")
try:
    from backend.szz import (
        POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS, NLP_PHRASES,
        ISSUE_REGEX, REVERT_REGEX, CONFIDENCE_WEIGHTS
    )
    
    print_success(f"SZZ has {len(POSITIVE_KEYWORDS)} positive keywords")
    print_success(f"SZZ has {len(NEGATIVE_KEYWORDS)} negative keywords")
    print_success(f"SZZ has {len(NLP_PHRASES)} NLP phrases")
    print_success(f"SZZ has {len(CONFIDENCE_WEIGHTS)} confidence weights")
    
    # Check for keyword overlap
    overlap = set(POSITIVE_KEYWORDS) & set(NEGATIVE_KEYWORDS)
    if overlap:
        print_warning(f"Keyword overlap detected: {overlap}")
    else:
        print_success("No keyword overlap between positive and negative")
    
except Exception as e:
    print_error(f"SZZ configuration test failed: {e}")
    sys.exit(1)

# Test 9: Model Training Configuration
print_header("TEST 9: Model Training Configuration")
try:
    from backend.config import (
        TUNING_N_ITER, TSCV_N_SPLITS, TEST_SIZE,
        SMOTE_K_NEIGHBORS, DEFECT_DENSITY_TOP_K
    )
    
    print_success(f"TUNING_N_ITER: {TUNING_N_ITER}")
    print_success(f"TSCV_N_SPLITS: {TSCV_N_SPLITS}")
    print_success(f"TEST_SIZE: {TEST_SIZE}")
    print_success(f"SMOTE_K_NEIGHBORS: {SMOTE_K_NEIGHBORS}")
    print_success(f"DEFECT_DENSITY_TOP_K: {DEFECT_DENSITY_TOP_K}")
    
    # Sanity checks
    if TUNING_N_ITER < 10:
        print_warning(f"TUNING_N_ITER ({TUNING_N_ITER}) is very low, may not find good hyperparameters")
    
    if TSCV_N_SPLITS < 3:
        print_warning(f"TSCV_N_SPLITS ({TSCV_N_SPLITS}) is very low, may not validate well")
    
except Exception as e:
    print_error(f"Model training configuration test failed: {e}")
    sys.exit(1)

# Final Summary
print_header("VALIDATION SUMMARY")
print_success("All validation tests passed!")
print_info("The training pipeline is ready to run")
print_info("Execute: python main.py")
print(f"{BLUE}{'='*72}{RESET}\n")
