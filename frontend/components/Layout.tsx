
import React from 'react';
import { ViewType } from '../types';

interface LayoutProps {
  children: React.ReactNode;
  activeView: ViewType;
  setView: (view: ViewType) => void;
  isDarkMode: boolean;
  toggleTheme: () => void;
}

const Layout: React.FC<LayoutProps> = ({ children, activeView, setView, isDarkMode, toggleTheme }) => {
  const isAuthPage = activeView === 'login' || activeView === 'signup';

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDarkMode ? 'bg-[#0F172A] text-[#F1F5F9]' : 'bg-[#F8FAFC] text-[#1E293B]'}`}>
      <header className={`sticky top-0 z-50 border-b ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'} px-6 py-4`}>
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => setView('verify')}>
            <div className="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-emerald-500/20">
              FD
            </div>
            <h1 className="text-xl font-bold tracking-tight">Fake News <span className="text-emerald-500">Detection</span></h1>
          </div>
          
          <nav className="hidden md:flex items-center gap-8 font-medium">
            <button 
              onClick={() => setView('verify')}
              className={`hover:text-emerald-500 transition-colors ${activeView === 'verify' ? 'text-emerald-500' : ''}`}
            >
              Verify
            </button>
            <button 
              onClick={() => setView('history')}
              className={`hover:text-emerald-500 transition-colors ${activeView === 'history' ? 'text-emerald-500' : ''}`}
            >
              History
            </button>
            <button 
              onClick={() => setView('admin')}
              className={`hover:text-emerald-500 transition-colors ${activeView === 'admin' ? 'text-emerald-500' : ''}`}
            >
              Dashboard
            </button>
          </nav>

          <div className="flex items-center gap-3">
            <button 
              onClick={toggleTheme}
              className={`p-2 rounded-full ${isDarkMode ? 'bg-[#334155] text-amber-400' : 'bg-slate-100 text-slate-600'}`}
            >
              {isDarkMode ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m12.728 0l-.707-.707M6.343 6.343l-.707-.707M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>
              )}
            </button>
            
            {!isAuthPage ? (
              <div className="flex items-center gap-3 ml-2">
                <button 
                  onClick={() => setView('login')}
                  className={`hidden sm:block text-sm font-bold hover:text-emerald-500 transition-colors ${isDarkMode ? 'text-slate-300' : 'text-slate-600'}`}
                >
                  Log in
                </button>
                <button 
                  onClick={() => setView('signup')}
                  className="bg-emerald-500 text-white text-xs font-bold px-4 py-2 rounded-xl hover:bg-emerald-600 transition-all"
                >
                  Register
                </button>
              </div>
            ) : (
              <button 
                onClick={() => setView('verify')}
                className="text-xs font-bold opacity-50 hover:opacity-100 underline underline-offset-4 ml-4"
              >
                Back home
              </button>
            )}
          </div>
        </div>
      </header>

      <main className={`max-w-7xl mx-auto px-4 ${isAuthPage ? 'py-4' : 'py-8'}`}>
        {children}
      </main>

      <footer className={`mt-20 border-t ${isDarkMode ? 'border-[#334155] bg-[#1E293B]' : 'border-[#E2E8F0] bg-white'} py-12`}>
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 md:grid-cols-4 gap-8">
          <div className="col-span-2">
            <h2 className="text-lg font-bold mb-4">Fake News Detection</h2>
            <p className={`max-w-md ${isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'}`}>
              Advanced AI-powered verification engine ensuring information integrity. We analyze linguistics, source metadata, and cross-reference authoritative databases to combat misinformation.
            </p>
          </div>
          <div>
            <h3 className="font-bold mb-4">Verification</h3>
            <ul className={`space-y-2 ${isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'}`}>
              <li>How it Works</li>
              <li>API Integration</li>
              <li>Whitepaper</li>
            </ul>
          </div>
          <div>
            <h3 className="font-bold mb-4">Legal</h3>
            <ul className={`space-y-2 ${isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'}`}>
              <li>Privacy Policy</li>
              <li>Terms of Service</li>
              <li>Data Usage</li>
            </ul>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
