import { Link, useLocation } from 'react-router-dom';
import { Home, BarChart3, Info, Github } from 'lucide-react';

export default function Layout({ children }) {
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  return (
    <div className="min-h-screen flex flex-col">
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex space-x-8">
              <Link
                to="/"
                className="inline-flex items-center px-1 pt-1 text-sm font-medium text-slate-900 border-b-2 border-transparent hover:border-slate-300"
              >
                <Home className="w-4 h-4 mr-2" />
                Home
              </Link>
              <Link
                to="/about"
                className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                  isActive('/about')
                    ? 'text-slate-900 border-b-2 border-slate-900'
                    : 'text-slate-500 border-b-2 border-transparent hover:border-slate-300 hover:text-slate-700'
                }`}
              >
                <Info className="w-4 h-4 mr-2" />
                About
              </Link>
              <Link
                to="/dashboard"
                className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                  isActive('/dashboard')
                    ? 'text-slate-900 border-b-2 border-slate-900'
                    : 'text-slate-500 border-b-2 border-transparent hover:border-slate-300 hover:text-slate-700'
                }`}
              >
                <BarChart3 className="w-4 h-4 mr-2" />
                Dashboard
              </Link>
            </div>
            <div className="flex items-center">
              <a
                href="/auth/github/login"
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-slate-700 hover:text-slate-900"
              >
                <Github className="w-4 h-4 mr-2" />
                Sign in
              </a>
            </div>
          </div>
        </div>
      </nav>

      <main className="flex-1">{children}</main>

      <footer className="bg-white border-t border-slate-200 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-slate-500">
            AI Bug Predictor - ML-powered defect prediction
          </p>
        </div>
      </footer>
    </div>
  );
}
