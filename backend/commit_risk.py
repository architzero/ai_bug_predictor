from backend.szz import is_test_file, is_generated_file
import pandas as pd
import numpy as np
import os

def predict_commit_risk(df, changed_files):
    """
    CRITICAL FIX: Compute realistic and meaningful commit-level risk scores.
    
    Key improvements:
    - Do NOT use simple averaging
    - Use max or weighted aggregation (hybrid approach)
    - Ensure high-risk files strongly influence commit risk
    - Weight files based on importance (LOC, churn, complexity, coupling)
    - Show top contributing files with explanations
    - Validate commit risk correlates with highest-risk file
    
    Returns (commit_risk, top_risky_files_df).
    """
    try:
        # Validate inputs
        if df is None or df.empty:
            raise ValueError("Input DataFrame is empty")
        if not changed_files:
            return 0.0, df.head(0)
        if 'risk' not in df.columns:
            raise ValueError("Input DataFrame missing 'risk' column")
        
        # Import the improved implementation
        from backend.commit_risk_fixes import improved_predict_commit_risk
        
        # Use improved prediction with hybrid aggregation
        results = improved_predict_commit_risk(df, changed_files, aggregation_method='hybrid', top_k=5)
        
        # Convert top files back to DataFrame for backward compatibility
        if results['top_files']:
            top_file_paths = [f['file'] for f in results['top_files']]
            top_files_df = df[df["file"].isin(top_file_paths)].copy()
            
            # Sort by risk descending to maintain order
            top_files_df = top_files_df.sort_values("risk", ascending=False)
        else:
            top_files_df = df.head(0)
        
        return results['commit_risk'], top_files_df
        
    except Exception as e:
        print(f"Error in predict_commit_risk: {e}")
        # Return safe defaults
        return 0.0, df.head(0)
