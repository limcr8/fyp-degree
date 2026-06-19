
import React, { useState, useEffect } from 'react';
import Layout from './components/Layout';
import VerificationView from './components/VerificationView';
import AdminView from './components/AdminView';
import LoginView from './components/LoginView';
import SignupView from './components/SignupView';
import PortalView from './components/PortalView';
import ProfileView from './components/ProfileView';
import { ViewType, VerificationResult } from './types';
import { onAuthStateChanged, User } from 'firebase/auth';
import { auth, logoutUser, getVerificationHistory } from './services/firebase';
import { getValidAccessToken, logoutBackendUser, getUserProfile, UserProfileResponse, getUserHistory } from './services/apiService';

const App: React.FC = () => {
  const [activeView, setActiveView] = useState<ViewType>('verify');
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [historyResults, setHistoryResults] = useState<VerificationResult[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [activeResult, setActiveResult] = useState<VerificationResult | null>(null);
  
  // Lifted Verification states for background execution & persistence
  const [inputText, setInputText] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<VerificationResult | null>(null);

  const handleLogout = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          await logoutBackendUser(token);
        } catch (backendErr) {
          console.error("Backend logout error (ignoring):", backendErr);
        }
      }
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      setUser(null);
      setProfile(null);
      await logoutUser();
      setActiveView('verify');
    } catch (err) {
      console.error('Logout error:', err);
    }
  };
  
  // Sync historical result selection into verification state
  useEffect(() => {
    if (activeResult) {
      setInputText(activeResult.text);
      setVerificationResult(activeResult);
      setActiveResult(null);
    }
  }, [activeResult]);

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

  // Listen to Auth State Changes
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      if (currentUser) {
        const token = localStorage.getItem('access_token');
        // Only force-logout if we're NOT on an auth page and there's no backend token.
        // On page refresh, localStorage is synchronously available, so this is safe.
        if (!token && activeView !== 'login' && activeView !== 'signup') {
          console.warn("Firebase session active but no backend token. Forcing logout to re-sync.");
          try { await logoutUser(); } catch (_) {}
          setUser(null);
          setProfile(null);
          setLoading(false);
          return;
        }
      }
      setUser(currentUser);
      setLoading(false);
    });
    return () => unsubscribe();
  }, []); // Run once on mount — activeView changes are handled by other effects


  // Keep backend session fresh by auto-refreshing access token if needed and fetch user profile
  useEffect(() => {
    if (user && activeView !== 'login' && activeView !== 'signup') {
      const checkAndRefresh = async () => {
        try {
          const token = await getValidAccessToken();
          if (token) {
            const profileData = await getUserProfile(token);
            setProfile(profileData);
          } else {
            console.warn("Backend token expired or invalid. Force logging out.");
            handleLogout();
          }
        } catch (err) {
          console.error("Token refresh check or profile fetch failed:", err);
          handleLogout();
        }
      };

      checkAndRefresh();

      const interval = setInterval(checkAndRefresh, 5 * 60 * 1000); // Check every 5 minutes
      return () => clearInterval(interval);
    } else if (!user) {
      setProfile(null);
    }
  }, [user, activeView]);

  // Load history from backend when navigating to history view
  useEffect(() => {
    if (activeView === 'history' && user) {
      setLoadingHistory(true);
      
      const loadHistory = async () => {
        try {
          // 1. Try loading directly from client-side Firestore subcollection
          try {
            console.log("Attempting to load history from Firestore subcollection for user:", user.uid);
            const firestoreHistory = await getVerificationHistory(user.uid);
            if (firestoreHistory && firestoreHistory.length > 0) {
              setHistoryResults(firestoreHistory);
              return;
            }
          } catch (fsErr) {
            console.warn("Could not load history from client-side Firestore, falling back to backend API:", fsErr);
          }

          // 2. Fallback to backend API
          const token = await getValidAccessToken();
          if (!token) throw new Error("No active session.");

          const response = await getUserHistory(token, 50, 0);
          const mapped: VerificationResult[] = response.history.map((item: any) => ({
            id: item.article_id,
            text: item.text,
            classification: item.classification,
            finalAssessment: item.finalAssessment || {
              score: item.classification.confidence,
              label: item.classification.verdict,
              reasoning: item.classification.explanation
            },
            explanation: item.explanation || {
              shapData: [],
              summary: "",
              topFactors: []
            },
            verification: item.verification || {
              sources: [],
              verificationScore: 1.0,
              explanation: ""
            },
            blockchain: item.blockchain,
            timestamp: item.verified_at,
            processingTimeMs: item.processingTimeMs || 0,
            platform: item.platform || "twitter",
            language: item.language || "en"
          }));

          setHistoryResults(mapped);
        } catch (err) {
          console.error("Error loading history:", err);
        } finally {
          setLoadingHistory(false);
        }
      };

      loadHistory();
    }
  }, [activeView, user]);

  const toggleTheme = () => setIsDarkMode(!isDarkMode);

  const renderContent = () => {
    switch (activeView) {
      case 'verify':
        return (
          <VerificationView 
            isDarkMode={isDarkMode} 
            user={user} 
            inputText={inputText}
            setInputText={setInputText}
            result={verificationResult}
            setResult={setVerificationResult}
            isVerifying={isVerifying}
            setIsVerifying={setIsVerifying}
          />
        );
      case 'admin':
        return <AdminView isDarkMode={isDarkMode} profile={profile} />;
      case 'profile':
        return <ProfileView isDarkMode={isDarkMode} profile={profile} setProfile={setProfile} />;
      case 'portal':
        return <PortalView isDarkMode={isDarkMode} />;
      case 'login':
        return <LoginView setView={setActiveView} isDarkMode={isDarkMode} />;
      case 'signup':
        return <SignupView setView={setActiveView} isDarkMode={isDarkMode} />;
      case 'history':
        if (!user) {
          return (
            <div className="text-center py-20 animate-fade-in">
               <div className="w-20 h-20 mx-auto bg-slate-200 dark:bg-slate-800 rounded-full flex items-center justify-center mb-4">
                 <svg className="w-10 h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
               </div>
               <h2 className="text-2xl font-bold">Access Verification History</h2>
               <p className={`mt-2 text-sm ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>Please log in to view your past news verifications stored securely in the database.</p>
               <button 
                 onClick={() => setActiveView('login')}
                 className="mt-8 bg-emerald-500 hover:bg-emerald-600 text-white px-8 py-3 rounded-xl font-bold shadow-lg shadow-emerald-500/20 transition-all"
               >
                 Log In Now
               </button>
            </div>
          );
        }

        return (
          <div className="animate-fade-in space-y-6">
            <h2 className="text-3xl font-black tracking-tight">Your Verification History</h2>
            <p className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>Past news verifications and credibility scores saved to your profile.</p>

            {loadingHistory ? (
              <div className="flex items-center justify-center py-20">
                <div className="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
              </div>
            ) : historyResults.length === 0 ? (
              <div className="text-center py-12 border-2 border-dashed border-slate-300 dark:border-slate-800 rounded-3xl">
                <p className="opacity-50">No verification results found yet.</p>
                <button 
                  onClick={() => setActiveView('verify')}
                  className="mt-4 text-emerald-500 font-bold hover:underline"
                >
                  Verify your first news item
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {historyResults.map((item, idx) => {
                  const getLabel = () => {
                    const label = item.finalAssessment?.label || item.status || 'UNCERTAIN';
                    return label.replace('_', ' ').toUpperCase();
                  };
                  const getLabelClass = () => {
                    const label = (item.finalAssessment?.label || item.status || '').toUpperCase();
                    if (label.includes('REAL')) return 'bg-emerald-500/10 text-emerald-500';
                    if (label.includes('FAKE')) return 'bg-rose-500/10 text-rose-500';
                    return 'bg-amber-500/10 text-amber-500';
                  };
                  const getConfidenceText = () => {
                    const conf = item.finalAssessment ? item.finalAssessment.score : (item.confidence !== undefined ? item.confidence : 0.5);
                    return `${(conf * 100).toFixed(0)}%`;
                  };
                  return (
                    <div 
                      key={idx} 
                      className={`p-6 rounded-2xl border transition-all hover:scale-[1.01] cursor-pointer ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}
                      onClick={() => {
                        setActiveResult(item);
                        setActiveView('verify');
                      }}
                    >
                      <div className="flex justify-between items-start mb-4">
                        <span className={`px-2.5 py-1 text-[10px] font-black rounded uppercase tracking-wider ${getLabelClass()}`}>
                          {getLabel()} ({getConfidenceText()})
                        </span>
                        <span className="text-[10px] opacity-40">
                          {item.timestamp ? new Date(item.timestamp).toLocaleDateString() : 'N/A'}
                        </span>
                      </div>
                      <p className="line-clamp-3 font-semibold text-sm mb-2">{item.text}</p>
                      <p className={`text-xs line-clamp-2 ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                        {item.finalAssessment?.reasoning || item.explanation}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      default:
        return (
          <VerificationView 
            isDarkMode={isDarkMode} 
            user={user} 
            inputText={inputText}
            setInputText={setInputText}
            result={verificationResult}
            setResult={setVerificationResult}
            isVerifying={isVerifying}
            setIsVerifying={setIsVerifying}
          />
        );
    }
  };

  return (
    <Layout 
      activeView={activeView} 
      setView={setActiveView} 
      isDarkMode={isDarkMode}
      toggleTheme={toggleTheme}
      user={user}
      handleLogout={handleLogout}
      profile={profile}
    >
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      ) : (
        renderContent()
      )}
    </Layout>
  );
};

export default App;
