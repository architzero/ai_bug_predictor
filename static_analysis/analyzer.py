import os
import lizard


SUPPORTED_EXTENSIONS = (
    ".py", ".c", ".cpp", ".h",
    ".java", ".js", ".ts",
    ".go", ".php", ".cs"
)

# Directories to skip — they contain generated, tutorial, or example code
# that is never the target of real bug-fix commits
SKIP_DIR_PATTERNS = [
    "docs_src", "docs", "examples", "example",
    "node_modules", "vendor", "dist", "build",
    ".venv", "venv", "env", "__pycache__",
    "migrations", "coverage", "generated", "__generated__",
    "scripts",
]


def _should_skip_dir(dirpath):
    """Return True if any path component matches a skip pattern."""
    parts = dirpath.replace("\\", "/").lower().split("/")
    return any(part in SKIP_DIR_PATTERNS for part in parts)


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

            if not file.endswith(SUPPORTED_EXTENSIONS):
                skipped_files.append(file)
                continue

            file_path = os.path.normpath(os.path.join(root, file))

            try:
                analysis  = lizard.analyze_file(file_path)
                functions = analysis.function_list

                if functions:
                    avg_complexity      = sum(f.cyclomatic_complexity for f in functions) / len(functions)
                    max_complexity      = max(f.cyclomatic_complexity for f in functions)
                    avg_params          = sum(f.parameter_count for f in functions) / len(functions)
                    max_function_length = max(f.length for f in functions)
                else:
                    avg_complexity      = 0
                    max_complexity      = 0
                    avg_params          = 0
                    max_function_length = 0

                result = {
                    "file":                file_path,
                    "loc":                 analysis.nloc,
                    "avg_complexity":      avg_complexity,
                    "max_complexity":      max_complexity,
                    "functions":           len(functions),
                    "avg_params":          avg_params,
                    "max_function_length": max_function_length,
                }

                results.append(result)

            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")

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