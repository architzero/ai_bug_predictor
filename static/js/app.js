'use strict';

/* ═══════════════════════════════════════════════════════════════════════════
   FEATURE NAME MAP  — raw internal name → human-readable label
═══════════════════════════════════════════════════════════════════════════ */
const FEATURE_LABELS = {
  avg_complexity:          'Code Complexity',
  complexity_density:      'Complexity Density',
  loc_per_function:        'Lines per Function',
  max_complexity:          'Peak Function Complexity',
  function_count:          'Function Count',
  loc:                     'File Size (LOC)',
  commits:                 'Total Commits',
  lines_added:             'Lines Added',
  lines_deleted:           'Lines Deleted',
  churn:                   'Change Frequency',
  max_added:               'Peak Change Size',
  author_count:            'Unique Authors',
  commits_2w:              'Commits (2 weeks)',
  commits_1m:              'Recent Activity (1 mo)',
  commits_3m:              'Activity (3 months)',
  recent_churn_ratio:      'Change Intensity',
  recent_activity_score:   'Recent Activity Score',
  instability_score:       'Instability Score',
  avg_commit_size:         'Avg Change Size',
  max_commit_size:         'Peak Commit Size',
  max_commit_ratio:        'Large Commit Ratio',
  ownership:               'Code Ownership',
  minor_contributor_ratio: 'Minor Contributor Ratio',
  low_history_flag:        'Low History Flag',
  file_age_bucket:         'File Age',
  days_since_last_change:  'Days Since Last Change',
  recency_ratio:           'Recency Ratio',
  bug_fixes:               'Bug History',
  bug_density:             'Bug Density',
  coupling_risk:           'Coupling Risk',
  temporal_bug_risk:       'Temporal Bug Risk',
};

const GLOSSARY = [
  { term: 'Code Complexity',        def: 'Cyclomatic complexity — how many independent execution paths exist. Higher values mean harder-to-maintain code.' },
  { term: 'Change Frequency',       def: 'How often this file has been modified over its lifetime. Frequently changed files tend to accumulate bugs.' },
  { term: 'Change Intensity',       def: 'Speed of recent changes relative to historical average. A sudden spike signals instability.' },
  { term: 'Recent Activity',        def: 'Number of commits touching this file in the last 30 days.' },
  { term: 'Bug History',            def: 'Number of times this file was involved in a bug-fix commit (detected via SZZ algorithm).' },
  { term: 'Code Ownership',         def: 'Fraction of commits made by the single most active author. Low ownership = many hands = higher risk.' },
  { term: 'Minor Contributor Ratio',def: 'Proportion of authors who made fewer than 5% of commits. High ratio correlates with bugs.' },
  { term: 'Instability Score',      def: 'Composite measure of how volatile the file is — combines churn, commit size, and recency.' },
  { term: 'File Age',               def: 'How long the file has existed in the repository. Older files have more accumulated complexity.' },
  { term: 'Coupling Risk',          def: 'How often this file changes together with other files. High coupling increases blast radius of bugs.' },
];

function featureLabel(raw) {
  return FEATURE_LABELS[raw] || raw.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/* ═══════════════════════════════════════════════════════════════════════════
   STATE
═══════════════════════════════════════════════════════════════════════════ */
let filesData = [];
let charts    = {};
let selectedRow = null;

/* ═══════════════════════════════════════════════════════════════════════════
   BOOT
═══════════════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initTooltips();
  buildGlossary();

  document.getElementById('btn-scan').addEventListener('click', handleScan);
  document.getElementById('btn-simulate').addEventListener('click', handleSimulate);
  document.getElementById('search-input').addEventListener('input', handleSearch);
  document.getElementById('risk-filter').addEventListener('change', handleSearch);

  loadOverview();
  loadFiles();
  loadImportance();
});

/* ═══════════════════════════════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════════════════════════════ */
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.remove('hidden');
    });
  });
}

/* ═══════════════════════════════════════════════════════════════════════════
   TOOLTIPS
═══════════════════════════════════════════════════════════════════════════ */
function initTooltips() {
  const box = document.getElementById('tooltip');
  document.addEventListener('mouseover', e => {
    const el = e.target.closest('.tip');
    if (!el) return;
    const text = el.getAttribute('title') || el.getAttribute('data-tip') || '';
    if (!text) return;
    el.removeAttribute('title');
    el.setAttribute('data-tip', text);
    box.textContent = text;
    box.classList.remove('hidden');
  });
  document.addEventListener('mousemove', e => {
    const box = document.getElementById('tooltip');
    if (box.classList.contains('hidden')) return;
    box.style.left = (e.clientX + 14) + 'px';
    box.style.top  = (e.clientY + 14) + 'px';
  });
  document.addEventListener('mouseout', e => {
    if (!e.target.closest('.tip')) return;
    document.getElementById('tooltip').classList.add('hidden');
  });
}

/* ═══════════════════════════════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════════════════════════════ */
function riskClass(v) {
  if (v >= 0.70) return 'high';
  if (v >= 0.50) return 'medium';
  return 'low';
}
function riskLabel(v) {
  if (v >= 0.70) return 'High Risk';
  if (v >= 0.50) return 'Medium Risk';
  return 'Low Risk';
}
function riskColor(v) {
  if (v >= 0.70) return 'red';
  if (v >= 0.50) return 'orange';
  return 'green';
}
function pct(v) { return (v * 100).toFixed(1) + '%'; }

/* ═══════════════════════════════════════════════════════════════════════════
   OVERVIEW — stat cards + histogram + donut
═══════════════════════════════════════════════════════════════════════════ */
async function loadOverview() {
  try {
    const res  = await fetch('/api/overview');
    const data = await res.json();
    renderStatCards(data.metrics);
    drawHistogram(data.histogram);
    drawDonut(data.histogram);
  } catch(e) { console.error('overview', e); }
}

function renderStatCards(m) {
  const high   = filesData.filter(f => f.risk >= 0.70).length;
  const medium = filesData.filter(f => f.risk >= 0.50 && f.risk < 0.70).length;

  document.getElementById('stat-row').innerHTML = `
    <div class="stat-card">
      <div class="stat-lbl">Files Analyzed</div>
      <div class="stat-val">${m.files_analyzed.toLocaleString()}</div>
    </div>
    <div class="stat-card">
      <div class="stat-lbl">High Risk Files</div>
      <div class="stat-val red">${high}</div>
      <div class="stat-sub">risk ≥ 70%</div>
    </div>
    <div class="stat-card">
      <div class="stat-lbl">Buggy Files</div>
      <div class="stat-val ${m.buggy_count > 0 ? 'red' : ''}">${m.buggy_count}</div>
      <div class="stat-sub">labeled by SZZ</div>
    </div>
    <div class="stat-card">
      <div class="stat-lbl">Avg Risk Score</div>
      <div class="stat-val accent">${pct(m.avg_risk)}</div>
    </div>
    <div class="stat-card">
      <div class="stat-lbl">Defect Capture</div>
      <div class="stat-val green">${m.defect_at_20}%</div>
      <div class="stat-sub">bugs caught in top 20%</div>
    </div>
  `;
}

function drawHistogram(hist) {
  const ctx = document.getElementById('c-histogram').getContext('2d');
  if (charts.histogram) charts.histogram.destroy();

  const labels = hist.map(d => d.bin);
  const counts = hist.map(d => d.count);

  // colour each bar by risk zone
  const colors = labels.map(b => {
    const v = parseFloat(b);
    if (v >= 0.70) return 'rgba(224,92,92,0.75)';
    if (v >= 0.50) return 'rgba(232,148,58,0.75)';
    return 'rgba(62,207,142,0.6)';
  });

  charts.histogram = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ data: counts, backgroundColor: colors, borderRadius: 3, borderSkipped: false }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a2840', borderColor: '#253447', borderWidth: 1,
          titleColor: '#6b7f96', bodyColor: '#c9d1d9',
          callbacks: { title: c => `Risk ${c[0].label}–${(parseFloat(c[0].label)+0.05).toFixed(2)}`, label: c => ` ${c.raw} files` }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#6b7f96', maxRotation: 45, minRotation: 45, font: { size: 10 } } },
        y: { grid: { color: '#1e2d3d', borderDash: [3,3] }, ticks: { color: '#6b7f96', font: { size: 10 } }, beginAtZero: true }
      }
    }
  });
}

function drawDonut(hist) {
  const ctx = document.getElementById('c-donut').getContext('2d');
  if (charts.donut) charts.donut.destroy();

  let low = 0, med = 0, high = 0;
  hist.forEach(d => {
    const v = parseFloat(d.bin);
    if (v >= 0.70) high += d.count;
    else if (v >= 0.50) med += d.count;
    else low += d.count;
  });

  charts.donut = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Low Risk', 'Medium Risk', 'High Risk'],
      datasets: [{ data: [low, med, high], backgroundColor: ['#0a2e1e','#3a2010','#3a1010'], borderColor: ['#3ecf8e','#e8943a','#e05c5c'], borderWidth: 2, hoverOffset: 4 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '68%',
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: '#1a2840', borderColor: '#253447', borderWidth: 1, bodyColor: '#c9d1d9' }
      }
    }
  });

  document.getElementById('donut-legend').innerHTML = [
    { label: 'Low', color: '#3ecf8e', count: low },
    { label: 'Medium', color: '#e8943a', count: med },
    { label: 'High', color: '#e05c5c', count: high },
  ].map(i => `<div class="leg-item"><div class="leg-dot" style="background:${i.color}"></div>${i.label} (${i.count})</div>`).join('');
}

/* ═══════════════════════════════════════════════════════════════════════════
   FILES TABLE
═══════════════════════════════════════════════════════════════════════════ */
async function loadFiles() {
  try {
    const res = await fetch('/api/files');
    filesData = await res.json();
    renderTable(filesData);
    // re-render stat cards now that filesData is populated
    const ovRes  = await fetch('/api/overview');
    const ovData = await ovRes.json();
    renderStatCards(ovData.metrics);
  } catch(e) { console.error('files', e); }
}

function renderTable(data) {
  const tbody = document.getElementById('files-tbody');
  if (!data.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="5">No files found.</td></tr>';
    return;
  }
  tbody.innerHTML = data.map(row => {
    const rc = riskClass(row.risk);
    return `
      <tr data-id="${esc(row.id)}" onclick="selectFile(this,'${esc(row.id)}')">
        <td>
          <span class="td-repo">${esc(row.repo)}</span>
          <span class="td-file" title="${esc(row.filename)}">${esc(row.filename)}</span>
        </td>
        <td><span class="pill ${rc}">${pct(row.risk)}</span></td>
        <td class="td-num">${row.complexity}</td>
        <td class="td-num hide-sm">${row.commits_1m}</td>
        <td class="hide-md">${row.buggy ? '<span class="badge-bug">Buggy</span>' : '<span class="badge-ok">Clean</span>'}</td>
      </tr>`;
  }).join('');
}

function handleSearch() {
  const q      = document.getElementById('search-input').value.toLowerCase();
  const filter = document.getElementById('risk-filter').value;
  const result = filesData.filter(f => {
    const matchText = !q || f.filename.toLowerCase().includes(q) || f.repo.toLowerCase().includes(q);
    const matchRisk = filter === 'all'
      || (filter === 'high'   && f.risk >= 0.70)
      || (filter === 'medium' && f.risk >= 0.50 && f.risk < 0.70)
      || (filter === 'low'    && f.risk < 0.50);
    return matchText && matchRisk;
  });
  renderTable(result);
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ═══════════════════════════════════════════════════════════════════════════
   FILE DETAIL
═══════════════════════════════════════════════════════════════════════════ */
async function selectFile(tr, fileId) {
  // highlight row
  document.querySelectorAll('#files-tbody tr').forEach(r => r.classList.remove('selected'));
  tr.classList.add('selected');

  document.getElementById('detail-blank').classList.add('hidden');
  const body = document.getElementById('detail-body');
  body.classList.remove('hidden');
  body.style.opacity = '0.4';

  try {
    const res  = await fetch('/api/file?id=' + encodeURIComponent(fileId));
    const data = await res.json();
    if (data.error) { body.style.opacity = '1'; return; }

    // filepath + repo
    document.getElementById('d-filepath').textContent = data.filepath;
    const repoName = fileId.split(/[\\/]/).slice(-2, -1)[0] || '';
    document.getElementById('d-repo').textContent = repoName;

    // gauges
    const rc = riskColor(data.risk);
    document.getElementById('d-risk').textContent = pct(data.risk);
    document.getElementById('d-risk').className   = `gauge-val ${rc}`;
    document.getElementById('d-tier').textContent = riskLabel(data.risk);

    // find complexity from filesData
    const fileRow = filesData.find(f => f.id === fileId);
    document.getElementById('d-cx').textContent = fileRow ? fileRow.complexity : '—';

    // structured explanation
    renderExplanation(data.risk, data.shap);

    // SHAP bars
    renderShap(data.shap);

    // actions
    renderActions(data.risk, data.shap);

    // functions
    renderFunctions(data.top_funcs);

  } catch(e) { console.error('file detail', e); }
  finally    { body.style.opacity = '1'; }
}

function renderExplanation(risk, shap) {
  const drivers = shap.positive.slice(0, 3).map(s => featureLabel(s.feature));

  let summary = '';
  if (risk >= 0.70) {
    summary = drivers.length
      ? `This file is <strong>high risk</strong> — primarily driven by ${drivers.join(', ')}.`
      : 'This file is <strong>high risk</strong> based on multiple combined factors.';
  } else if (risk >= 0.50) {
    summary = drivers.length
      ? `This file has <strong>moderate risk</strong> — watch ${drivers[0] || 'recent changes'}.`
      : 'This file has moderate risk.';
  } else {
    summary = 'This file is <strong>low risk</strong>. No major concerns detected.';
  }
  document.getElementById('d-summary').innerHTML = summary;

  const bullets = shap.positive.slice(0, 4).map(s => {
    const lbl = featureLabel(s.feature);
    const intensity = s.value > 0.1 ? 'high' : 'elevated';
    return `<div class="bullet"><div class="bdot red"></div><span>${lbl} is ${intensity} — increases bug probability</span></div>`;
  }).concat(
    shap.negative.slice(0, 2).map(s => {
      const lbl = featureLabel(s.feature);
      return `<div class="bullet"><div class="bdot green"></div><span>${lbl} is favorable — reduces risk</span></div>`;
    })
  );
  document.getElementById('d-bullets').innerHTML = bullets.join('') || '<div class="bullet"><div class="bdot orange"></div><span>Insufficient SHAP data for detailed breakdown.</span></div>';
}

function renderShap(shap) {
  const all = [
    ...shap.positive.map(s => ({ ...s, dir: 'pos' })),
    ...shap.negative.map(s => ({ ...s, dir: 'neg' })),
  ];
  const maxAbs = Math.max(...all.map(s => Math.abs(s.value)), 0.001);

  if (!all.length) {
    document.getElementById('d-shap').innerHTML = '<div style="font-size:12px;color:var(--faint)">No SHAP data available.</div>';
    return;
  }

  document.getElementById('d-shap').innerHTML = all.map(s => {
    const w   = (Math.abs(s.value) / maxAbs * 100).toFixed(1);
    const pos = s.dir === 'pos';
    const sign = pos ? '+' : '';
    return `
      <div class="shap-row">
        <div class="shap-lbl" title="${esc(featureLabel(s.feature))}">${esc(featureLabel(s.feature))}</div>
        <div class="shap-track"><div class="${pos ? 'shap-fill-pos' : 'shap-fill-neg'}" style="width:${w}%"></div></div>
        <div class="shap-num ${pos ? 'pos' : 'neg'}">${sign}${s.value.toFixed(2)}</div>
      </div>`;
  }).join('');
}

function renderActions(risk, shap) {
  const actions = [];
  const topFeatures = shap.positive.map(s => s.feature);

  if (topFeatures.some(f => f.includes('complexity'))) actions.push('Refactor complex functions into smaller units');
  if (topFeatures.some(f => f.includes('churn') || f.includes('commit'))) actions.push('Review recent commits for unintended side effects');
  if (topFeatures.some(f => f.includes('ownership') || f.includes('contributor'))) actions.push('Assign a primary owner and improve documentation');
  if (topFeatures.some(f => f.includes('bug'))) actions.push('Add regression tests for previously fixed bugs');
  if (risk >= 0.70) actions.push('Prioritize this file in the next code review');
  if (!actions.length) actions.push('No specific actions required — maintain current quality');

  document.getElementById('d-actions').innerHTML = actions.map(a =>
    `<div class="action-item"><span class="action-arrow">→</span>${a}</div>`
  ).join('');
}

function renderFunctions(funcs) {
  if (!funcs || !funcs.length) {
    document.getElementById('d-funcs').innerHTML = '<div style="font-size:12px;color:var(--faint)">No function data available.</div>';
    return;
  }
  document.getElementById('d-funcs').innerHTML = funcs.map(f =>
    `<div class="func-item">
       <span class="func-name" title="${esc(f.name)}">↳ ${esc(f.name)}</span>
       <span class="func-meta">cx=${f.cx} · ${f.len} lines</span>
     </div>`
  ).join('');
}

/* ═══════════════════════════════════════════════════════════════════════════
   GLOBAL IMPORTANCE CHART
═══════════════════════════════════════════════════════════════════════════ */
async function loadImportance() {
  try {
    const res  = await fetch('/api/importance');
    const data = await res.json();
    drawImportance(data);
  } catch(e) { console.error('importance', e); }
}

function drawImportance(data) {
  const ctx = document.getElementById('c-importance').getContext('2d');
  if (charts.importance) charts.importance.destroy();

  const labels = data.map(d => featureLabel(d.feature)).reverse();
  const values = data.map(d => d.value).reverse();

  charts.importance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: values.map((_, i) => `rgba(79,142,247,${0.9 - i * 0.06})`),
        borderRadius: 4,
        borderSkipped: false,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a2840', borderColor: '#253447', borderWidth: 1,
          bodyColor: '#c9d1d9',
          callbacks: { label: c => ` SHAP: ${c.raw.toFixed(4)}` }
        }
      },
      scales: {
        x: { grid: { color: '#1e2d3d', borderDash: [3,3] }, ticks: { color: '#6b7f96', font: { size: 11 } } },
        y: { grid: { display: false }, ticks: { color: '#c9d1d9', font: { size: 12 } } }
      }
    }
  });
}

/* ═══════════════════════════════════════════════════════════════════════════
   GLOSSARY
═══════════════════════════════════════════════════════════════════════════ */
function buildGlossary() {
  document.getElementById('glossary').innerHTML = GLOSSARY.map(g =>
    `<div class="glos-item">
       <div class="glos-term">${g.term}</div>
       <div class="glos-def">${g.def}</div>
     </div>`
  ).join('');
}

/* ═══════════════════════════════════════════════════════════════════════════
   COMMIT SIMULATOR
═══════════════════════════════════════════════════════════════════════════ */
async function handleSimulate() {
  const input = document.getElementById('sim-files').value.trim();
  if (!input) return;

  const files = input.split(/[\n,]/).map(s => s.trim()).filter(Boolean);
  const btn   = document.getElementById('btn-simulate');
  btn.disabled = true;
  btn.textContent = 'Predicting…';

  try {
    const res  = await fetch('/api/predict_commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files })
    });
    const data = await res.json();

    const box = document.getElementById('sim-result');
    box.classList.remove('hidden');

    const score = document.getElementById('sim-score');
    score.textContent = pct(data.risk);
    score.className   = 'sim-score ' + riskColor(data.risk);

    const bar = document.getElementById('sim-bar');
    bar.style.width      = (data.risk * 100) + '%';
    bar.style.background = data.risk >= 0.70 ? 'var(--red)' : data.risk >= 0.50 ? 'var(--orange)' : 'var(--green)';

    document.getElementById('sim-driver').textContent = data.main_driver || '—';

    document.getElementById('sim-chips').innerHTML = (data.matched_files || [])
      .map(f => `<span class="chip">${esc(f)}</span>`).join('');

  } catch(e) { console.error('simulate', e); }
  finally {
    btn.disabled = false;
    btn.textContent = 'Predict Commit Risk';
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   SCAN REPO
═══════════════════════════════════════════════════════════════════════════ */
async function handleScan() {
  const path = document.getElementById('scan-path').value.trim();
  if (!path) return;

  const btn    = document.getElementById('btn-scan');
  const banner = document.getElementById('scan-banner');
  const status = document.getElementById('status-text');

  btn.disabled = true;
  btn.textContent = 'Scanning…';
  banner.classList.remove('hidden');
  status.textContent = 'Scanning…';

  // skeleton cards
  document.getElementById('stat-row').innerHTML = Array(5).fill('<div class="stat-card skel"></div>').join('');

  try {
    const res  = await fetch('/api/scan_repo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    const data = await res.json();

    if (data.error) {
      alert('Scan failed: ' + data.error);
    } else {
      await loadFiles();
      await loadOverview();
      await loadImportance();
    }
  } catch(e) {
    console.error('scan', e);
    alert('Scan failed — check the console for details.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Scan';
    banner.classList.add('hidden');
    status.textContent = 'Online';
  }
}
