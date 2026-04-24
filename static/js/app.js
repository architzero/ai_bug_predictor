// =========================================================
// AI Risk Intelligence UI Controller
// =========================================================

Chart.defaults.color = '#888888';
Chart.defaults.font.family = "'Inter', sans-serif";

const COLORS = {
    danger: '#ff453a',
    warning: '#ff9f0a',
    success: '#32d74b',
    brand: '#0A84FF',
    border: '#222222'
};

// --- Dictionary for Narratives ---
const DICTIONARY = {
    "avg_complexity": { name: "Code Complexity", narrative: "The file's functions contain complex decision-making logic.", action: "Refactor to split large complex functions." },
    "complexity_density": { name: "Complexity Density", narrative: "Extreme amount of complex logic crammed into too few lines.", action: "Untangle logic paths." },
    "commits": { name: "Total Commits", narrative: "The file is modified constantly throughout history.", action: "Assess if this file has become a 'God Object'." },
    "recent_churn_ratio": { name: "Change Intensity", narrative: "Experiencing unusually high modification rates recently.", action: "Code freeze recommended." },
    "author_count": { name: "Contributors", narrative: "High variance in contributors modifying this file.", action: "Assign a strict code owner." },
    "minor_contributor_ratio": { name: "Minor Contributor Edits", narrative: "Recent edits made by infrequent contributors.", action: "Senior review required." },
    "instability_score": { name: "Instability Score", narrative: "Churn volume is massive compared to file size.", action: "Increase unit test coverage." },
    "coupled_recent_missing": { name: "Coupling Warning", narrative: "Part of a coupled network but related files not updated.", action: "Check linked schemas/types." },
    "commit_burst_score": { name: "Burst Commits", narrative: "Frantic clustered edits within very short time windows.", action: "Review rushed hotfixes." },
    "temporal_bug_risk": { name: "Prior Bug Pattern", narrative: "Statistically likely to contain a defect based on history.", action: "Extensive regression testing required." },
    "default": { name: "Metric", narrative: "Contributed to elevated risk calculation.", action: "Review code thoroughly." }
};

function getNarrative(key) {
    return DICTIONARY[key] || { name: key, ...DICTIONARY["default"] };
}

function appLog(msg) {
    const t = document.getElementById('terminal-output');
    if (!t) return;
    const time = new Date().toISOString().substring(11,19);
    t.innerHTML += `<br><span style="color:#888;">[${time}]</span> ${msg}`;
    t.scrollTop = t.scrollHeight;
}

// Get CSRF token from meta tag
function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

// --- Toast Notifications ---
function showToast(message, type = 'error') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    const bgColor = type === 'error' ? 'bg-red-500/20 border-red-500 text-red-400' : 'bg-green-500/20 border-green-500 text-green-400';
    const icon = type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-check';
    
    toast.className = `flex items-center gap-3 px-4 py-3 border rounded-lg shadow-lg ${bgColor} transform transition-all duration-300 translate-x-full opacity-0`;
    toast.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <span class="font-medium text-sm">${message}</span>
        <button class="ml-2 text-gray-400 hover:text-white" onclick="this.parentElement.remove()">
            <i class="fa-solid fa-xmark"></i>
        </button>
    `;
    
    container.appendChild(toast);
    
    // Animate in
    requestAnimationFrame(() => {
        toast.classList.remove('translate-x-full', 'opacity-0');
    });
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-x-full');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// --- Chart.js Dashboard Support ---
let riskTrendChart = null;
let bugTypeChart = null;

function initializeDashboardCharts() {
    // Risk Trend Chart
    const riskCtx = document.getElementById('risk-trend-chart');
    if (riskCtx) {
        riskTrendChart = new Chart(riskCtx, {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'High Risk %',
                    data: [12, 15, 18, 14, 16, 11],
                    borderColor: '#ff453a',
                    backgroundColor: 'rgba(255, 69, 58, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#333' },
                        ticks: { color: '#888' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#888' }
                    }
                }
            }
        });
    }

    // Bug Type Chart
    const bugCtx = document.getElementById('bug-type-chart');
    if (bugCtx) {
        bugTypeChart = new Chart(bugCtx, {
            type: 'bar',
            data: {
                labels: ['Logic', 'Memory', 'Security', 'Other'],
                datasets: [{
                    data: [35, 25, 20, 20],
                    backgroundColor: [
                        '#ff453a',
                        '#ff9f0a', 
                        '#32d74b',
                        '#888888'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#333' },
                        ticks: { color: '#888' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#888' }
                    }
                }
            }
        });
    }
}

// --- File Detail Panel Functions ---
function showFileDetailPanel(filepath, risk, language, explanations) {
    const panel = document.getElementById('file-detail-panel');
    if (!panel) return;
    
    // Update panel content
    document.getElementById('detail-filepath').textContent = filepath;
    
    // Show panel
    panel.classList.remove('hidden');
}

function hideFileDetailPanel() {
    const panel = document.getElementById('file-detail-panel');
    if (panel) {
        panel.classList.add('hidden');
    }
}

// --- Landing Page Functions ---
function initializeLandingPage() {
    // Handle analyze button
    const analyzeBtn = document.getElementById('analyze-btn');
    const repoInput = document.getElementById('repo-input');
    
    if (analyzeBtn && repoInput) {
        analyzeBtn.addEventListener('click', () => {
            const repoUrl = repoInput.value.trim();
            if (repoUrl) {
                // Redirect to login, but preserve the requested repo scan
                window.location.href = `/auth/github/login?redirect=${encodeURIComponent('/?scan=' + repoUrl)}`;
            } else {
                showToast("Please enter a valid GitHub repository URL");
            }
        });
        
        // Handle Enter key in input
        repoInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                analyzeBtn.click();
            }
        });
    }
    
    // Handle recent scan view buttons
    document.querySelectorAll('#recent-scans button').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            // Navigate to scan results
            console.log('View scan results');
        });
    });
}

// --- Tabs ---
document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
        document.getElementById(`tab-${btn.dataset.tab}`).classList.remove('hidden');
    });
});

// --- API ---
async function fetchOverview() {
    const res = await fetch("/api/overview");
    const data = await res.json();
    
    // Update metrics
    const m = data.metrics;
    const mPrecision = document.getElementById("m-precision");
    const mRecall = document.getElementById("m-recall");
    const mF1 = document.getElementById("m-f1");
    const mRocAuc = document.getElementById("m-roc-auc");
    const mFiles = document.getElementById("m-files");
    const mBugs = document.getElementById("m-bugs");
    const mRisk = document.getElementById("m-risk");
    const mDefect20 = document.getElementById("m-defect20");
    
    if (mPrecision) mPrecision.innerText = m.precision.toFixed(2);
    if (mRecall) mRecall.innerText = m.recall.toFixed(2);
    if (mF1) mF1.innerText = m.f1.toFixed(2);
    if (mRocAuc) mRocAuc.innerText = m.roc_auc.toFixed(2);
    if (mFiles) mFiles.innerText = m.files_analyzed;
    if (mBugs) mBugs.innerText = m.buggy_count;
    if (mRisk) mRisk.innerText = m.avg_risk.toFixed(3);
    if (mDefect20) mDefect20.innerText = m.defect_at_20 + "%";
    
    // Update dashboard health score
    const healthScore = document.getElementById("health-score");
    if (healthScore) {
        healthScore.innerText = Math.round((1 - m.avg_risk) * 100);
    }
    
    // Fetch files for risk buckets
    try {
        const filesRes = await fetch("/api/files");
        const files = await filesRes.json();
        
        const highRisk = files.filter(f => f.risk >= 0.7).length;
        const medRisk = files.filter(f => f.risk >= 0.4 && f.risk < 0.7).length;
        const lowRisk = files.filter(f => f.risk < 0.4).length;
        
        const highRiskCount = document.getElementById("high-risk-count");
        const medRiskCount = document.getElementById("medium-risk-count");
        const lowRiskCount = document.getElementById("low-risk-count");
        
        if (highRiskCount) highRiskCount.innerText = highRisk;
        if (medRiskCount) medRiskCount.innerText = medRisk;
        if (lowRiskCount) lowRiskCount.innerText = lowRisk;
        
        // Update top risky files
        updateTopRiskyFiles(files.slice(0, 10));
    } catch (e) {
        console.error('Error fetching files:', e);
    }
    
    // Update confidence section if available
    if (m.confidence) {
        updateConfidenceDisplay(m.confidence);
    }
    
    // Update effort-aware recommendations
    fetchEffortRecommendations();
    
    // Update charts
    updateHistogram(data.histogram);
    updateConfusionMatrix(data.confusion_matrix);
    updateHealthTrend(data.health_trend);
    
    // Update top risk files list (for metrics panel)
    const topRiskList = document.getElementById("top-risk-list");
    if (topRiskList) {
        topRiskList.innerHTML = "";
        data.top_risk_files.forEach(item => {
            const li = document.createElement("li");
            li.className = "flex justify-between items-center py-1";
            li.innerHTML = `
                <span class="text-sm text-gray-300">${item.file}</span>
                <span class="text-sm font-medium text-gray-100">${(item.risk * 100).toFixed(1)}%</span>
            `;
            topRiskList.appendChild(li);
        });
    }
}

// Update top risky files with click handlers
function updateTopRiskyFiles(files) {
    const container = document.getElementById("top-risky-files");
    if (!container || !files || files.length === 0) return;
    
    container.innerHTML = "";
    
    files.forEach(file => {
        const riskPercent = (file.risk * 100).toFixed(0);
        let borderColor = "border-red-500";
        let bgColor = "bg-red-500";
        
        if (file.risk < 0.7) {
            borderColor = "border-yellow-500";
            bgColor = "bg-yellow-500";
        }
        if (file.risk < 0.4) {
            borderColor = "border-green-500";
            bgColor = "bg-green-500";
        }
        
        const div = document.createElement("div");
        div.className = `${borderColor} border-l-4 pl-4 py-2 cursor-pointer hover:bg-gray-800 transition-colors`;
        div.onclick = () => loadDetail(file.id);
        
        // Get language badge color
        let langColor = "bg-blue-500/20 text-blue-400";
        if (file.filename && file.filename.endsWith('.js')) langColor = "bg-yellow-500/20 text-yellow-400";
        if (file.filename && file.filename.endsWith('.java')) langColor = "bg-red-500/20 text-red-400";
        
        div.innerHTML = `
            <div class="flex justify-between items-start">
                <div class="flex-1">
                    <div class="font-mono text-sm text-white mb-1">${file.filename || 'Unknown'}</div>
                    <div class="flex items-center gap-2 mb-1">
                        <span class="px-2 py-1 ${langColor} rounded text-xs">Python</span>
                        <div class="flex items-center gap-1">
                            <div class="w-20 bg-gray-700 rounded-full h-2">
                                <div class="${bgColor} h-2 rounded-full" style="width: ${riskPercent}%"></div>
                            </div>
                            <span class="text-sm text-gray-400">${riskPercent}%</span>
                        </div>
                    </div>
                    <div class="text-sm text-gray-400">
                        ${file.complexity ? `Complexity: ${file.complexity}` : 'High churn, complex functions'}
                    </div>
                </div>
            </div>
        `;
        
        container.appendChild(div);
    });
}

function updateConfidenceDisplay(confidence) {
    const confidenceSection = document.getElementById("confidence-section");
    const confidenceScore = document.getElementById("confidence-score");
    const confidenceMessage = document.getElementById("confidence-message");
    const confidenceBadge = document.getElementById("confidence-badge");
    const confidenceWarnings = document.getElementById("confidence-warnings");
    
    // Show confidence section
    confidenceSection.classList.remove("hidden");
    
    // Update score
    confidenceScore.textContent = (confidence.score * 100).toFixed(1) + "%";
    
    // Update message
    confidenceMessage.textContent = confidence.message;
    
    // Update badge styling
    confidenceBadge.textContent = confidence.level;
    confidenceBadge.className = "text-xs px-2 py-1 rounded-full";
    
    if (confidence.level === "HIGH") {
        confidenceBadge.classList.add("bg-green-500/20", "text-green-400");
    } else if (confidence.level === "MEDIUM") {
        confidenceBadge.classList.add("bg-yellow-500/20", "text-yellow-400");
    } else {
        confidenceBadge.classList.add("bg-red-500/20", "text-red-400");
    }
    
    // Update warnings
    confidenceWarnings.innerHTML = "";
    if (confidence.warnings && confidence.warnings.length > 0) {
        confidence.warnings.forEach(warning => {
            const warningDiv = document.createElement("div");
            warningDiv.className = "flex items-start gap-2 text-sm text-gray-300";
            warningDiv.innerHTML = `
                <i class="fa-solid fa-exclamation-triangle text-yellow-500 mt-0.5"></i>
                <span>${warning}</span>
            `;
            confidenceWarnings.appendChild(warningDiv);
        });
    } else {
        const noWarningsDiv = document.createElement("div");
        noWarningsDiv.className = "text-sm text-gray-400 italic";
        noWarningsDiv.textContent = "No issues detected - predictions are reliable";
        confidenceWarnings.appendChild(noWarningsDiv);
    }
}

async function fetchEffortRecommendations() {
    try {
        const response = await fetch('/api/effort_recommendations?top_n=5');
        const data = await response.json();
        
        if (data.error) {
            console.error('Effort recommendations error:', data.error);
            return;
        }
        
        displayEffortRecommendations(data);
        
    } catch (error) {
        console.error('Failed to fetch effort recommendations:', error);
    }
}

function displayEffortRecommendations(data) {
    const effortSection = document.getElementById("effort-section");
    const filesCount = document.getElementById("effort-files-count");
    const totalLoc = document.getElementById("effort-total-loc");
    const riskCaptured = document.getElementById("effort-risk-captured");
    const efficiency = document.getElementById("effort-efficiency");
    const recommendationsContainer = document.getElementById("effort-recommendations");
    
    // Show effort section
    effortSection.classList.remove("hidden");
    
    // Update summary metrics
    const summary = data.summary;
    filesCount.textContent = summary.files_recommended;
    totalLoc.textContent = summary.total_loc.toLocaleString();
    riskCaptured.textContent = (summary.total_risk_captured * 100).toFixed(1) + "%";
    efficiency.textContent = summary.efficiency_efficiency.toFixed(3);
    
    // Update recommendations
    recommendationsContainer.innerHTML = "";
    data.recommendations.forEach(rec => {
        const recDiv = document.createElement("div");
        recDiv.className = "flex items-center justify-between p-3 bg-gray-900 rounded";
        
        // Category styling
        let categoryColor = "text-gray-400";
        let categoryBg = "bg-gray-700/50";
        if (rec.effort_category === "HIGH_VALUE") {
            categoryColor = "text-green-400";
            categoryBg = "bg-green-500/20";
        } else if (rec.effort_category === "EFFICIENT") {
            categoryColor = "text-blue-400";
            categoryBg = "bg-blue-500/20";
        } else if (rec.effort_category === "EXPENSIVE") {
            categoryColor = "text-orange-400";
            categoryBg = "bg-orange-500/20";
        } else if (rec.effort_category === "LOW_PRIORITY") {
            categoryColor = "text-gray-500";
            categoryBg = "bg-gray-600/20";
        }
        
        // Effort styling
        let effortColor = "text-green-400";
        if (rec.review_effort === "Medium") effortColor = "text-yellow-400";
        else if (rec.review_effort === "High") effortColor = "text-red-400";
        
        recDiv.innerHTML = `
            <div class="flex-1">
                <div class="flex items-center gap-2 mb-1">
                    <span class="text-sm font-medium text-gray-100">${rec.file}</span>
                    <span class="text-xs px-2 py-1 rounded ${categoryBg} ${categoryColor}">${rec.effort_category}</span>
                </div>
                <div class="flex items-center gap-4 text-xs text-gray-400">
                    <span>Risk: ${(rec.risk * 100).toFixed(1)}%</span>
                    <span>LOC: ${rec.loc.toLocaleString()}</span>
                    <span>Risk/LOC: ${(rec.risk_per_loc * 1000000).toFixed(2)}</span>
                </div>
            </div>
            <div class="text-right">
                <div class="${effortColor} font-medium text-sm">${rec.review_effort}</div>
                <div class="text-xs text-gray-400">effort</div>
            </div>
        `;
        
        recommendationsContainer.appendChild(recDiv);
    });
}

async function fetchFiles() {
    try {
        const res = await fetch('/api/files');
        window.allFilesData = await res.json();
        renderTable();
    } catch (e) {}
}

async function fetchGlobalImportance() {
    try {
        const res = await fetch('/api/importance');
        const data = await res.json();
        renderImportanceChart(data);
    } catch (e) { }
}

function updateStatCards(m) {
    const row = document.getElementById('overview-metrics');
    row.innerHTML = `
        <div class="card">
            <div class="stat-label">Files Analyzed</div>
            <div class="stat-value">${m.files_analyzed}</div>
        </div>
        <div class="card">
            <div class="stat-label">Identified Hotspots</div>
            <div class="stat-value" style="color:${COLORS.danger}">${m.buggy_count}</div>
        </div>
        <div class="card">
            <div class="stat-label">Mean Repository Risk</div>
            <div class="stat-value">${(m.avg_risk * 100).toFixed(1)}%</div>
        </div>
        <div class="card">
            <div class="stat-label">Density @ Top 20%</div>
            <div class="stat-value">${m.defect_at_20}%</div>
        </div>
    `;
}

// --- Charts ---
let chHist, chImp;
function renderCharts(histData, metrics) {
    if (chHist) chHist.destroy();
    const ctxH = document.getElementById('c-histogram').getContext('2d');
    chHist = new Chart(ctxH, {
        type: 'bar',
        data: {
            labels: histData.map(d => d.bin),
            datasets: [{
                data: histData.map(d => d.count),
                backgroundColor: COLORS.brand,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: { y: { grid: { color: COLORS.border } }, x: { grid: { display: false } } },
            plugins: { legend: { display: false } }
        }
    });
}

function renderImportanceChart(data) {
    if (chImp) chImp.destroy();
    const ctx = document.getElementById('c-importance').getContext('2d');
    chImp = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => getNarrative(d.feature).name),
            datasets: [{
                data: data.map(d => d.value),
                backgroundColor: '#ffffff',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            scales: { x: { grid: { color: COLORS.border } }, y: { grid: { display: false } } },
            plugins: { legend: { display: false } }
        }
    });
}

// --- Table & Details ---
function renderTable() {
    if (!window.allFilesData) return;
    const body = document.getElementById('files-tbody');
    const filter = document.getElementById('risk-filter').value;
    const search = document.getElementById('search-input').value.toLowerCase();
    
    let html = '';
    window.allFilesData.forEach(row => {
        if (search && !row.filename.toLowerCase().includes(search)) return;
        
        let tr = row.risk >= 0.70 ? 'high' : (row.risk >= 0.50 ? 'medium' : 'low');
        if (filter !== 'all' && filter !== tr) return;
        
        let badgeClass = tr === 'high' ? 'danger' : (tr === 'medium' ? 'warning' : 'success');
        
        html += `<tr data-id="${row.id}">
            <td class="mono-font">${row.filename}</td>
            <td><strong>${(row.risk * 100).toFixed(1)}%</strong> <span class="badge ${badgeClass}">${tr}</span></td>
            <td class="mono-font">${row.complexity}</td>
            <td class="mono-font">${row.commits_1m}</td>
        </tr>`;
    });
    body.innerHTML = html;
    
    body.querySelectorAll('tr').forEach(tr => {
        tr.addEventListener('click', () => {
            body.querySelectorAll('tr').forEach(t => t.classList.remove('selected'));
            tr.classList.add('selected');
            loadDetail(tr.dataset.id);
        });
    });
}

document.getElementById('risk-filter').addEventListener('change', renderTable);
document.getElementById('search-input').addEventListener('keyup', renderTable);

async function loadDetail(fileId) {
    document.getElementById('detail-blank').classList.add('hidden');
    document.getElementById('detail-body').classList.remove('hidden');
    
    try {
        const res = await fetch(`/api/file?id=${encodeURIComponent(fileId)}`);
        const data = await res.json();
        
        document.getElementById('d-filepath').innerText = data.filepath;
        
        let rr = data.risk;
        document.getElementById('d-risk').innerText = (rr * 100).toFixed(1) + '%';
        let tier = document.getElementById('d-tier');
        
        if (rr >= 0.7) { tier.innerText = 'HIGH'; tier.className = 'badge danger'; }
        else if (rr >= 0.5) { tier.innerText = 'MED';  tier.className = 'badge warning'; }
        else { tier.innerText = 'LOW'; tier.className = 'badge success'; }
        
        let summaryText = rr >= 0.5 
            ? "Exhibits structural and historical patterns correlated with defects. Prioritize review."
            : "Exhibits stable patterns historically. Low risk of defects.";
        document.getElementById('d-summary').innerHTML = summaryText;
        
        let actionsHtml = "", bulletHtml = "", shapHtml = '';
        
        // Handle human-readable explanations (new format)
        if (data.explanation && typeof data.explanation === 'string') {
            // Split by " | " separator and format as cards
            const explanations = data.explanation.split(' | ').filter(exp => exp.trim());
            bulletHtml = explanations.map(exp => {
                // Remove bullet point character if present
                const cleanExp = exp.replace(/^·\s*/, '');
                return `<div class="risk-factor-card">
                    <div class="flex items-start gap-2">
                        <i class="fa-solid fa-exclamation-triangle text-orange-500 mt-0.5"></i>
                        <p class="text-sm text-gray-200 leading-relaxed">${cleanExp}</p>
                    </div>
                </div>`;
            }).join('');
        } else if (data.shap && data.shap.positive) {
            // Fallback to old format
            data.shap.positive.forEach(item => {
                const feat = getNarrative(item.feature);
                bulletHtml += `<li>${feat.narrative}</li>`;
                actionsHtml += `<div class="action-card">${feat.action}</div>`;
            });
        }
        
        // Handle SHAP visualization
        if (data.shap && data.shap.positive) {
            data.shap.positive.forEach(item => {
                const feat = getNarrative(item.feature);
                shapHtml += `<div class="metric-row"><div class="metric-label">${feat.name}</div><div class="metric-bar-wrap"><div class="metric-bar-fill pos" style="width:${Math.min(item.value*100, 100)}%"></div></div><div class="metric-val">+${item.value.toFixed(2)}</div></div>`;
            });
            
            data.shap.negative.forEach(item => {
                const feat = getNarrative(item.feature);
                shapHtml += `<div class="metric-row"><div class="metric-label">${feat.name}</div><div class="metric-bar-wrap" style="transform:scaleX(-1)"><div class="metric-bar-fill neg" style="width:${Math.min(Math.abs(item.value)*100, 100)}%"></div></div><div class="metric-val" style="color:var(--success)">${item.value.toFixed(2)}</div></div>`;
            });
        }
        
        document.getElementById('d-bullets').innerHTML = bulletHtml;
        document.getElementById('d-actions').innerHTML = actionsHtml;
        document.getElementById('d-shap').innerHTML = shapHtml;
        document.getElementById('d-actions-wrap').style.display = actionsHtml ? "block" : "none";
        
    } catch (e) {}
}

// --- PR Analysis ---
async function analyzePR() {
    const prUrl = document.getElementById('pr-url').value.trim();
    if (!prUrl) {
        showToast('Please enter a PR URL');
        return;
    }
    
    // Validate URL format
    if (!prUrl.includes('github.com/') || !prUrl.includes('/pull/')) {
        showToast('Please enter a valid GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)');
        return;
    }
    
    try {
        const response = await fetch('/api/analyze_pr', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCSRFToken()
            },
            body: JSON.stringify({ pr_url: prUrl })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to analyze PR');
        }
        
        // Display results
        displayPRResults(data);
        
    } catch (error) {
        console.error('PR analysis error:', error);
        showToast('Error analyzing PR: ' + error.message);
    }
}

function displayPRResults(data) {
    // Show results section
    document.getElementById('pr-results').classList.remove('hidden');
    
    // Display PR information
    document.getElementById('pr-title').textContent = data.pr_info.title;
    document.getElementById('pr-author').textContent = data.pr_info.author;
    document.getElementById('pr-state').textContent = data.pr_info.state;
    document.getElementById('pr-files-changed').textContent = data.pr_info.changed_files;
    
    // Display author experience
    const experience = data.author_experience;
    document.getElementById('author-experience').textContent = experience.experience_level;
    document.getElementById('author-commits').textContent = experience.repo_contributions;
    document.getElementById('author-contributions').textContent = experience.total_contributions;
    
    // Set experience level color
    const expElement = document.getElementById('author-experience');
    if (experience.experience_level === 'SENIOR') {
        expElement.className = 'text-2xl font-bold text-green-500';
    } else if (experience.experience_level === 'MEDIUM') {
        expElement.className = 'text-2xl font-bold text-blue-500';
    } else if (experience.experience_level === 'JUNIOR') {
        expElement.className = 'text-2xl font-bold text-yellow-500';
    } else {
        expElement.className = 'text-2xl font-bold text-gray-500';
    }
    
    // Display risk analysis
    const riskScore = data.risk_analysis.overall_risk;
    document.getElementById('pr-risk-score').textContent = (riskScore * 100).toFixed(1) + '%';
    
    const riskLevel = data.risk_analysis.risk_level;
    const riskElement = document.getElementById('pr-risk-level');
    riskElement.textContent = riskLevel;
    
    // Set risk level color
    if (riskLevel === 'HIGH') {
        riskElement.className = 'text-2xl font-bold text-red-500';
    } else if (riskLevel === 'MEDIUM') {
        riskElement.className = 'text-2xl font-bold text-yellow-500';
    } else {
        riskElement.className = 'text-2xl font-bold text-green-500';
    }
    
    // Display complexity and bug areas
    document.getElementById('pr-complexity').textContent = data.risk_analysis.complexity_factor;
    document.getElementById('pr-bug-areas').textContent = data.risk_analysis.past_bug_files_count;
    
    // Set complexity color
    const complexityElement = document.getElementById('pr-complexity');
    if (data.risk_analysis.complexity_factor === 'HIGH') {
        complexityElement.className = 'text-2xl font-bold text-orange-500';
    } else {
        complexityElement.className = 'text-2xl font-bold text-blue-500';
    }
    
    // Set bug areas color
    const bugAreasElement = document.getElementById('pr-bug-areas');
    if (data.risk_analysis.past_bug_files_count > 0) {
        bugAreasElement.className = 'text-2xl font-bold text-red-500';
    } else {
        bugAreasElement.className = 'text-2xl font-bold text-green-500';
    }
    
    document.getElementById('pr-recommendation').textContent = data.risk_analysis.recommendation;
    
    // Display file risks
    const fileRisksContainer = document.getElementById('pr-file-risks');
    fileRisksContainer.innerHTML = '';
    
    data.file_risks.forEach(file => {
        const fileRisk = document.createElement('div');
        fileRisk.className = 'flex items-center justify-between p-3 bg-gray-900 rounded';
        
        const riskPercent = (file.risk * 100).toFixed(1);
        let riskColor = 'text-green-500';
        if (file.risk > 0.7) riskColor = 'text-red-500';
        else if (file.risk > 0.4) riskColor = 'text-yellow-500';
        
        // Past bug area indicator
        const bugIndicator = file.is_past_bug_area ? 
            '<span class="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded ml-2">Past Bug Area</span>' : '';
        
        fileRisk.innerHTML = `
            <div class="flex-1">
                <div class="flex items-center gap-2">
                    <div class="text-sm font-medium text-gray-100">${file.filename}</div>
                    ${bugIndicator}
                </div>
                <div class="text-xs text-gray-400">+${file.additions} -${file.deletions} lines</div>
            </div>
            <div class="text-right">
                <div class="${riskColor} font-medium">${riskPercent}%</div>
                <div class="text-xs text-gray-400">risk</div>
            </div>
        `;
        
        fileRisksContainer.appendChild(fileRisk);
    });
    
    // Scroll to results
    document.getElementById('pr-results').scrollIntoView({ behavior: 'smooth' });
}

// --- Scanning ---
// Function to load overview data (called from Alpine.js)
window.loadOverviewData = async function() {
    try {
        await fetchOverview();
        await fetchFiles();
        await fetchGlobalImportance();
        
        // Update Alpine.js state
        if (window.Alpine) {
            window.Alpine.store('scan', {
                scanning: false,
                scanProgress: 100,
                scanStatus: 'complete'
            });
        }
        
        // Switch to overview tab
        document.querySelector('[data-tab="overview"]').click();
        
        appLog('<span style="color:var(--success)">Success</span> Pipeline execution complete. Synchronizing UI state.');
    } catch (e) {
        appLog('<span style="color:var(--danger)">Error loading overview data: ' + e.message + '</span>');
        console.error('Error loading overview data:', e);
    }
};

// Custom scan function with real progress tracking
window.scanCustomRepo = async function(presetUrl = null) {
    const pathInput = document.getElementById('custom-scan-path');
    const path = presetUrl || (pathInput ? pathInput.value : null);
    
    if (!path) {
        showToast('Please enter a repository URL');
        return;
    }
    
    const btn = document.getElementById('custom-scan-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Scanning...</span>';
    }
    
    if (pathInput && pathInput.value !== path) {
        pathInput.value = path;
    }
    
    appLog('> Initiating target scan on <strong>' + path + '</strong>');
    
    try {
        const res = await fetch('/api/scan_repo', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCSRFToken()
            },
            body: JSON.stringify({path})
        });
        
        const data = await res.json();
        
        if (res.ok && data.scan_id) {
            // Start listening to progress updates
            listenToScanProgress(data.scan_id);
        } else {
            appLog('<span style="color:var(--danger)">Error</span> ' + (data.error || 'Unknown error'));
            showToast('Scan Failed: ' + (data.error || 'Unknown error'));
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-radar"></i> <span class="font-semibold">Scan Repository</span>';
            }
        }
    } catch (e) {
        appLog('<span style="color:var(--danger)">Network exception</span>');
        showToast('Network error occurred while scanning');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-radar"></i> <span class="font-semibold">Scan Repository</span>';
        }
    }
};

// Listen to real-time scan progress via Server-Sent Events
function listenToScanProgress(scanId) {
    const eventSource = new EventSource(`/api/scan_progress/${scanId}`);
    
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        // Update Alpine.js state
        const alpineContext = document.querySelector('[x-data]');
        if (alpineContext && alpineContext._x_dataStack) {
            const alpineObj = alpineContext._x_dataStack[0];
            alpineObj.scanProgress = data.progress;
            alpineObj.scanStatus = data.status;
            
            if (data.complete) {
                if (data.error) {
                    appLog('<span style="color:var(--danger)">Error</span> ' + data.error);
                    showToast('Scan Failed: ' + data.error);
                    alpineObj.scanning = false;
                    alpineObj.currentTab = 'repos';
                } else {
                    appLog('<span style="color:var(--success)">Success</span> Scan complete!');
                    window.loadOverviewData();
                    showToast('Scan completed successfully!', 'success');
                }
                
                // Re-enable button
                const btn = document.getElementById('custom-scan-btn');
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa-solid fa-radar"></i> <span class="font-semibold">Scan Repository</span>';
                }
                
                eventSource.close();
            }
        }
    };
    
    eventSource.onerror = function(error) {
        console.error('SSE Error:', error);
        eventSource.close();
        showToast('Connection error during scan');
        
        const btn = document.getElementById('custom-scan-btn');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-radar"></i> <span class="font-semibold">Scan Repository</span>';
        }
    };
}

// Add event listener for custom scan button
document.addEventListener('DOMContentLoaded', function() {
    const customScanBtn = document.getElementById('custom-scan-btn');
    if (customScanBtn) {
        customScanBtn.addEventListener('click', window.scanCustomRepo);
    }
});

// --- Sim ---
const btnSimulate = document.getElementById('btn-simulate');
if (btnSimulate) {
    btnSimulate.addEventListener('click', async () => {
        const text = document.getElementById('sim-files').value;
        const files = text.split(/[\n,]+/).map(s => s.trim()).filter(s => s);
        if (!files.length) return;
        
        const res = await fetch('/api/predict_commit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCSRFToken()
            },
            body: JSON.stringify({files})
        });
        const data = await res.json();
        
        const simResult = document.getElementById('sim-result');
        const simScore = document.getElementById('sim-score');
        const simDriver = document.getElementById('sim-driver');
        
        if (simResult) simResult.classList.remove('hidden');
        if (simScore) simScore.innerText = (data.risk * 100).toFixed(1) + '%';
        if (simDriver) simDriver.innerText = data.main_driver;
    });
}

// --- Model Evaluation Data Fetching ---
let modelEvaluationData = null;

async function fetchModelEvaluationData() {
    try {
        const response = await fetch('/api/model_evaluation');
        if (!response.ok) {
            throw new Error('Failed to fetch model evaluation data');
        }
        modelEvaluationData = await response.json();
        updateModelEvaluationUI();
    } catch (error) {
        console.error('Error fetching model evaluation data:', error);
        appLog('<span style="color:var(--danger)">Error</span> Failed to load model evaluation data');
    }
}

let modelEvaluationData = null;

async function fetchModelEvaluationData() {
    try {
        const res = await fetch('/api/model_evaluation');
        if (res.ok) {
            modelEvaluationData = await res.json();
            updateModelEvaluationUI();
        }
    } catch (e) {
        console.error("Error fetching model evaluation data:", e);
    }
}

function updateModelEvaluationUI() {
    if (!modelEvaluationData) return;
    
    // The index.html has #m-precision, #m-recall, #m-f1, #m-roc, #topk-recall-10, #topk-precision-10
    // We will populate these using the best performing model averages
    const stats = modelEvaluationData.model_comparison;
    const bestModel = modelEvaluationData.summary.best_overall_model;
    
    if (stats && stats[bestModel]) {
        const mPrec = document.getElementById('m-precision');
        if (mPrec) mPrec.textContent = stats[bestModel].precision10.toFixed(3);
        
        const mRec = document.getElementById('m-recall');
        if (mRec) mRec.textContent = stats[bestModel].recall10.toFixed(3);
        
        const mF1 = document.getElementById('m-f1');
        if (mF1) mF1.textContent = stats[bestModel].f1.toFixed(3);
        
        const mRoc = document.getElementById('m-roc');
        if (mRoc) mRoc.textContent = stats[bestModel].pr_auc.toFixed(3);
        
        const tRec = document.getElementById('topk-recall-10');
        if (tRec) tRec.textContent = (stats[bestModel].recall10 * 100).toFixed(1) + '%';
        
        const tPrec = document.getElementById('topk-precision-10');
        if (tPrec) tPrec.textContent = (stats[bestModel].precision10 * 100).toFixed(1) + '%';
    }
    
    // Populate About page tables AND Model Eval tables
    populateCrossProjectTable(modelEvaluationData.cross_project, 'cross-project-table');
    populateCrossProjectTable(modelEvaluationData.cross_project, 'about-cross-project-table');
    
    // Render charts
    renderAblationChart(modelEvaluationData.model_comparison);
    renderModelComparisonChart(modelEvaluationData.model_comparison);
}

function populateCrossProjectTable(data, tableId) {
    const tbody = document.getElementById(tableId);
    if (!tbody || !data) return;
    
    tbody.innerHTML = '';
    
    data.forEach(item => {
        const row = document.createElement('tr');
        row.className = 'border-b border-gray-800 hover:bg-gray-700/50 transition-colors';
        
        let f1Color = 'text-gray-300';
        if (item.f1 >= 0.8) f1Color = 'text-green-400';
        else if (item.f1 >= 0.6) f1Color = 'text-yellow-400';
        else if (item.f1 >= 0.4) f1Color = 'text-orange-400';
        else f1Color = 'text-red-400';
        
        let recallColor = 'text-gray-300';
        if (item.recall10 >= 0.7) recallColor = 'text-green-400';
        else if (item.recall10 >= 0.4) recallColor = 'text-yellow-400';
        else if (item.recall10 >= 0.2) recallColor = 'text-orange-400';
        else recallColor = 'text-red-400';
        
        row.innerHTML = `
            <td class="py-2 px-3 font-medium text-gray-100">${item.repo}</td>
            <td class="py-2 px-3 text-center">
                <span class="px-2 py-1 rounded text-xs font-medium ${
                    item.model === 'RF' ? 'bg-green-500/20 text-green-400' :
                    item.model === 'LR' ? 'bg-blue-500/20 text-blue-400' :
                    'bg-yellow-500/20 text-yellow-400'
                }">${item.model}</span>
            </td>
            <td class="py-2 px-3 text-right font-semibold ${f1Color}">${item.f1.toFixed(3)}</td>
            <td class="py-2 px-3 text-right text-gray-300">${item.pr_auc.toFixed(3)}</td>
            <td class="py-2 px-3 text-right font-semibold ${recallColor}">${(item.recall10 * 100).toFixed(1)}%</td>
        `;
        tbody.appendChild(row);
    });
}

function renderAblationChart(avgStats) {
    const ctx = document.getElementById('ablation-chart');
    if (!ctx || !avgStats) return;
    
    if (window.ablationChart) window.ablationChart.destroy();
    
    const models = Object.keys(avgStats);
    const f1Scores = models.map(m => avgStats[m].f1);
    const prAucs = models.map(m => avgStats[m].pr_auc);
    
    window.ablationChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: models,
            datasets: [
                {
                    label: 'F1 Score',
                    data: f1Scores,
                    backgroundColor: 'rgba(50, 215, 75, 0.7)',
                    borderColor: 'rgba(50, 215, 75, 1)',
                    borderWidth: 1
                },
                {
                    label: 'PR-AUC',
                    data: prAucs,
                    backgroundColor: 'rgba(10, 132, 255, 0.7)',
                    borderColor: 'rgba(10, 132, 255, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, max: 1.0, grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            },
            plugins: { legend: { position: 'top', labels: { color: '#c9d1d9' } } }
        }
    });
}

function renderModelComparisonChart(avgStats) {
    const ctx = document.getElementById('model-comparison-chart');
    if (!ctx || !avgStats) return;
    
    if (window.modelComparisonChart) window.modelComparisonChart.destroy();
    
    const models = Object.keys(avgStats);
    const f1Scores = models.map(m => avgStats[m].f1);
    const prAucs = models.map(m => avgStats[m].pr_auc);
    const recalls = models.map(m => avgStats[m].recall10);
    
    window.modelComparisonChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: models,
            datasets: [
                { label: 'F1 Score', data: f1Scores, backgroundColor: 'rgba(50, 215, 75, 0.6)' },
                { label: 'PR-AUC', data: prAucs, backgroundColor: 'rgba(10, 132, 255, 0.6)' },
                { label: 'Recall@10', data: recalls, backgroundColor: 'rgba(255, 159, 10, 0.6)' }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, max: 1.0, grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            },
            plugins: { legend: { position: 'top', labels: { color: '#c9d1d9' } } }
        }
    });
}

async function fetchAdditionalDashData() {
    try {
        const resImp = await fetch('/api/importance');
        if (resImp.ok) {
            const dataImp = await resImp.json();
            renderImportanceChartNew(dataImp);
        }
        
        const resOver = await fetch('/api/overview');
        if (resOver.ok) {
            const dataOver = await resOver.json();
            renderHistogramChart(dataOver.histogram);
            renderHealthTrendChart(dataOver.health_trend);
        }
    } catch (e) {
        console.error("Error fetching additional dashboard data:", e);
    }
}

function renderImportanceChartNew(data) {
    const ctx = document.getElementById('importance-chart');
    if (!ctx || !data || data.length === 0) return;
    
    if (window.importanceChartNew) window.importanceChartNew.destroy();
    
    window.importanceChartNew = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.feature.replace(/_/g, ' ')),
            datasets: [{
                label: 'Mean Absolute SHAP Value',
                data: data.map(d => d.value),
                backgroundColor: 'rgba(191, 90, 242, 0.6)',
                borderColor: 'rgba(191, 90, 242, 1)',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { grid: { display: false } }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function renderHistogramChart(data) {
    const ctx = document.getElementById('histogram-chart');
    if (!ctx || !data || data.length === 0) return;
    
    if (window.histogramChart) window.histogramChart.destroy();
    
    window.histogramChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.bin),
            datasets: [{
                label: 'Number of Files',
                data: data.map(d => d.count),
                backgroundColor: 'rgba(10, 132, 255, 0.6)',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function renderHealthTrendChart(data) {
    const ctx = document.getElementById('health-trend-chart');
    if (!ctx || !data || data.length === 0) return;
    
    if (window.healthTrendChart) window.healthTrendChart.destroy();
    
    window.healthTrendChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.repo),
            datasets: [
                {
                    label: 'Mean Risk Score',
                    data: data.map(d => d.avg_risk),
                    backgroundColor: 'rgba(255, 69, 58, 0.6)'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            },
            plugins: { legend: { display: false } }
        }
    });
}

// Initialize model evaluation data when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Fetch model evaluation data
    fetchModelEvaluationData();
    fetchAdditionalDashData();
    
    // Hook into tab clicks to re-render charts when their containers become visible
    // Chart.js requires containers to be display:block to measure them correctly.
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (btn && btn.hasAttribute('@click')) {
            const clickAttr = btn.getAttribute('@click');
            if (clickAttr && (clickAttr.includes("'model'") || clickAttr.includes("'about'"))) {
                // Wait 100ms for AlpineJS to set display: block, then fetch and render
                setTimeout(() => {
                    fetchModelEvaluationData();
                    fetchAdditionalDashData();
                }, 100);
            }
        }
    });
});

// Boot
appLog("> Display logic initialized.");

// Initialize dashboard components when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check for auto-scan URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const scanUrl = urlParams.get('scan');
    if (scanUrl) {
        // Clear the param to prevent refresh-looping
        window.history.replaceState({}, document.title, "/");
        
        // Wait for Alpine to initialize, then trigger scan
        setTimeout(() => {
            const alpineObj = document.querySelector('[x-data]')?._x_dataStack?.[0];
            if (alpineObj) {
                alpineObj.currentTab = 'scan';
                alpineObj.scanning = true;
                alpineObj.scanProgress = 10;
                alpineObj.scanStatus = 'Initializing...';
            }
            window.scanCustomRepo(scanUrl);
        }, 500);
    }

    // Initialize PR Analyzer
    fetchUserPRs();

    // Handle PR Dropdown Selection
    const prDropdown = document.getElementById('pr-dropdown');
    if (prDropdown) {
        prDropdown.addEventListener('change', (e) => {
            const selectedOption = e.target.options[e.target.selectedIndex];
            const prUrl = selectedOption.value;
            const prUrlInput = document.getElementById('pr-url');
            if (prUrl && prUrlInput) {
                prUrlInput.value = prUrl;
            }
        });
    }

    // Initialize landing page if analyze button exists
    if (document.getElementById('analyze-btn')) {
        initializeLandingPage();
    }
    
    // Initialize dashboard charts
    initializeDashboardCharts();
    
    // Initialize file detail panel close buttons
    const closeButtons = document.querySelectorAll('[onclick*="file-detail-panel"]');
    closeButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            if (e.target.closest('#file-detail-panel')) {
                hideFileDetailPanel();
            }
        });
    });
    
    // Handle file clicks in dashboard
    const fileElements = document.querySelectorAll('#top-risky-files .border-l-4');
    fileElements.forEach(element => {
        element.addEventListener('click', () => {
            const filename = element.querySelector('.font-mono').textContent;
            const riskText = element.querySelector('.text-gray-400').textContent;
            showFileDetailPanel(filename, '78%', 'Python', []);
        });
    });
});

// Fetch user's PRs for the PR analyzer dropdown
async function fetchUserPRs() {
    const dropdown = document.getElementById('pr-dropdown');
    if (!dropdown) return;
    
    try {
        const res = await fetch('/api/repo_prs');
        if (!res.ok) {
            dropdown.innerHTML = '<option value="">Could not load PRs</option>';
            return;
        }
        
        const data = await res.json();
        const prs = data.prs || [];
        
        if (prs.length === 0) {
            dropdown.innerHTML = '<option value="">No open Pull Requests found</option>';
            return;
        }
        
        dropdown.innerHTML = '<option value="">-- Select an open Pull Request --</option>';
        prs.forEach(pr => {
            const option = document.createElement('option');
            option.value = pr.url;
            option.textContent = `[${pr.repo}] #${pr.number} - ${pr.title}`;
            dropdown.appendChild(option);
        });
        
    } catch (e) {
        console.error('Error fetching PRs:', e);
        dropdown.innerHTML = '<option value="">Error loading PRs</option>';
    }
}

// Only fetch if authenticated
if (document.querySelector('[x-data]')) {
    fetchOverview().catch(e => console.log('Overview not available:', e));
    fetchFiles().catch(e => console.log('Files not available:', e));
    fetchGlobalImportance().catch(e => console.log('Importance not available:', e));
}
