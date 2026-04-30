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

        charts: {
            riskHistogram: null,
            featureImportance: null,
            confusionMatrix: null
        },

        async init() {
            console.log('Initializing results dashboard with scanId:', this.scanId);
            
            if (!this.scanId) {
                console.error('No scan ID provided');
                this.error = "No scan ID provided. Please start a new scan.";
                this.isLoading = false;
                return;
            }
            
            try {
                console.log('Fetching results from:', `/api/scan_results/${this.scanId}`);
                
                // Fetch scan-specific results
                const response = await fetch(`/api/scan_results/${this.scanId}`);
                
                console.log('Response status:', response.status);
                
                if (!response.ok) {
                    if (response.status === 404) {
                        throw new Error('Scan results not found. They may have expired (results are kept for 1 hour). Try running a new scan.');
                    }
                    const errorText = await response.text();
                    console.error('Error response:', errorText);
                    throw new Error(`Failed to fetch scan results: ${response.status}`);
                }

                const data = await response.json();
                console.log('Received data:', data);
                
                if (!data.files || data.files.length === 0) {
                    console.warn('No files in scan results');
                    this.error = "Scan completed but no files were found in the results.";
                    this.isLoading = false;
                    return;
                }
                
                this.overview = { metrics: data.metrics };
                this.repoName = data.repo_name;
                this.files = data.files || [];
                this.filteredFiles = [...this.files];

                console.log(`Loaded ${this.files.length} files for repo: ${this.repoName}`);

                // Setup charts after DOM is updated and transition completes
                this.$nextTick(() => {
                    console.log('$nextTick fired, waiting for transition...');
                    // Delay chart creation to ensure Alpine x-show transition is complete
                    setTimeout(() => {
                        console.log('Initializing charts after transition delay...');
                        this.initCharts();
                    }, 350);
                });

                // Set up search watcher
                this.$watch('searchQuery', (value) => {
                    const query = value.toLowerCase();
                    this.filteredFiles = this.files.filter(f => 
                        f.filename.toLowerCase().includes(query)
                    );
                });

            } catch (error) {
                console.error("Dashboard initialization failed:", error);
                this.error = error.message;
            } finally {
                this.isLoading = false;
                console.log('Initialization complete. Error:', this.error, 'Files:', this.files.length);
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
            console.log('Risk histogram canvas found:', !!histCtx);
            
            // Check if canvas is visible
            if (histCtx) {
                const rect = histCtx.getBoundingClientRect();
                console.log('Canvas visible:', rect.width > 0 && rect.height > 0, 'size:', rect.width, 'x', rect.height);
            }
            
            const histogramData = this.generateHistogram();
            console.log('Histogram data:', histogramData);
            
            if (histCtx && histogramData.length > 0 && histCtx.offsetParent !== null) {
                if (this.charts.riskHistogram) this.charts.riskHistogram.destroy();
                
                console.log('Creating risk histogram chart...');
                this.charts.riskHistogram = new Chart(histCtx, {
                    type: 'bar',
                    data: {
                        labels: histogramData.map(d => d.bin),
                        datasets: [{
                            label: 'Files',
                            data: histogramData.map(d => d.count),
                            backgroundColor: '#4F46E5', // indigo-600
                            borderRadius: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            y: { beginAtZero: true, grid: { borderDash: [2, 4] } },
                            x: { grid: { display: false } }
                        }
                    }
                });
                console.log('✅ Risk histogram chart created');
            } else {
                console.warn('Risk histogram canvas not found or no data');
            }

            // 2. Confusion Matrix Pie Chart - Hide for scans without buggy labels
            const cmCtx = document.getElementById('confusionMatrixChart');
            console.log('Confusion matrix canvas found:', !!cmCtx, 'visible:', cmCtx ? cmCtx.offsetParent !== null : false);
            
            if (cmCtx && cmCtx.offsetParent !== null) {
                // For scans, we don't have ground truth labels, so show placeholder
                const hasBuggyLabels = this.files.some(f => f.buggy === 1);
                console.log('Has buggy labels:', hasBuggyLabels);
                
                if (this.charts.confusionMatrix) {
                    this.charts.confusionMatrix.destroy();
                }
                
                if (hasBuggyLabels) {
                    // Calculate from files
                    const tp = this.files.filter(f => f.buggy === 1 && f.risk >= 0.5).length;
                    const fp = this.files.filter(f => f.buggy === 0 && f.risk >= 0.5).length;
                    const tn = this.files.filter(f => f.buggy === 0 && f.risk < 0.5).length;
                    const fn = this.files.filter(f => f.buggy === 1 && f.risk < 0.5).length;
                    
                    console.log('Creating confusion matrix with TP:', tp, 'FP:', fp, 'TN:', tn, 'FN:', fn);
                    
                    this.charts.confusionMatrix = new Chart(cmCtx, {
                        type: 'doughnut',
                        data: {
                            labels: ['True Positive', 'False Positive', 'True Negative', 'False Negative'],
                            datasets: [{
                                data: [tp, fp, tn, fn],
                                backgroundColor: ['#16A34A', '#EA580C', '#3B82F6', '#DC2626'],
                                borderWidth: 0
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            cutout: '70%',
                            plugins: {
                                legend: { position: 'right', labels: { boxWidth: 12 } },
                                tooltip: {
                                    callbacks: {
                                        label: function(context) {
                                            return ` ${context.label}: ${context.raw}`;
                                        }
                                    }
                                }
                            }
                        }
                    });
                    console.log('✅ Confusion matrix chart created');
                } else {
                    // Show placeholder message
                    cmCtx.parentElement.innerHTML = '<div class="h-48 flex items-center justify-center text-gray-400 text-sm text-center">Confusion matrix unavailable<br>(no ground truth labels for scanned repository)</div>';
                    console.log('ℹ️ Confusion matrix placeholder shown (no ground truth)');
                }
            }

            // 3. Feature Importance - Use risk distribution instead
            const featCtx = document.getElementById('featureImportanceChart');
            console.log('Feature importance canvas found:', !!featCtx, 'visible:', featCtx ? featCtx.offsetParent !== null : false);
            
            if (featCtx && featCtx.offsetParent !== null) {
                if (this.charts.featureImportance) {
                    this.charts.featureImportance.destroy();
                }
                
                // Show risk tier distribution instead of feature importance for scans
                const critical = this.files.filter(f => f.risk >= 0.8).length;
                const high = this.files.filter(f => f.risk >= 0.6 && f.risk < 0.8).length;
                const moderate = this.files.filter(f => f.risk >= 0.4 && f.risk < 0.6).length;
                const low = this.files.filter(f => f.risk < 0.4).length;
                
                console.log('Risk tiers - Critical:', critical, 'High:', high, 'Moderate:', moderate, 'Low:', low);
                
                this.charts.featureImportance = new Chart(featCtx, {
                    type: 'bar',
                    data: {
                        labels: ['Critical (80-100%)', 'High (60-80%)', 'Moderate (40-60%)', 'Low (0-40%)'],
                        datasets: [{
                            label: 'Files',
                            data: [critical, high, moderate, low],
                            backgroundColor: ['#DC2626', '#EA580C', '#D97706', '#16A34A'],
                            borderRadius: 4
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            x: { beginAtZero: true, grid: { borderDash: [2, 4] } },
                            y: { grid: { display: false } }
                        }
                    }
                });
                console.log('✅ Feature importance (risk tier) chart created');
            } else {
                console.warn('Feature importance canvas not found');
            }
            
            console.log('✅ All charts initialized successfully');
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
