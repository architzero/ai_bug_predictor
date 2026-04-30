import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { CheckCircle2, Circle, Loader2, AlertCircle } from 'lucide-react';

export default function ScanProgressPage() {
  const { scanId } = useParams();
  const navigate = useNavigate();
  const [progress, setProgress] = useState({
    progress: 0,
    status: 'Initializing...',
    complete: false,
    error: null,
  });

  useEffect(() => {
    const eventSource = new EventSource(`/api/scan_progress/${scanId}`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setProgress(data);

      if (data.complete) {
        eventSource.close();
        if (!data.error) {
          setTimeout(() => {
            navigate(`/analysis/${scanId}`);
          }, 2000);
        }
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setProgress((prev) => ({
        ...prev,
        error: 'Connection lost. Please refresh the page.',
      }));
    };

    return () => eventSource.close();
  }, [scanId, navigate]);

  const steps = [
    { label: 'Clone repository', threshold: 10 },
    { label: 'Mine git history', threshold: 25 },
    { label: 'Analyze code', threshold: 45 },
    { label: 'Build features', threshold: 65 },
    { label: 'Predict risks', threshold: 80 },
    { label: 'Generate explanations', threshold: 90 },
  ];

  const getStepStatus = (threshold) => {
    if (progress.progress > threshold) return 'complete';
    if (progress.progress >= threshold - 10) return 'active';
    return 'pending';
  };

  return (
    <div className="min-h-[calc(100vh-8rem)] bg-slate-50 py-12">
      <div className="max-w-2xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-lg p-8">
          <h1 className="text-2xl font-bold text-slate-900 mb-6">
            Analyzing Repository
          </h1>

          <div className="mb-8">
            <div className="flex justify-between text-sm text-slate-600 mb-2">
              <span>{progress.status}</span>
              <span>{progress.progress}%</span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress.progress}%` }}
              />
            </div>
          </div>

          <div className="space-y-4">
            {steps.map((step, index) => {
              const status = getStepStatus(step.threshold);
              return (
                <div key={index} className="flex items-center text-sm">
                  {status === 'complete' && (
                    <CheckCircle2 className="w-6 h-6 text-green-600 mr-3" />
                  )}
                  {status === 'active' && (
                    <Loader2 className="w-6 h-6 text-blue-600 mr-3 animate-spin" />
                  )}
                  {status === 'pending' && (
                    <Circle className="w-6 h-6 text-slate-300 mr-3" />
                  )}
                  <span
                    className={
                      status === 'pending'
                        ? 'text-slate-500'
                        : 'text-slate-900 font-medium'
                    }
                  >
                    {step.label}
                  </span>
                </div>
              );
            })}
          </div>

          {progress.complete && !progress.error && (
            <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm text-green-800 mb-2">Analysis complete!</p>
              <a
                href={`/analysis/${scanId}`}
                className="text-sm text-green-600 hover:text-green-700 font-medium"
              >
                View Results →
              </a>
            </div>
          )}

          {progress.error && (
            <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-center text-sm text-red-800 mb-2">
                <AlertCircle className="w-4 h-4 mr-1" />
                {progress.error}
              </div>
              <a
                href="/"
                className="text-sm text-red-600 hover:text-red-700 font-medium"
              >
                Try again
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
