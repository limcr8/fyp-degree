import React from 'react';
import { ViewType } from '../types';
import { User } from 'firebase/auth';
import { UserProfileResponse } from '../services/apiService';

interface LayoutProps {
  children: React.ReactNode;
  activeView: ViewType;
  setView: (view: ViewType) => void;
  isDarkMode: boolean;
  toggleTheme: () => void;
  user: User | null;
  handleLogout: () => void;
  profile?: UserProfileResponse | null;
}

const Layout: React.FC<LayoutProps> = ({ 
  children, 
  activeView, 
  setView, 
  isDarkMode, 
  toggleTheme,
  user,
  handleLogout,
  profile
}) => {
  const isAuthPage = activeView === 'login' || activeView === 'signup';
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

  return (
    <div className={`min-h-screen flex flex-col transition-colors duration-300 ${isDarkMode ? 'bg-[#0F172A] text-[#F1F5F9]' : 'bg-[#F8FAFC] text-[#1E293B]'}`}>
      <header className={`sticky top-0 z-50 border-b ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'} px-4 sm:px-6 py-3 sm:py-4`}>
        <div className="max-w-7xl mx-auto flex justify-between items-center gap-2">
          {/* Logo */}
          <div className="flex items-center gap-2 cursor-pointer shrink-0" onClick={() => setView('verify')}>
            <div className="w-9 h-9 sm:w-10 sm:h-10 bg-emerald-500 rounded-lg flex items-center justify-center text-white font-bold text-lg sm:text-xl shadow-lg shadow-emerald-500/20">
              FD
            </div>
            <h1 className="text-base sm:text-xl font-bold tracking-tight whitespace-nowrap">
              <span className="hidden xs:inline sm:hidden">Fake News</span>
              <span className="hidden sm:inline">Fake News <span className="text-emerald-500">Detection</span></span>
            </h1>
          </div>
          
          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-8 font-medium">
            {profile?.role === 'admin' ? (
              <>
                <button
                  onClick={() => setView('admin')}
                  className={`hover:text-emerald-500 transition-colors ${activeView === 'admin' ? 'text-emerald-500' : ''}`}
                >
                  Dashboard
                </button>
                <button
                  onClick={() => setView('admin-users')}
                  className={`hover:text-emerald-500 transition-colors ${activeView === 'admin-users' ? 'text-emerald-500' : ''}`}
                >
                  Manage Users
                </button>
                <button
                  onClick={() => setView('admin-feedback')}
                  className={`hover:text-emerald-500 transition-colors ${activeView === 'admin-feedback' ? 'text-emerald-500' : ''}`}
                >
                  Feedback
                </button>
                <button
                  onClick={() => setView('admin-sources')}
                  className={`hover:text-emerald-500 transition-colors ${activeView === 'admin-sources' ? 'text-emerald-500' : ''}`}
                >
                  Trusted Sources
                </button>
                <button
                  onClick={() => setView('admin-datasets')}
                  className={`hover:text-emerald-500 transition-colors ${activeView === 'admin-datasets' ? 'text-emerald-500' : ''}`}
                >
                  Datasets
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => setView('verify')}
                  className={`hover:text-emerald-500 transition-colors ${activeView === 'verify' ? 'text-emerald-500' : ''}`}
                >
                  Verify
                </button>
                <button
                  onClick={() => setView('portal')}
                  className={`hover:text-emerald-500 transition-colors ${activeView === 'portal' ? 'text-emerald-500' : ''}`}
                >
                  Portal
                </button>
                <button
                  onClick={() => setView('history')}
                  className={`hover:text-emerald-500 transition-colors ${activeView === 'history' ? 'text-emerald-500' : ''}`}
                >
                  History
                </button>
              </>
            )}
          </nav>

          {/* Right-side controls grouped together */}
          <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
            <button 
              onClick={toggleTheme}
              className={`p-2 rounded-lg transition-colors ${isDarkMode ? 'bg-[#334155] text-amber-400 hover:bg-[#3d4d63]' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
              aria-label="Toggle theme"
            >
              {isDarkMode ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m12.728 0l-.707-.707M6.343 6.343l-.707-.707M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>
              )}
            </button>
            
            {/* Mobile hamburger menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className={`md:hidden p-2 rounded-lg transition-colors ${isDarkMode ? 'bg-[#334155] text-slate-200 hover:bg-[#3d4d63]' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
              )}
            </button>
            
            {user ? (
              <div className="flex items-center gap-2 sm:gap-3 ml-1 sm:ml-2">
                <span className={`hidden lg:block text-sm font-semibold ${isDarkMode ? 'text-slate-300' : 'text-slate-600'}`}>
                  Hi, {user.displayName || profile?.username || user.email?.split('@')[0]}
                </span>
                <button 
                  onClick={() => setView('profile')}
                  className={`p-2 rounded-lg transition-colors ${
                    activeView === 'profile' 
                      ? 'text-emerald-500 bg-emerald-500/10' 
                      : `${isDarkMode ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'}`
                  }`}
                  title="Profile Settings"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </button>
                <button 
                  onClick={handleLogout}
                  className="bg-[#EF4444] text-white text-xs font-bold px-3 sm:px-4 py-2 rounded-lg hover:bg-red-600 transition-all"
                >
                  Log out
                </button>
              </div>
            ) : !isAuthPage ? (
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

        {/* Mobile dropdown navigation menu */}
        {mobileMenuOpen && !isAuthPage && (
          <nav className={`md:hidden border-t mt-4 pt-4 pb-2 space-y-1 ${isDarkMode ? 'border-[#334155]' : 'border-[#E2E8F0]'}`}>
            {profile?.role === 'admin' ? (
              <>
                <button
                  onClick={() => { setView('admin'); setMobileMenuOpen(false); }}
                  className={`block w-full text-left px-4 py-2.5 rounded-lg font-medium transition-colors ${
                    activeView === 'admin'
                      ? 'text-emerald-500 bg-emerald-500/10'
                      : isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Dashboard
                </button>
                <button
                  onClick={() => { setView('admin-users'); setMobileMenuOpen(false); }}
                  className={`block w-full text-left px-4 py-2.5 rounded-lg font-medium transition-colors ${
                    activeView === 'admin-users'
                      ? 'text-emerald-500 bg-emerald-500/10'
                      : isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Manage Users
                </button>
                <button
                  onClick={() => { setView('admin-feedback'); setMobileMenuOpen(false); }}
                  className={`block w-full text-left px-4 py-2.5 rounded-lg font-medium transition-colors ${
                    activeView === 'admin-feedback'
                      ? 'text-emerald-500 bg-emerald-500/10'
                      : isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Feedback
                </button>
                <button
                  onClick={() => { setView('admin-sources'); setMobileMenuOpen(false); }}
                  className={`block w-full text-left px-4 py-2.5 rounded-lg font-medium transition-colors ${
                    activeView === 'admin-sources'
                      ? 'text-emerald-500 bg-emerald-500/10'
                      : isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Trusted Sources
                </button>
                <button
                  onClick={() => { setView('admin-datasets'); setMobileMenuOpen(false); }}
                  className={`block w-full text-left px-4 py-2.5 rounded-lg font-medium transition-colors ${
                    activeView === 'admin-datasets'
                      ? 'text-emerald-500 bg-emerald-500/10'
                      : isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Datasets
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => { setView('verify'); setMobileMenuOpen(false); }}
                  className={`block w-full text-left px-4 py-2.5 rounded-lg font-medium transition-colors ${
                    activeView === 'verify'
                      ? 'text-emerald-500 bg-emerald-500/10'
                      : isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Verify
                </button>
                <button
                  onClick={() => { setView('portal'); setMobileMenuOpen(false); }}
                  className={`block w-full text-left px-4 py-2.5 rounded-lg font-medium transition-colors ${
                    activeView === 'portal'
                      ? 'text-emerald-500 bg-emerald-500/10'
                      : isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Portal
                </button>
                <button
                  onClick={() => { setView('history'); setMobileMenuOpen(false); }}
                  className={`block w-full text-left px-4 py-2.5 rounded-lg font-medium transition-colors ${
                    activeView === 'history'
                      ? 'text-emerald-500 bg-emerald-500/10'
                      : isDarkMode ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  History
                </button>
              </>
            )}
          </nav>
        )}
      </header>

      <main className={`max-w-7xl mx-auto px-4 w-full flex-1 ${isAuthPage ? 'py-4' : 'py-8'}`}>
        {children}
      </main>

      <footer className={`border-t mt-12 ${isDarkMode ? 'border-[#334155] bg-[#1E293B]' : 'border-[#E2E8F0] bg-white'} py-12`}>
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="text-lg font-bold mb-4">Fake News Detection</h2>
          <p className={`max-w-md ${isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'}`}>
            Advanced AI-powered verification engine ensuring information integrity. We analyze linguistics, source metadata, and cross-reference authoritative databases to combat misinformation.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
