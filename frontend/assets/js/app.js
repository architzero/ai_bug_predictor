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

// Percentile-based tier assignment — matches backend logic exactly:
// CRITICAL = top 10%, HIGH = 10–25%, MODERATE = 25–50%, LOW = bottom 50%
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
  // Return in original order (sorted by risk desc already)
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
    _chartsInitialized: false,
    charts: { histogram: null, cumGain: null, importance: null, recency: null, confusion: null },

    async init() {
      if (!this.scanId) {
        this.error = 'No scan ID provided. Please start a new scan.';
        this.isLoading = false;
        return;
      }

      try {
        const res = await fetch(`/api/scan_results/${this.scanId}`);
        if (!res.ok) {
          if (res.status === 404) throw new Error('Scan results not found or expired (results kept for 1 hour). Please run a new scan.');
          throw new Error(`Server error ${res.status}`);
        }

        const data = await res.json();

        if (!data.files || data.files.length === 0) {
          this.error = 'Scan completed but no source files were found.';
          this.isLoading = false;
          return;
        }

        this.overview      = { metrics: data.metrics };
        this.repoName      = data.repo_name || 'Unknown Repository';
        // Apply percentile-based tiers matching backend logic
        this.originalFiles = assignPercentileTiers(data.files);
        this.applyFilters();

        this.$watch('searchQuery', () => this.applyFilters());

        this.$nextTick(() => {
          setTimeout(() => this.initCharts(), 400);
        });

      } catch (err) {
        this.error = err.message;
      } finally {
        this.isLoading = false;
      }
    },

    // ── Computed ──────────────────────────────────────────────────────────────
    get highRiskCount() {
      return this.originalFiles.filter(f => f._tier === 'CRITICAL' || f._tier === 'HIGH').length;
    },

    // Tier counts using percentile-based assignment (matches backend)
    get tierCounts() {
      return {
        critical: this.originalFiles.filter(f => f._tier === 'CRITICAL').length,
        high:     this.originalFiles.filter(f => f._tier === 'HIGH').length,
        moderate: this.originalFiles.filter(f => f._tier === 'MODERATE').length,
        low:      this.originalFiles.filter(f => f._tier === 'LOW').length,
      };
    },

    // ── Filtering & sorting ───────────────────────────────────────────────────
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

    // ── Risk helpers exposed to template ─────────────────────────────────────
    getRiskBadgeClass(file) {
      // Use percentile tier if available, fall back to score-based
      if (file && file._tier) return tierBadgeClass(file._tier);
      return riskBadgeClass(file?.risk ?? file ?? 0);
    },
    getTextColor: riskTextClass,
    getTierBadge: tierBadgeClass,

    // ── File detail panel ─────────────────────────────────────────────────────
    async selectFile(fileId) {
      this.selectedFileId      = fileId;
      this.selectedFileDetails = null;
      this.isPanelOpen         = true;

      try {
        const res = await fetch(`/api/file?id=${encodeURIComponent(fileId)}&scan_id=${encodeURIComponent(this.scanId)}`);
        if (!res.ok) throw new Error('Failed to fetch file details');
        const details = await res.json();

        // Attach tier from originalFiles
        const fileObj = this.originalFiles.find(f => f.id === fileId);
        details._tier = fileObj?._tier || null;

        // Build human-readable explanation from SHAP values
        details.explanation = buildExplanation(details.shap);

        // Translate raw feature names to human labels in SHAP arrays
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

    // ── Chart initialisation ──────────────────────────────────────────────────
    initCharts() {
      if (this._chartsInitialized) return;
      if (!this.originalFiles || this.originalFiles.length === 0) return;
      this._chartsInitialized = true;

      this._buildHistogram();
      this._buildCumulativeGain();
      this._buildImportance();
      this._buildRiskRecency();
      this._buildConfusionMatrix();
    },

    _buildHistogram() {
      const ctx = safeCanvas('riskHistogram');
      if (!ctx) return;

      // Use percentile tiers for histogram
      const counts = {
        CRITICAL: this.tierCounts.critical,
        HIGH:     this.tierCounts.high,
        MODERATE: this.tierCounts.moderate,
        LOW:      this.tierCounts.low,
      };

      this.charts.histogram = destroyChart(this.charts.histogram);
      this.charts.histogram = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['CRITICAL\n(top 10%)', 'HIGH\n(10–25%)', 'MODERATE\n(25–50%)', 'LOW\n(bottom 50%)'],
          datasets: [{
            label: 'Files',
            data: [counts.CRITICAL, counts.HIGH, counts.MODERATE, counts.LOW],
            backgroundColor: ['#DC2626', '#EA580C', '#D97706', '#16A34A'],
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (item) => ` ${item.raw} file${item.raw !== 1 ? 's' : ''}`,
              },
            },
          },
          scales: {
            y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#f1f5f9' } },
            x: { grid: { display: false } },
          },
        },
      });
    },

    _buildCumulativeGain() {
      const ctx = safeCanvas('cumulativeGainChart');
      if (!ctx) return;

      const sorted    = [...this.originalFiles].sort((a, b) => b.risk - a.risk);
      const totalBugs = sorted.filter(f => f.buggy === 1).length;
      const hasBuggy  = totalBugs > 0;

      let captured = 0;
      const modelPoints = sorted.map((f, i) => {
        if (f.buggy === 1) captured++;
        return {
          x: +((i + 1) / sorted.length * 100).toFixed(1),
          y: hasBuggy ? +(captured / totalBugs * 100).toFixed(1) : +((i + 1) / sorted.length * 100).toFixed(1),
        };
      });

      const randomPoints = [{ x: 0, y: 0 }, { x: 100, y: 100 }];

      this.charts.cumGain = destroyChart(this.charts.cumGain);
      this.charts.cumGain = new Chart(ctx, {
        type: 'line',
        data: {
          datasets: [
            {
              label: 'Model',
              data: modelPoints,
              borderColor: '#4F46E5',
              backgroundColor: 'rgba(79,70,229,0.08)',
              fill: true,
              tension: 0.3,
              pointRadius: 0,
              borderWidth: 2,
            },
            {
              label: 'Random baseline',
              data: randomPoints,
              borderColor: '#94a3b8',
              borderDash: [5, 5],
              pointRadius: 0,
              borderWidth: 1.5,
              fill: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
            tooltip: {
              callbacks: {
                title: (items) => `Review top ${items[0].parsed.x.toFixed(0)}% of files`,
                label: (item) => ` ${item.dataset.label}: catch ${item.parsed.y.toFixed(0)}% of bugs`,
              },
            },
          },
          scales: {
            x: { type: 'linear', min: 0, max: 100, title: { display: true, text: '% Files Reviewed', font: { size: 11 } }, grid: { color: '#f1f5f9' } },
            y: { min: 0, max: 100, title: { display: true, text: '% Bugs Caught', font: { size: 11 } }, grid: { color: '#f1f5f9' } },
          },
        },
      });
    },

    _buildImportance() {
      const ctx = safeCanvas('featureImportanceChart');
      if (!ctx) return;

      const buildFallback = () => {
        const tc = this.tierCounts;
        this.charts.importance = destroyChart(this.charts.importance);
        this.charts.importance = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: ['CRITICAL (top 10%)', 'HIGH (10–25%)', 'MODERATE (25–50%)', 'LOW (bottom 50%)'],
            datasets: [{
              label: 'Files',
              data: [tc.critical, tc.high, tc.moderate, tc.low],
              backgroundColor: ['#DC2626', '#EA580C', '#D97706', '#16A34A'],
              borderRadius: 3,
            }],
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              title: { display: true, text: 'Risk Tier Distribution (percentile)', font: { size: 11 } },
            },
            scales: {
              x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#f1f5f9' } },
              y: { grid: { display: false } },
            },
          },
        });
      };

      fetch('/api/importance')
        .then(r => r.ok ? r.json() : Promise.reject())
        .then(data => {
          if (!Array.isArray(data) || data.length === 0) throw new Error('empty');
          const top8 = data.slice(0, 8);
          this.charts.importance = destroyChart(this.charts.importance);
          this.charts.importance = new Chart(ctx, {
            type: 'bar',
            data: {
              labels: top8.map(d => featureLabel(d.feature)),
              datasets: [{
                label: 'Mean |SHAP|',
                data: top8.map(d => d.value),
                backgroundColor: '#4F46E5',
                borderRadius: 3,
              }],
            },
            options: {
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              plugins: { legend: { display: false } },
              scales: {
                x: { beginAtZero: true, title: { display: true, text: 'Mean |SHAP|', font: { size: 10 } }, grid: { color: '#f1f5f9' } },
                y: { grid: { display: false }, ticks: { font: { size: 10 } } },
              },
            },
          });
        })
        .catch(() => buildFallback());
    },

    _buildRiskRecency() {
      const ctx = safeCanvas('riskRecencyChart');
      if (!ctx) return;

      const points = this.originalFiles
        .filter(f => f.days_since_last_change !== undefined && f.days_since_last_change !== null)
        .map(f => ({
          x: f.days_since_last_change,
          y: +(f.risk * 100).toFixed(1),
          filename: f.filename,
          risk: f.risk,
        }));

      if (points.length === 0) {
        ctx.parentElement.innerHTML = '<div class="h-48 flex items-center justify-center text-gray-400 text-sm">No recency data available</div>';
        return;
      }

      this.charts.recency = destroyChart(this.charts.recency);
      this.charts.recency = new Chart(ctx, {
        type: 'scatter',
        data: {
          datasets: [{
            label: 'Files',
            data: points,
            backgroundColor: points.map(p => riskChartColor(p.risk) + 'aa'),
            borderColor: points.map(p => riskChartColor(p.risk)),
            borderWidth: 1,
            pointRadius: 5,
            pointHoverRadius: 7,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (item) => `${item.raw.filename}: ${item.raw.y}% risk, ${item.raw.x}d ago`,
              },
            },
          },
          scales: {
            x: { title: { display: true, text: 'Days Since Last Change', font: { size: 11 } }, grid: { color: '#f1f5f9' } },
            y: { min: 0, max: 100, title: { display: true, text: 'Risk Score (%)', font: { size: 11 } }, grid: { color: '#f1f5f9' } },
          },
        },
      });
    },

    _buildConfusionMatrix() {
      const ctx = safeCanvas('confusionMatrixChart');
      if (!ctx) return;

      const hasBuggy = this.originalFiles.some(f => f.buggy !== undefined && f.buggy !== null);
      if (!hasBuggy) {
        ctx.parentElement.innerHTML = '<div class="h-48 flex items-center justify-center text-gray-400 text-sm text-center px-4">Model validation unavailable<br>(no ground truth labels in this scan)</div>';
        return;
      }

      const tp = this.originalFiles.filter(f => f.buggy === 1 && f.risk >= 0.5).length;
      const fp = this.originalFiles.filter(f => f.buggy === 0 && f.risk >= 0.5).length;
      const tn = this.originalFiles.filter(f => f.buggy === 0 && f.risk < 0.5).length;
      const fn = this.originalFiles.filter(f => f.buggy === 1 && f.risk < 0.5).length;

      const precision = tp + fp > 0 ? (tp / (tp + fp) * 100).toFixed(0) : 0;
      const recall    = tp + fn > 0 ? (tp / (tp + fn) * 100).toFixed(0) : 0;

      this.charts.confusion = destroyChart(this.charts.confusion);
      this.charts.confusion = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: [
            `True Positive (${tp})`,
            `False Positive (${fp})`,
            `True Negative (${tn})`,
            `False Negative (${fn})`,
          ],
          datasets: [{
            data: [tp, fp, tn, fn],
            backgroundColor: ['#16A34A', '#EA580C', '#3B82F6', '#DC2626'],
            borderWidth: 0,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '65%',
          plugins: {
            legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } },
            tooltip: { callbacks: { label: (item) => ` ${item.label}` } },
          },
        },
        plugins: [{
          id: 'centerText',
          afterDraw(chart) {
            const { ctx: c, chartArea: { left, top, right, bottom } } = chart;
            const cx = (left + right) / 2;
            const cy = (top + bottom) / 2;
            c.save();
            c.textAlign = 'center';
            c.fillStyle = '#1e293b';
            c.font = 'bold 14px sans-serif';
            c.fillText(`P: ${precision}%`, cx, cy - 8);
            c.font = '12px sans-serif';
            c.fillStyle = '#64748b';
            c.fillText(`R: ${recall}%`, cx, cy + 10);
            c.restore();
          },
        }],
      });
    },
  }));
}

// ─── Bootstrap ────────────────────────────────────────────────────────────────
document.addEventListener('alpine:init', registerAlpineComponents);
