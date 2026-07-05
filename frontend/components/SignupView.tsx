
import React, { useState } from 'react';
import { ViewType } from '../types';
import { createUserWithEmailAndPassword, updateProfile, User } from 'firebase/auth';
import { auth, db } from '../services/firebase';
import { doc, setDoc } from 'firebase/firestore';
import { registerBackendUser, loginBackendUser } from '../services/apiService';

interface SignupViewProps {
  setView: (view: ViewType) => void;
  isDarkMode: boolean;
  setUser: (user: User | null) => void;
}

const SignupView: React.FC<SignupViewProps> = ({ setView, isDarkMode, setUser }) => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiKeySuccess, setApiKeySuccess] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // 1. Create Firebase Auth user first so we have the uid
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);
      if (userCredential.user) {
        await updateProfile(userCredential.user, { displayName: name });
      }

      // 2. Register with backend (uses display name; backend auto-generates if empty)
      const backendUser = await registerBackendUser(name, email, password, userCredential.user?.uid);
      const generatedApiKey = backendUser.api_key;

      if (userCredential.user) {
        // Sync local user state immediately so displayName is populated in top-right nav
        await userCredential.user.reload();
        setUser(null);
        setTimeout(() => {
          setUser(auth.currentUser);
        }, 0);
      }

      // 3. Authenticate with backend API to retrieve access tokens immediately
      const loginData = await loginBackendUser(email, password);
      localStorage.setItem('access_token', loginData.access_token);
      localStorage.setItem('refresh_token', loginData.refresh_token);
      localStorage.setItem('user', JSON.stringify(loginData.user));

      setApiKeySuccess(generatedApiKey);
    } catch (err: any) {
      console.error("Signup Error:", err);
      if (err.message && err.message.includes("registered")) {
        setError("This email address or username is already registered.");
      } else if (err.code === 'auth/email-already-in-use') {
        setError("This email address is already in use.");
      } else if (err.code === 'auth/invalid-email') {
        setError("Please enter a valid email address.");
      } else if (err.code === 'auth/weak-password') {
        setError("Password should be at least 6 characters.");
      } else {
        setError(err.message || "An error occurred during signup.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (apiKeySuccess) {
    const handleCopy = () => {
      navigator.clipboard.writeText(apiKeySuccess);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    };

    return (
      <div className="flex flex-col items-center justify-center py-12 px-4 animate-fade-in">
        <div className={`w-full max-w-md p-8 rounded-3xl border text-center ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-xl shadow-slate-200/50'}`}>
          <div className="w-16 h-16 bg-emerald-500 rounded-full flex items-center justify-center text-white font-bold text-3xl shadow-lg shadow-emerald-500/20 mx-auto mb-6">
            ✓
          </div>
          <h2 className="text-2xl font-bold">Registration Successful!</h2>
          <p className={`mt-2 text-sm ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
            Your account is created. Save your API key for accessing verification services.
          </p>

          <div className={`mt-8 p-4 rounded-xl border text-left space-y-2 relative overflow-hidden ${
            isDarkMode ? 'bg-[#0F172A] border-[#334155]' : 'bg-[#F8FAFC] border-[#E2E8F0]'
          }`}>
            <span className="text-[9px] font-black uppercase text-slate-400 tracking-wider">Your Secret API Key</span>
            <div className="flex justify-between items-center gap-2">
              <span className="font-mono text-xs text-emerald-400 truncate select-all">{apiKeySuccess}</span>
              <button 
                onClick={handleCopy}
                className="bg-emerald-500 hover:bg-emerald-600 text-white text-[10px] font-bold px-3 py-1.5 rounded-lg transition-all transform active:scale-95 shrink-0"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          <button
            onClick={() => setView('verify')}
            className="w-full mt-8 py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98]"
          >
            Continue to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 animate-fade-in">
      <div className={`w-full max-w-md p-8 rounded-3xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-xl shadow-slate-200/50'}`}>
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-emerald-500 rounded-2xl flex items-center justify-center text-white font-bold text-2xl shadow-lg shadow-emerald-500/20 mx-auto mb-4">
            FD
          </div>
          <h2 className="text-2xl font-bold">Create Account</h2>
          <p className={`mt-2 text-sm ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
            Join the decentralized truth network
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs font-semibold flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-semibold mb-2 ml-1">Full Name</label>
            <input
              type="text"
              required
              disabled={loading}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="John Doe"
              className={`w-full px-4 py-3 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'} disabled:opacity-50`}
            />
          </div>

          <div>
            <label className="block text-sm font-semibold mb-2 ml-1">Email Address</label>
            <input
              type="email"
              required
              disabled={loading}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              className={`w-full px-4 py-3 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'} disabled:opacity-50`}
            />
          </div>

          <div>
            <label className="text-sm font-semibold mb-2 block ml-1">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                disabled={loading}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 6 characters"
                className={`w-full pl-4 pr-12 py-3 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'} disabled:opacity-50`}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 focus:outline-none transition-colors"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div className="flex items-start gap-2 ml-1">
            <input type="checkbox" required disabled={loading} className="mt-1 accent-emerald-500" />
            <span className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
              I agree to the <button type="button" className="text-emerald-500 font-bold">Terms of Service</button> and <button type="button" className="text-emerald-500 font-bold">Privacy Policy</button>
            </span>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98] mt-2 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                Creating Account...
              </>
            ) : "Get Started"}
          </button>
        </form>

        <p className={`mt-8 text-center text-sm ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
          Already have an account?{' '}
          <button onClick={() => setView('login')} className="font-bold text-emerald-500 hover:text-emerald-600 underline underline-offset-4">Sign in here</button>
        </p>
      </div>
    </div>
  );
};

export default SignupView;
