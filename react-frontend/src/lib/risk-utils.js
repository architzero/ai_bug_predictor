export const RISK_COLORS = {
  CRITICAL: {
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
    badge: 'bg-red-100 text-red-800',
    chart: '#DC2626',
  },
  HIGH: {
    bg: 'bg-orange-50',
    text: 'text-orange-700',
    border: 'border-orange-200',
    badge: 'bg-orange-100 text-orange-800',
    chart: '#EA580C',
  },
  MODERATE: {
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
    badge: 'bg-amber-100 text-amber-800',
    chart: '#D97706',
  },
  LOW: {
    bg: 'bg-green-50',
    text: 'text-green-700',
    border: 'border-green-200',
    badge: 'bg-green-100 text-green-800',
    chart: '#16A34A',
  },
};

export function getRiskLevel(score) {
  if (score >= 0.8) return 'CRITICAL';
  if (score >= 0.6) return 'HIGH';
  if (score >= 0.4) return 'MODERATE';
  return 'LOW';
}

export function getRiskColor(score) {
  const level = getRiskLevel(score);
  return RISK_COLORS[level];
}

export const FEATURE_LABELS = {
  bug_recency_score: 'Bug history',
  avg_complexity: 'Code complexity (avg)',
  max_complexity: 'Code complexity (peak)',
  temporal_bug_memory: 'Long-term bug memory',
  instability_score: 'File instability',
  commits: 'Total commit history',
  author_count: 'Contributor count',
  max_coupling_strength: 'Coupling strength',
  recency_ratio: 'Recent vs. historical activity',
  commit_burst_score: 'Commit burst activity',
  coupling_risk: 'Coupling risk',
  avg_params: 'Avg function parameters',
  max_function_length: 'Longest function',
  complexity_vs_baseline: 'Complexity vs language baseline',
  loc_per_function: 'Avg function size',
  lines_added: 'Lines added (lifetime)',
  lines_deleted: 'Lines deleted (lifetime)',
  max_added: 'Largest single addition',
  avg_commit_size: 'Avg commit size',
  max_commit_ratio: 'Largest commit proportion',
  days_since_last_change: 'Days since last change',
  coupled_file_count: 'Coupled file count',
  coupled_recent_missing: 'Co-changed files lagging',
  recent_commit_burst: 'Recent activity burst',
  recent_bug_flag: 'Recent bug indicator',
  ownership: 'Code ownership',
  loc: 'Lines of code',
  burst_risk: 'Burst risk',
  temporal_bug_risk: 'Temporal bug risk',
};

export function getFeatureLabel(feature) {
  return FEATURE_LABELS[feature] || feature;
}
