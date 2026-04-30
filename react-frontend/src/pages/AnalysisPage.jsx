import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { scanApi } from '../lib/api';
import { useState, useMemo } from 'react';
import LoadingSpinner from '../components/LoadingSpinner';
import RiskBadge from '../components/RiskBadge';
import { getRiskLevel, RISK_COLORS, getRiskColor } from '../lib/risk-utils';
import { formatPercent, formatNumber } from '../lib/utils';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Search, Filter } from 'lucide-react';

export default function AnalysisPage() {
  const { scanId } = useParams();
  const [searchTerm, setSearchTerm] = useState('');
  const [filterTier, setFilterTier] = useState(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['analysis', scanId],
    queryFn: () => scanApi.getScanResults(scanId),
  });

  const filteredFiles = useMemo(() => {
    if (!data?.files) return [];

    let result = data.files;

    if (searchTerm) {
      result = result.filter((file) =>
        file.filepath.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    if (filterTier) {
      result = result.filter((file) => getRiskLevel(file.risk) === filterTier);
    }

    return result;
  }, [data?.files, searchTerm, filterTier]);

  if (isLoading) {
    return (
      <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading analysis results..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">Failed to load results</p>
          <Link to="/" className="text-blue-600 hover:underline">
            Go back
          </Link>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const riskDistData = [
    { name: 'CRITICAL', value: data.summary.criticalCount, color: RISK_COLORS.CRITICAL.chart },
    { name: 'HIGH', value: data.summary.highCount, color: RISK_COLORS.HIGH.chart },
    { name: 'MODERATE', value: data.summary.moderateCount, color: RISK_COLORS.MODERATE.chart },
    { name: 'LOW', value: data.summary.lowCount, color: RISK_COLORS.LOW.chart },
  ];

  return (
    <div className="min-h-[calc(100vh-8rem)] bg-slate-50 py-8">
      <div className="max-w-7xl mx-auto px-4 space-y-8">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-slate-900">{data.repoName}</h1>
              <p className="text-slate-600 mt-1">
                {data.language} · {data.summary.totalFiles} files · {new Date(data.scanDate).toLocaleDateString()}
              </p>
            </div>
            <div className="text-right">
              <div className="text-4xl font-bold text-slate-900">
                {Math.round(data.summary.avgRisk * 100)}%
              </div>
              <p className="text-sm text-slate-600">Average Risk</p>
            </div>
          </div>
        </div>

        {/* Risk Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            { label: 'CRITICAL', count: data.summary.criticalCount, level: 'CRITICAL' },
            { label: 'HIGH', count: data.summary.highCount, level: 'HIGH' },
            { label: 'MODERATE', count: data.summary.moderateCount, level: 'MODERATE' },
            { label: 'LOW', count: data.summary.lowCount, level: 'LOW' },
          ].map((stat) => {
            const colors = RISK_COLORS[stat.level];
            return (
              <div
                key={stat.label}
                className={`bg-white rounded-lg shadow p-6 border-l-4 ${colors.border}`}
              >
                <div className="flex justify-between items-center">
                  <span className={`text-sm font-semibold ${colors.text}`}>
                    {stat.label}
                  </span>
                  <span className={`text-2xl font-bold ${colors.text}`}>
                    {stat.count}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">
              Risk Distribution
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={riskDistData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#3B82F6">
                  {riskDistData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">
              Risk Breakdown
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={riskDistData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {riskDistData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* File List */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-slate-200">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="Search files..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setFilterTier(null)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium ${
                    filterTier === null
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  All
                </button>
                {['CRITICAL', 'HIGH', 'MODERATE', 'LOW'].map((tier) => (
                  <button
                    key={tier}
                    onClick={() => setFilterTier(tier)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium ${
                      filterTier === tier
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    {tier}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Risk
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    File
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Score
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Complexity
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Commits
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {filteredFiles.map((file) => (
                  <tr key={file.id} className="hover:bg-slate-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <RiskBadge score={file.risk} />
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-slate-900">
                        {file.filename}
                      </div>
                      <div className="text-sm text-slate-500 truncate max-w-md">
                        {file.filepath}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <span className={`text-sm font-medium ${getRiskColor(file.risk).text}`}>
                        {formatPercent(file.risk)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-slate-900">
                      {file.metrics?.maxComplexity || 0}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-slate-900">
                      {file.metrics?.commits || 0}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                      <Link
                        to={`/file/${encodeURIComponent(file.id)}`}
                        className="text-blue-600 hover:text-blue-700 font-medium"
                      >
                        Details →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {filteredFiles.length === 0 && (
            <div className="p-8 text-center text-slate-500">
              No files match your filters
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
