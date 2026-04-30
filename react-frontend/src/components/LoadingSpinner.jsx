import { Loader2 } from 'lucide-react';

export default function LoadingSpinner({ size = 'md', text }) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  return (
    <div className="flex flex-col items-center justify-center p-8">
      <Loader2 className={`${sizeClasses[size]} animate-spin text-slate-600`} />
      {text && <p className="mt-4 text-sm text-slate-600">{text}</p>}
    </div>
  );
}
