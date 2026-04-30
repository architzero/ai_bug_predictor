import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { scanApi } from '../lib/api';
import LoadingSpinner from '../components/LoadingSpinner';
import RiskBadge from '../components/RiskBadge';
import { getFeatureLabel, getRiskColor } from '../lib/risk-utils';
import { formatNumber } from '../lib/utils';
import { ArrowLeft, AlertTriangle, CheckCircle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function FileDetailPage() {
  const { fileId } = useParams();

  const { data, isLoading, error } = useQuery({
    queryKey: ['file-detail', fileId],
    queryFn: () => scanApi.getFileDetail(decodeURIComponent(fileId)),
  });

  if (isLoading) {
    return (
      <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading file details..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">Failed to load file details</p>
          <Link to="/" className="text-blue-600 hover:underline">
            Go back
          </Link>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const shapData = data.shap?.positive?.slice(0, 6).map((item) => ({
    feature: getFeatureLabel(item.feature),
    value: item.value,
    color: item.value > 0 ? '#DC2626' : '#16A34A',
  })) || [];

  const topReasons = data.explanation?.topReasons || [];

  return (
    <div className="min-h-[calc(100vh-8rem)] bg-slate-50 py-8">
      <div className="max-w-5xl mx-auto px-4 space-y-6">
        {/* Back Button */}
        <Link
          to={`/analysis/${data.scanId || ''}`}
          className="inline-flex items-center text-sm text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to analysis
        </Link>

        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-slate-900 break-words">
                {data.filename}
              </h1>
              <p className="text-sm text-slate-500 mt-1">{data.filepath}</p>
              <span className="inline-block mt-2 px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded">
                {data.language}
              </span>
            </div>
            <div className="text-right ml-4">
              <div className={`text-4xl font-bold ${getRiskColor(data.risk).text}`}>
                {Math.round(data.risk * 100)}%
              </div>
              <RiskBadge score={data.risk} className="mt-2" />
            </div>
          </div>
        </div>

        {/* Why Risky Section */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">
            Why This File Is Risky
          </h2>
          <div className="space-y-3">
            {topReasons.map((reason, index) => (
              <div key={index} className="flex items-start">
                {reason.impact === 'positive' ? (
                  <AlertTriangle className="w-5 h-5 text-red-600 mr-3 mt-0.5 flex-shrink-0" />
                ) : (
                  <CheckCircle className="w-5 h-5 text-green-600 mr-3 mt-0.5 flex-shrink-0" />
                )}
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    {reason.label}
                  </p>
                  <p className="text-sm text-slate-600">
                    Value: {formatNumber(reason.value)} (Weight: {reason.weight.toFixed(2)})
                  </p>
                </div>
              </div>
            ))}
          </div>

          {data.explanation?.recommendation && (
            <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-900">
                <strong>Recommendation:</strong> {data.explanation.recommendation}
              </p>
            </div>
          )}
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <MetricCard
            label="Cyclomatic Complexity"
            value={data.metrics?.maxComplexity || 0}
            description="Maximum function complexity"
          />
          <MetricCard
            label="Total Commits"
            value={data.metrics?.commits || 0}
            description="Lifetime commit count"
          />
          <MetricCard
            label="Contributors"
            value={data.metrics?.authorCount || 0}
            description="Unique developers"
          />
          <MetricCard
            label="Lines of Code"
            value={data.metrics?.loc || 0}
            description="Total lines"
          />
          <MetricCard
            label="Lines Added"
            value={data.metrics?.linesAdded || 0}
            description="Cumulative additions"
          />
          <MetricCard
            label="Lines Deleted"
            value={data.metrics?.linesDeleted || 0}
            description="Cumulative deletions"
          />
        </div>

        {/* SHAP Feature Contributions */}
        {shapData.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">
              Feature Contributions (SHAP Values)
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={shapData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="feature" type="category" width={150} />
                <Tooltip />
                <Bar dataKey="value">
                  {shapData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="text-xs text-slate-500 mt-2">
              Red bars increase risk, green bars decrease risk
            </p>
          </div>
        )}

        {/* Top Functions */}
        {data.topFunctions && data.topFunctions.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">
              Top Risky Functions
            </h2>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">
                      Function
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">
                      Complexity
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">
                      Length
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">
                      Parameters
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {data.topFunctions.map((func, index) => (
                    <tr key={index}>
                      <td className="px-4 py-3 text-sm font-mono text-slate-900">
                        {func.name}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-slate-900">
                        {func.cx}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-slate-900">
                        {func.len}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-slate-900">
                        {func.params || 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value, description }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-sm text-slate-600">{label}</p>
      <p className="text-2xl font-bold text-slate-900 mt-1">
        {formatNumber(value)}
      </p>
      <p className="text-xs text-slate-500 mt-1">{description}</p>
    </div>
  );
}
