import os
import lizard
from pathlib import Path
from backend.config import SKIP_DIR_PATTERNS, SKIP_FILE_PATTERNS, ALWAYS_INCLUDE_DIRS, ALLOWED_EXTENSIONS, EXCLUDED_EXTENSIONS, EXCLUDED_DIRS, CORE_DIRS, CONDITIONAL_DIRS, FRAMEWORK_KEYWORDS

# ── 3-LAYER FILTERING SYSTEM ───────────────────────────────────────────────────────
# Backward compatibility
VALID_EXTENSIONS = {ext: ext.replace('.', '').lower() for ext in ALLOWED_EXTENSIONS}
SUPPORTED_EXTENSIONS = VALID_EXTENSIONS

# Known non-code files to exclude even if extension passes
EXCLUDE_FILES = {
    "README.md", "readme.md", "README.txt", "readme.txt",
    "requirements.txt", "requirements-dev.txt",
    "Dockerfile", "docker-compose.yml", "Makefile", "CMakeLists.txt",
    "LICENSE", "LICENSE.txt", "HISTORY.md", "CHANGELOG.md"
}

EXCLUDE_PATTERNS = [
    # Test file patterns
    lambda p: Path(p).name.startswith("test_") or Path(p).name.endswith("_test.py"),
    lambda p: Path(p).name.startswith("spec_") or Path(p).name.endswith("_spec.py"),
    
    # Private/utility files (except important ones)
    lambda p: (Path(p).stem.startswith("_") and 
               not Path(p).name in ["__init__.py", "__init__.js", "__init__.ts"] and
               not Path(p).name.startswith("_utils") and
               not Path(p).name.startswith("_config")),
    
    # Generated and build artifacts
    lambda p: any(x in p.lower() for x in [
        "node_modules", "__pycache__", ".venv", "venv/", "env/",
        "coverage/", "__generated__"
    ]),
    lambda p: p.endswith(".min.js"),
    lambda p: p.endswith(".min.css"),
    lambda p: p.endswith("_pb2.py"),
    lambda p: p.endswith(".pb.go"),
    lambda p: p.endswith(".lock"),
    lambda p: p.endswith(".log"),
    
    # Specific non-code files
    lambda p: Path(p).name in EXCLUDE_FILES,
]


def get_language(filepath: str) -> str | None:
    """Get language identifier from file extension."""
    return SUPPORTED_EXTENSIONS.get(Path(filepath).suffix.lower())


def should_exclude(filepath: str) -> bool:
    """Check if file should be excluded from analysis."""
    return any(fn(filepath) for fn in EXCLUDE_PATTERNS)


def _should_skip_dir(dirpath, repo_path=None):
    """Return True if any path component matches a skip pattern from config.py."""
    parts = dirpath.replace("\\", "/").lower().split("/")
    
    # If any part of the path is in the absolute whitelist, NEVER skip it
    if any(part in ALWAYS_INCLUDE_DIRS for part in parts):
        return False
        
    # Dynamically include repo name as a core dir
    if repo_path:
        repo_name = os.path.basename(repo_path).lower()
        if repo_name in parts:
            return False
            
    return any(part in SKIP_DIR_PATTERNS for part in parts)


def _has_test_file(filepath: str, search_dir: Path) -> bool:
    """
    Check if there's a corresponding test file for the given source file.
    This is a fast heuristic that checks for common test file naming patterns.
    
    Args:
        filepath: Path to the source file
        search_dir: Directory to search for test files (typically the source file's directory)
        
    Returns:
        True if a test file exists, False otherwise
    """
    if not search_dir.exists():
        return False
    
    file_path = Path(filepath)
    file_stem = file_path.stem
    file_name = file_path.name
    
    # Common test file patterns to check
    test_patterns = [
        f"test_{file_stem}",           # test_auth.py
        f"{file_stem}_test",           # auth_test.py
        f"spec_{file_stem}",           # spec_auth.py
        f"{file_stem}_spec",           # auth_spec.py
        f"{file_stem}.spec",           # auth.spec
        f"{file_stem}.test",           # auth.test
    ]
    
    # Check in the same directory first
    for pattern in test_patterns:
        test_file = search_dir / f"{pattern}{file_path.suffix}"
        if test_file.exists():
            return True
    
    # Check for test directories (tests/, test/, spec/)
    test_dirs = ["tests", "test", "spec", "__tests__"]
    for test_dir in test_dirs:
        test_dir_path = search_dir.parent / test_dir
        if test_dir_path.exists():
            for pattern in test_patterns:
                test_file = test_dir_path / f"{pattern}{file_path.suffix}"
                if test_file.exists():
                    return True
    
    return False


def empty_metrics(language: str) -> dict:
    """Return empty metrics for files with no analyzable functions."""
    return {
        "file": "",
        "loc": 0,
        "avg_complexity": 0,
        "max_complexity": 0,
        "functions": 0,
        "avg_params": 0,
        "max_function_length": 0,
        "max_nesting_depth": 0,
        "language": language,
        "has_test_file": False,
        "top_functions": []
    }


def _max_nesting_depth(filepath: str) -> int:
    """
    Compute the maximum block-nesting depth in a Python file via AST.
    Counts: if/elif/else, for, while, try/except, with, match.
    Returns 0 for non-Python files or parse errors.
    
    Deep nesting (≥5) is strongly correlated with bug-prone code paths
    and provides a distinct signal from cyclomatic complexity.
    """
    if not filepath.endswith(".py"):
        return 0
    try:
        import ast as _ast
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = _ast.parse(source)
    except Exception:
        return 0

    _NESTING_NODES = (
        _ast.If, _ast.For, _ast.While, _ast.Try,
        _ast.With, _ast.ExceptHandler,
    )
    # Python 3.10+: ast.Match
    try:
        _NESTING_NODES = _NESTING_NODES + (_ast.Match,)
    except AttributeError:
        pass

    def _depth(node, current=0):
        """Recursively walk AST, tracking nesting level of block statements."""
        max_d = current
        for child in _ast.iter_child_nodes(node):
            if isinstance(child, _NESTING_NODES):
                max_d = max(max_d, _depth(child, current + 1))
            else:
                max_d = max(max_d, _depth(child, current))
        return max_d

    return _depth(tree)


# ── 3-LAYER FILTERING IMPLEMENTATION ───────────────────────────────────────────────

def layer1_extension_filter(filepath: str) -> bool:
    """LAYER 1: Extension filter (coarse filter)"""
    ext = Path(filepath).suffix.lower()
    
    # Hard exclude
    if ext in EXCLUDED_EXTENSIONS:
        return False
    
    # Only allow allowed extensions
    return ext in ALLOWED_EXTENSIONS

def layer2_directory_filter(filepath: str, repo_path=None) -> tuple[bool, str]:
    """LAYER 2: Directory intelligence - returns (should_exclude, directory_type)"""
    path_parts = Path(filepath).parts
    path_parts_lower = [p.lower() for p in path_parts]
    
    # Check excluded dirs first
    for part in path_parts_lower:
        if part in EXCLUDED_DIRS:
            return True, "excluded"
    
    # Check core dirs
    for part in path_parts_lower:
        if part in CORE_DIRS:
            return False, "core"
            
    # Dynamically check repo name as a core dir
    if repo_path:
        repo_name = os.path.basename(repo_path).lower()
        if repo_name in path_parts_lower:
            return False, "core"
    
    # Check conditional dirs
    for part in path_parts_lower:
        if part in CONDITIONAL_DIRS:
            return False, "conditional"
    
    return False, "other"

def has_important_keywords(filepath: str) -> bool:
    """Check for important keywords in file path"""
    important_keywords = [
        "model", "db", "database", "api", "route",
        "controller", "service", "schema", "auth",
        "migration", "seed", "config", "settings",
        # Framework-specific keywords
        "middleware", "dependency", "security", "static",
        "template", "websocket", "cors", "gzip", "openapi"
    ]
    
    filepath_lower = filepath.lower()
    return any(keyword in filepath_lower for keyword in important_keywords)

def should_use_relaxed_filtering(repo_path: str, total_files: int) -> bool:
    """Size-aware filtering: use relaxed criteria for large repos to avoid over-filtering."""
    # For repos with >500 files, use more inclusive filtering
    return total_files > 500

def is_meaningful_file(filepath: str, analysis_result, repo_path=None, total_files=None) -> bool:
    """LAYER 3: Semantic filter - Is this file actually meaningful?"""
    
    # Size-aware filtering for large repos
    use_relaxed = should_use_relaxed_filtering(repo_path, total_files or 0)
    
    # 1. Core directories → always keep
    _, dir_type = layer2_directory_filter(filepath, repo_path=repo_path)
    if dir_type == "core":
        return True
    
    # 2. Framework infrastructure files → more lenient (keyword-based, research-clean)
    if any(keyword in filepath.lower() for keyword in FRAMEWORK_KEYWORDS):
        # For framework infrastructure files, be more lenient
        if has_important_keywords(filepath):
            return True
        # Keep framework infrastructure files with any functions or decent size
        if len(analysis_result.function_list) >= 1 or analysis_result.nloc >= 10:
            return True
    
    # 3. Entry point files → always keep
    filename = os.path.basename(filepath).lower()
    entry_points = {'index.js', 'main.py', 'app.py', 'package.json', 'setup.py'}
    if filename in entry_points:
        return True
    
    # 4. Has real logic (relaxed for large repos)
    logic_threshold = 1 if use_relaxed else 2
    if len(analysis_result.function_list) >= logic_threshold:
        return True
    
    # 5. Moderate size + logic (relaxed for large repos)
    size_threshold = 10 if use_relaxed else 15
    if analysis_result.nloc >= size_threshold and len(analysis_result.function_list) >= 1:
        return True
    
    # 6. DB / API / ML files (even small ones)
    if has_important_keywords(filepath):
        return True
    
    # 7. Examples and tutorials with decent content (exclude for production)
    # For large repos, be more selective about examples
    if not use_relaxed and any(keyword in filepath.lower() for keyword in ["example", "tutorial"]):
        # More lenient for examples - keep if they have functions OR decent size
        if len(analysis_result.function_list) >= 1 or analysis_result.nloc >= 10:
            return True
    
    # 8. Core application logic (backend/frontend)
    if any(keyword in filepath.lower() for keyword in ["app", "service", "controller", "route", "handler", "middleware", "auth", "util", "helper"]):
        # Keep core application logic even if small
        if analysis_result.nloc >= 5 or len(analysis_result.function_list) >= 1:
            return True
    
    # 8. High complexity
    if analysis_result.nloc >= 50:  # High LOC as proxy for complexity
        return True
    
    return False

def is_trivial_file(filepath: str, analysis_result) -> bool:
    """Check if file is trivial and should be excluded"""
    
    # Entry point files are never trivial (index.js, main.py, app.py, package.json)
    filename = os.path.basename(filepath).lower()
    entry_points = {'index.js', 'main.py', 'app.py', 'package.json', 'setup.py'}
    if filename in entry_points:
        return False
    
    # Framework infrastructure files are never trivial (keyword-based, research-clean)
    if any(keyword in filepath.lower() for keyword in FRAMEWORK_KEYWORDS):
        return False  # Never exclude framework infrastructure files
    
    # Config files without functions (but keep important ones)
    if (filepath.endswith(('.json', '.yaml', '.yml')) and 
        len(analysis_result.function_list) == 0):
        # Keep package.json, setup.py as they contain important metadata
        if filename in {'package.json', 'setup.py'}:
            return False
        # Exclude other config files without functions
        return True
    
    # Too small AND no functions (but allow small framework infrastructure files)
    if analysis_result.nloc <= 3 and len(analysis_result.function_list) == 0:
        # Check if this is a framework infrastructure file
        if any(keyword in filepath.lower() for keyword in FRAMEWORK_KEYWORDS):
            return False  # Never exclude small framework infrastructure files
        return True  # Exclude small non-framework files
    
    # Example files - be more selective, keep substantial ones
    if "example" in filepath.lower():
        # Keep examples with decent complexity
        if analysis_result.nloc >= 20 or len(analysis_result.function_list) >= 2:
            return False
        # Keep tutorial examples that might be important
        if "tutorial" in filepath.lower() and analysis_result.nloc >= 15:
            return False
        return True
    
    # No logic and not important keywords
    if len(analysis_result.function_list) == 0 and analysis_result.nloc < 30:
        if not has_important_keywords(filepath):
            return True
    
    return False

def should_include_file(filepath: str, analysis_result, repo_path=None, buggy_paths=None, total_files=None) -> bool:
    """
    🧠 FINAL ALGORITHM (CLEAN VERSION)
    3-Layer filtering system + Buggy preservation override
    """
    # PART 2: BUGGY PRESERVATION OVERRIDE
    # If file is known to be buggy from SZZ, ALWAYS include it
    if buggy_paths:
        from backend.labeling import _norm_rel
        norm_path = _norm_rel(filepath, repo_path) if repo_path else filepath
        if norm_path in buggy_paths:
            return True

    # STEP 1: extension filter
    if not layer1_extension_filter(filepath):
        return False
    
    # STEP 2: exclude bad dirs
    should_exclude, dir_type = layer2_directory_filter(filepath, repo_path=repo_path)
    if should_exclude:
        return False
    
    # STEP 3: core dirs → always include
    if dir_type == "core":
        return True
    
    # STEP 4: remove trivial
    if is_trivial_file(filepath, analysis_result):
        return False
    
    # STEP 5: include meaningful
    if is_meaningful_file(filepath, analysis_result, repo_path=repo_path, total_files=total_files):
        return True
    
    return False


def analyze_file(filepath: str, repo_path=None, buggy_paths=None, total_files=None) -> dict | None:
    """Analyze a single file and return static metrics using 3-layer filtering."""
    
    # STEP 1: Quick extension check (unless it's a buggy file)
    is_buggy = False
    if buggy_paths:
        from backend.labeling import _norm_rel
        norm_path = _norm_rel(filepath, repo_path) if repo_path else filepath
        if norm_path in buggy_paths:
            is_buggy = True

    if not is_buggy and not layer1_extension_filter(filepath):
        return None
    
    # STEP 2: Directory check (unless it's a buggy file)
    if not is_buggy:
        should_exclude, dir_type = layer2_directory_filter(filepath, repo_path=repo_path)
        if should_exclude:
            return None
    
    # STEP 3: Analyze the file
    lang = get_language(filepath)
    if lang is None:
        return None

    result = lizard.analyze_file(filepath)
    
    # Even if no functions, use LOC from lizard
    if not result or not result.function_list:
        # File has no functions but may have LOC (imports, constants, etc.)
        has_test_file = _has_test_file(filepath, Path(filepath).parent)
        nesting_depth = _max_nesting_depth(filepath)
        
        # Apply 3-layer filtering to files without functions
        if not should_include_file(filepath, result if result else type('MockResult', (), {'nloc': 0, 'function_list': []})(), repo_path=repo_path, buggy_paths=buggy_paths, total_files=total_files):
            return None
        
        return {
            "file": filepath,
            "loc": result.nloc if result else 0,
            "avg_complexity": 0,
            "max_complexity": 0,
            "functions": 0,
            "avg_params": 0,
            "max_function_length": 0,
            "loc_per_function": 0,
            "complexity_density": 0,
            "max_nesting_depth": nesting_depth,
            "language": lang,
            "has_test_file": has_test_file,
            "top_functions": [],
        }

    # STEP 4: Apply 3-layer semantic filtering
    if not should_include_file(filepath, result, repo_path=repo_path, buggy_paths=buggy_paths, total_files=total_files):
        return None

    fns = result.function_list
    complexities = [f.cyclomatic_complexity for f in fns]
    params       = [f.parameter_count for f in fns]
    lengths      = [f.length for f in fns]

    # Check for test coverage proxy
    has_test_file = _has_test_file(filepath, Path(filepath).parent)

    # AST-based nesting depth (Python only; 0 for other languages)
    nesting_depth = _max_nesting_depth(filepath)

    return {
        # Same names as before — model contract unchanged
        "file": filepath,
        "loc": result.nloc,
        "avg_complexity":    sum(complexities) / len(complexities),
        "max_complexity":    max(complexities),
        "functions":         len(fns),
        "avg_params":        sum(params) / len(params),
        "max_function_length": max(lengths),
        "loc_per_function":  sum(lengths) / len(lengths),
        "complexity_density": sum(complexities) / max(result.nloc, 1),
        # AST-based feature: max block nesting depth (Python; 0 for others)
        "max_nesting_depth": nesting_depth,
        # New column
        "language":          lang,
        # Test coverage proxy feature
        "has_test_file":     has_test_file,
        # For UI display only (not a model feature)
        "top_functions": sorted([
            {"name": f.name, "cx": f.cyclomatic_complexity,
             "length": f.length, "params": f.parameter_count}
            for f in fns
        ], key=lambda x: x["cx"], reverse=True)[:5],
    }


def get_top_functions(file_path, top_n=3):
    """
    Return the top-N most complex functions in a file (by cyclomatic complexity).
    Used for function-level risk output in the final report.
    Returns a list of dicts: [{name, complexity, length, params}, ...].
    Returns [] on any error (file not found, parse error, etc.).
    """
    try:
        analysis = lizard.analyze_file(str(file_path))
        funcs = sorted(
            analysis.function_list,
            key=lambda f: f.cyclomatic_complexity,
            reverse=True
        )[:top_n]
        return [
            {
                "name":       f.name,
                "complexity": f.cyclomatic_complexity,
                "length":     f.length,
                "params":     f.parameter_count,
            }
            for f in funcs
        ]
    except Exception:
        return []


def analyze_repository(repo_path, verbose=False, parallel=False, max_workers=4, buggy_paths=None):
    """
    Walk repo_path and return per-file static metrics via lizard.
    
    Args:
        repo_path: Path to repository
        verbose: Whether to print progress
        parallel: Whether to use parallel processing
        max_workers: Maximum number of worker threads
        buggy_paths: Set of paths that should always be included (SZZ protection)
        
    Returns:
        List of dictionaries with static metrics per file
    """
    
    # Validate drop rate to ensure dataset quality
    total_files_found = 0
    files_included = 0
    results      = []
    skipped_dirs  = []
    skipped_files = []
    files_to_analyze = []
    
    # Enhanced filtering statistics
    filter_stats = {
        'excluded_by_extension': 0,
        'excluded_by_pattern': 0,
        'excluded_by_meaningful': 0,
        'excluded_by_directory': 0,
        'total_files_found': 0,
        'final_included': 0
    }

    # First pass: collect all files to analyze
    for root, dirs, files in os.walk(repo_path):
        # Prune skipped directories in-place so os.walk doesn't descend into them
        pruned = [d for d in dirs if _should_skip_dir(os.path.join(root, d), repo_path=repo_path)]
        dirs[:] = [d for d in dirs if not _should_skip_dir(os.path.join(root, d), repo_path=repo_path)]
        skipped_dirs.extend(os.path.join(root, d) for d in pruned)

        if _should_skip_dir(root, repo_path=repo_path):
            continue

        for file in files:
            file_path = os.path.normpath(os.path.join(root, file))
            filter_stats['total_files_found'] += 1
            
            # Track filtering reasons
            if get_language(file_path) is None:
                filter_stats['excluded_by_extension'] += 1
                skipped_files.append(file)
                continue
                
            if should_exclude(file_path):
                filter_stats['excluded_by_pattern'] += 1
                skipped_files.append(file)
                continue
                
            files_to_analyze.append(file_path)
    
    # Second pass: analyze files (parallel or sequential)
    if parallel and len(files_to_analyze) > 10:
        # Use ThreadPoolExecutor for Windows compatibility (avoids multiprocessing issues)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(analyze_file, fp, repo_path=repo_path, buggy_paths=buggy_paths, total_files=len(files_to_analyze)): fp for fp in files_to_analyze}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    file_path = futures[future]
                    if verbose:
                        print(f"  Error analyzing {file_path}: {e}")
    else:
        # Sequential analysis for small repos or when parallel is disabled
        for file_path in files_to_analyze:
            result = analyze_file(file_path, repo_path=repo_path, buggy_paths=buggy_paths, total_files=len(files_to_analyze))
            if result is not None:
                results.append(result)

    filter_stats['final_included'] = len(results)
    filter_stats['excluded_by_directory'] = len(skipped_dirs)
    
    # Validate drop rate to ensure dataset quality
    drop_rate = (filter_stats['excluded_by_extension'] + filter_stats['excluded_by_pattern'] + 
                 filter_stats['excluded_by_meaningful'] + filter_stats['excluded_by_directory']) / filter_stats['total_files_found'] if filter_stats['total_files_found'] > 0 else 0
    
    if verbose:
        print(f"\n  [Enhanced Analyzer Audit for {os.path.basename(repo_path)}]")
        print(f"  ══════════════════════════════════════════════════════════════")
        print(f"  📊 FILTERING STATISTICS:")
        print(f"     Total files found     : {filter_stats['total_files_found']}")
        print(f"     Excluded by extension: {filter_stats['excluded_by_extension']}")
        print(f"     Excluded by pattern  : {filter_stats['excluded_by_pattern']}")
        print(f"     Excluded by meaningful: {filter_stats['excluded_by_meaningful']}")
        print(f"     Excluded by directory: {filter_stats['excluded_by_directory']}")
        print(f"     Final included files  : {filter_stats['final_included']}")
        print(f"     Drop rate            : {drop_rate:.1%}")
        
        # Validation warning for excessive filtering
        if drop_rate > 0.75:
            print(f"     ⚠️  WARNING: High drop rate ({drop_rate:.1%}%) - may remove real logic")
        elif drop_rate < 0.40:
            print(f"     ✓ Drop rate ({drop_rate:.1%}%) within acceptable range (40-70%)")
        else:
            print(f"     ✓ Drop rate ({drop_rate:.1%}%) good - balanced filtering")
        print(f"     Inclusion rate       : {filter_stats['final_included']/filter_stats['total_files_found']*100:.1f}%")
        print(f"  ══════════════════════════════════════════════════════════════")
        print(f"  📁 First 10 analyzed files:")
        for r in results[:10]:
            print(f"     {os.path.relpath(r['file'], repo_path)} ({r['loc']} LOC, {r['functions']} funcs)")
        if skipped_dirs:
            print(f"  📁 First 10 pruned directories:")
            for d in skipped_dirs[:10]:
                print(f"     {os.path.relpath(d, repo_path)}")
        if skipped_files:
            print(f"  📄 First 10 skipped files (extension/pattern):")
            for f in skipped_files[:10]:
                reason = "extension" if get_language(os.path.join(root, f)) is None else "pattern"
                print(f"     {f} ({reason})")
        print(f"  ══════════════════════════════════════════════════════════════")

    return results