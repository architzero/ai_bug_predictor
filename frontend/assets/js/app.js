// ─── Feature label map ────────────────────────────────────────────────────────
const FEATURE_LABELS = {
  bug_recency_score:      'Bug history',
  avg_complexity:         'Code complexity (avg)',
  max_complexity:         'Code complexity (peak)',
  temporal_bug_memory:    'Long-term bug memory',
  instability_score:      'File instability',
  commits:                'Total commit history',
  author_count:           'Contributor count',
  max_coupling_strength:  'Coupling strength',
  recency_ratio:          'Recent vs. historical activity',
  commit_burst_score:     'Commit burst activity',
  coupling_risk:          'Coupling risk',
  avg_params:             'Avg function parameters',
  max_function_length:    'Longest function',
  complexity_vs_baseline: 'Complexity vs language baseline',
  loc_per_function:       'Avg function size',
  lines_added:            'Lines added (lifetime)',
  lines_deleted:          'Lines deleted (lifetime)',
  max_added:              'Largest single addition',
  avg_commit_size:        'Avg commit size',
  max_commit_ratio:       'Largest commit proportion',
  days_since_last_change: 'Days since last change',
  coupled_file_count:     'Coupled file count',
  coupled_recent_missing: 'Co-changed files lagging',
  recent_commit_burst:    'Recent activity burst',
  recent_bug_flag:        'Recent bug indicator',
  ownership:              'Code ownership',
  loc:                    'Lines of code',
  burst_risk:             'Burst risk',
  temporal_bug_risk:      'Temporal bug risk',
  experience_score:       'Developer experience',
  minor_contributor_ratio:'Minor contributor ratio',
  file_age_bucket:        'File age',
  complexity_density:     'Complexity density',
  complexity_per_function:'Complexity per function',
  functions:              'Function count',
};

function featureLabel(key) {
  return FEATURE_LABELS[key] || key;
}

// ─── Risk helpers ─────────────────────────────────────────────────────────────
function riskTier(score) {
  if (score >= 0.8) return 'critical';
  if (score >= 0.6) return 'high';
  if (score >= 0.4) return 'moderate';
  return 'low';
}

function assignPercentileTiers(files) {
  if (!files || files.length === 0) return files;
  const sorted = [...files].sort((a, b) => b.risk - a.risk);
  const n = sorted.length;
  const criticalCutoff = Math.ceil(n * 0.10);
  const highCutoff     = Math.ceil(n * 0.25);
  const moderateCutoff = Math.ceil(n * 0.50);
  sorted.forEach((f, i) => {
    if (i < criticalCutoff)      f._tier = 'CRITICAL';
    else if (i < highCutoff)     f._tier = 'HIGH';
    else if (i < moderateCutoff) f._tier = 'MODERATE';
    else                          f._tier = 'LOW';
  });
  return sorted;
}

function tierBadgeClass(tier) {
  if (tier === 'CRITICAL') return 'bg-red-100 text-red-800 border border-red-200';
  if (tier === 'HIGH')     return 'bg-orange-100 text-orange-800 border border-orange-200';
  if (tier === 'MODERATE') return 'bg-yellow-100 text-yellow-800 border border-yellow-200';
  return 'bg-green-100 text-green-800 border border-green-200';
}

function riskBadgeClass(score) {
  const t = riskTier(score);
  if (t === 'critical') return 'bg-red-100 text-red-800 border border-red-200';
  if (t === 'high')     return 'bg-orange-100 text-orange-800 border border-orange-200';
  if (t === 'moderate') return 'bg-yellow-100 text-yellow-800 border border-yellow-200';
  return 'bg-green-100 text-green-800 border border-green-200';
}

function riskTextClass(score) {
  const t = riskTier(score);
  if (t === 'critical') return 'text-red-600';
  if (t === 'high')     return 'text-orange-600';
  if (t === 'moderate') return 'text-yellow-600';
  return 'text-green-600';
}

function riskChartColor(score) {
  const t = riskTier(score);
  if (t === 'critical') return '#DC2626';
  if (t === 'high')     return '#EA580C';
  if (t === 'moderate') return '#D97706';
  return '#16A34A';
}

// ─── SHAP explanation builder ─────────────────────────────────────────────────
function buildExplanation(shap) {
  const risk_factors = [];
  const protective_factors = [];

  (shap?.positive || []).forEach(item => {
    const label = featureLabel(item.feature);
    const val   = item.value;
    if (val > 0.05) {
      if (item.feature === 'bug_recency_score' || item.feature === 'temporal_bug_memory') {
        risk_factors.push(`Strong bug history — this file has been the source of past bugs (SHAP +${val.toFixed(2)})`);
      } else if (item.feature === 'max_complexity' || item.feature === 'avg_complexity') {
        risk_factors.push(`High cyclomatic complexity — complex logic is error-prone (SHAP +${val.toFixed(2)})`);
      } else if (item.feature === 'instability_score' || item.feature === 'commit_burst_score') {
        risk_factors.push(`Frequently changed in recent commits — active churn increases risk (SHAP +${val.toFixed(2)})`);
      } else if (item.feature === 'coupling_risk' || item.feature === 'max_coupling_strength') {
        risk_factors.push(`High coupling — co-changes with other risky files (SHAP +${val.toFixed(2)})`);
      } else if (item.feature === 'author_count') {
        risk_factors.push(`Many contributors — coordination overhead increases defect probability (SHAP +${val.toFixed(2)})`);
      } else if (item.feature === 'recent_bug_flag') {
        risk_factors.push(`Recent bug indicator — a bug was recently fixed in this file (SHAP +${val.toFixed(2)})`);
      } else if (item.feature === 'commits') {
        risk_factors.push(`High commit frequency — frequently modified file (SHAP +${val.toFixed(2)})`);
      } else if (item.feature === 'lines_added' || item.feature === 'max_added') {
        risk_factors.push(`Large code additions — significant growth increases risk (SHAP +${val.toFixed(2)})`);
      } else {
        risk_factors.push(`${label} is elevated (SHAP +${val.toFixed(2)})`);
      }
    }
  });

  (shap?.negative || []).forEach(item => {
    const label = featureLabel(item.feature);
    const val   = Math.abs(item.value);
    if (val > 0.05) {
      if (item.feature === 'days_since_last_change') {
        protective_factors.push(`Not recently modified — stable file reduces risk (SHAP ${item.value.toFixed(2)})`);
      } else if (item.feature === 'ownership') {
        protective_factors.push(`Clear code ownership — single primary author reduces coordination risk (SHAP ${item.value.toFixed(2)})`);
      } else if (item.feature === 'experience_score') {
        protective_factors.push(`Experienced contributors — reduces defect probability (SHAP ${item.value.toFixed(2)})`);
      } else {
        protective_factors.push(`${label} is low — reduces risk (SHAP ${item.value.toFixed(2)})`);
      }
    }
  });

  return { risk_factors, protective_factors };
}

// ─── Chart helpers ────────────────────────────────────────────────────────────
function destroyChart(instance) {
  if (instance) { try { instance.destroy(); } catch (_) {} }
  return null;
}

function safeCanvas(id) {
  const el = document.getElementById(id);
  if (!el || el.offsetParent === null) return null;
  return el;
}

// ─── Alpine component: resultsDashboard ──────────────────────────────────────
function registerAlpineComponents() {
  if (typeof Alpine === 'undefined') return;

  Alpine.data('resultsDashboard', (scanId) => ({
    scanId,
    files: [],
    filteredFiles: [],
    originalFiles: [],
    overview: null,
    repoName: '',
    searchQuery: '',
    timeFilter: 'all',
    sortBy: 'risk',
    selectedFileId: null,
    selectedFileDetails: null,
    isPanelOpen: false,
    isLoading: true,
    error: null,
    modelEval: null,
    _chartsInitialized: false,
    charts: { 
      histogram: null, 
      topFiles: null, 
      importance: null, 
      roc: null, 
      pr: null, 
      confusion: null 
    },

    async init() {
      if (!this.scanId) {
        this.error = 'No scan ID provided.';
        this.isLoading = false;
        return;
      }

      try {
        // First try to get overview data to check if backend is ready
        const overviewRes = await fetch('/api/overview');
        let overviewData = null;
        
        if (overviewRes.ok) {
          overviewData = await overviewRes.json();
          this.overview = overviewData;
          
          // Check if backend is still initializing
          if (overviewData.status === 'initializing') {
            this.error = 'Backend is still initializing. Please wait a moment and refresh.';
            this.isLoading = false;
            
            // Auto-refresh after 3 seconds
            setTimeout(() => {
              window.location.reload();
            }, 3000);
            return;
          }
        }

        // Get scan results
        const scanRes = await fetch(`/api/scan_results/${this.scanId}`);
        if (!scanRes.ok) {
          throw new Error('Scan results not found or expired.');
        }

        const data = await scanRes.json();

        if (!data.files || data.files.length === 0) {
          this.error = 'No source files found in scan.';
          this.isLoading = false;
          return;
        }

        this.repoName      = data.repo_name || 'Unknown Repository';
        this.originalFiles = assignPercentileTiers(data.files);
        this.applyFilters();

        this.$watch('searchQuery', () => this.applyFilters());

        this.$nextTick(() => {
          setTimeout(() => this.initCharts(), 400);
        });

      } catch (err) {
        this.error = err.message;
        console.error('Dashboard initialization error:', err);
      } finally {
        this.isLoading = false;
      }
    },

    get tierCounts() {
      return {
        critical: this.originalFiles.filter(f => f._tier === 'CRITICAL').length,
        high:     this.originalFiles.filter(f => f._tier === 'HIGH').length,
        moderate: this.originalFiles.filter(f => f._tier === 'MODERATE').length,
        low:      this.originalFiles.filter(f => f._tier === 'LOW').length,
      };
    },

    applyFilters() {
      let result = [...this.originalFiles];
      if (this.timeFilter !== 'all') {
        const days = parseInt(this.timeFilter);
        result = result.filter(f => (f.days_since_last_change || 9999) <= days);
      }
      if (this.searchQuery) {
        const q = this.searchQuery.toLowerCase();
        result = result.filter(f => f.filename.toLowerCase().includes(q));
      }
      this.files = result;
      this.applySorting();
    },

    applySorting() {
      this.files.sort((a, b) => {
        switch (this.sortBy) {
          case 'commits': return (b.commits || 0) - (a.commits || 0);
          case 'churn':   return ((b.lines_added || 0) + (b.lines_deleted || 0)) - ((a.lines_added || 0) + (a.lines_deleted || 0));
          case 'recency': return (a.days_since_last_change || 9999) - (b.days_since_last_change || 9999);
          default:        return b.risk - a.risk;
        }
      });
      this.filteredFiles = [...this.files];
    },

    getRiskBadgeClass(file) {
      if (file && file._tier) return tierBadgeClass(file._tier);
      return riskBadgeClass(file?.risk ?? file ?? 0);
    },
    getTextColor: riskTextClass,
    getTierBadge: tierBadgeClass,

    async selectFile(fileId) {
      this.selectedFileId = fileId;
      this.selectedFileDetails = null;
      this.isPanelOpen = true;

      try {
        const res = await fetch(`/api/file?id=${encodeURIComponent(fileId)}&scan_id=${encodeURIComponent(this.scanId)}`);
        if (!res.ok) throw new Error('Failed to fetch file details');
        const details = await res.json();

        const fileObj = this.originalFiles.find(f => f.id === fileId);
        details._tier = fileObj?._tier || null;
        details.explanation = buildExplanation(details.shap);

        if (details.shap?.positive) {
          details.shap.positive = details.shap.positive.map(s => ({ ...s, label: featureLabel(s.feature) }));
        }
        if (details.shap?.negative) {
          details.shap.negative = details.shap.negative.map(s => ({ ...s, label: featureLabel(s.feature) }));
        }

        this.selectedFileDetails = details;
      } catch (err) {
        this.selectedFileDetails = {
          filepath: 'Error: ' + err.message,
          risk: 0,
          _tier: null,
          shap: { positive: [], negative: [] },
          top_funcs: [],
          explanation: { risk_factors: [], protective_factors: [] },
        };
      }
    },

    initCharts() {
      if (this._chartsInitialized) return;
      if (!this.originalFiles || this.originalFiles.length === 0) return;
      this._chartsInitialized = true;

      this._buildHistogram();
      this._buildTopFilesChart();
      this._buildImportance();
      this._buildROC();
      this._buildPR();
      this._buildConfusionMatrix();
    },

    _buildHistogram() {
      const ctx = safeCanvas('riskHistogram');
      if (!ctx) return;
      
      // Use real histogram data from API
      const histogramData = this.overview?.histogram || [];
      if (!histogramData || histogramData.length === 0) {
        // Fallback to tier counts if histogram data not available
        const tc = this.tierCounts;
        this.charts.histogram = destroyChart(this.charts.histogram);
        this.charts.histogram = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: ['CRITICAL', 'HIGH', 'MODERATE', 'LOW'],
            datasets: [{
              label: 'Files',
              data: [tc.critical, tc.high, tc.moderate, tc.low],
              backgroundColor: ['#DC2626', '#EA580C', '#D97706', '#16A34A'],
              borderRadius: 4,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
              legend: { display: false },
              title: { display: true, text: 'Risk Distribution by Tier', font: { size: 13, weight: '600' } }
            },
            scales: {
              y: { beginAtZero: true, title: { display: true, text: 'Number of Files' } },
              x: { grid: { display: false } }
            }
          }
        });
        return;
      }
      
      // Build proper histogram from risk scores
      this.charts.histogram = destroyChart(this.charts.histogram);
      this.charts.histogram = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: histogramData.map(d => d.bin),
          datasets: [{
            label: 'Files',
            data: histogramData.map(d => d.count),
            backgroundColor: '#6366F1',
            borderColor: '#4F46E5',
            borderWidth: 1,
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { 
            legend: { display: false },
            title: { display: true, text: 'Risk Score Distribution', font: { size: 13, weight: '600' } }
          },
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'Number of Files' } },
            x: { 
              title: { display: true, text: 'Risk Score Bins' },
              grid: { display: false } 
            }
          }
        }
      });
    },

    _buildTopFilesChart() {
      const ctx = safeCanvas('topFilesChart');
      if (!ctx) return;
      const top10 = [...this.originalFiles].sort((a, b) => b.risk - a.risk).slice(0, 10);
      this.charts.topFiles = destroyChart(this.charts.topFiles);
      this.charts.topFiles = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: top10.map(f => f.filename.length > 20 ? f.filename.substring(0, 17) + '...' : f.filename),
          datasets: [{
            label: 'Risk Score',
            data: top10.map(f => +(f.risk * 100).toFixed(1)),
            backgroundColor: top10.map(f => riskChartColor(f.risk)),
            borderRadius: 4,
          }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: { 
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: (items) => top10[items[0].dataIndex].filename,
                label: (item) => ` Risk: ${item.raw}% (${top10[item.dataIndex]._tier})`
              }
            }
          },
          scales: {
            x: { min: 0, max: 100, title: { display: true, text: 'Risk Probability (%)', font: { size: 10 } } },
            y: { grid: { display: false }, ticks: { font: { size: 10 } } }
          }
        }
      });
    },

    _buildROC() {
      const ctx = safeCanvas('rocCurveChart');
      if (!ctx) return;
      
      // Use real ROC data from API
      const rocData = this.overview?.roc_curve;
      if (!rocData || !rocData.has_labels || !rocData.points || rocData.points.length === 0) {
        // Show "No data available" message
        this.charts.roc = destroyChart(this.charts.roc);
        this.charts.roc = new Chart(ctx, {
          type: 'line',
          data: {
            datasets: [{
              label: 'No data available',
              data: [{x: 0, y: 0}],
              borderColor: '#94a3b8',
              borderWidth: 2,
              pointRadius: 0,
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              title: { display: true, text: 'ROC Curve - No Data Available', font: { size: 13, weight: '600' } },
              legend: { display: false }
            },
            scales: {
              x: { type: 'linear', min: 0, max: 1, title: { display: true, text: 'False Positive Rate' } },
              y: { min: 0, max: 1, title: { display: true, text: 'True Positive Rate' } }
            }
          }
        });
        return;
      }

      // Validate points structure
      const validPoints = rocData.points.filter(p => 
        typeof p.x === 'number' && typeof p.y === 'number' && 
        !isNaN(p.x) && !isNaN(p.y) && 
        p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1
      );

      if (validPoints.length === 0) {
        console.warn('ROC curve: No valid points found');
        return;
      }

      this.charts.roc = destroyChart(this.charts.roc);
      this.charts.roc = new Chart(ctx, {
        type: 'line',
        data: {
          datasets: [
            {
              label: 'Model ROC',
              data: validPoints,
              borderColor: '#4F46E5',
              borderWidth: 2.5,
              pointRadius: 0,
              fill: false,
              tension: 0.1
            },
            {
              label: 'Random',
              data: [{x: 0, y: 0}, {x: 1, y: 1}],
              borderColor: '#94a3b8',
              borderDash: [5, 5],
              pointRadius: 0,
              fill: false
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { 
            title: { 
              display: true, 
              text: `ROC Curve (AUC: ${rocData.auc || 'N/A'})`,
              font: { size: 13, weight: '600' }
            },
            legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
          },
          scales: {
            x: { type: 'linear', min: 0, max: 1, title: { display: true, text: 'False Positive Rate', font: { size: 10 } } },
            y: { min: 0, max: 1, title: { display: true, text: 'True Positive Rate', font: { size: 10 } } }
          }
        }
      });
    },

    _buildPR() {
      const ctx = safeCanvas('prCurveChart');
      if (!ctx) return;
      
      // Use real PR curve data from API
      const prData = this.overview?.pr_curve;
      if (!prData || !prData.has_labels || !prData.points || prData.points.length === 0) {
        // Show "No data available" message
        this.charts.pr = destroyChart(this.charts.pr);
        this.charts.pr = new Chart(ctx, {
          type: 'line',
          data: {
            datasets: [{
              label: 'No data available',
              data: [{x: 0, y: 0}],
              borderColor: '#94a3b8',
              borderWidth: 2,
              pointRadius: 0,
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              title: { display: true, text: 'Precision-Recall Curve - No Data Available', font: { size: 13, weight: '600' } },
              legend: { display: false }
            },
            scales: {
              x: { type: 'linear', min: 0, max: 1, title: { display: true, text: 'Recall' } },
              y: { min: 0, max: 1, title: { display: true, text: 'Precision' } }
            }
          }
        });
        return;
      }

      // Validate points structure
      const validPoints = prData.points.filter(p => 
        typeof p.x === 'number' && typeof p.y === 'number' && 
        !isNaN(p.x) && !isNaN(p.y) && 
        p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1
      );

      if (validPoints.length === 0) {
        console.warn('PR curve: No valid points found');
        return;
      }

      this.charts.pr = destroyChart(this.charts.pr);
      this.charts.pr = new Chart(ctx, {
        type: 'line',
        data: {
          datasets: [{
            label: 'Precision-Recall',
            data: validPoints,
            borderColor: '#10B981',
            borderWidth: 2.5,
            pointRadius: 0,
            fill: false,
            tension: 0.1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { 
            title: { 
              display: true, 
              text: 'Precision-Recall Curve',
              font: { size: 13, weight: '600' }
            },
            legend: { display: false }
          },
          scales: {
            x: { type: 'linear', min: 0, max: 1, title: { display: true, text: 'Recall', font: { size: 10 } } },
            y: { min: 0, max: 1, title: { display: true, text: 'Precision', font: { size: 10 } } }
          }
        }
      });
    },

    _buildImportance() {
      const ctx = safeCanvas('featureImportanceChart');
      if (!ctx) return;
      
      // Use real importance data from API
      const importanceData = this.overview?.feature_importance || [];
      if (!importanceData || importanceData.length === 0) {
        // Fallback to API call if not in overview
        fetch('/api/importance')
          .then(r => r.ok ? r.json() : [])
          .then(data => {
            const top8 = data.slice(0, 8);
            this._renderImportanceChart(ctx, top8);
          })
          .catch(err => {
            console.warn('Failed to fetch feature importance:', err);
            this._renderImportanceChart(ctx, []);
          });
        return;
      }
      
      this._renderImportanceChart(ctx, importanceData.slice(0, 8));
    },
    
    _renderImportanceChart(ctx, data) {
      if (!data || data.length === 0) {
        // Show "No data available" message
        this.charts.importance = destroyChart(this.charts.importance);
        this.charts.importance = new Chart(ctx, {
          type: 'bar',
          data: {
            datasets: [{
              label: 'No data available',
              data: [],
              backgroundColor: '#94a3b8',
              borderRadius: 4,
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              title: { display: true, text: 'Feature Importance - No Data Available', font: { size: 13, weight: '600' } },
              legend: { display: false }
            },
            scales: {
              x: { beginAtZero: true, title: { display: true, text: 'Importance' } },
              y: { grid: { display: false } }
            }
          }
        });
        return;
      }
      
      this.charts.importance = destroyChart(this.charts.importance);
      this.charts.importance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: data.map(d => featureLabel(d.feature)),
          datasets: [{
            label: 'Mean |SHAP|',
            data: data.map(d => d.value),
            backgroundColor: '#6366F1',
            borderRadius: 4,
          }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: { 
            legend: { display: false },
            title: { display: true, text: 'Feature Importance (SHAP)', font: { size: 13, weight: '600' } }
          },
          scales: {
            x: { beginAtZero: true, title: { display: true, text: 'Importance' } },
            y: { grid: { display: false } }
          }
        }
      });
    },

    _buildConfusionMatrix() {
      const ctx = safeCanvas('confusionMatrixChart');
      if (!ctx) return;
      
      // Use real confusion matrix data from API
      const cmData = this.overview?.confusion_matrix;
      if (!cmData || !cmData.has_labels) {
        // Show "No data available" message
        this.charts.confusion = destroyChart(this.charts.confusion);
        this.charts.confusion = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: ['No labels available'],
            datasets: [{
              label: 'No data',
              data: [0],
              backgroundColor: ['#94a3b8'],
              borderRadius: 4,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              title: { display: true, text: 'Confusion Matrix - No Data Available', font: { size: 13, weight: '600' } },
              legend: { display: false }
            },
            scales: {
              y: { beginAtZero: true },
              x: { grid: { display: false } }
            }
          }
        });
        return;
      }

      // Use bar chart for confusion matrix (more reliable than matrix type)
      this.charts.confusion = destroyChart(this.charts.confusion);
      this.charts.confusion = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['True Negative', 'False Positive', 'False Negative', 'True Positive'],
          datasets: [{
            label: 'Count',
            data: [cmData.tn, cmData.fp, cmData.fn, cmData.tp],
            backgroundColor: ['#3B82F6', '#F59E0B', '#EF4444', '#10B981'],
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { 
            title: { display: true, text: 'Confusion Matrix', font: { size: 13, weight: '600' } },
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (context) => {
                  const labels = ['True Negative (Correct)', 'False Positive (Error)', 'False Negative (Missed)', 'True Positive (Correct)'];
                  return `${labels[context.dataIndex]}: ${context.raw}`;
                }
              }
            }
          },
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'Count' } },
            x: { grid: { display: false } }
          }
        }
      });
    },
  }));
}

document.addEventListener('alpine:init', registerAlpineComponents);
