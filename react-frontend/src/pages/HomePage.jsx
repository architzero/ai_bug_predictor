import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { scanApi } from '../lib/api';
import { Github, AlertCircle } from 'lucide-react';

export default function HomePage() {
  const [repoUrl, setRepoUrl] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const scanMutation = useMutation({
    mutationFn: scanApi.startScan,
    onSuccess: (data) => {
      navigate(`/scan/${data.scan_id}`);
    },
    onError: (err) => {
      setError(err.response?.data?.error || 'Failed to start scan');
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    if (!repoUrl.trim()) {
      setError('Please enter a repository URL');
      return;
    }

    if (repoUrl.startsWith('http') && !repoUrl.includes('github.com')) {
      setError('Only GitHub repositories are supported');
      return;
    }

    scanMutation.mutate({ path: repoUrl });
  };

  return (
    <div className="min-h-[calc(100vh-8rem)] bg-gradient-to-b from-slate-50 to-slate-100">
      <div className="max-w-4xl mx-auto px-4 py-24">
        <div className="text-center space-y-6 mb-12">
          <h1 className="text-5xl font-bold text-slate-900">
            AI Bug Predictor
          </h1>
          <p className="text-xl text-slate-600 max-w-2xl mx-auto">
            Predict defect-prone files before failures occur using ML-powered
            static analysis and Git history mining
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-xl p-8 mb-12">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <input
                type="text"
                placeholder="https://github.com/owner/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-lg"
                disabled={scanMutation.isPending}
              />
              {error && (
                <div className="mt-2 flex items-center text-sm text-red-600">
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {error}
                </div>
              )}
              <p className="mt-2 text-sm text-slate-500">
                Supported: Python, JavaScript, TypeScript, Java, Go, Ruby, PHP,
                C#, C++, Rust
              </p>
            </div>

            <button
              type="submit"
              disabled={scanMutation.isPending}
              className="w-full bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {scanMutation.isPending ? 'Starting Analysis...' : 'Analyze Repository'}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-slate-200">
            <a
              href="/auth/github/login"
              className="flex items-center justify-center w-full px-6 py-3 border border-slate-300 rounded-lg font-medium text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <Github className="w-5 h-5 mr-2" />
              Sign in with GitHub
            </a>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <FeatureCard
            icon="🎯"
            title="ML-Powered Prediction"
            description="Random Forest model trained on 1,654 files across 9 repositories"
          />
          <FeatureCard
            icon="📊"
            title="Explainable AI"
            description="SHAP-based explanations show why each file is risky"
          />
          <FeatureCard
            icon="⚡"
            title="Cross-Project Learning"
            description="Generalizes across languages with 94% PR-AUC"
          />
        </div>
      </div>
    </div>
  );
}

function FeatureCard({ icon, title, description }) {
  return (
    <div className="bg-white rounded-lg p-6 text-center space-y-3 shadow-sm">
      <div className="text-4xl">{icon}</div>
      <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
      <p className="text-sm text-slate-600">{description}</p>
    </div>
  );
}
