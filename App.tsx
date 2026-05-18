
import React, { useState, useEffect } from 'react';
import Layout from './components/Layout';
import VerificationView from './components/VerificationView';
import AdminView from './components/AdminView';
import LoginView from './components/LoginView';
import SignupView from './components/SignupView';
import { ViewType } from './types';

const App: React.FC = () => {
  const [activeView, setActiveView] = useState<ViewType>('verify');
  const [isDarkMode, setIsDarkMode] = useState(false);

  // Sync theme with body class for simple transitions
  useEffect(() => {
    if (isDarkMode) {
      document.body.classList.add('bg-[#0F172A]');
      document.body.classList.remove('bg-[#F8FAFC]');
    } else {
      document.body.classList.add('bg-[#F8FAFC]');
      document.body.classList.remove('bg-[#0F172A]');
    }
  }, [isDarkMode]);

  const toggleTheme = () => setIsDarkMode(!isDarkMode);

  const renderContent = () => {
    switch (activeView) {
      case 'verify':
        return <VerificationView isDarkMode={isDarkMode} />;
      case 'admin':
        return <AdminView isDarkMode={isDarkMode} />;
      case 'login':
        return <LoginView setView={setActiveView} isDarkMode={isDarkMode} />;
      case 'signup':
        return <SignupView setView={setActiveView} isDarkMode={isDarkMode} />;
      case 'history':
        return (
          <div className="text-center py-20 animate-fade-in">
             <div className="w-20 h-20 mx-auto bg-slate-200 rounded-full flex items-center justify-center mb-4">
               <svg className="w-10 h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
             </div>
             <h2 className="text-2xl font-bold">Verification History</h2>
             <p className="opacity-50 mt-2">Connect your wallet to see your past verifications on-chain.</p>
             <button className="mt-8 bg-emerald-500 text-white px-8 py-3 rounded-xl font-bold shadow-lg shadow-emerald-500/20">Connect Wallet</button>
          </div>
        );
      default:
        return <VerificationView isDarkMode={isDarkMode} />;
    }
  };

  return (
    <Layout 
      activeView={activeView} 
      setView={setActiveView} 
      isDarkMode={isDarkMode}
      toggleTheme={toggleTheme}
    >
      {renderContent()}
    </Layout>
  );
};

export default App;
