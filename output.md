
(venv) C:\Users\archi\project\ai-bug-predictor>python main.py

════════════════════════════════════════════════════════════════════════
  STAGE 0  ·  FILE FILTERING AUDIT
════════════════════════════════════════════════════════════════════════
  Repo                 Total    Included   Excluded   Drop %   Key Excluded Dirs
  ------------------------------------------------------------------------------------------
  requests             36       19         17           47.2%  tests
  flask                83       24         59           71.1%  tests
  fastapi              1125     48         1077         95.7%  app_testing, tests, async_tests
  httpx                60       22         38           63.3%  tests
  celery               416      207        209          50.2%  testing, tests
  sqlalchemy           668      229        439          65.7%  testing, build, test
  express              141      7          134          95.0%  test
  axios                192      70         122          63.5%  tests
  guava                3223     730        2493         77.4%  guava-testlib, guava-tests, test-super

  ✓ File filtering audit complete
  ✓ Verify excluded dirs are test/docs/generated (not src/core/lib)

════════════════════════════════════════════════════════════════════════
  STAGE 1  ·  DATA COLLECTION (Parallel Processing)
════════════════════════════════════════════════════════════════════════
  Using 4 parallel workers for 9 repositories...
  Loaded mining cache for requests
  SZZ: loaded from cache (70 buggy files)
  Loaded mining cache for httpx

  Label Audit:
  SZZ raw paths     : 70
  Files in analysis : 17
  Matched buggy     : 4 (23.5% of analyzed files)
  SZZ match rate    : 5.7% of SZZ paths exist in analyzer
  Clean files       : 13 (76.5%)
  ✓ Label prevalence 23.5% looks healthy
  ✓  requests                 17 files  |     4 labelled buggy
  SZZ: loaded from cache (78 buggy files)

  Label Audit:
  SZZ raw paths     : 78
  Files in analysis : 9
  Matched buggy     : 6 (66.7% of analyzed files)
  SZZ match rate    : 7.7% of SZZ paths exist in analyzer
  Clean files       : 3 (33.3%)
  ⚠ Many buggy files — SZZ filter may be too loose
  ✓  httpx                     9 files  |     6 labelled buggy
  Loaded mining cache for flask
  SZZ: loaded from cache (92 buggy files)

  Label Audit:
  SZZ raw paths     : 92
  Files in analysis : 23
  Matched buggy     : 20 (87.0% of analyzed files)
  SZZ match rate    : 21.7% of SZZ paths exist in analyzer
  Clean files       : 3 (13.0%)
  ⚠ Many buggy files — SZZ filter may be too loose
  ✓  flask                    23 files  |    20 labelled buggy
  Loaded mining cache for fastapi
  Loaded mining cache for express
  SZZ: loaded from cache (33 buggy files)

  Label Audit:
  SZZ raw paths     : 33
  Files in analysis : 47
  Matched buggy     : 23 (48.9% of analyzed files)
  SZZ match rate    : 69.7% of SZZ paths exist in analyzer
  Clean files       : 24 (51.1%)
  ✓ Label prevalence 48.9% looks healthy
  SZZ: loaded from cache (69 buggy files)
  ✓  fastapi                  47 files  |    23 labelled buggy

  Label Audit:
  SZZ raw paths     : 69
  Files in analysis : 7
  Matched buggy     : 6 (85.7% of analyzed files)
  SZZ match rate    : 8.7% of SZZ paths exist in analyzer
  Clean files       : 1 (14.3%)
  ⚠ Many buggy files — SZZ filter may be too loose
  ✓  express                   7 files  |     6 labelled buggy
  Loaded mining cache for axios
  SZZ: loaded from cache (87 buggy files)

  Label Audit:
  SZZ raw paths     : 87
  Files in analysis : 70
  Matched buggy     : 48 (68.6% of analyzed files)
  SZZ match rate    : 55.2% of SZZ paths exist in analyzer
  Clean files       : 22 (31.4%)
  ⚠ Many buggy files — SZZ filter may be too loose
  ✓  axios                    70 files  |    48 labelled buggy
  Loaded mining cache for celery
  SZZ: loaded from cache (320 buggy files)

  Label Audit:
  SZZ raw paths     : 320
  Files in analysis : 214
  Matched buggy     : 127 (59.3% of analyzed files)
  SZZ match rate    : 39.7% of SZZ paths exist in analyzer
  Clean files       : 87 (40.7%)
  ✓ Label prevalence 59.3% looks healthy
  ✓  celery                  214 files  |   127 labelled buggy
  Loaded mining cache for sqlalchemy
  SZZ: loaded from cache (269 buggy files)

  Label Audit:
  SZZ raw paths     : 269
  Files in analysis : 236
  Matched buggy     : 171 (72.5% of analyzed files)
  SZZ match rate    : 63.6% of SZZ paths exist in analyzer
  Clean files       : 65 (27.5%)
  ⚠ Many buggy files — SZZ filter may be too loose
  ✓  sqlalchemy              236 files  |   171 labelled buggy
  Loaded mining cache for guava
  SZZ: loaded from cache (663 buggy files)

  Label Audit:
  SZZ raw paths     : 663
  Files in analysis : 1031
  Matched buggy     : 411 (39.9% of analyzed files)
  SZZ match rate    : 62.0% of SZZ paths exist in analyzer
  Clean files       : 620 (60.1%)
  ✓ Label prevalence 39.9% looks healthy
  ✓  guava                  1031 files  |   411 labelled buggy

════════════════════════════════════════════════════════════════════════
  STAGE 2  ·  FEATURE PIPELINE
════════════════════════════════════════════════════════════════════════
  Global StandardScaler applied  →  14 git features  |  1654 total files

  Bug type classifier ...
  Bug type classifier: loaded from cache

  Dataset summary  →  1654 files  |  816 buggy
  Bug type distribution (buggy files only):
    performance            479  ( 58.7%)  ███████████████████████
    security               166  ( 20.3%)  ████████
    exception              159  ( 19.5%)  ███████
    null_pointer             7  (  0.9%)  █
    memory_leak              4  (  0.5%)  █
    race_condition           1  (  0.1%)  █

  ⚠  29 filename(s) shared across repos (verify no label leak):
     __init__.py                         → {'httpx', 'fastapi', 'flask', 'sqlalchemy', 'requests', 'celery'}
     api.py                              → {'sqlalchemy', 'requests'}
     app.py                              → {'flask', 'celery'}
     base.py                             → {'httpx', 'fastapi', 'sqlalchemy', 'celery'}
     cli.py                              → {'fastapi', 'flask'}
     collections.py                      → {'sqlalchemy', 'celery'}

════════════════════════════════════════════════════════════════════════
  STAGE 3  ·  CROSS-PROJECT MODEL TRAINING
════════════════════════════════════════════════════════════════════════

Selecting global feature set (RFE on full data)...
  Temporal validation: using 1654 files sorted by last change date
  RFE: kept 26, dropped 16 (threshold='median')
    Dropped: ['functions', 'language_id', 'has_test_file', 'complexity_density', 'complexity_per_function', 'commits_2w', 'commits_1m', 'commits_3m', 'recent_churn_ratio', 'recent_activity_score', 'low_history_flag', 'minor_contributor_ratio', 'file_age_bucket', 'days_since_last_change', 'commit_burst_score', 'burst_ratio']
    Rescued sparse features from RFE: ['coupled_recent_missing', 'coupling_risk', 'burst_risk', 'temporal_bug_risk', 'recent_bug_flag']
  Global feature set (26 cols): ['loc', 'avg_complexity', 'max_complexity', 'avg_params', 'max_function_length', 'complexity_vs_baseline', 'loc_per_function', 'commits', 'lines_added', 'lines_deleted', 'max_added', 'author_count', 'ownership', 'instability_score', 'avg_commit_size', 'max_commit_ratio', 'recency_ratio', 'max_coupling_strength', 'coupled_file_count', 'bug_recency_score', 'temporal_bug_memory', 'coupled_recent_missing', 'coupling_risk', 'burst_risk', 'temporal_bug_risk', 'recent_bug_flag']

============================================================
TEST PROJECT : C:\Users\archi\project\ai-bug-predictor\dataset\requests
TRAIN        : ['C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\httpx', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\flask', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\fastapi', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\express', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\axios', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\celery', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\sqlalchemy', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\guava']
  Temporal validation: using 1637 files sorted by last change date
  Temporal validation: using 17 files sorted by last change date
  Data  train=1380 (buggy=690)  test=17 (buggy=4)
    LR (baseline)                   P=0.400  R=1.000  F1=0.5714  ROC=0.8846  PR-AUC=0.7986
  Best RF params : {'n_estimators': 200, 'min_samples_split': 20, 'min_samples_leaf': 4, 'max_samples': 0.8, 'max_depth': 8}
    RF                              P=0.429  R=0.750  F1=0.5455  ROC=0.9038  PR-AUC=0.8611
  Best XGB params: {'subsample': 0.85, 'n_estimators': 300, 'min_child_weight': 1, 'max_depth': 5, 'learning_rate': 0.05, 'gamma': 0.05, 'colsample_bytree': 0.75}
    XGB                             P=0.400  R=1.000  F1=0.5714  ROC=0.9231  PR-AUC=0.8750
  → Best: LR  F1=0.5714

============================================================
TEST PROJECT : C:\Users\archi\project\ai-bug-predictor\dataset\httpx
TRAIN        : ['C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\requests', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\flask', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\fastapi', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\express', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\axios', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\celery', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\sqlalchemy', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\guava']
  Temporal validation: using 1645 files sorted by last change date
  Temporal validation: using 9 files sorted by last change date
  Data  train=1404 (buggy=702)  test=9 (buggy=6)
    LR (baseline)                   P=0.750  R=1.000  F1=0.8571  ROC=1.0000  PR-AUC=1.0000
  Best RF params : {'n_estimators': 200, 'min_samples_split': 5, 'min_samples_leaf': 2, 'max_samples': 0.8, 'max_depth': 8}
    RF                              P=1.000  R=1.000  F1=1.0000  ROC=1.0000  PR-AUC=1.0000
  Best XGB params: {'subsample': 0.8, 'n_estimators': 400, 'min_child_weight': 1, 'max_depth': 5, 'learning_rate': 0.03, 'gamma': 0.05, 'colsample_bytree': 0.85}
    XGB                             P=0.857  R=1.000  F1=0.9231  ROC=1.0000  PR-AUC=1.0000
  → Best: RF  F1=1.0000

============================================================
TEST PROJECT : C:\Users\archi\project\ai-bug-predictor\dataset\flask
TRAIN        : ['C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\requests', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\httpx', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\fastapi', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\express', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\axios', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\celery', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\sqlalchemy', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\guava']
  Temporal validation: using 1631 files sorted by last change date
  Temporal validation: using 23 files sorted by last change date
  Data  train=1408 (buggy=704)  test=23 (buggy=20)
    LR (baseline)                   P=0.947  R=0.900  F1=0.9231  ROC=0.8167  PR-AUC=0.9719
  Best RF params : {'n_estimators': 200, 'min_samples_split': 10, 'min_samples_leaf': 4, 'max_samples': 0.6, 'max_depth': 8}
    RF                              P=1.000  R=0.850  F1=0.9189  ROC=0.9500  PR-AUC=0.9935
  Best XGB params: {'subsample': 0.85, 'n_estimators': 200, 'min_child_weight': 3, 'max_depth': 5, 'learning_rate': 0.03, 'gamma': 0.1, 'colsample_bytree': 0.8}
    XGB                             P=1.000  R=0.900  F1=0.9474  ROC=0.9833  PR-AUC=0.9976
  → Best: XGB  F1=0.9474

============================================================
TEST PROJECT : C:\Users\archi\project\ai-bug-predictor\dataset\fastapi
TRAIN        : ['C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\requests', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\httpx', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\flask', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\express', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\axios', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\celery', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\sqlalchemy', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\guava']
  Temporal validation: using 1607 files sorted by last change date
  Temporal validation: using 47 files sorted by last change date
  Data  train=1370 (buggy=685)  test=47 (buggy=23)
    LR (baseline)                   P=1.000  R=0.870  F1=0.9302  ROC=0.9764  PR-AUC=0.9797
  Best RF params : {'n_estimators': 100, 'min_samples_split': 10, 'min_samples_leaf': 2, 'max_samples': 0.7, 'max_depth': 6}
    RF                              P=0.950  R=0.826  F1=0.8837  ROC=0.9565  PR-AUC=0.9599
  Best XGB params: {'subsample': 0.75, 'n_estimators': 200, 'min_child_weight': 3, 'max_depth': 7, 'learning_rate': 0.05, 'gamma': 0.1, 'colsample_bytree': 0.85}
    XGB                             P=0.952  R=0.870  F1=0.9091  ROC=0.9801  PR-AUC=0.9755
  → Best: LR  F1=0.9302

============================================================
TEST PROJECT : C:\Users\archi\project\ai-bug-predictor\dataset\express
TRAIN        : ['C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\requests', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\httpx', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\flask', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\fastapi', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\axios', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\celery', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\sqlalchemy', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\guava']
  Temporal validation: using 1647 files sorted by last change date
  Temporal validation: using 7 files sorted by last change date
  Data  train=1408 (buggy=704)  test=7 (buggy=6)
    LR (baseline)                   P=1.000  R=1.000  F1=1.0000  ROC=1.0000  PR-AUC=1.0000
  Best RF params : {'n_estimators': 300, 'min_samples_split': 20, 'min_samples_leaf': 4, 'max_samples': 0.8, 'max_depth': 6}
    RF                              P=1.000  R=1.000  F1=1.0000  ROC=1.0000  PR-AUC=1.0000
  Best XGB params: {'subsample': 0.75, 'n_estimators': 300, 'min_child_weight': 2, 'max_depth': 7, 'learning_rate': 0.05, 'gamma': 0.05, 'colsample_bytree': 0.75}
    XGB                             P=1.000  R=1.000  F1=1.0000  ROC=1.0000  PR-AUC=1.0000
  → Best: LR  F1=1.0000

============================================================
TEST PROJECT : C:\Users\archi\project\ai-bug-predictor\dataset\axios
TRAIN        : ['C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\requests', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\httpx', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\flask', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\fastapi', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\express', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\celery', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\sqlalchemy', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\guava']
  Temporal validation: using 1584 files sorted by last change date
  Temporal validation: using 70 files sorted by last change date
  Data  train=1386 (buggy=693)  test=70 (buggy=48)
    LR (baseline)                   P=0.919  R=0.708  F1=0.8000  ROC=0.8835  PR-AUC=0.9465
  Best RF params : {'n_estimators': 300, 'min_samples_split': 10, 'min_samples_leaf': 2, 'max_samples': 0.6, 'max_depth': 8}
    RF                              P=0.926  R=0.521  F1=0.6667  ROC=0.8835  PR-AUC=0.9444
  Best XGB params: {'subsample': 0.75, 'n_estimators': 200, 'min_child_weight': 3, 'max_depth': 7, 'learning_rate': 0.05, 'gamma': 0.1, 'colsample_bytree': 0.85}
    XGB                             P=0.935  R=0.604  F1=0.7342  ROC=0.8731  PR-AUC=0.9355
  → Best: LR  F1=0.8000

============================================================
TEST PROJECT : C:\Users\archi\project\ai-bug-predictor\dataset\celery
TRAIN        : ['C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\requests', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\httpx', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\flask', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\fastapi', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\express', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\axios', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\sqlalchemy', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\guava']
  Temporal validation: using 1440 files sorted by last change date
  Temporal validation: using 214 files sorted by last change date
  Data  train=1272 (buggy=636)  test=214 (buggy=127)
    LR (baseline)                   P=0.899  R=0.913  F1=0.9062  ROC=0.9329  PR-AUC=0.9478
  Best RF params : {'n_estimators': 300, 'min_samples_split': 5, 'min_samples_leaf': 2, 'max_samples': 0.8, 'max_depth': 6}
    RF                              P=0.948  R=0.858  F1=0.9008  ROC=0.9551  PR-AUC=0.9547
  Best XGB params: {'subsample': 0.8, 'n_estimators': 300, 'min_child_weight': 1, 'max_depth': 5, 'learning_rate': 0.05, 'gamma': 0.05, 'colsample_bytree': 0.75}
    XGB                             P=0.981  R=0.835  F1=0.9021  ROC=0.9583  PR-AUC=0.9548
  → Best: LR  F1=0.9062

============================================================
TEST PROJECT : C:\Users\archi\project\ai-bug-predictor\dataset\sqlalchemy
TRAIN        : ['C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\requests', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\httpx', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\flask', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\fastapi', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\express', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\axios', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\celery', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\guava']
  Temporal validation: using 1418 files sorted by last change date
  Temporal validation: using 236 files sorted by last change date
  Data  train=1338 (buggy=669)  test=236 (buggy=171)
    LR (baseline)                   P=0.849  R=0.918  F1=0.8820  ROC=0.8521  PR-AUC=0.9339
  Best RF params : {'n_estimators': 100, 'min_samples_split': 5, 'min_samples_leaf': 2, 'max_samples': 0.7, 'max_depth': 6}
    RF                              P=0.837  R=0.959  F1=0.8937  ROC=0.8213  PR-AUC=0.9115
  Best XGB params: {'subsample': 0.75, 'n_estimators': 400, 'min_child_weight': 2, 'max_depth': 5, 'learning_rate': 0.03, 'gamma': 0, 'colsample_bytree': 0.75}
    XGB                             P=0.832  R=0.982  F1=0.9008  ROC=0.7854  PR-AUC=0.8596
  → Best: XGB  F1=0.9008

============================================================
TEST PROJECT : C:\Users\archi\project\ai-bug-predictor\dataset\guava
TRAIN        : ['C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\requests', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\httpx', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\flask', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\fastapi', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\express', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\axios', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\celery', 'C:\\Users\\archi\\project\\ai-bug-predictor\\dataset\\sqlalchemy']
  Temporal validation: using 623 files sorted by last change date
  Temporal validation: using 1031 files sorted by last change date
  Data  train=752 (buggy=376)  test=1031 (buggy=411)
    LR (baseline)                   P=0.724  R=0.689  F1=0.7057  ROC=0.8316  PR-AUC=0.7561
  Best RF params : {'n_estimators': 100, 'min_samples_split': 10, 'min_samples_leaf': 4, 'max_samples': 0.6, 'max_depth': 6}
    RF                              P=0.556  R=0.876  F1=0.6799  ROC=0.8289  PR-AUC=0.7785
  Best XGB params: {'subsample': 0.75, 'n_estimators': 300, 'min_child_weight': 2, 'max_depth': 6, 'learning_rate': 0.05, 'gamma': 0.1, 'colsample_bytree': 0.85}
    XGB                             P=0.491  R=0.876  F1=0.6294  ROC=0.7549  PR-AUC=0.6909
  → Best: LR  F1=0.7057

========================================================================
  CROSS-PROJECT EVALUATION SUMMARY
========================================================================
  Fold         Model  N     Bug   P      R      F1     ROC    PR-AUC   Rec@20%
  --------------------------------------------------------------------------------
  requests     LR     17    4     0.400  1.000  0.571  0.885  0.799    0.500
  httpx        RF     9     6     1.000  1.000  1.000  1.000  1.000    0.167
  flask        XGB    23    20    1.000  0.900  0.947  0.983  0.998    0.200
  fastapi      LR     47    23    1.000  0.870  0.930  0.976  0.980    0.391
  express      LR     7     6     1.000  1.000  1.000  1.000  1.000    0.167
  axios        LR     70    48    0.919  0.708  0.800  0.884  0.946    0.292
  celery       LR     214   127   0.899  0.913  0.906  0.933  0.948    0.323
  sqlalchemy   XGB    236   171   0.832  0.982  0.901  0.785  0.860    0.234
  guava        LR     1031  411   0.724  0.689  0.706  0.832  0.756    0.426
  --------------------------------------------------------------------------------
  Average                         0.864  0.896  0.862  0.920  0.921    0.300
================================================================================

  * Folds with <20 test files may not be statistically meaningful:
    requests, httpx, express

  SUMMARY METRICS:
  ═══════════════════════════════════════════════════════════
  PRIMARY METRICS (Use These for Reporting):
  ─────────────────────────────────────────────────────────
  Weighted F1:   0.775  ← Most realistic (by repo size)
  PR-AUC:        0.921  ← Elite ranking quality (target: >0.85)
  ROC-AUC:       0.920  ← Strong discrimination (target: >0.90)
  Recall@20%:    0.300  ← Achieves 74.2% of theoretical max (0.404)
                              (With 49.3% buggy rate, max possible = 0.404)

  SECONDARY METRICS (For Context):
  ─────────────────────────────────────────────────────────
  Macro avg F1:  0.862  (all 9 folds, may be inflated by tiny repos)
  Honest avg F1: 0.865  (excluding folds with <20 test files)
  Defects@20%:   30.0%  (same as Recall@20%, legacy metric name)
  ═══════════════════════════════════════════════════════════

========================================================================
  BENCHMARK DEFINITIONS
========================================================================

  FULL BENCHMARK (all 9 repos):
    Macro F1:      0.862
    Weighted F1:   0.775
    PR-AUC:        0.921
    ROC-AUC:       0.920
    Recall@20%:    0.300

  RELIABLE BENCHMARK (5 repos, ≥30 files):
    Included: fastapi, axios, celery, sqlalchemy, guava
    Excluded: requests, httpx, flask, express
    Honest F1:      0.865
    Honest PR-AUC:  0.898
    Honest Rec@20%: 0.333
    Honest Precision: 0.896
    Honest Recall:    0.844

  ✓ Use RELIABLE BENCHMARK as headline metric in presentation
  ✓ Present FULL BENCHMARK as 'including edge cases' result

  Benchmarks saved to ml/benchmarks.json
  ⚠️  DO NOT CHANGE THESE NUMBERS BEFORE PRESENTATION

BEST ARCHITECTURE: LR (avg composite=0.6040, avg F1=0.8418 across 9 folds)
  Composite score = 0.4*PR-AUC + 0.4*Recall@20% + 0.2*F1
  This metric directly rewards operational goal: review top 20% to catch most bugs
Retraining on full dataset...
  Temporal validation: using 1654 files sorted by last change date
Using LR (winner of composite metric)...

  MODEL VERIFICATION:
  Selected architecture: LR
  Composite score: 0.6040
  This model won based on: 0.4*PR-AUC + 0.4*Recall@20% + 0.2*F1
  Calibrating probabilities (isotonic)...
  Calibration  pred=0.588  actual=0.589  Brier=0.0841  ✓ well-calibrated
  Calibration curve saved → model/calibration_curve.png
Model saved → C:\Users\archi\project\ai-bug-predictor\ml\models\bug_predictor_v1_20260429_164841.pkl
Latest alias updated → C:\Users\archi\project\ai-bug-predictor\ml\models\bug_predictor_latest.pkl
Training log updated → C:\Users\archi\project\ai-bug-predictor\ml\training_log.jsonl
Model expects 26 feature(s): ['loc', 'avg_complexity', 'max_complexity', 'avg_params', 'max_function_length', 'complexity_vs_baseline', 'loc_per_function', 'commits', 'lines_added', 'lines_deleted', 'max_added', 'author_count', 'ownership', 'instability_score', 'avg_commit_size', 'max_commit_ratio', 'recency_ratio', 'max_coupling_strength', 'coupled_file_count', 'bug_recency_score', 'temporal_bug_memory', 'coupled_recent_missing', 'coupling_risk', 'burst_risk', 'temporal_bug_risk', 'recent_bug_flag']
  Scaler persisted inside model artifact

════════════════════════════════════════════════════════════════════════
  STAGE 4  ·  RISK PREDICTION
════════════════════════════════════════════════════════════════════════
  Large dataset detected (1654 files)
  Using SHAP sampling: 992 files for explanations

Computing SHAP values on sample of 992 files (out of 1654)...
C:\Users\archi\project\ai-bug-predictor\venv\Lib\site-packages\shap\explainers\_linear.py:123: FutureWarning: The feature_perturbation option is now deprecated in favor of using the appropriate masker (maskers.Independent, maskers.Partition or maskers.Impute).
  warnings.warn(wmsg, FutureWarning)
Saving global SHAP plots...
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_bar.png (300 DPI)
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_beeswarm.png (300 DPI)
Saving local SHAP plots for top 5 risky files...

════════════════════════════════════════════════════════════════════════
  GITSENTINEL  ·  FINAL RISK REPORT
════════════════════════════════════════════════════════════════════════

  ┌─ httpx  (1 files │ 0 buggy │ 0 flagged risky)
  │     0%  [   ]  LOW       httpx\_transports\mock.py               unknown           · Lower-risk file based on historical…
  │             ↳  handle_request                  cx=  2  len=   9
  │             ↳  handle_async_request            cx=  2  len=  15

  ┌─ celery  (9 files │ 0 buggy │ 0 flagged risky)
  │     0%  [   ]  LOW       celery\contrib\testing\app.py           unknown           · Lower-risk file based on historical…
  │             ↳  TestApp                         cx=  6  len=  19
  │             ↳  setup_default_app               cx=  4  len=  23
  │     0%  [   ]  LOW       celery\contrib\testing\manager.py       unknown
  │             ↳  join                            cx=  7  len=  24
  │             ↳  wait_until_idle                 cx=  7  len=  21
  │     0%  [   ]  LOW       celery\contrib\testing\mocks.py         unknown
  │             ↳  task_message_from_sig           cx= 12  len=  33
  │             ↳  TaskMessage                     cx=  3  len=  32
  │     0%  [   ]  LOW       celery\contrib\testing\tasks.py         unknown
  │             ↳  ping                            cx=  1  len=   4
  │     0%  [   ]  LOW       celery\contrib\testing\__init__.py      unknown           · Very recent changes (347700.0% of file…
  │     0%  [   ]  LOW       celery\contrib\testing\worker.py        unknown
  │             ↳  __init__                        cx=  4  len=  23
  │             ↳  _start_worker_thread            cx=  4  len=  53
  │     0%  [   ]  LOW       t\integration\conftest.py               unknown           · Lower-risk file based on historical…
  │             ↳  check_for_logs                  cx=  4  len=   7
  │             ↳  celery_config                   cx=  2  len=  21
  │     0%  [   ]  LOW       t\smoke\conftest.py                     unknown
  │             ↳  default_worker_app              cx=  3  len=   5
  │             ↳  ready                           cx=  1  len=   7
  │     0%  [   ]  LOW       t\unit\conftest.py                      unknown           · Lower-risk file based on historical…
  │             ↳  module_exists                   cx=  8  len=  30
  │             ↳  sanity_logging_side_effects     cx=  7  len=  17

  ┌─ sqlalchemy  (27 files │ 0 buggy │ 0 flagged risky)
  │     0%  [   ]  LOW       lib\sqlalchemy\engine\mock.py           unknown           · Lower-risk file based on historical…
  │             ↳  create_mock_engine              cx=  3  len=  62
  │             ↳  __init__                        cx=  1  len=   3
  │     0%  [   ]  LOW       lib\sqlalchemy\testing\assertions.py    unknown           · Lower-risk file based on historical…
  │             ↳  assert_compile                  cx= 48  len= 270
  │             ↳  _expect_warnings.our_warn       cx= 16  len=  29
  │     0%  [   ]  LOW       lib\sqlalchemy\testing\config.py        unknown
  │             ↳  variation                       cx=  8  len=  67
  │             ↳  generate_cases                  cx=  5  len=  15
  │     0%  [   ]  LOW       lib\sqlalchemy\testing\asyncio.py       unknown
  │             ↳  _maybe_async_provisioning       cx=  3  len=  19
  │             ↳  _maybe_async                    cx=  3  len=  18
  │     0%  [   ]  LOW       lib\sqlalchemy\testing\assertsql.py     unknown           · Lower-risk file based on historical…
  │             ↳  process_statement               cx= 12  len=  50
  │             ↳  process_statement               cx=  7  len=  17
  │     0%  [   ]  LOW       lib\sqlalchemy\testing\engines.py       unknown           · Lower-risk file based on historical…
  │             ↳  testing_engine                  cx= 18  len=  71
  │             ↳  _drop_testing_engines           cx=  8  len=  17
  │     0%  [   ]  LOW       lib\sqlalchemy\testing\exclusions.py    unknown
  │             ↳  as_predicate                    cx= 13  len=  34
  │             ↳  __call__                        cx= 10  len=  26
  │     0%  [   ]  LOW       lib\sqlalchemy\testing\pickleable.py    unknown
  │             ↳  __eq__                          cx=  3  len=   6
  │             ↳  __eq__                          cx=  3  len=   6
  │     0%  [   ]  LOW       lib\sqlalchemy\testing\entities.py      unknown           · Complexity is 1.7x above language…
  │             ↳  __eq__                          cx= 20  len=  63
  │             ↳  __repr__                        cx=  5  len=  17
  │     0%  [   ]  LOW       lib\sqlalchemy\testing\profiling.py     unknown
  │             ↳  count_functions                 cx= 11  len=  66
  │             ↳  platform_key                    cx=  8  len=  27

  ┌─ guava  (301 files │ 0 buggy │ 0 flagged risky)
  │     0%  [   ]  LOW       guava\src\com\google\common\util\concurrent\CycleDetectingLockFactory.java  unknown           · Lower-risk file based on historical…
  │             ↳  LockGraphNode::findPathTo       cx=  5  len=  24
  │             ↳  Policies::createNodes           cx=  4  len=  21
  │     0%  [   ]  LOW       guava\src\com\google\common\util\concurrent\ThreadFactoryBuilder.java  unknown
  │             ↳  (anonymous)::newThread          cx=  5  len=  19
  │             ↳  ThreadFactoryBuilder::doBuild   cx=  3  len=  33
  │     0%  [   ]  LOW       guava-gwt\test-super\com\google\common\collect\testing\super\com\google\common\collect\testing\Platform.java  unknown           · Lower-risk file based on historical…
  │             ↳  Platform::format                cx=  5  len=  29
  │             ↳  Platform::checkCast             cx=  1  len=   1
  │     0%  [   ]  LOW       guava-gwt\test-super\com\google\common\collect\testing\super\com\google\common\collect\testing\testers\Platform.java  unknown           · Lower-risk file based on historical…
  │             ↳  Platform::format                cx=  5  len=  29
  │             ↳  Platform::listListIteratorTesterNumIterations  cx=  1  len=   4
  │     0%  [   ]  LOW       guava-gwt\test-super\com\google\common\testing\super\com\google\common\testing\Platform.java  unknown           · Lower-risk file based on historical…
  │             ↳  Platform::reserialize           cx=  1  len=   3
  │             ↳  Platform::Platform              cx=  1  len=   1
  │     0%  [   ]  LOW       guava-testlib\src\com\google\common\collect\testing\AbstractCollectionTester.java  unknown           · Lower-risk file based on historical…
  │             ↳  AbstractCollectionTester::expectNullMissingWhenNullUnsupported  cx=  2  len=   7
  │             ↳  AbstractCollectionTester::actualContents  cx=  1  len=   3
  │     0%  [   ]  LOW       guava-testlib\src\com\google\common\collect\testing\AbstractCollectionTestSuiteBuilder.java  unknown
  │             ↳  AbstractCollectionTestSuiteBuilder::getTesters  cx=  1  len=  23
  │     0%  [   ]  LOW       guava-testlib\src\com\google\common\collect\testing\AbstractContainerTester.java  unknown  
  │             ↳  AbstractContainerTester::expectMissing  cx=  2  len=   5
  │             ↳  ArrayWithDuplicate::getOrderedElements  cx=  2  len=   7
  │     0%  [   ]  LOW       guava-testlib\src\com\google\common\collect\testing\AbstractIteratorTester.java  unknown           · Lower-risk file based on historical…
  │             ↳  AbstractIteratorTester::internalExecuteAndCompare  cx= 10  len=  69
  │             ↳  KnownOrder::compareResultsForThisListOfStimuli  cx=  7  len=  20
  │     0%  [   ]  LOW       guava-testlib\src\com\google\common\collect\testing\AbstractTester.java  unknown           · Lower-risk file based on historical…
  │             ↳  AbstractTester::setUp           cx=  2  len=   5
  │             ↳  AbstractTester::tearDown        cx=  2  len=   5

════════════════════════════════════════════════════════════════════════

════════════════════════════════════════════════════════════════════════
  STAGE 6  ·  COMMIT RISK SIMULATION
════════════════════════════════════════════════════════════════════════

  Simulated changed files (3):
    • ForwardingBlockingDeque.java
    • types.py
    • AtomicDouble.java

  Commit risk score : 0.46  [MODERATE]
  Highest-risk file : types.py  →  64.3%

════════════════════════════════════════════════════════════════════════
  STAGE 7  ·  ABLATION STUDY (Skipped)
════════════════════════════════════════════════════════════════════════
  To run ablation study, set environment variable: RUN_ABLATION=1

════════════════════════════════════════════════════════════════════════
  PIPELINE COMPLETE
════════════════════════════════════════════════════════════════════════

════════════════════════════════════════════════════════════════════════
  RISK TIER METHODOLOGY
════════════════════════════════════════════════════════════════════════
  Risk tiers are assigned based on within-repository percentile ranking:
    CRITICAL: Top 10% of files by risk score
    HIGH:     10-25% (next 15%)
    MODERATE: 25-50% (next 25%)
    LOW:      Bottom 50%

  This approach is robust to base rate shifts and ensures every scan
  produces actionable results regardless of absolute probability values.
  Absolute probabilities are shown for reference but should not be
  interpreted as literal bug probabilities across different repositories.

  Base rate context: Training data has 49.3% buggy files after filtering.
  Real-world repos typically have 15-25% buggy files, so absolute
  probabilities will be systematically higher than true bug rates.
════════════════════════════════════════════════════════════════════════


(venv) C:\Users\archi\project\ai-bug-predictor>python bug_predictor.py dataset/httpx

Analyzing repository: dataset/httpx
Loaded model from C:\Users\archi\project\ai-bug-predictor\ml\models\bug_predictor_latest.pkl
✓ Loaded pre-trained model

1. Static analysis...

  [Analyzer audit for httpx]
  Analyzed files   : 9
  Skipped dirs     : 5
  Skipped files    : 22 (unsupported extension)
  First 20 analyzed:
    httpx\_config.py
    httpx\_utils.py
    httpx\__init__.py
    httpx\_transports\asgi.py
    httpx\_transports\base.py
    httpx\_transports\default.py
    httpx\_transports\mock.py
    httpx\_transports\wsgi.py
    httpx\_transports\__init__.py
  First 10 pruned dirs:
    .git
    .github
    docs
    scripts
    tests
   ✓ Analyzed 9 files

2. Git history mining...
   (This may take 1-5 minutes for large repos on first run)
   (Subsequent runs will be instant due to caching)
  Checkpoint saved (1000 commits)
  Checkpoint saved (2000 commits)
  Processed 2964 commits successfully
  SZZ (inline): 78 buggy files identified during mining
   ✓ Mined 319 files

3. Feature engineering...

⚠  WARNING: Small repository detected (9 files)
   Results are directional only. Predictions more reliable for repos with 25+ files.
   Confidence scores will reflect this limitation.
  SZZ: loaded from cache (78 buggy files)

  Label Audit:
  SZZ raw paths     : 78
  Files in analysis : 9
  Matched buggy     : 6 (66.7% of analyzed files)
  SZZ match rate    : 7.7% of SZZ paths exist in analyzer
  Clean files       : 3 (33.3%)
  ⚠ Many buggy files — SZZ filter may be too loose
   ✓ Built features for 9 files

4. Risk prediction...
   ✓ Predicted risk for 9 files
   Confidence: HIGH (0.76)
   Warnings:
     - Extreme values detected in commits
     - Extreme values detected in lines_added
     - Extreme values detected in lines_deleted
     - Extreme values detected in max_added
     - Extreme values detected in author_count
     - Extreme values detected in instability_score
     - Extreme values detected in avg_commit_size
     - Small repository (8 files) - predictions less reliable

5. Generating explanations...

Computing SHAP values...
C:\Users\archi\project\ai-bug-predictor\venv\Lib\site-packages\shap\explainers\_linear.py:123: FutureWarning: The feature_perturbation option is now deprecated in favor of using the appropriate masker (maskers.Independent, maskers.Partition or maskers.Impute).
  warnings.warn(wmsg, FutureWarning)
Saving global SHAP plots...
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_bar.png (300 DPI)
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_beeswarm.png (300 DPI)
Saving local SHAP plots for top 5 risky files...
   ✓ Generated SHAP explanations

======================================================================
  ANALYSIS SUMMARY
======================================================================
  Repository: httpx
  Files analyzed: 9
  Buggy files (labeled): 6
  High-risk files (>0.7): 8
  Medium-risk files (0.4-0.7): 0
  Low-risk files (<0.4): 1
  Average risk: 0.844
  Prediction confidence: HIGH

======================================================================
  TOP 15 RISK FILES
======================================================================
  Rank   Risk         Tier       LOC    File
  ----------------------------------------------------------------------
  #1     95.0%        CRI        182    _config.py
  #2     95.0%        CRI        123    _utils.py
  #3     95.0%        CRI        99     __init__.py
  #4     95.0%        CRI        116    asgi.py
  #5     95.0%        CRI        42     base.py
  #6     95.0%        CRI        329    default.py
  #7     95.0%        CRI        94     wsgi.py
  #8     95.0%        CRI        14     __init__.py
  #9     0.0%         LOW        28     mock.py

======================================================================

✓ Analysis complete!

SHAP plots saved to: C:\Users\archi\project\ai-bug-predictor\ml\plots
  - global_bar.png: Feature importance
  - global_beeswarm.png: Feature distribution
  - local_waterfall_*.png: Per-file explanations


(venv) C:\Users\archi\project\ai-bug-predictor>python bug_predictor.py dataset/requests

Analyzing repository: dataset/requests
Loaded model from C:\Users\archi\project\ai-bug-predictor\ml\models\bug_predictor_latest.pkl
✓ Loaded pre-trained model

1. Static analysis...

  [Analyzer audit for requests]
  Analyzed files   : 17
  Skipped dirs     : 4
  Skipped files    : 29 (unsupported extension)
  First 20 analyzed:
    setup.py
    src\requests\adapters.py
    src\requests\api.py
    src\requests\auth.py
    src\requests\certs.py
    src\requests\compat.py
    src\requests\cookies.py
    src\requests\exceptions.py
    src\requests\help.py
    src\requests\hooks.py
    src\requests\models.py
    src\requests\packages.py
    src\requests\sessions.py
    src\requests\status_codes.py
    src\requests\structures.py
    src\requests\utils.py
    src\requests\__init__.py
  First 10 pruned dirs:
    .git
    .github
    docs
    tests
   ✓ Analyzed 17 files

2. Git history mining...
   (This may take 1-5 minutes for large repos on first run)
   (Subsequent runs will be instant due to caching)
  Loaded mining cache for requests
   ✓ Mined 461 files

3. Feature engineering...

⚠  WARNING: Small repository detected (17 files)
   Results are directional only. Predictions more reliable for repos with 25+ files.
   Confidence scores will reflect this limitation.
  SZZ: loaded from cache (70 buggy files)

  Label Audit:
  SZZ raw paths     : 70
  Files in analysis : 17
  Matched buggy     : 4 (23.5% of analyzed files)
  SZZ match rate    : 5.7% of SZZ paths exist in analyzer
  Clean files       : 13 (76.5%)
  ✓ Label prevalence 23.5% looks healthy
   ✓ Built features for 17 files

4. Risk prediction...
   ✓ Predicted risk for 17 files
   Confidence: MEDIUM (0.65)
   Warnings:
     - Extreme values detected in lines_added
     - Sparse git history detected
     - Small repository (17 files) - predictions less reliable

5. Generating explanations...

Computing SHAP values...
Saving global SHAP plots...
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_bar.png (300 DPI)
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_beeswarm.png (300 DPI)
Saving local SHAP plots for top 5 risky files...
   ✓ Generated SHAP explanations

======================================================================
  ANALYSIS SUMMARY
======================================================================
  Repository: requests
  Files analyzed: 17
  Buggy files (labeled): 4
  High-risk files (>0.7): 10
  Medium-risk files (0.4-0.7): 7
  Low-risk files (<0.4): 0
  Average risk: 0.691
  Prediction confidence: MEDIUM

======================================================================
  TOP 15 RISK FILES
======================================================================
  Rank   Risk         Tier       LOC    File
  ----------------------------------------------------------------------
  #1     91.8%        CRI        6      setup.py
  #2     91.8%        CRI        379    adapters.py
  #3     91.8%        CRI        599    models.py
  #4     91.8%        CRI        572    utils.py
  #5     83.3%        HIG        103    __init__.py
  #6     77.8%        MOD        14     hooks.py
  #7     77.8%        MOD        205    auth.py
  #8     77.8%        MOD        39     exceptions.py
  #9     77.8%        MOD        98     help.py
  #10    77.8%        MOD        406    sessions.py
  #11    60.9%        LOW        3      certs.py
  #12    52.9%        LOW        292    cookies.py
  #13    52.9%        LOW        15     packages.py
  #14    42.1%        LOW        60     compat.py
  #15    42.1%        LOW        19     api.py

======================================================================

✓ Analysis complete!

SHAP plots saved to: C:\Users\archi\project\ai-bug-predictor\ml\plots
  - global_bar.png: Feature importance
  - global_beeswarm.png: Feature distribution
  - local_waterfall_*.png: Per-file explanations

✓ Opened plots folder in Explorer

(venv) C:\Users\archi\project\ai-bug-predictor>python bug_predictor.py dataset/flask

Analyzing repository: dataset/flask
Loaded model from C:\Users\archi\project\ai-bug-predictor\ml\models\bug_predictor_latest.pkl
✓ Loaded pre-trained model

1. Static analysis...

  [Analyzer audit for flask]
  Analyzed files   : 23
  Skipped dirs     : 5
  Skipped files    : 14 (unsupported extension)
  First 20 analyzed:
    src\flask\app.py
    src\flask\blueprints.py
    src\flask\cli.py
    src\flask\config.py
    src\flask\ctx.py
    src\flask\debughelpers.py
    src\flask\globals.py
    src\flask\helpers.py
    src\flask\logging.py
    src\flask\sessions.py
    src\flask\signals.py
    src\flask\templating.py
    src\flask\testing.py
    src\flask\typing.py
    src\flask\views.py
    src\flask\wrappers.py
    src\flask\__init__.py
    src\flask\json\provider.py
    src\flask\json\tag.py
    src\flask\json\__init__.py
  First 10 pruned dirs:
    .git
    .github
    docs
    examples
    tests
   ✓ Analyzed 23 files

2. Git history mining...
   (This may take 1-5 minutes for large repos on first run)
   (Subsequent runs will be instant due to caching)
  Checkpoint saved (1000 commits)
  Checkpoint saved (2000 commits)
  Checkpoint saved (3000 commits)
  Checkpoint saved (4000 commits)
  Checkpoint saved (5000 commits)
  Checkpoint saved (6000 commits)
  Checkpoint saved (7000 commits)
  Processed 7610 commits successfully
  SZZ (inline): 92 buggy files identified during mining
   ✓ Mined 643 files

3. Feature engineering...

⚠  WARNING: Small repository detected (23 files)
   Results are directional only. Predictions more reliable for repos with 25+ files.
   Confidence scores will reflect this limitation.
  SZZ: loaded from cache (92 buggy files)

  Label Audit:
  SZZ raw paths     : 92
  Files in analysis : 23
  Matched buggy     : 20 (87.0% of analyzed files)
  SZZ match rate    : 21.7% of SZZ paths exist in analyzer
  Clean files       : 3 (13.0%)
  ⚠ Many buggy files — SZZ filter may be too loose
   ✓ Built features for 23 files

4. Risk prediction...
   ✓ Predicted risk for 23 files
   Confidence: MEDIUM (0.72)
   Warnings:
     - Extreme values detected in commits
     - Extreme values detected in lines_added
     - Extreme values detected in lines_deleted
     - Extreme values detected in max_added
     - Extreme values detected in instability_score
     - Extreme values detected in avg_commit_size
     - Small repository (23 files) - predictions less reliable

5. Generating explanations...

Computing SHAP values...
Saving global SHAP plots...
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_bar.png (300 DPI)
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_beeswarm.png (300 DPI)
Saving local SHAP plots for top 5 risky files...
   ✓ Generated SHAP explanations

======================================================================
  ANALYSIS SUMMARY
======================================================================
  Repository: flask
  Files analyzed: 23
  Buggy files (labeled): 20
  High-risk files (>0.7): 18
  Medium-risk files (0.4-0.7): 5
  Low-risk files (<0.4): 0
  Average risk: 0.819
  Prediction confidence: MEDIUM

======================================================================
  TOP 15 RISK FILES
======================================================================
  Rank   Risk         Tier       LOC    File
  ----------------------------------------------------------------------
  #1     95.0%        CRI        684    app.py
  #2     94.1%        CRI        691    cli.py
  #3     94.1%        CRI        207    ctx.py
  #4     94.1%        CRI        347    app.py
  #5     94.1%        CRI        170    testing.py
  #6     94.1%        CRI        158    sessions.py
  #7     94.1%        CRI        219    helpers.py
  #8     91.8%        MOD        61     views.py
  #9     91.8%        MOD        129    templating.py
  #10    91.8%        MOD        141    config.py
  #11    91.8%        MOD        63     blueprints.py
  #12    91.4%        MOD        28     __init__.py
  #13    83.3%        LOW        129    debughelpers.py
  #14    83.3%        LOW        288    scaffold.py
  #15    83.3%        LOW        92     wrappers.py

======================================================================

✓ Analysis complete!

SHAP plots saved to: C:\Users\archi\project\ai-bug-predictor\ml\plots
  - global_bar.png: Feature importance
  - global_beeswarm.png: Feature distribution
  - local_waterfall_*.png: Per-file explanations

✓ Opened plots folder in Explorer

(venv) C:\Users\archi\project\ai-bug-predictor>python bug_predictor.py dataset/axios

Analyzing repository: dataset/axios
Loaded model from C:\Users\archi\project\ai-bug-predictor\ml\models\bug_predictor_latest.pkl
✓ Loaded pre-trained model

1. Static analysis...

  [Analyzer audit for axios]
  Analyzed files   : 70
  Skipped dirs     : 8
  Skipped files    : 25 (unsupported extension)
  First 20 analyzed:
    eslint.config.js
    gulpfile.js
    index.d.ts
    index.js
    rollup.config.js
    vitest.config.js
    webpack.config.js
    lib\axios.js
    lib\utils.js
    lib\adapters\adapters.js
    lib\adapters\fetch.js
    lib\adapters\http.js
    lib\adapters\xhr.js
    lib\cancel\CanceledError.js
    lib\cancel\CancelToken.js
    lib\cancel\isCancel.js
    lib\core\Axios.js
    lib\core\AxiosError.js
    lib\core\AxiosHeaders.js
    lib\core\buildFullPath.js
  First 10 pruned dirs:
    .git
    .github
    .husky
    docs
    examples
    scripts
    tests
    lib\env
   ✓ Analyzed 70 files

2. Git history mining...
   (This may take 1-5 minutes for large repos on first run)
   (Subsequent runs will be instant due to caching)
  Checkpoint saved (1000 commits)
  Checkpoint saved (2000 commits)
  Checkpoint saved (3000 commits)
  Processed 3502 commits successfully
  SZZ (inline): 87 buggy files identified during mining
   ✓ Mined 694 files

3. Feature engineering...

⚠  WARNING: Multi-language repository detected
   Languages found: javascript, typescript
   Model trained primarily on Python - predictions for other languages may be less reliable
  SZZ: loaded from cache (87 buggy files)

  Label Audit:
  SZZ raw paths     : 87
  Files in analysis : 70
  Matched buggy     : 48 (68.6% of analyzed files)
  SZZ match rate    : 55.2% of SZZ paths exist in analyzer
  Clean files       : 22 (31.4%)
  ⚠ Many buggy files — SZZ filter may be too loose
   ✓ Built features for 70 files

4. Risk prediction...
   ✓ Predicted risk for 70 files
   Confidence: HIGH (0.81)
   Warnings:
     - Extreme values detected in commits
     - Extreme values detected in lines_added
     - Extreme values detected in lines_deleted
     - Extreme values detected in max_added
     - Extreme values detected in instability_score
     - Extreme values detected in avg_commit_size

5. Generating explanations...

Computing SHAP values...
C:\Users\archi\project\ai-bug-predictor\venv\Lib\site-packages\shap\explainers\_linear.py:123: FutureWarning: The feature_perturbation option is now deprecated in favor of using the appropriate masker (maskers.Independent, maskers.Partition or maskers.Impute).
  warnings.warn(wmsg, FutureWarning)
Saving global SHAP plots...
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_bar.png (300 DPI)
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_beeswarm.png (300 DPI)
Saving local SHAP plots for top 5 risky files...
   ✓ Generated SHAP explanations

======================================================================
  ANALYSIS SUMMARY
======================================================================
  Repository: axios
  Files analyzed: 70
  Buggy files (labeled): 48
  High-risk files (>0.7): 70
  Medium-risk files (0.4-0.7): 0
  Low-risk files (<0.4): 0
  Average risk: 0.950
  Prediction confidence: HIGH

======================================================================
  TOP 15 RISK FILES
======================================================================
  Rank   Risk         Tier       LOC    File
  ----------------------------------------------------------------------
  #1     95.0%        CRI        51     eslint.config.js
  #2     95.0%        CRI        64     gulpfile.js
  #3     95.0%        CRI        609    index.d.ts
  #4     95.0%        CRI        38     index.js
  #5     95.0%        CRI        122    rollup.config.js
  #6     95.0%        CRI        45     vitest.config.js
  #7     95.0%        CRI        23     webpack.config.js
  #8     95.0%        CRI        49     axios.js
  #9     95.0%        CRI        461    utils.js
  #10    95.0%        CRI        67     adapters.js
  #11    95.0%        CRI        282    fetch.js
  #12    95.0%        CRI        807    http.js
  #13    95.0%        CRI        161    xhr.js
  #14    95.0%        CRI        10     CanceledError.js
  #15    95.0%        CRI        85     CancelToken.js

======================================================================

✓ Analysis complete!

SHAP plots saved to: C:\Users\archi\project\ai-bug-predictor\ml\plots
  - global_bar.png: Feature importance
  - global_beeswarm.png: Feature distribution
  - local_waterfall_*.png: Per-file explanations

✓ Opened plots folder in Explorer

(venv) C:\Users\archi\project\ai-bug-predictor>python bug_predictor.py dataset/celery

Analyzing repository: dataset/celery
Loaded model from C:\Users\archi\project\ai-bug-predictor\ml\models\bug_predictor_latest.pkl
✓ Loaded pre-trained model

1. Static analysis...

  [Analyzer audit for celery]
  Analyzed files   : 214
  Skipped dirs     : 8
  Skipped files    : 234 (unsupported extension)
  First 20 analyzed:
    setup.py
    celery\beat.py
    celery\bootsteps.py
    celery\canvas.py
    celery\exceptions.py
    celery\local.py
    celery\platforms.py
    celery\result.py
    celery\schedules.py
    celery\signals.py
    celery\states.py
    celery\__init__.py
    celery\app\amqp.py
    celery\app\annotations.py
    celery\app\autoretry.py
    celery\app\backends.py
    celery\app\base.py
    celery\app\builtins.py
    celery\app\control.py
    celery\app\defaults.py
  First 10 pruned dirs:
    .git
    .github
    docs
    examples
    scripts
    docker\docs
    docker\scripts
    t\smoke\tests
   ✓ Analyzed 214 files

2. Git history mining...
   (This may take 1-5 minutes for large repos on first run)
   (Subsequent runs will be instant due to caching)
  Checkpoint saved (1000 commits)
  Checkpoint saved (2000 commits)
  Checkpoint saved (3000 commits)
  Checkpoint saved (4000 commits)
  Checkpoint saved (5000 commits)
  Checkpoint saved (6000 commits)
  Checkpoint saved (7000 commits)
  Checkpoint saved (8000 commits)
  Checkpoint saved (9000 commits)
  Checkpoint saved (10000 commits)
  Checkpoint saved (11000 commits)
  Checkpoint saved (12000 commits)
  Checkpoint saved (13000 commits)
  Checkpoint saved (14000 commits)
  Checkpoint saved (15000 commits)
  Checkpoint saved (16000 commits)
  Checkpoint saved (17000 commits)
  Checkpoint saved (18000 commits)
  Checkpoint saved (19000 commits)
  Checkpoint saved (20000 commits)
  Checkpoint saved (21000 commits)
  Checkpoint saved (22000 commits)
  Checkpoint saved (23000 commits)
  Checkpoint saved (24000 commits)
  Processed 24190 commits successfully
  SZZ (inline): 320 buggy files identified during mining
   ✓ Mined 2261 files

3. Feature engineering...
  SZZ: loaded from cache (320 buggy files)

  Label Audit:
  SZZ raw paths     : 320
  Files in analysis : 214
  Matched buggy     : 127 (59.3% of analyzed files)
  SZZ match rate    : 39.7% of SZZ paths exist in analyzer
  Clean files       : 87 (40.7%)
  ✓ Label prevalence 59.3% looks healthy
   ✓ Built features for 214 files

4. Risk prediction...
   ✓ Predicted risk for 214 files
   Confidence: HIGH (0.80)
   Warnings:
     - Extreme values detected in commits
     - Extreme values detected in lines_added
     - Extreme values detected in lines_deleted
     - Extreme values detected in max_added
     - Extreme values detected in author_count
     - Extreme values detected in instability_score
     - Extreme values detected in avg_commit_size

5. Generating explanations...

Computing SHAP values...
C:\Users\archi\project\ai-bug-predictor\venv\Lib\site-packages\shap\explainers\_linear.py:123: FutureWarning: The feature_perturbation option is now deprecated in favor of using the appropriate masker (maskers.Independent, maskers.Partition or maskers.Impute).
  warnings.warn(wmsg, FutureWarning)
Saving global SHAP plots...
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_bar.png (300 DPI)
  Saved → C:\Users\archi\project\ai-bug-predictor\ml\plots/global_beeswarm.png (300 DPI)
Saving local SHAP plots for top 5 risky files...
   ✓ Generated SHAP explanations

======================================================================
  ANALYSIS SUMMARY
======================================================================
  Repository: celery
  Files analyzed: 214
  Buggy files (labeled): 127
  High-risk files (>0.7): 188
  Medium-risk files (0.4-0.7): 1
  Low-risk files (<0.4): 25
  Average risk: 0.838
  Prediction confidence: HIGH

======================================================================
  TOP 15 RISK FILES
======================================================================
  Rank   Risk         Tier       LOC    File
  ----------------------------------------------------------------------
  #1     95.0%        CRI        134    setup.py
  #2     95.0%        CRI        508    beat.py
  #3     95.0%        CRI        274    bootsteps.py
  #4     95.0%        CRI        1163   canvas.py
  #5     95.0%        CRI        116    exceptions.py
  #6     95.0%        CRI        377    local.py
  #7     95.0%        CRI        472    platforms.py
  #8     95.0%        CRI        588    result.py
  #9     95.0%        CRI        497    schedules.py
  #10    95.0%        CRI        125    signals.py
  #11    95.0%        CRI        48     states.py
  #12    95.0%        CRI        114    __init__.py
  #13    95.0%        CRI        502    amqp.py
  #14    95.0%        CRI        30     annotations.py
  #15    95.0%        CRI        54     autoretry.py

======================================================================

✓ Analysis complete!

SHAP plots saved to: C:\Users\archi\project\ai-bug-predictor\ml\plots
  - global_bar.png: Feature importance
  - global_beeswarm.png: Feature distribution
  - local_waterfall_*.png: Per-file explanations

✓ Opened plots folder in Explorer