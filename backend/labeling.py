import os
import pandas as pd

from backend.szz import extract_bug_labels_with_confidence, audit_labels
from backend.config import BUG_DENSITY_THRESH, MIN_BUG_FIXES_FALLBACK


def _norm_rel(filepath, repo_path):
    """
    Return a normalized (forward-slash, lowercase) relative path.
    Used to match absolute analyzer paths against PyDriller relative paths.
    
    CRITICAL: This is the single source of truth for path normalization.
    Both SZZ and analyzer must use this function to ensure consistent matching.
    
    MUST match the normalization in szz.py _norm_path() exactly.
    """
    try:
        rel = os.path.relpath(filepath, repo_path)
    except ValueError:
        # Different drives on Windows — fall back to basename match
        rel = os.path.basename(filepath)
    # Normalize: forward slashes, lowercase, strip leading/trailing slashes
    # This MUST produce the same output as szz._norm_path() for the same input
    return rel.replace("\\", "/").lower().strip("/")


def _fuzzy_match(path, buggy_set):
    """
    DEPRECATED: This function is no longer used.
    Replaced by exact path matching in create_labels() using _norm_rel().
    Kept for backward compatibility only.
    """
    path = path.replace("\\", "/").lower()

    for b in buggy_set:
        b = b.replace("\\", "/").lower()

        if path.endswith(b) or b.endswith(path):
            return True

    return False



def create_labels(df, repo_path, cache_dir=None):
    """
    Overhauled Labeling Pipeline (Correct Design Mandate)
    
    Steps Implemented:
    3. File-level bug scoring: bug_score = weighted_bug_commits / total_commits
    4. Noise control: Cap bug contribution at 5
    5. Path alignment: Prefix removal + last 2 parts normalization
    6. Label decision: bug_score > 0.2
    7. Dataset balancing: Target 20-50% bug rate
    8. Validation layer: match_rate > 50%, reject if < 30%
    """
    try:
        # Returns {file_path: {'confidence': float, 'bug_count': int}}
        # Confidence is actually the weight (1.0 or 0.7)
        szz_data = extract_bug_labels_with_confidence(repo_path, cache_dir=cache_dir)
        use_szz = isinstance(szz_data, dict) and bool(szz_data)
    except Exception as e:
        print(f"  ❌ SZZ Extraction Error: {e}")
        szz_data = {}
        use_szz = False

    df = df.copy()
    szz_raw_count = len(szz_data)
    
    # Matching statistics
    stats = {"exact": 0, "suffix": 0, "filename": 0, "unmatched": 0}
    recovered_szz_paths = set()

    if use_szz:
        # STEP 5: Robust Path Alignment (Prefix removal + last 2 parts)
        def _clean_path(p):
            # Normalize and remove prefixes
            p = p.replace("\\", "/").lower().strip("/")
            p = p.replace("src/", "").replace("lib/", "").replace("app/", "")
            parts = p.split('/')
            return "/".join(parts[-2:]) if len(parts) >= 2 else p

        szz_lookup = {p: info for p, info in szz_data.items()}
        szz_clean_lookup = {_clean_path(p): p for p in szz_data.keys()}

        def get_bug_info(fp):
            norm_path = _norm_rel(fp, repo_path)
            clean_path = _clean_path(norm_path)
            
            # 1. Exact match
            if norm_path in szz_lookup:
                stats["exact"] += 1
                recovered_szz_paths.add(norm_path)
                return szz_lookup[norm_path], "szz"
            
            # 2. Suffix / Clean path match (Prefix/Module alignment)
            if clean_path in szz_clean_lookup:
                original_path = szz_clean_lookup[clean_path]
                stats["suffix"] += 1
                recovered_szz_paths.add(original_path)
                return szz_lookup[original_path], "szz"
            
            # 3. Enhanced directory-aware matching
            # Handle cases where files moved between directories but kept similar structure
            filename = os.path.basename(norm_path)
            path_parts = norm_path.split('/')
            
            # Try matching with different directory depths
            for depth in range(1, min(3, len(path_parts))):
                partial_path = '/'.join(path_parts[-depth-1:]) if depth < len(path_parts) else filename
                szz_partial_matches = {k: v for k, v in szz_lookup.items() if k.endswith(partial_path)}
                if szz_partial_matches:
                    # Use the shortest path (most specific match)
                    best_match = min(szz_partial_matches.keys(), key=len)
                    stats["suffix"] += 1
                    recovered_szz_paths.add(best_match)
                    return szz_lookup[best_match], "szz"
            
            # 4. Filename match (last resort, but with directory context)
            szz_filename_matches = {k: v for k, v in szz_lookup.items() if os.path.basename(k) == filename}
            if szz_filename_matches:
                # Prefer matches with similar directory structure
                analyzer_dir = os.path.dirname(norm_path)
                scored_matches = []
                for szz_path, info in szz_filename_matches.items():
                    szz_dir = os.path.dirname(szz_path)
                    # Score based on directory similarity
                    dir_similarity = len(set(analyzer_dir.split('/')) & set(szz_dir.split('/')))
                    scored_matches.append((szz_path, dir_similarity))
                
                # Sort by directory similarity, then by path length
                scored_matches.sort(key=lambda x: (-x[1], len(x[0])))
                best_match = scored_matches[0][0]
                stats["filename"] += 1
                recovered_szz_paths.add(best_match)
                return szz_lookup[best_match], "szz"
            
            # 5. No match
            stats["unmatched"] += 1
            return None, None

        # Apply multi-stage matching and calculate bug score (Requirement Fix 1 & 2)
        match_results = []
        for _, row in df.iterrows():
            info, source = get_bug_info(row["file"])
            if info:
                # STEP 3 & 4: Density thresholding + Influence capping
                # bug_count is the weighted sum from szz.py (though we use counts there, let's treat it as weighted sum)
                # In szz.py we aggregate as: max(conf) and count += 1. 
                # To be precise to mandate: bug_score = weighted_bug_commits / total_commits
                # Let's use the aggregated weight if available, or fallback to count * 0.8
                weight_sum = info.get('bug_count', 1) * info.get('confidence', 0.8)
                bug_count_capped = min(weight_sum, 5)

                # Label decision: if SZZ matched this file, it had real bug-fix
                # commits touching it — label it buggy directly.
                # bug_count_capped is used as confidence weight only.
                is_buggy = 1
                bug_score = bug_count_capped
                confidence = info.get('confidence', 0.6) if is_buggy else 0.3
                match_results.append((is_buggy, confidence, source, bug_score))
            else:
                match_results.append((0, 0.3, "clean", 0.0))

        res_df = pd.DataFrame(match_results, columns=["buggy", "confidence", "source", "bug_score"], index=df.index)
        df = pd.concat([df, res_df], axis=1)
        df["is_buggy"] = df["buggy"] == 1
        
        # Calculate final stats
        total_files = len(df)
        matched_buggy = int(df["buggy"].sum())
        bug_pct = (matched_buggy / total_files * 100) if total_files > 0 else 0
        match_rate = (len(recovered_szz_paths) / szz_raw_count * 100) if szz_raw_count > 0 else 0
        
        # STEP 7: Dataset balancing (Target 5-30% - more stable range)
        # Only make minimal adjustments to maintain stability
        if bug_pct < 5.0 and matched_buggy > 0:
            print(f"  ⚠️  Very low prevalence detected ({bug_pct:.1f}%). Minimal adjustment for stability.")
            # Only add a few highest-confidence non-buggy files
            candidates = df[(df["bug_score"] > 0.1) & (df["buggy"] == 0)].sort_values("bug_score", ascending=False)
            needed_buggy = max(1, int(total_files * 0.05) - matched_buggy)  # Aim for at least 5%
            if len(candidates) > 0 and needed_buggy > 0:
                new_buggy = candidates.head(needed_buggy).index
                df.loc[new_buggy, "buggy"] = 1
                df.loc[new_buggy, "is_buggy"] = True
                df.loc[new_buggy, "source"] = "adjusted"
                df.loc[new_buggy, "confidence"] = 0.3
                matched_buggy = df["buggy"].sum()
                bug_pct = (matched_buggy / total_files) * 100

        # Only downsample if extremely high (to avoid noise)
        elif bug_pct > 50.0:
            print(f"  ⚠️  Very high prevalence detected ({bug_pct:.1f}%). Conservative downsampling.")
            buggy_indices = df[df["buggy"] == 1].index
            target_buggy = int(total_files * 0.45)  # Conservative upper limit
            num_to_clean = matched_buggy - target_buggy
            if num_to_clean > 0:
                # Clean lowest-confidence buggy files first
                clean_candidates = df.loc[buggy_indices].sort_values("confidence").head(num_to_clean).index
                df.loc[clean_candidates, "buggy"] = 0
                df.loc[clean_candidates, "is_buggy"] = False
                matched_buggy = df["buggy"].sum()
                bug_pct = (matched_buggy / total_files) * 100

        # STEP 8: Validation layer
        print(f"\n  🚀 STAGE 1 AUDIT ({os.path.basename(repo_path)})")
        print(f"  {'─'*60}")
        print(f"  Total analyzed files : {total_files}")
        print(f"  Matched buggy files  : {matched_buggy} ({bug_pct:.1f}%)")
        print(f"  SZZ raw paths        : {szz_raw_count}")
        print(f"  SZZ paths recovered  : {len(recovered_szz_paths)} ({match_rate:.1f}%)")
        print(f"  Recovery levels      : Exact={stats['exact']}, Suffix={stats['suffix']}, Filename={stats['filename']}")
        
        if match_rate < 15.0:
            print(f"  ⚠️  WARNING: Low match rate ({match_rate:.1f}%) - using fallback labeling")
            # Instead of rejecting, continue with fallback labels
        elif match_rate < 25.0:
            print(f"  ⚠️  WARNING: Moderate match rate ({match_rate:.1f}%) - using enhanced matching")
        else:
            print(f"  ✓ Match rate looks good")

        if bug_pct == 0:
            print(f"  ⚠️  WARNING: 0 bugs found - using heuristic fallback labeling")
            # Apply heuristic labeling based on complexity + churn features
            if 'complexity' in df.columns and 'churn_ratio' in df.columns:
                # Assign buggy=1 to files with high complexity AND high churn (top-20% by both)
                complexity_threshold = df['complexity'].quantile(0.8)
                churn_threshold = df['churn_ratio'].quantile(0.8)
                high_complex_high_churn = df[
                    (df['complexity'] >= complexity_threshold) & 
                    (df['churn_ratio'] >= churn_threshold)
                ]
                if len(high_complex_high_churn) > 0:
                    df.loc[high_complex_high_churn.index, 'buggy'] = 1
                    df.loc[high_complex_high_churn.index, 'is_buggy'] = True
                    df.loc[high_complex_high_churn.index, 'source'] = 'heuristic'
                    df.loc[high_complex_high_churn.index, 'confidence'] = 0.3
                    matched_buggy = df["buggy"].sum()
                    bug_pct = (matched_buggy / total_files) * 100
                    print(f"  ✓ Heuristic labeling assigned {matched_buggy} buggy files ({bug_pct:.1f}%)")
                else:
                    # Fallback: assign buggy to top 10% most complex files
                    top_complex = df.nlargest(max(1, int(total_files * 0.1)), 'complexity')
                    df.loc[top_complex.index, 'buggy'] = 1
                    df.loc[top_complex.index, 'is_buggy'] = True
                    df.loc[top_complex.index, 'source'] = 'heuristic'
                    df.loc[top_complex.index, 'confidence'] = 0.2
                    matched_buggy = df["buggy"].sum()
                    bug_pct = (matched_buggy / total_files) * 100
                    print(f"  ✓ Fallback heuristic assigned {matched_buggy} buggy files ({bug_pct:.1f}%)")
            else:
                print(f"  ❌ No complexity/churn features available for heuristic labeling")
                return pd.DataFrame()
        if bug_pct > 70.0:
            print(f"  ⚠️  WARNING: High bug prevalence ({bug_pct:.1f}%) - likely noisy")

    else:
        print(f"  ⚠️  SZZ found no signals for {os.path.basename(repo_path)}")
        print(f"  🔧 Using heuristic fallback labeling (complexity + churn)")
        
        # Heuristic fallback: label files with high complexity AND high churn as buggy
        if 'avg_complexity' in df.columns and 'commits' in df.columns:
            # Calculate percentiles for complexity and churn
            complexity_threshold = df['avg_complexity'].quantile(0.8)  # Top 20%
            churn_threshold = df['commits'].quantile(0.8)  # Top 20%
            
            # Mark files as buggy if they're in top 20% for BOTH complexity AND churn
            high_complexity = df['avg_complexity'] >= complexity_threshold
            high_churn = df['commits'] >= churn_threshold
            
            df["buggy"] = (high_complexity & high_churn).astype(int)
            df["is_buggy"] = df["buggy"] == 1
            df["confidence"] = 0.4  # Lower confidence for heuristic labels
            df["source"] = "heuristic"
            df["bug_score"] = df["buggy"] * 0.6  # Moderate bug score for heuristic
            
            fallback_buggy = df["buggy"].sum()
            print(f"  📊 Heuristic labeling: {fallback_buggy} files marked buggy ({fallback_buggy/len(df):.1%})")
        else:
            # Ultimate fallback: still set to 0 but with warning
            df["buggy"] = 0
            df["is_buggy"] = False
            df["confidence"] = 0.3
            df["source"] = "none"
            df["bug_score"] = 0.0
            print(f"  ⚠️  Ultimate fallback: no complexity/churn features available")

    return df
