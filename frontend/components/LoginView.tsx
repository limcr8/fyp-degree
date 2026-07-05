
import React, { useState } from 'react';
import { ViewType } from '../types';
import { signInWithEmailAndPassword } from 'firebase/auth';
import { auth, signInWithGoogle } from '../services/firebase';
import { loginBackendUser, registerBackendUser } from '../services/apiService';

interface LoginViewProps {
  setView: (view: ViewType) => void;
  isDarkMode: boolean;
}

const LoginView: React.FC<LoginViewProps> = ({ setView, isDarkMode }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // 1. Authenticate with Firebase first to verify active Firebase credentials
      const userCredential = await signInWithEmailAndPassword(auth, email, password);

      // 2. Authenticate with backend API
      let loginData;
      try {
        loginData = await loginBackendUser(email, password);
      } catch (err: any) {
        // If the backend doesn't have a record of this user (but Firebase successfully authenticated them),
        // auto-register the user on the backend.
        if (err.message && err.message.includes("Invalid email or password")) {
          const formattedUsername = userCredential.user.displayName?.replace(/\s+/g, '_').toLowerCase() || email.split('@')[0];
          await registerBackendUser(formattedUsername, email, password);
          // Try to log in again now that the backend record is synced
          loginData = await loginBackendUser(email, password);
        } else {
          throw err;
        }
      }

      localStorage.setItem('access_token', loginData.access_token);
      localStorage.setItem('refresh_token', loginData.refresh_token);
      localStorage.setItem('user', JSON.stringify(loginData.user));

      setView('verify');
    } catch (err: any) {
      console.error("Login Error:", err);
      if (err.code === 'auth/invalid-credential') {
        setError("Invalid email or password.");
      } else if (err.code === 'auth/invalid-email') {
        setError("Please enter a valid email address.");
      } else if (err.code === 'auth/user-disabled') {
        setError("This account has been disabled.");
      } else {
        setError(err.message || "An error occurred during login.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setError(null);
    setLoading(true);

    try {
      const firebaseUser = await signInWithGoogle();
      if (firebaseUser && firebaseUser.email) {
        const email = firebaseUser.email;
        // Use a secure derived password based on the Firebase UID
        const password = `GoogleUser_${firebaseUser.uid}_SecretPass!`;
        
        let loginData;
        try {
          loginData = await loginBackendUser(email, password);
        } catch (err: any) {
          // If the backend doesn't have a record of this user, auto-register them
          if (err.message && err.message.includes("Invalid email or password")) {
            const formattedUsername = firebaseUser.displayName?.replace(/\s+/g, '_').toLowerCase() || email.split('@')[0];
            await registerBackendUser(formattedUsername, email, password);
            // Try to log in again now that the backend record is synced
            loginData = await loginBackendUser(email, password);
          } else {
            throw err;
          }
        }

        localStorage.setItem('access_token', loginData.access_token);
        localStorage.setItem('refresh_token', loginData.refresh_token);
        localStorage.setItem('user', JSON.stringify(loginData.user));
      }
      setView('verify');
    } catch (err: any) {
      console.error("Google login error:", err);
      if (err.code !== 'auth/popup-closed-by-user') {
        setError(err.message || "An error occurred during Google sign-in.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 animate-fade-in">
      <div className={`w-full max-w-md p-8 rounded-3xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-xl shadow-slate-200/50'}`}>
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-emerald-500 rounded-2xl flex items-center justify-center text-white font-bold text-2xl shadow-lg shadow-emerald-500/20 mx-auto mb-4">
            FD
          </div>
          <h2 className="text-2xl font-bold">Welcome Back</h2>
          <p className={`mt-2 text-sm ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
            Securely access your verification dashboard
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
            <div className="flex justify-between items-center mb-2 ml-1">
              <label className="text-sm font-semibold">Password</label>
              <button type="button" className="text-xs font-bold text-emerald-500 hover:text-emerald-600">Forgot?</button>
            </div>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                disabled={loading}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
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

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98] mt-2 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                Signing In...
              </>
            ) : "Sign In"}
          </button>
        </form>

        <div className="mt-8 relative">
          <div className="absolute inset-0 flex items-center">
            <div className={`w-full border-t ${isDarkMode ? 'border-[#334155]' : 'border-[#E2E8F0]'}`}></div>
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className={`px-2 ${isDarkMode ? 'bg-[#1E293B] text-slate-500' : 'bg-white text-slate-400'}`}>Or continue with</span>
          </div>
        </div>

        <div className="mt-6 flex justify-center">
          <button 
            type="button"
            disabled={loading}
            onClick={handleGoogleLogin}
            className={`flex items-center justify-center gap-2 py-2.5 px-8 rounded-xl border font-medium text-sm transition-all ${isDarkMode ? 'border-[#334155] hover:bg-[#334155]' : 'border-[#E2E8F0] hover:bg-slate-50'} disabled:opacity-50`}
          >
            <img src="https://www.google.com/favicon.ico" className="w-4 h-4" alt="Google" />
            Google
          </button>
        </div>

        <p className={`mt-8 text-center text-sm ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
          Don't have an account?{' '}
          <button onClick={() => setView('signup')} className="font-bold text-emerald-500 hover:text-emerald-600 underline underline-offset-4">Create account</button>
        </p>
      </div>
    </div>
  );
};

export default LoginView;
