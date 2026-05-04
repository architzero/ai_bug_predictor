// CodeSentinel Frontend JavaScript
// Uses Alpine.js for interactivity and Chart.js for data visualization

function registerAlpineComponents() {
    if (typeof Alpine === 'undefined') {
        console.error('Alpine.js not loaded yet!');
        return;
    }
    
    Alpine.data('resultsDashboard', (scanId) => ({
        scanId: scanId,
        files: [],
        filteredFiles: [],
        overview: null,
        repoName: '',
        searchQuery: '',
        selectedFileId: null,
        selectedFileDetails: null,
        isPanelOpen: false,
        maxShapValue: 1,
        isLoading: true,
        error: null,
        
        // New filtering and sorting
        timeFilter: 'all',
        sortBy: 'risk',
        originalFiles: [],

        charts: {
            riskHistogram: null,
            featureImportance: null,
            confusionMatrix: null,
            cumulativeGain: null,
            riskRecency: null
        },

        async init() {
            console.log('🚀 Initializing results dashboard with scanId:', this.scanId);
            
            if (!this.scanId) {
                console.error('❌ No scan ID provided');
                this.error = "No scan ID provided. Please start a new scan.";
                this.isLoading = false;
                return;
            }
            
            try {
                console.log('📡 Fetching results from:', `/api/scan_results/${this.scanId}`);
                
                // Fetch scan-specific results
                const response = await fetch(`/api/scan_results/${this.scanId}`);
                
                console.log('📊 Response status:', response.status);
                
                if (!response.ok) {
                    if (response.status === 404) {
                        throw new Error('Scan results not found. They may have expired (results are kept for 1 hour). Try running a new scan.');
                    }
                    const errorText = await response.text();
                    console.error('❌ Error response:', errorText);
                    throw new Error(`Failed to fetch scan results: ${response.status}`);
                }

                const data = await response.json();
                console.log('✅ Received data structure:', {
                    hasFiles: !!data.files,
                    fileCount: data.files?.length,
                    hasMetrics: !!data.metrics,
                    hasRepoName: !!data.repo_name,
                    totalFiles: data.total_files
                });
                
                if (!data.files || data.files.length === 0) {
                    console.warn('⚠️ No files in scan results');
                    this.error = "Scan completed but no files were found in the results.";
                    this.isLoading = false;
                    return;
                }
                
                // Validate file data structure
                const sampleFile = data.files[0];
                console.log('📄 Sample file structure:', {
                    hasId: !!sampleFile.id,
                    hasFilename: !!sampleFile.filename,
                    hasRisk: 'risk' in sampleFile,
                    riskValue: sampleFile.risk,
                    hasCommits: 'commits' in sampleFile,
                    hasLoc: 'loc' in sampleFile
                });
                
                this.overview = { metrics: data.metrics };
                this.repoName = data.repo_name || 'Unknown Repository';
                this.files = data.files || [];
                this.originalFiles = [...this.files];
                this.filteredFiles = [...this.files];

                console.log(`📁 Loaded ${this.files.length} files for repo: ${this.repoName}`);

                // Initialize filters and sorting
                this.applyFilters();

                // Setup charts after DOM is updated and transition completes
                this.$nextTick(() => {
                    console.log('⏰ $nextTick fired, waiting for transition...');
                    // Delay chart creation to ensure Alpine x-show transition is complete
                    setTimeout(() => {
                        console.log('📈 Initializing charts after transition delay...');
                        this.initCharts();
                    }, 350);
                });

                // Set up search watcher
                this.$watch('searchQuery', () => {
                    this.applyFilters();
                });

            } catch (error) {
                console.error("💥 Dashboard initialization failed:", error);
                this.error = error.message;
            } finally {
                this.isLoading = false;
                console.log('🏁 Initialization complete. Error:', this.error, 'Files:', this.files.length);
            }
        },

        get highRiskCount() {
            if (!this.files) return 0;
            return this.files.filter(f => f.risk >= 0.8).length;
        },

        getRiskBadgeClass(risk) {
            if (risk >= 0.8) return 'bg-red-100 text-red-800 border border-red-200';
            if (risk >= 0.6) return 'bg-orange-100 text-orange-800 border border-orange-200';
            if (risk >= 0.4) return 'bg-yellow-100 text-yellow-800 border border-yellow-200';
            return 'bg-green-100 text-green-800 border border-green-200';
        },

        getTextColor(risk) {
            if (risk >= 0.8) return 'text-red-600';
            if (risk >= 0.6) return 'text-orange-600';
            if (risk >= 0.4) return 'text-yellow-600';
            return 'text-green-600';
        },

        async selectFile(fileId) {
            this.selectedFileId = fileId;
            this.selectedFileDetails = null; // show loading state
            this.isPanelOpen = true;

            try {
                console.log('Fetching file details for:', fileId, 'scanId:', this.scanId);
                const response = await fetch(`/api/file?id=${encodeURIComponent(fileId)}&scan_id=${encodeURIComponent(this.scanId)}`);
                
                if (!response.ok) {
                    const errorData = await response.text();
                    console.error('File API error:', response.status, errorData);
                    throw new Error('Failed to fetch file details');
                }
                
                const details = await response.json();
                console.log('File details received:', details);
                this.selectedFileDetails = details;

                // Calculate max SHAP value for scaling bars
                const allShaps = [
                    ...(details.shap?.positive || []).map(s => s.value),
                    ...(details.shap?.negative || []).map(s => Math.abs(s.value))
                ];
                this.maxShapValue = allShaps.length ? Math.max(...allShaps) : 1;
                console.log('SHAP values found:', allShaps.length, 'maxShapValue:', this.maxShapValue);

            } catch (error) {
                console.error("Failed to fetch file details:", error);
                this.selectedFileDetails = {
                    filepath: 'Error loading file details: ' + error.message,
                    risk: 0,
                    shap: { positive: [], negative: [] },
                    top_funcs: []
                };
            }
        },

        generateHistogram() {
            // Generate histogram from files data
            if (!this.files || this.files.length === 0) return [];
            
            const bins = Array(20).fill(0);
            this.files.forEach(file => {
                const binIndex = Math.min(Math.floor(file.risk * 20), 19);
                bins[binIndex]++;
            });
            
            return bins.map((count, i) => ({
                bin: `${(i * 0.05).toFixed(2)}-${((i + 1) * 0.05).toFixed(2)}`,
                count: count
            })).filter(d => d.count > 0);
        },

        initCharts() {
            console.log('initCharts called, files count:', this.files?.length);
            
            // Prevent multiple initializations
            if (this._chartsInitialized) {
                console.log('Charts already initialized, skipping');
                return;
            }
            
            if (!this.files || this.files.length === 0) {
                console.warn('No files to chart');
                return;
            }
            
            this._chartsInitialized = true;

            // 1. Risk Histogram
            const histCtx = document.getElementById('riskHistogram');
            const histogramData = this.generateHistogram();
            
            if (histCtx && histogramData.length > 0 && histCtx.offsetParent !== null) {
                if (this.charts.riskHistogram) this.charts.riskHistogram.destroy();
                this.charts.riskHistogram = new Chart(histCtx, {
                    type: 'bar',
                    data: {
                        labels: histogramData.map(d => d.bin),
                        datasets: [{
                            label: 'Files',
                            data: histogramData.map(d => d.count),
                            backgroundColor: histogramData.map(d => {
                                const mid = parseFloat(d.bin.split('-')[0]) + 0.025;
                                if (mid >= 0.8) return '#DC2626';
                                if (mid >= 0.6) return '#EA580C';
                                if (mid >= 0.4) return '#D97706';
                                return '#16A34A';
                            }),
                            borderRadius: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { beginAtZero: true, grid: { borderDash: [2, 4] } },
                            x: { grid: { display: false } }
                        }
                    }
                });
                console.log('✅ Risk histogram chart created');
            
            // 3. Global Feature Importance — fetch real SHAP data from API, fall back to risk tiers
            const featCtx = document.getElementById('featureImportanceChart');
            if (featCtx && featCtx.offsetParent !== null) {
                if (this.charts.featureImportance) this.charts.featureImportance.destroy();

                const buildRiskTierChart = () => {
                    const critical = this.files.filter(f => f.risk >= 0.8).length;
                    const high     = this.files.filter(f => f.risk >= 0.6 && f.risk < 0.8).length;
                    const moderate = this.files.filter(f => f.risk >= 0.4 && f.risk < 0.6).length;
                    const low      = this.files.filter(f => f.risk < 0.4).length;
                    this.charts.featureImportance = new Chart(featCtx, {
                        type: 'bar',
                        data: {
                            labels: ['Critical (≥80%)', 'High (60-80%)', 'Moderate (40-60%)', 'Low (<40%)'],
                            datasets: [{ label: 'Files', data: [critical, high, moderate, low],
                                backgroundColor: ['#DC2626', '#EA580C', '#D97706', '#16A34A'], borderRadius: 4 }]
                        },
                        options: {
                            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                            plugins: { legend: { display: false }, title: { display: true, text: 'Risk Tier Distribution', font: { size: 11 } } },
                            scales: { x: { beginAtZero: true, grid: { borderDash: [2, 4] } }, y: { grid: { display: false } } }
                        }
                    });
                    console.log('✅ Risk tier distribution chart created (SHAP fallback)');
                };

                fetch('/api/importance')
                    .then(r => r.ok ? r.json() : Promise.reject(r.status))
                    .then(data => {
                        if (!Array.isArray(data) || data.length === 0) throw new Error('empty');
                        this.charts.featureImportance = new Chart(featCtx, {
                            type: 'bar',
                            data: {
                                labels: data.map(d => d.feature),
                                datasets: [{ label: 'Mean |SHAP|', data: data.map(d => d.value), backgroundColor: '#4F46E5', borderRadius: 4 }]
                            },
                            options: {
                                indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                                plugins: { legend: { display: false } },
                                scales: {
                                    x: { beginAtZero: true, grid: { borderDash: [2, 4] }, title: { display: true, text: 'Mean |SHAP Value|' } },
                                    y: { grid: { display: false } }
                                }
                            }
                        });
                        console.log('✅ SHAP feature importance chart created from API');
                    })
                    .catch(() => buildRiskTierChart());
            }

            // 4. Risk vs Recency Scatter Plot
            const rrCtx = document.getElementById('riskRecencyChart');
            if (rrCtx && rrCtx.offsetParent !== null) {
                if (this.charts.riskRecency) this.charts.riskRecency.destroy();
                this.charts.riskRecency = new Chart(rrCtx, {
                    type: 'scatter',
                    data: {
                        datasets: [{
                            label: 'Files',
                            data: this.generateRiskRecencyData(),
                            backgroundColor: 'rgba(79, 70, 229, 0.6)',
                            borderColor: '#4F46E5',
                            borderWidth: 1,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        }]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: { callbacks: { label: ctx => `${ctx.raw.filename}: ${ctx.raw.y.toFixed(1)}% risk, ${ctx.raw.x}d ago` } }
                        },
                        scales: {
                            x: { title: { display: true, text: 'Days Since Last Change' }, grid: { borderDash: [2, 4] } },
                            y: { title: { display: true, text: 'Risk Score (%)' }, grid: { borderDash: [2, 4] }, min: 0, max: 100 }
                        }
                    }
                });
                console.log('✅ Risk recency chart created');
            }

            // 5. Model Validation (Confusion Matrix)
            const cmCtx = document.getElementById('confusionMatrixChart');
            if (cmCtx && cmCtx.offsetParent !== null) {
                if (this.charts.confusionMatrix) this.charts.confusionMatrix.destroy();
                const hasBuggyLabels = this.files.some(f => f.buggy !== undefined && f.buggy !== null);
                if (hasBuggyLabels) {
                    const tp = this.files.filter(f => f.buggy === 1 && f.risk >= 0.5).length;
                    const fp = this.files.filter(f => f.buggy === 0 && f.risk >= 0.5).length;
                    const tn = this.files.filter(f => f.buggy === 0 && f.risk < 0.5).length;
                    const fn = this.files.filter(f => f.buggy === 1 && f.risk < 0.5).length;
                    this.charts.confusionMatrix = new Chart(cmCtx, {
                        type: 'doughnut',
                        data: {
                            labels: ['True Positive', 'False Positive', 'True Negative', 'False Negative'],
                            datasets: [{ data: [tp, fp, tn, fn], backgroundColor: ['#16A34A', '#EA580C', '#3B82F6', '#DC2626'], borderWidth: 0 }]
                        },
                        options: {
                            responsive: true, maintainAspectRatio: false, cutout: '70%',
                            plugins: {
                                legend: { position: 'right', labels: { boxWidth: 12 } },
                                tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.raw}` } }
                            }
                        }
                    });
                    console.log('✅ Confusion matrix chart created');
                } else {
                    cmCtx.parentElement.innerHTML = '<div class="h-48 flex items-center justify-center text-gray-400 text-sm text-center">Model validation unavailable<br>(no ground truth labels)</div>';
                }
            }

            console.log('✅ All charts initialized');
        },

        // New filtering and sorting methods
        applyFilters() {
            let filtered = [...this.originalFiles];
            
            // Apply temporal filter
            if (this.timeFilter !== 'all') {
                const days = parseInt(this.timeFilter);
                const cutoffDate = new Date();
                cutoffDate.setDate(cutoffDate.getDate() - days);
                
                filtered = filtered.filter(file => {
                    const lastChange = new Date(file.last_change_date || file.days_since_last_change);
                    return lastChange >= cutoffDate;
                });
            }
            
            // Apply search filter
            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                filtered = filtered.filter(f => 
                    f.filename.toLowerCase().includes(query)
                );
            }
            
            this.files = filtered;
            this.applySorting();
        },

        applySorting() {
            this.files.sort((a, b) => {
                switch (this.sortBy) {
                    case 'risk':
                        return b.risk - a.risk;
                    case 'commits':
                        return (b.commits || 0) - (a.commits || 0);
                    case 'churn':
                        return ((b.lines_added || 0) + (b.lines_deleted || 0)) - 
                               ((a.lines_added || 0) + (a.lines_deleted || 0));
                    case 'recency':
                        return (a.days_since_last_change || 0) - (b.days_since_last_change || 0);
                    default:
                        return b.risk - a.risk;
                }
            });
            
            this.filteredFiles = [...this.files];
        },

        // Generate cumulative gain data
        generateCumulativeGain() {
            if (!this.files || this.files.length === 0) return [];
            
            // Sort by risk descending
            const sorted = [...this.files].sort((a, b) => b.risk - a.risk);
            const totalBugs = sorted.filter(f => f.buggy === 1).length;
            
            if (totalBugs === 0) return [];
            
            const gainData = [];
            let capturedBugs = 0;
            
            for (let i = 0; i < sorted.length; i++) {
                if (sorted[i].buggy === 1) {
                    capturedBugs++;
                }
                
                const percentFiles = ((i + 1) / sorted.length) * 100;
                const percentBugs = (capturedBugs / totalBugs) * 100;
                
                gainData.push({
                    x: percentFiles,
                    y: percentBugs
                });
            }
            
            return gainData;
        },

        // Generate risk vs recency data
        generateRiskRecencyData() {
            if (!this.files || this.files.length === 0) return [];
            
            return this.files.map(file => ({
                x: file.days_since_last_change || 0,
                y: file.risk * 100,
                filename: file.filename
            }));
        }
    }));
}

// Register components when Alpine is ready
if (typeof Alpine !== 'undefined') {
    // Alpine already loaded, register immediately
    document.addEventListener('alpine:init', registerAlpineComponents);
    // Also try direct registration in case alpine:init already fired
    if (Alpine.version) {
        registerAlpineComponents();
    }
} else {
    // Alpine not loaded yet, wait for it
    document.addEventListener('alpine:init', registerAlpineComponents);
}
