import React, { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { UserProfileResponse, getAdminDashboard, AdminDashboardResponse, getValidAccessToken, getAdminAnalytics, AdminAnalyticsResponse } from '../services/apiService';

const chartData = [
  { name: 'Mon', count: 400 },
  { name: 'Tue', count: 300 },
  { name: 'Wed', count: 600 },
  { name: 'Thu', count: 800 },
  { name: 'Fri', count: 500 },
  { name: 'Sat', count: 900 },
  { name: 'Sun', count: 1200 },
];

interface AdminViewProps {
  isDarkMode: boolean;
  profile: UserProfileResponse | null;
}

const AdminView: React.FC<AdminViewProps> = ({ isDarkMode, profile }) => {
  const cardClass = `p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`;
  const [showApiKey, setShowApiKey] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  // Live admin dashboard data states
  const [stats, setStats] = useState<AdminDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Analytics states
  const [analytics, setAnalytics] = useState<AdminAnalyticsResponse | null>(null);
  const [period, setPeriod] = useState<string>("30d");
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  useEffect(() => {
    const fetchDashboardStats = async () => {
      try {
        const token = await getValidAccessToken();
        if (!token) {
          throw new Error("No active session token found. Please log in.");
        }
        // Retrieve custom admin override token from env
        const adminToken = import.meta.env.VITE_ADMIN_TOKEN || "super_secret_admin_token_change_me";
        const response = await getAdminDashboard(token, adminToken);
        setStats(response);
      } catch (err: any) {
        setError(err.message || "Failed to load dashboard metrics.");
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardStats();
  }, []);

  useEffect(() => {
    const fetchAnalytics = async () => {
      setAnalyticsLoading(true);
      try {
        const token = await getValidAccessToken();
        if (!token) return;
        const adminToken = import.meta.env.VITE_ADMIN_TOKEN || "super_secret_admin_token_change_me";
        const response = await getAdminAnalytics(token, adminToken, period);
        setAnalytics(response);
      } catch (err: any) {
        console.error("Failed to load analytics: ", err);
      } finally {
        setAnalyticsLoading(false);
      }
    };

    fetchAnalytics();
  }, [period]);

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4 animate-fade-in">
        <div className="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
        <p className={`text-sm font-semibold ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
          Loading system metrics...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-md mx-auto p-6 rounded-2xl border border-red-500/20 bg-red-500/5 text-center space-y-4 animate-fade-in my-12">
        <span className="text-3xl">⚠️</span>
        <h3 className="font-bold text-lg text-red-500">Dashboard Loading Failed</h3>
        <p className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>{error}</p>
        <button
          onClick={() => {
            setLoading(true);
            setError(null);
            // Quick force reload of component values
            window.location.reload();
          }}
          className="bg-red-500 hover:bg-red-600 text-white font-bold px-6 py-2 rounded-xl transition-all"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold">System Dashboard</h2>
          <p className={isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'}>Monitoring news verification metrics and model health.</p>
        </div>
        <button className="bg-emerald-500 text-white px-6 py-2 rounded-xl font-bold shadow-lg shadow-emerald-500/20">
          Generate Report
        </button>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Today', val: stats?.daily_verifications.toLocaleString() || '0', trend: '+12%' },
          { label: 'Active Users', val: stats?.active_users.toLocaleString() || '0', trend: '+8%' },
          { label: 'Uptime', val: `${stats?.system_uptime_percent}%`, trend: '+0%' },
          { label: 'Total Verifications', val: stats?.total_verifications.toLocaleString() || '0', trend: '+22%' }
        ].map((stat, i) => (
          <div key={i} className={cardClass}>
            <span className="text-sm font-medium uppercase opacity-50">{stat.label}</span>
            <div className="flex items-end gap-2 mt-1">
              <span className="text-2xl font-black">{stat.val}</span>
              <span className="text-xs text-emerald-500 font-bold mb-1">{stat.trend}</span>
            </div>
            <div className="text-[10px] uppercase font-bold mt-2 opacity-30 tracking-widest">Verified Checks</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Model Stats */}
        <div className={`lg:col-span-2 ${cardClass}`}>
          <div className="flex justify-between items-center mb-6">
            <h3 className="font-bold">Model Performance (mBERT-crypto-v2.1)</h3>
            <span className={`px-3 py-1 rounded-full text-xs font-bold border ${
              stats?.api_health === 'healthy' 
                ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' 
                : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
            }`}>
              {stats?.api_health === 'healthy' ? 'Active' : 'Degraded'}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-6 mb-8">
             <div>
               <div className="text-3xl font-black text-emerald-500">
                 {stats ? `${(stats.model_accuracy * 100).toFixed(1)}%` : '0.0%'}
               </div>
               <div className="text-xs font-medium opacity-50 uppercase mt-1">Accuracy Score</div>
             </div>
             <div>
               <div className="text-3xl font-black">
                 {analytics ? analytics.model_performance.f1_score.toFixed(3) : '0.82'}
               </div>
               <div className="text-xs font-medium opacity-50 uppercase mt-1">F1 Harmonic Mean</div>
             </div>
             <div>
               <div className="text-3xl font-black">Dec 15</div>
               <div className="text-xs font-medium opacity-50 uppercase mt-1">Last Trained</div>
             </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDarkMode ? '#334155' : '#E2E8F0'} />
                <XAxis dataKey="name" stroke={isDarkMode ? '#64748B' : '#94A3B8'} fontSize={12} />
                <YAxis stroke={isDarkMode ? '#64748B' : '#94A3B8'} fontSize={12} />
                <Tooltip 
                  contentStyle={{ backgroundColor: isDarkMode ? '#1E293B' : '#FFF', borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                />
                <Area type="monotone" dataKey="count" stroke="#10b981" fillOpacity={1} fill="url(#colorCount)" strokeWidth={3} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Alerts & Usage */}
        <div className="space-y-6">
          <div className={cardClass}>
             <h3 className="font-bold mb-4">API Usage</h3>
             <div className="space-y-4">
                {[
                  { label: 'Google Search', val: '87/100', p: 87 },
                  { label: 'Twitter API', val: '1.2k/5k', p: 24 },
                  { label: 'IPFS Storage', val: '234/1024 MB', p: 22 }
                ].map((api, i) => (
                  <div key={i} className="space-y-1 text-sm">
                    <div className="flex justify-between">
                       <span className="font-medium">{api.label}</span>
                       <span className="opacity-50">{api.val}</span>
                    </div>
                    <div className={`w-full h-1.5 rounded-full ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-100'} overflow-hidden`}>
                      <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${api.p}%` }} />
                    </div>
                  </div>
                ))}
             </div>
             <div className="mt-6 p-4 rounded-xl bg-slate-500/10 border border-slate-500/10 text-xs font-bold text-center">
               Est. Monthly Cost: {analytics ? `$${analytics.cost_analysis.total_monthly.toFixed(2)}` : '$0 (Free Tiers)'}
             </div>
          </div>

          {profile && (
            <div className={cardClass}>
              <h3 className="font-bold mb-4 flex items-center gap-2 text-slate-800 dark:text-[#F1F5F9]">
                <span>🔑</span> Personal API Credentials
              </h3>
              <div className="space-y-4">
                {/* API Key Box */}
                <div className={`p-3.5 rounded-xl border text-left space-y-1.5 relative overflow-hidden ${
                  isDarkMode ? 'bg-[#0F172A] border-[#334155]' : 'bg-[#F8FAFC] border-[#E2E8F0]'
                }`}>
                  <span className="text-[9px] font-black uppercase text-slate-400 tracking-wider">Your API Key</span>
                  <div className="flex justify-between items-center gap-2">
                    <span className="font-mono text-xs text-emerald-500 dark:text-emerald-400 truncate select-all">
                      {showApiKey ? profile.api_key : `${profile.api_key.substring(0, 12)}••••••••••••`}
                    </span>
                    <div className="flex gap-2 shrink-0">
                      <button 
                        onClick={() => setShowApiKey(!showApiKey)}
                        className={`text-[10px] font-bold px-2.5 py-1 rounded-lg border transition-all ${
                          isDarkMode ? 'border-[#334155] hover:bg-[#334155]' : 'border-[#E2E8F0] hover:bg-white'
                        }`}
                      >
                        {showApiKey ? "Hide" : "Show"}
                      </button>
                      <button 
                        onClick={() => handleCopyKey(profile.api_key)}
                        className="bg-emerald-500 hover:bg-emerald-600 text-white text-[10px] font-bold px-3 py-1 rounded-lg transition-all"
                      >
                        {copiedKey ? "Copied!" : "Copy"}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Quota Usage bar */}
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="font-medium">Daily Quota Usage</span>
                    <span className="opacity-70 font-semibold">
                      {profile.api_quota.used_today} / {profile.api_quota.daily_limit}
                    </span>
                  </div>
                  <div className={`w-full h-2 rounded-full ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-100'} overflow-hidden`}>
                    <div 
                      className={`h-full rounded-full transition-all duration-500 ${
                        (profile.api_quota.used_today / profile.api_quota.daily_limit) > 0.8 ? 'bg-[#EF4444]' : 'bg-emerald-500'
                      }`} 
                      style={{ width: `${Math.min(100, (profile.api_quota.used_today / profile.api_quota.daily_limit) * 100)}%` }} 
                    />
                  </div>
                  <div className="text-[10px] opacity-40 text-right mt-1">
                    Resets at: {profile.api_quota.reset_at ? new Date(profile.api_quota.reset_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'N/A'}
                  </div>
                </div>

                {/* Meta details */}
                <div className="pt-3 border-t border-slate-500/10 grid grid-cols-2 gap-4 text-[11px] opacity-60">
                  <div>
                    <span className="block text-[8px] uppercase tracking-wider opacity-60">Last Login</span>
                    <span className="font-semibold">{profile.last_login ? new Date(profile.last_login).toLocaleString() : 'N/A'}</span>
                  </div>
                  <div>
                    <span className="block text-[8px] uppercase tracking-wider opacity-60">Account Created</span>
                    <span className="font-semibold">{profile.created_at ? new Date(profile.created_at).toLocaleDateString() : 'N/A'}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className={cardClass}>
            <h3 className="font-bold mb-4">Critical Alerts</h3>
            <div className="space-y-3">
              <div className="flex gap-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs">
                <span className="text-amber-500 text-lg">⚠️</span>
                <div>
                  <div className="font-bold text-amber-500">Model accuracy drift</div>
                  <div className="opacity-70 mt-0.5">Performance dropped to 82% (threshold 80%)</div>
                </div>
              </div>
              <div className="flex gap-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs">
                <span className="text-emerald-500 text-lg">✅</span>
                <div>
                  <div className="font-bold text-emerald-500">Blockchain Synced</div>
                  <div className="opacity-70 mt-0.5">Verification 100% operational on BSC Testnet</div>
                </div>
              </div>
              <div className="flex gap-3 p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-xs">
                <span className="text-blue-500 text-lg">ℹ️</span>
                <div>
                  <div className="font-bold text-blue-500">Review Queue</div>
                  <div className="opacity-70 mt-0.5">{stats?.pending_reviews} items pending manual classification</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Detailed Analytics Section */}
      <div className="space-y-6 border-t border-slate-500/10 pt-8 animate-fade-in">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h3 className="text-2xl font-bold">Detailed System Analytics</h3>
            <p className={`text-sm ${isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'}`}>
              Usage breakdowns, model diagnostics, and infrastructure cost analysis.
            </p>
          </div>
          <div className="flex items-center gap-1.5 bg-slate-500/10 p-1 rounded-xl border border-slate-500/10 self-end sm:self-auto">
            {['7d', '30d', '90d'].map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  period === p
                    ? 'bg-emerald-500 text-white shadow-md'
                    : isDarkMode ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {analyticsLoading && !analytics ? (
          <div className="flex flex-col items-center justify-center py-12 space-y-3">
            <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-xs opacity-50">Refetching analytics...</p>
          </div>
        ) : (
          analytics && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {/* Verification Distribution */}
              <div className={cardClass}>
                <h4 className="font-bold mb-4 flex items-center gap-2">
                  <span>📊</span> Credibility Verdicts
                </h4>
                <div className="space-y-4">
                  <div className="text-center py-1">
                    <div className="text-3xl font-black text-slate-800 dark:text-white">
                      {analytics.verification_stats.total.toLocaleString()}
                    </div>
                    <span className="text-[10px] opacity-50 uppercase font-medium">Total Analyzed ({period})</span>
                  </div>
                  
                  {/* Real vs Fake bar */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-[11px] font-bold">
                      <span className="text-emerald-500">Real ({analytics.verification_stats.total > 0 ? ((analytics.verification_stats.real / analytics.verification_stats.total) * 100).toFixed(1) : 0}%)</span>
                      <span className="text-rose-500">Fake ({analytics.verification_stats.total > 0 ? ((analytics.verification_stats.fake / analytics.verification_stats.total) * 100).toFixed(1) : 0}%)</span>
                    </div>
                    <div className={`w-full h-3 rounded-full ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-100'} overflow-hidden flex`}>
                      <div 
                        className="h-full bg-gradient-to-r from-emerald-500 to-teal-500" 
                        style={{ width: `${analytics.verification_stats.total > 0 ? (analytics.verification_stats.real / analytics.verification_stats.total) * 100 : 0}%` }}
                      />
                      <div 
                        className="h-full bg-gradient-to-r from-rose-500 to-red-600" 
                        style={{ width: `${analytics.verification_stats.total > 0 ? (analytics.verification_stats.fake / analytics.verification_stats.total) * 100 : 0}%` }}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-slate-500/10">
                    <div>
                      <span className="opacity-50 block">Real News</span>
                      <span className="font-bold text-emerald-500">{analytics.verification_stats.real.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="opacity-50 block">Fake/Risky</span>
                      <span className="font-bold text-rose-500">{analytics.verification_stats.fake.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* API Load Analytics */}
              <div className={cardClass}>
                <h4 className="font-bold mb-4 flex items-center gap-2">
                  <span>🚀</span> Request & API Load
                </h4>
                <div className="space-y-4">
                  <div className="flex justify-between items-center py-1.5 border-b border-slate-500/5">
                    <span className="text-xs opacity-60">Total Hits ({period})</span>
                    <span className="font-bold text-sm">{analytics.api_usage.total_requests.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5 border-b border-slate-500/5">
                    <span className="text-xs opacity-60">Daily Average</span>
                    <span className="font-bold text-sm text-emerald-500">{analytics.api_usage.daily_average.toLocaleString()}/day</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5">
                    <span className="text-xs opacity-60">Peak Daily Load</span>
                    <span className="font-bold text-sm text-amber-500">{analytics.api_usage.peak_daily.toLocaleString()} req</span>
                  </div>
                  
                  <div className="p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/10 text-center">
                    <span className="text-[10px] text-emerald-500 font-bold uppercase tracking-wider">System Latency: Stable</span>
                  </div>
                </div>
              </div>

              {/* Model Diagnostics */}
              <div className={cardClass}>
                <h4 className="font-bold mb-4 flex items-center gap-2">
                  <span>🧠</span> Model Diagnostics
                </h4>
                <div className="space-y-3.5">
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="opacity-60">Accuracy</span>
                      <span className="font-bold text-emerald-500">{(analytics.model_performance.accuracy * 100).toFixed(1)}%</span>
                    </div>
                    <div className={`w-full h-1.5 rounded-full ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-100'} overflow-hidden`}>
                      <div className="h-full bg-emerald-500" style={{ width: `${analytics.model_performance.accuracy * 100}%` }} />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="opacity-60">Precision</span>
                      <span className="font-bold text-teal-500">{(analytics.model_performance.precision * 100).toFixed(1)}%</span>
                    </div>
                    <div className={`w-full h-1.5 rounded-full ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-100'} overflow-hidden`}>
                      <div className="h-full bg-teal-500" style={{ width: `${analytics.model_performance.precision * 100}%` }} />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="opacity-60">Recall / Sensitivity</span>
                      <span className="font-bold text-indigo-500">{(analytics.model_performance.recall * 100).toFixed(1)}%</span>
                    </div>
                    <div className={`w-full h-1.5 rounded-full ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-100'} overflow-hidden`}>
                      <div className="h-full bg-indigo-500" style={{ width: `${analytics.model_performance.recall * 100}%` }} />
                    </div>
                  </div>

                  <div className="flex justify-between text-xs pt-1">
                    <span className="opacity-60 font-medium">F1-Score Harmonic</span>
                    <span className="font-extrabold text-slate-800 dark:text-white">{analytics.model_performance.f1_score.toFixed(3)}</span>
                  </div>
                </div>
              </div>

              {/* Infrastructure Costs */}
              <div className={`${cardClass} bg-gradient-to-br ${isDarkMode ? 'from-[#1E293B] to-[#0F172A]' : 'from-white to-[#F8FAFC]'}`}>
                <h4 className="font-bold mb-4 flex items-center gap-2">
                  <span>💰</span> Infrastructure Costs
                </h4>
                <div className="space-y-3">
                  <div className="flex justify-between items-center py-1 border-b border-slate-500/5">
                    <span className="text-xs opacity-60">Google Custom Search</span>
                    <span className="font-mono text-sm font-semibold">${analytics.cost_analysis.google_api_cost.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-slate-500/5">
                    <span className="text-xs opacity-60">IPFS Storage (Pinata)</span>
                    <span className="font-mono text-sm font-semibold">${(analytics.cost_analysis.ipfs_storage_gb * 0.15).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 text-xs text-slate-400">
                    <span>IPFS Usage Size</span>
                    <span>{analytics.cost_analysis.ipfs_storage_gb.toFixed(1)} GB</span>
                  </div>

                  <div className="pt-2 mt-2 border-t border-slate-500/10 flex justify-between items-end">
                    <div>
                      <span className="text-[9px] uppercase font-bold opacity-40 block">Estimated Monthly</span>
                      <span className="text-xl font-black text-emerald-500">${analytics.cost_analysis.total_monthly.toFixed(2)}</span>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-500 font-bold border border-emerald-500/20">
                      Paid Tier
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
};

export default AdminView;
