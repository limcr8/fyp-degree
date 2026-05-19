
import React, { useState } from 'react';
import { ViewType } from '../types';

interface LoginViewProps {
  setView: (view: ViewType) => void;
  isDarkMode: boolean;
}

const LoginView: React.FC<LoginViewProps> = ({ setView, isDarkMode }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Simulate login
    setView('verify');
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

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-semibold mb-2 ml-1">Email Address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              className={`w-full px-4 py-3 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'}`}
            />
          </div>

          <div>
            <div className="flex justify-between items-center mb-2 ml-1">
              <label className="text-sm font-semibold">Password</label>
              <button type="button" className="text-xs font-bold text-emerald-500 hover:text-emerald-600">Forgot?</button>
            </div>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className={`w-full px-4 py-3 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'}`}
            />
          </div>

          <button
            type="submit"
            className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98] mt-2"
          >
            Sign In
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

        <div className="mt-6 grid grid-cols-2 gap-4">
          <button className={`flex items-center justify-center gap-2 py-2.5 rounded-xl border font-medium text-sm transition-all ${isDarkMode ? 'border-[#334155] hover:bg-[#334155]' : 'border-[#E2E8F0] hover:bg-slate-50'}`}>
            <img src="https://www.google.com/favicon.ico" className="w-4 h-4" alt="Google" />
            Google
          </button>
          <button className={`flex items-center justify-center gap-2 py-2.5 rounded-xl border font-medium text-sm transition-all ${isDarkMode ? 'border-[#334155] hover:bg-[#334155]' : 'border-[#E2E8F0] hover:bg-slate-50'}`}>
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.627 0-12 5.373-12 12s5.373 12 12 12 12-5.373 12-12-5.373-12-12-12zm3 8h-1.35c-.538 0-.65.221-.65.778v1.222h2l-.209 2h-1.791v7h-3v-7h-2v-2h2v-2.308c0-1.769.931-2.692 3.029-2.692h1.971v3z"/></svg>
            MetaMask
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
