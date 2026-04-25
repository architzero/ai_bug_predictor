import os
import lizard
from pathlib import Path
from config import SKIP_DIR_PATTERNS, SKIP_FILE_PATTERNS


SUPPORTED_EXTENSIONS = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "javascript", ".tsx": "typescript", ".java": "java",
    ".go": "go", ".rb": "ruby", ".php": "php", ".cs": "csharp",
    ".cpp": "cpp", ".c": "cpp", ".rs": "rust", ".swift": "swift",
    ".scala": "scala", ".h": "cpp"
}

EXCLUDE_PATTERNS = [
    lambda p: Path(p).name.startswith("test_") or Path(p).name.endswith("_test.py"),
    lambda p: Path(p).name.startswith("spec_") or Path(p).name.endswith("_spec.py"),
    lambda p: (Path(p).stem.startswith("_") and 
               not Path(p).name in ["__init__.py", "__init__.js", "__init__.ts"] and
               not Path(p).name.startswith("_utils") and
               not Path(p).name.startswith("_config")),
    lambda p: any(x in p for x in [
        "generated", "vendor", "node_modules",
        "dist/", "build/", "__pycache__", "docs", "examples",
        "example", "scripts", "migrations", "coverage",
        "__generated__", ".venv", "venv", "env"
    ]),
    lambda p: p.endswith(".min.js"),
    lambda p: p.endswith(".pb.go"),
    lambda p: p.endswith("_pb2.py"),
]


def get_language(filepath: str) -> str | None:
    """Get language identifier from file extension."""
    return SUPPORTED_EXTENSIONS.get(Path(filepath).suffix.lower())


def should_exclude(filepath: str) -> bool:
    """Check if file should be excluded from analysis."""
    return any(fn(filepath) for fn in EXCLUDE_PATTERNS)


def _should_skip_dir(dirpath):
    """Return True if any path component matches a skip pattern from config.py."""
    parts = dirpath.replace("\\", "/").lower().split("/")
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


def analyze_file(filepath: str) -> dict | None:
    """Analyze a single file and return static metrics."""
    lang = get_language(filepath)
    if lang is None or should_exclude(filepath):
        return None

    result = lizard.analyze_file(filepath)
    if not result or not result.function_list:
        empty_result = empty_metrics(lang)
        empty_result["file"] = filepath
        return empty_result

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


def analyze_repository(repo_path, verbose=False):
    """
    Walk repo_path and return per-file static metrics via lizard.

    verbose=True prints a full audit: how many files were analyzed vs skipped,
    which directories were pruned, and the first 20 analyzed paths.
    Set verbose=True when diagnosing low analyzer coverage.
    """
    results      = []
    skipped_dirs  = []
    skipped_files = []

    for root, dirs, files in os.walk(repo_path):
        # Prune skipped directories in-place so os.walk doesn't descend into them
        pruned = [d for d in dirs if _should_skip_dir(os.path.join(root, d))]
        dirs[:] = [d for d in dirs if not _should_skip_dir(os.path.join(root, d))]
        skipped_dirs.extend(os.path.join(root, d) for d in pruned)

        if _should_skip_dir(root):
            continue

        for file in files:
            file_path = os.path.normpath(os.path.join(root, file))
            
            # Use the new analyze_file function
            result = analyze_file(file_path)
            if result is None:
                skipped_files.append(file)
                continue
                
            results.append(result)

    if verbose:
        print(f"\n  [Analyzer audit for {os.path.basename(repo_path)}]")
        print(f"  Analyzed files   : {len(results)}")
        print(f"  Skipped dirs     : {len(skipped_dirs)}")
        print(f"  Skipped files    : {len(skipped_files)} (unsupported extension)")
        print(f"  First 20 analyzed:")
        for r in results[:20]:
            print(f"    {os.path.relpath(r['file'], repo_path)}")
        if skipped_dirs:
            print(f"  First 10 pruned dirs:")
            for d in skipped_dirs[:10]:
                print(f"    {os.path.relpath(d, repo_path)}")

    return results