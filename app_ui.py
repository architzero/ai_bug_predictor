import os
import joblib
import pandas as pd
from flask import Flask, jsonify, render_template, request

# Import existing domain logic
from static_analysis.analyzer import analyze_repository, get_top_functions
from git_mining.git_miner import mine_git_data
from feature_engineering.feature_builder import build_features, filter_correlated_features
from feature_engineering.labeler import create_labels
from model.predict import predict
from explainability.explainer import _compute_shap, _get_features, NON_FEATURE_COLS
from model.commit_predictor import predict_commit_risk
from config import REPOS, SZZ_CACHE_DIR, BASE_DIR

MODEL_PATH = os.path.join(BASE_DIR, "model", "bug_predictor.pkl")

GIT_FEATURES_TO_NORMALIZE = [
    'commits', 'lines_added', 'lines_deleted',
    'commits_2w', 'commits_1m', 'commits_3m',
    'recent_churn_ratio', 'recent_activity_score',
    'instability_score', 'avg_commit_size',
    'max_commit_size', 'max_commit_ratio',
    'max_added', 'author_count',
    'minor_contributor_ratio'
]

app = Flask(__name__)

# Basic in-memory store so API endpoints are instant
app_state = {
    "df": None,
    "model": None,
    "global_shap": None,
    "global_shap_X": None,
    "metrics": {
        "files_analyzed": 0,
        "buggy_count": 0,
        "avg_risk": 0,
        "defect_at_20": 0.0
    }
}

def init_app_state():
    """Build dataset from caches and load model."""
    print("Loading AI Bug Predictor backend...")
    
    # Load model
    if not os.path.exists(MODEL_PATH):
        print(f"Error: Model not found at {MODEL_PATH}. Run 'python main.py' first.")
        return
    model_data = joblib.load(MODEL_PATH)
    app_state["model"] = model_data
    
    # Re-build dataset using cached outputs (should be very fast if cache exists)
    all_data = []
    for repo_path in REPOS:
        print(f"Loading data for {os.path.basename(repo_path)}")
        static_results = analyze_repository(repo_path)
        git_results    = mine_git_data(repo_path)
        
        df_repo = build_features(static_results, git_results)
        df_repo = create_labels(df_repo, repo_path, cache_dir=SZZ_CACHE_DIR)
        df_repo["repo"] = repo_path
        all_data.append(df_repo)
        
    df = pd.concat(all_data, ignore_index=True)
    
    # Normalize features logically
    from sklearn.preprocessing import StandardScaler
    normalized_dfs = []
    for repo_df in all_data:
        df_copy = repo_df.copy()
        cols_present = [c for c in GIT_FEATURES_TO_NORMALIZE if c in df_copy.columns]
        if cols_present:
            scaler = StandardScaler()
            df_copy[cols_present] = scaler.fit_transform(df_copy[cols_present])
        normalized_dfs.append(df_copy)
    
    df = pd.concat(normalized_dfs, ignore_index=True)
    df = filter_correlated_features(df)
    
    # Attach Risk probabilities using the pipeline
    df = predict(model_data, df)
    
    # Sort for best viewing
    df = df.sort_values("risk", ascending=False).reset_index(drop=True)
    app_state["df"] = df
    
    # Pre-compute Global SHAP for fast serving
    X = _get_features(df)
    features = model_data.get("features", getattr(model_data, "feature_names_in_", None)) if isinstance(model_data, dict) else getattr(model_data, "feature_names_in_", None)
    if features is not None:
        missing = [c for c in features if c not in X.columns]
        for c in missing:
            X[c] = 0
        X = X[features]
        
    raw_model = model_data["model"] if isinstance(model_data, dict) and "model" in model_data else model_data
    shap_vals, expected_val, X_disp = _compute_shap(raw_model, X)
    app_state["global_shap"] = shap_vals
    app_state["global_shap_X"] = X_disp
    
    # Compute Metrics
    buggy = df["buggy"].sum()
    risky = df["risky"].sum()
    
    # Defect @ 20%
    top_20_count = max(1, int(len(df) * 0.20))
    top_20_df = df.head(top_20_count)
    captured_bugs = top_20_df["buggy"].sum()
    defect_at_20 = (captured_bugs / buggy * 100) if buggy > 0 else 0
    
    app_state["metrics"] = {
        "files_analyzed": len(df),
        "buggy_count": int(buggy),
        "avg_risk": round(df["risk"].mean(), 3),
        "defect_at_20": round(defect_at_20, 1),
        "expected_value": float(expected_val) if not isinstance(expected_val, (list, tuple)) else float(expected_val[0])
    }
    
    print("Backend initialized successfully!")

# Initialize state on runtime
init_app_state()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/overview")
def api_overview():
    return jsonify({
        "metrics": app_state["metrics"],
        "histogram": _generate_histogram()
    })

def _generate_histogram():
    df = app_state["df"]
    if df is None: return []
    # 20 bins from 0.0 to 1.0
    bins = [i/20 for i in range(21)]
    hist = pd.cut(df["risk"], bins=bins).value_counts().sort_index()
    return [{"bin": f"{b.left:.2f}", "count": int(c)} for b, c in hist.items()]

@app.route("/api/files")
def api_files():
    df = app_state["df"]
    if df is None: return jsonify([])
    
    limit = min(500, len(df)) # limit payload size for performance
    files_list = []
    
    for _, row in df.head(limit).iterrows():
        repo_name = os.path.basename(str(row["repo"]))
        rel_path = os.path.relpath(str(row["file"]), str(row["repo"])).replace("\\", "/")
        
        files_list.append({
            "id": str(row["file"]),
            "repo": repo_name,
            "filename": rel_path,
            "risk": round(row.get("risk", 0.0), 3),
            "buggy": int(row.get("buggy", 0)),
            "complexity": int(row.get("avg_complexity", 0)),
            "coupling": round(row.get("coupling_risk", 0.0), 2) if "coupling_risk" in row else 0.0,
            "temporal": round(row.get("temporal_bug_risk", 0.0), 2) if "temporal_bug_risk" in row else 0.0,
            "commits_1m": int(row.get("commits_1m", 0)) if "commits_1m" in row else 0,
        })
        
    return jsonify(files_list)

@app.route("/api/file", methods=["GET"])
def api_file_detail():
    file_id = request.args.get("id")
    df = app_state["df"]
    if df is None or file_id not in df["file"].values:
        return jsonify({"error": "File not found"}), 404
        
    idx = df.index[df['file'] == file_id].tolist()[0]
    row = df.loc[idx]
    
    # Get Function details
    top_funcs = []
    try:
        funcs = get_top_functions(file_id, top_n=5)
        top_funcs = [{"name": f["name"], "cx": f["complexity"], "len": f["length"]} for f in funcs]
    except Exception:
        pass
        
    # Get SHAP explanations
    shap_vals = app_state["global_shap"]
    X_disp = app_state["global_shap_X"]
    
    if shap_vals is not None and len(shap_vals) > idx:
        sv = shap_vals[idx]
        if len(sv.shape) > 1 and sv.shape[1] > 1: # if 2D array
            sv = sv[:, 1]
            
        contribs = pd.Series(sv, index=X_disp.columns).sort_values(ascending=False)
        top_positive = contribs[contribs > 0].head(5).to_dict()
        top_negative = contribs[contribs < 0].tail(5).to_dict()
        
        shap_data = {
            "positive": [{"feature": k, "value": round(v, 4)} for k, v in top_positive.items()],
            "negative": [{"feature": k, "value": round(v, 4)} for k, v in top_negative.items()]
        }
    else:
        shap_data = {"positive": [], "negative": []}
        
    return jsonify({
        "filepath": os.path.relpath(file_id, row["repo"]).replace("\\", "/"),
        "risk": round(row["risk"], 3),
        "top_funcs": top_funcs,
        "shap": shap_data
    })

@app.route("/api/scan_repo", methods=["POST"])
def api_scan_repo():
    data = request.json
    repo_path = data.get("path", "").strip()
    
    if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
        return jsonify({"error": f"Invalid directory path: {repo_path}"}), 400
        
    try:
        print(f"Scanning target repository: {repo_path}")
        static_results = analyze_repository(repo_path)
        git_results    = mine_git_data(repo_path)
        
        df_repo = build_features(static_results, git_results)
        df_repo["repo"] = repo_path
        
        if len(df_repo) == 0:
            return jsonify({"error": "No valid source files or git history found in the provided directory."}), 400
            
        # Normalize target with base scalers if applicable
        from sklearn.preprocessing import StandardScaler
        cols_present = [c for c in GIT_FEATURES_TO_NORMALIZE if c in df_repo.columns]
        if cols_present:
            scaler = StandardScaler()
            df_repo[cols_present] = scaler.fit_transform(df_repo[cols_present])
            
        model_data = app_state["model"]
        df_repo = predict(model_data, df_repo)
        
        if "buggy" not in df_repo.columns:
            df_repo["buggy"] = 0
            
        df_repo = df_repo.sort_values("risk", ascending=False).reset_index(drop=True)
            
        # Recompute SHAP for internal state mapping
        X = _get_features(df_repo)
        features = model_data.get("features", getattr(model_data, "feature_names_in_", None)) if isinstance(model_data, dict) else getattr(model_data, "feature_names_in_", None)
        if features is not None:
            missing = [c for c in features if c not in X.columns]
            for c in missing:
                X[c] = 0
            X = X[features]
            
        raw_model = model_data["model"] if isinstance(model_data, dict) and "model" in model_data else model_data
        shap_vals, expected_val, X_disp = _compute_shap(raw_model, X)
        
        # Override the state
        app_state["df"] = df_repo
        app_state["global_shap"] = shap_vals
        app_state["global_shap_X"] = X_disp
        
        # Recalculate metrics
        buggy = int(df_repo.get("buggy", pd.Series([0]*len(df_repo))).sum())
        top_20_count = max(1, int(len(df_repo) * 0.20))
        top_20_df = df_repo.head(top_20_count)
        captured_bugs = int(top_20_df.get("buggy", pd.Series([0]*len(top_20_df))).sum())
        defect_at_20 = (captured_bugs / buggy * 100) if buggy > 0 else 0
        
        app_state["metrics"] = {
            "files_analyzed": len(df_repo),
            "buggy_count": buggy,
            "avg_risk": round(float(df_repo.get("risk", pd.Series([0])).mean()), 3),
            "defect_at_20": round(defect_at_20, 1),
            "expected_value": float(expected_val) if not isinstance(expected_val, (list, tuple)) else float(expected_val[0])
        }
        
        print("Success! UI arrays updated.")
        return jsonify({"success": True})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/predict_commit", methods=["POST"])
def api_predict_commit():
    data = request.json
    filenames = data.get("files", [])
    if not filenames:
        return jsonify({"risk": 0.0, "main_driver": "No files provided"})
        
    df = app_state["df"]
    # We need to map short filenames to absolute paths
    # Because input might be "requests/sessions.py" or just "sessions.py"
    changed_abs_paths = []
    for fn in filenames:
        matched = False
        for abs_p in df["file"].values:
            if fn.lower() in abs_p.lower():
                changed_abs_paths.append(abs_p)
                matched = True
                break
                
    if not changed_abs_paths:
        return jsonify({"risk": 0.0, "main_driver": "Files not found in analyzer dataset"})
        
    risk_score, risky_df = predict_commit_risk(df, changed_abs_paths)
    
    driver = "None"
    if not risky_df.empty:
        top = risky_df.sort_values("risk", ascending=False).iloc[0]
        driver = f"{os.path.basename(top['file'])} ({top['risk']:.1%})"
        
    return jsonify({
        "risk": round(risk_score, 2),
        "main_driver": driver,
        "matched_files": [os.path.basename(f) for f in changed_abs_paths]
    })

@app.route("/api/importance", methods=["GET"])
def api_importance():
    shap_vals = app_state["global_shap"]
    X_disp = app_state["global_shap_X"]
    
    if shap_vals is None: return jsonify([])
    
    # Calculate mean absolute SHAP for global importance
    import numpy as np
    mean_abs_shap = np.abs(shap_vals).mean(axis=0)
    
    importance = pd.Series(mean_abs_shap, index=X_disp.columns).sort_values(ascending=False).head(10)
    return jsonify([{"feature": k, "value": round(float(v), 4)} for k, v in importance.items()])


if __name__ == "__main__":
    app.run(port=5000, debug=True, use_reloader=False)
