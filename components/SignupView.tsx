
import React, { useState } from 'react';
import { ViewType } from '../types';

interface SignupViewProps {
  setView: (view: ViewType) => void;
  isDarkMode: boolean;
}

const SignupView: React.FC<SignupViewProps> = ({ setView, isDarkMode }) => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Simulate signup
    setView('verify');
  };

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

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-semibold mb-2 ml-1">Full Name</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="John Doe"
              className={`w-full px-4 py-3 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'}`}
            />
          </div>

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
            <label className="text-sm font-semibold mb-2 block ml-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min. 8 characters"
              className={`w-full px-4 py-3 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'}`}
            />
          </div>

          <div className="flex items-start gap-2 ml-1">
            <input type="checkbox" required className="mt-1 accent-emerald-500" />
            <span className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
              I agree to the <button type="button" className="text-emerald-500 font-bold">Terms of Service</button> and <button type="button" className="text-emerald-500 font-bold">Privacy Policy</button>
            </span>
          </div>

          <button
            type="submit"
            className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98] mt-2"
          >
            Get Started
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
