// CodeSentinel Frontend JavaScript
// Uses Alpine.js for interactivity and Chart.js for data visualization

document.addEventListener('alpine:init', () => {
    Alpine.data('resultsDashboard', () => ({
        files: [],
        filteredFiles: [],
        overview: null,
        searchQuery: '',
        selectedFileId: null,
        selectedFileDetails: null,
        isPanelOpen: false,
        maxShapValue: 1,

        charts: {
            riskHistogram: null,
            featureImportance: null,
            confusionMatrix: null
        },

        async init() {
            try {
                // Fetch overview and files in parallel
                const [overviewRes, filesRes] = await Promise.all([
                    fetch('/api/overview'),
                    fetch('/api/files')
                ]);

                if (!overviewRes.ok || !filesRes.ok) {
                    throw new Error('Failed to fetch dashboard data');
                }

                this.overview = await overviewRes.json();
                this.files = await filesRes.json();
                this.filteredFiles = [...this.files];

                // Setup charts after DOM is updated
                this.$nextTick(() => {
                    this.initCharts();
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
                const response = await fetch(`/api/file?id=${encodeURIComponent(fileId)}`);
                if (!response.ok) throw new Error('Failed to fetch file details');
                
                const details = await response.json();
                this.selectedFileDetails = details;

                // Calculate max SHAP value for scaling bars
                const allShaps = [
                    ...(details.shap?.positive || []).map(s => s.value),
                    ...(details.shap?.negative || []).map(s => Math.abs(s.value))
                ];
                this.maxShapValue = allShaps.length ? Math.max(...allShaps) : 1;

            } catch (error) {
                console.error("Failed to fetch file details:", error);
                this.selectedFileDetails = {
                    filepath: 'Error loading file details',
                    risk: 0,
                    shap: { positive: [], negative: [] },
                    top_funcs: []
                };
            }
        },

        initCharts() {
            if (!this.overview) return;

            // 1. Risk Histogram
            const histCtx = document.getElementById('riskHistogram');
            if (histCtx && this.overview.histogram) {
                if (this.charts.riskHistogram) this.charts.riskHistogram.destroy();
                
                this.charts.riskHistogram = new Chart(histCtx, {
                    type: 'bar',
                    data: {
                        labels: this.overview.histogram.map(d => d.bin),
                        datasets: [{
                            label: 'Files',
                            data: this.overview.histogram.map(d => d.count),
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
            }

            // 2. Confusion Matrix Pie Chart (using cm values)
            const cmCtx = document.getElementById('confusionMatrixChart');
            if (cmCtx && this.overview.confusion_matrix) {
                if (this.charts.confusionMatrix) this.charts.confusionMatrix.destroy();
                
                const cm = this.overview.confusion_matrix;
                // If it's all zeros (which happens if no buggy labels available), show empty
                const hasData = cm.tp + cm.fp + cm.tn + cm.fn > 0;
                
                this.charts.confusionMatrix = new Chart(cmCtx, {
                    type: 'doughnut',
                    data: {
                        labels: ['True Positive', 'False Positive', 'True Negative', 'False Negative'],
                        datasets: [{
                            data: hasData ? [cm.tp, cm.fp, cm.tn, cm.fn] : [0,0,1,0],
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
            }

            // 3. Global Feature Importance (fetch explicitly)
            fetch('/api/importance')
                .then(res => res.json())
                .then(importanceData => {
                    const featCtx = document.getElementById('featureImportanceChart');
                    if (featCtx && importanceData.length) {
                        if (this.charts.featureImportance) this.charts.featureImportance.destroy();
                        
                        this.charts.featureImportance = new Chart(featCtx, {
                            type: 'bar',
                            data: {
                                labels: importanceData.map(d => d.feature),
                                datasets: [{
                                    label: 'Impact',
                                    data: importanceData.map(d => d.value),
                                    backgroundColor: '#6366F1', // indigo-500
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
                    }
                })
                .catch(err => console.error("Failed to load feature importance", err));
        }
    }));
});
