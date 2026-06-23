import React, { useState, useEffect } from 'react';
import { AreaChart, Area, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { UserProfileResponse, getAdminDashboard, AdminDashboardResponse, getValidAccessToken, getAdminAnalytics, AdminAnalyticsResponse, getAdminUsers, AdminUserItem, deleteAdminUser, getAdminFeedback, FeedbackItem, getSystemHealth, getSystemStatus, getAdminTrend, SystemHealthResponse, SystemStatusResponse, AdminTrendResponse } from '../services/apiService';

const ALERT_TONE_STYLES: Record<string, { wrap: string; icon: string; title: string }> = {
  emerald: { wrap: 'bg-emerald-500/10 border-emerald-500/20', icon: 'text-emerald-500', title: 'text-emerald-500' },
  amber: { wrap: 'bg-amber-500/10 border-amber-500/20', icon: 'text-amber-500', title: 'text-amber-500' },
  blue: { wrap: 'bg-blue-500/10 border-blue-500/20', icon: 'text-blue-500', title: 'text-blue-500' },
};

interface AdminViewProps {
  isDarkMode: boolean;
  profile: UserProfileResponse | null;
  activePage: 'dashboard' | 'users' | 'feedback';
}

const AdminView: React.FC<AdminViewProps> = ({ isDarkMode, profile, activePage }) => {
  const cardClass = `p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`;

  // Live admin dashboard data states
  const [stats, setStats] = useState<AdminDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Analytics states
  const [analytics, setAnalytics] = useState<AdminAnalyticsResponse | null>(null);
  const [period, setPeriod] = useState<string>("30d");
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  // Manage Users states
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [userSearch, setUserSearch] = useState("");
  const [deleteUserId, setDeleteUserId] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // User Feedback states
  const [feedbackList, setFeedbackList] = useState<FeedbackItem[]>([]);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  // Live system health/status + verification trend
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [trend, setTrend] = useState<AdminTrendResponse | null>(null);

  useEffect(() => {
    const fetchDashboardStats = async () => {
      try {
        const token = await getValidAccessToken();
        if (!token) {
          throw new Error("No active session token found. Please log in.");
        }
        // Retrieve custom admin override token from env
        const adminToken = import.meta.env.VITE_ADMIN_TOKEN || "super_secret_admin_token_change_me";
        const [dash, tr] = await Promise.all([
          getAdminDashboard(token, adminToken),
          getAdminTrend(token, adminToken, 7).catch(() => null),
        ]);
        setStats(dash);
        if (tr) setTrend(tr);
        // Public health/status endpoints — fetched in parallel, never fatal to the dashboard
        Promise.all([
          getSystemHealth().then(setHealth).catch(() => {}),
          getSystemStatus().then(setStatus).catch(() => {}),
        ]);
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

  const fetchUsers = async () => {
    setUsersLoading(true);
    setUsersError(null);
    try {
      const token = await getValidAccessToken();
      if (!token) throw new Error("No active session token found. Please log in.");
      const adminToken = import.meta.env.VITE_ADMIN_TOKEN || "super_secret_admin_token_change_me";
      const response = await getAdminUsers(token, adminToken, 100, 0);
      setUsers(response.users);
    } catch (err: any) {
      setUsersError(err.message || "Failed to load user accounts.");
    } finally {
      setUsersLoading(false);
    }
  };

  const fetchFeedback = async () => {
    setFeedbackLoading(true);
    setFeedbackError(null);
    try {
      const response = await getAdminFeedback();
      setFeedbackList(response.feedback);
    } catch (err: any) {
      setFeedbackError(err.message || "Failed to load user feedback.");
    } finally {
      setFeedbackLoading(false);
    }
  };

  useEffect(() => {
    if (activePage === 'users' && users.length === 0) fetchUsers();
    if (activePage === 'feedback' && feedbackList.length === 0) fetchFeedback();
  }, [activePage]);

  const handleDeleteUser = async () => {
    if (!deleteUserId) return;
    setDeleteLoading(true);
    try {
      const token = await getValidAccessToken();
      if (!token) throw new Error("No active session token found. Please log in.");
      const adminToken = import.meta.env.VITE_ADMIN_TOKEN || "super_secret_admin_token_change_me";
      await deleteAdminUser(token, adminToken, deleteUserId);
      setUsers((prev) => prev.filter((u) => u.user_id !== deleteUserId));
      setDeleteUserId(null);
    } catch (err: any) {
      setUsersError(err.message || "Failed to delete user account.");
      setDeleteUserId(null);
    } finally {
      setDeleteLoading(false);
    }
  };

  const renderManageUsers = () => {
    const q = userSearch.toLowerCase();
    const filtered = users.filter(
      (u) => !q || u.username.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
    );
    return (
      <div className="space-y-6">
        <div className="flex justify-end">
        <div className="flex items-center gap-2 w-full sm:w-auto">
            <input
              type="text"
              placeholder="Search username or email..."
              value={userSearch}
              onChange={(e) => setUserSearch(e.target.value)}
              className={`flex-1 sm:w-64 px-4 py-2 rounded-xl text-sm border outline-none ${
                isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-white border-[#E2E8F0]'
              }`}
            />
            <button
              onClick={fetchUsers}
              className="bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold px-4 py-2 rounded-xl transition-all whitespace-nowrap"
            >
              Refresh
            </button>
          </div>
        </div>

        {usersError && (
          <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-red-500/5 border-red-500/20' : 'bg-red-50 border-red-200'} text-red-500 text-sm`}>
            {usersError}
          </div>
        )}

        {usersLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-10 h-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : (
          <div className={`${cardClass} overflow-hidden p-0`}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className={`text-left text-xs uppercase tracking-wider ${isDarkMode ? 'text-slate-400 border-b border-[#334155]' : 'text-slate-500 border-b border-[#E2E8F0]'}`}>
                    <th className="px-5 py-3 font-bold">User</th>
                    <th className="px-5 py-3 font-bold">Role</th>
                    <th className="px-5 py-3 font-bold">Verifications</th>
                    <th className="px-5 py-3 font-bold">Last Login</th>
                    <th className="px-5 py-3 font-bold text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-10 text-center opacity-50">No user accounts found.</td>
                    </tr>
                  ) : filtered.map((u) => (
                    <tr key={u.user_id} className={`border-b last:border-0 ${isDarkMode ? 'border-[#334155]' : 'border-[#E2E8F0]'}`}>
                      <td className="px-5 py-4">
                        <div className="font-semibold">{u.username}</div>
                        <div className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>{u.email}</div>
                      </td>
                      <td className="px-5 py-4">
                        <span className={`px-2.5 py-1 text-[10px] font-bold rounded uppercase tracking-wider ${
                          u.role === 'admin' ? 'bg-emerald-500/10 text-emerald-500' : isDarkMode ? 'bg-slate-500/10 text-slate-300' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-5 py-4 font-semibold">{u.verifications_count.toLocaleString()}</td>
                      <td className={`px-5 py-4 text-xs ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                        {u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <button
                          onClick={() => setDeleteUserId(u.user_id)}
                          disabled={u.role === 'admin'}
                          className={`text-xs font-bold px-3 py-1.5 rounded-lg transition-all ${
                            u.role === 'admin'
                              ? 'bg-slate-500/10 text-slate-500 cursor-not-allowed opacity-50'
                              : 'bg-red-500/10 text-red-500 hover:bg-red-500 hover:text-white'
                          }`}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  };

  const chartData = (trend?.trend || []).map((p) => ({
    name: new Date(`${p.date}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' }),
    count: p.count,
  }));

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

  const renderUserFeedback = () => (
    <div className="space-y-6">
      <div className="flex justify-end">
        <button
          onClick={fetchFeedback}
          className="bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold px-4 py-2 rounded-xl transition-all"
        >
          Refresh
        </button>
      </div>

      {feedbackError && (
        <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-red-500/5 border-red-500/20' : 'bg-red-50 border-red-200'} text-red-500 text-sm`}>
          {feedbackError}
        </div>
      )}

      {feedbackLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-10 h-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      ) : feedbackList.length === 0 ? (
        <div className={`text-center py-16 border-2 border-dashed rounded-2xl ${isDarkMode ? 'border-[#334155]' : 'border-[#E2E8F0]'}`}>
          <span className="text-4xl">📭</span>
          <p className="mt-3 opacity-50 font-medium">No feedback submissions yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {feedbackList.map((fb) => {
            const typeLabel = fb.feedback_type.replace(/_/g, ' ');
            const typeColor = fb.feedback_type.includes('incorrect')
              ? 'bg-rose-500/10 text-rose-500'
              : fb.feedback_type.includes('bug')
              ? 'bg-amber-500/10 text-amber-500'
              : 'bg-blue-500/10 text-blue-500';
            const dateStr = fb.submitted_at || fb.created_at;
            return (
              <div key={fb.feedback_id} className={cardClass}>
                <div className="flex justify-between items-start gap-3 mb-3">
                  <span className={`px-2.5 py-1 text-[10px] font-bold rounded uppercase tracking-wider ${typeColor}`}>
                    {typeLabel}
                  </span>
                  <span className={`text-[10px] ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                    {dateStr ? new Date(dateStr).toLocaleString() : 'N/A'}
                  </span>
                </div>
                <p className="text-sm font-medium mb-3">{fb.message}</p>
                <div className={`pt-3 border-t border-slate-500/10 flex justify-between items-center text-[11px] ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                  <span className="font-semibold truncate">{fb.user_email}</span>
                  {fb.article_id && (
                    <span className="font-mono opacity-60 truncate ml-2">#{fb.article_id.slice(0, 8)}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  const pageMeta = activePage === 'users'
    ? { title: 'Manage Users', subtitle: 'View, audit, and remove registered platform accounts.' }
    : activePage === 'feedback'
    ? { title: 'User Feedback', subtitle: 'Disputes and reports submitted by users about verification results.' }
    : { title: 'Administration', subtitle: 'Monitor platform operations, system health, and model performance.' };

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h2 className="text-3xl font-bold">{pageMeta.title}</h2>
        <p className={isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'}>{pageMeta.subtitle}</p>
      </div>

      {/* DASHBOARD TAB */}
      {activePage === 'dashboard' && (
      <>
      {/* Overview Stats */}
      {(() => {
        const t = trend?.trend || [];
        const todayCnt = t.length ? t[t.length - 1].count : 0;
        const yestCnt = t.length >= 2 ? t[t.length - 2].count : 0;
        const change = yestCnt > 0 ? Math.round(((todayCnt - yestCnt) / yestCnt) * 100) : null;
        const last7 = t.reduce((s, p) => s + p.count, 0);
        const upSec = health?.uptime_seconds ?? null;
        const upStr = upSec == null
          ? null
          : upSec >= 86400
            ? `${Math.floor(upSec / 86400)}d ${Math.floor((upSec % 86400) / 3600)}h`
            : upSec >= 3600
              ? `${Math.floor(upSec / 3600)}h ${Math.floor((upSec % 3600) / 60)}m`
              : `${Math.floor(upSec / 60)}m`;
        const cards = [
          { label: 'Today', val: stats?.daily_verifications.toLocaleString() ?? '0', sub: change != null ? `${change >= 0 ? '+' : ''}${change}%` : '—', footer: 'vs yesterday' },
          { label: 'Active Users', val: stats?.active_users.toLocaleString() ?? '0', sub: '', footer: 'registered accounts' },
          { label: 'Uptime', val: upStr ?? (stats ? `${stats.system_uptime_percent}%` : '—'), sub: health?.status ?? '', footer: 'live process uptime' },
          { label: 'Total Verifications', val: stats?.total_verifications.toLocaleString() ?? '0', sub: last7 > 0 ? `${last7}/7d` : '—', footer: 'all-time checks' }
        ];
        return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((stat, i) => (
          <div key={i} className={cardClass}>
            <span className="text-sm font-medium uppercase opacity-50">{stat.label}</span>
            <div className="flex items-end gap-2 mt-1">
              <span className="text-2xl font-black">{stat.val}</span>
              {stat.sub && <span className="text-xs text-emerald-500 font-bold mb-1">{stat.sub}</span>}
            </div>
            <div className="text-[10px] uppercase font-bold mt-2 opacity-30 tracking-widest">{stat.footer}</div>
          </div>
        ))}
      </div>
        );
      })()}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Model Stats */}
        <div className={`lg:col-span-2 ${cardClass}`}>
          <div className="flex justify-between items-center mb-6">
            <h3 className="font-bold">Model Performance (RoBERTa)</h3>
            <span className={`px-3 py-1 rounded-full text-xs font-bold border ${
              status?.components.ml_models.bert_loaded
                ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
            }`}>
              {status?.components.ml_models.bert_loaded ? 'Active' : 'Degraded'}
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
               <div className={`text-3xl font-black ${status?.components.ml_models.bert_loaded ? 'text-emerald-500' : 'text-amber-500'}`}>
                 {status ? (status.components.ml_models.bert_loaded ? 'Yes' : 'No') : '—'}
               </div>
               <div className="text-xs font-medium opacity-50 uppercase mt-1">Model Loaded</div>
             </div>
             <div>
               <div className="text-3xl font-black">
                 {status ? `${status.components.ml_models.average_inference_time_ms}ms` : '—'}
               </div>
               <div className="text-xs font-medium opacity-50 uppercase mt-1">Avg Inference</div>
             </div>
          </div>
          <div className="h-64 relative">
            {!trend && (
              <div className="absolute inset-0 flex items-center justify-center z-10">
                <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
              </div>
            )}
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
             <h3 className="font-bold mb-4">External API Status</h3>
             <div className="space-y-4">
                {[
                  { label: 'Google Search', state: status?.components.external_apis.google_search },
                  { label: 'Twitter API', state: status?.components.external_apis.twitter },
                  { label: 'Redis Cache', state: status?.components.external_apis.redis }
                ].map((api, i) => {
                  const operational = api.state === 'operational';
                  return (
                  <div key={i} className="space-y-1 text-sm">
                    <div className="flex justify-between">
                       <span className="font-medium">{api.label}</span>
                       <span className={`font-semibold ${operational ? 'text-emerald-500' : 'text-amber-500'}`}>
                         {api.state ? api.state.replace('_', ' ') : 'loading…'}
                       </span>
                    </div>
                    <div className={`w-full h-1.5 rounded-full ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-100'} overflow-hidden`}>
                      <div className={`h-full rounded-full ${operational ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ width: operational ? '100%' : '35%' }} />
                    </div>
                  </div>
                  );
                })}
             </div>
             <div className="mt-6 p-4 rounded-xl bg-slate-500/10 border border-slate-500/10 text-xs font-bold text-center">
               Est. Monthly Cost: {analytics ? `${analytics.cost_analysis.total_monthly.toFixed(2)}` : '$0 (Free Tiers)'}
             </div>
          </div>

          <div className={cardClass}>
            <h3 className="font-bold mb-4">System Alerts</h3>
            <div className="space-y-3">
              {[
                {
                  tone: status?.components.ml_models.bert_loaded ? 'emerald' : 'amber',
                  icon: '🧠',
                  title: status?.components.ml_models.bert_loaded ? 'Model Operational' : 'Model Not Loaded',
                  msg: status?.components.ml_models.bert_loaded
                    ? `RoBERTa active · ~${status.components.ml_models.average_inference_time_ms}ms avg inference`
                    : 'RoBERTa checkpoint unavailable on the server.'
                },
                {
                  tone: status?.components.database.status === 'operational' ? 'emerald' : 'amber',
                  icon: '🗄️',
                  title: status?.components.database.status === 'operational' ? 'Database Healthy' : 'Database Degraded',
                  msg: status?.components.database.status === 'operational'
                    ? `Connection pool: ${status?.components.database.connection_pool}`
                    : 'Database connectivity issues detected.'
                },
                {
                  tone: status?.components.external_apis.google_search === 'operational' ? 'emerald' : 'amber',
                  icon: '🔎',
                  title: status?.components.external_apis.google_search === 'operational' ? 'Google Search Connected' : 'Google Search Unconfigured',
                  msg: status?.components.external_apis.google_search === 'operational'
                    ? 'Source verification pipeline online.'
                    : 'Google CSE credentials missing — verification limited.'
                },
                {
                  tone: 'blue',
                  icon: '📋',
                  title: 'Review Queue',
                  msg: `${stats?.pending_reviews ?? 0} items pending manual classification`
                }
              ].map((a, i) => {
                const t = ALERT_TONE_STYLES[a.tone] || ALERT_TONE_STYLES.blue;
                return (
                  <div key={i} className={`flex gap-3 p-3 rounded-xl border text-xs ${t.wrap}`}>
                    <span className={`text-lg ${t.icon}`}>{a.icon}</span>
                    <div>
                      <div className={`font-bold ${t.title}`}>{a.title}</div>
                      <div className="opacity-70 mt-0.5">{a.msg}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Detailed Analytics Section */}
      <div className="space-y-6 border-t border-slate-500/10 pt-8 animate-fade-in">
        <div>
          <h3 className="text-2xl font-bold">Verification Distribution</h3>
          <p className={`text-sm ${isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'}`}>
            Live credibility verdict breakdown across all stored verifications.
          </p>
        </div>

        {analyticsLoading && !analytics ? (
          <div className="flex flex-col items-center justify-center py-12 space-y-3">
            <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-xs opacity-50">Refetching analytics...</p>
          </div>
        ) : (
          analytics && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
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
                  
                  {(() => {
                    const barData = [
                      { name: 'Real', count: analytics.verification_stats.real, fill: '#10b981' },
                      { name: 'Fake', count: analytics.verification_stats.fake, fill: '#ef4444' },
                      { name: 'Uncertain', count: analytics.verification_stats.uncertain || 0, fill: '#f59e0b' }
                    ];
                    return (
                      <div className="h-48 relative w-full mt-4">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={barData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDarkMode ? '#334155' : '#E2E8F0'} />
                            <XAxis dataKey="name" stroke={isDarkMode ? '#64748B' : '#94A3B8'} fontSize={12} tickLine={false} />
                            <YAxis stroke={isDarkMode ? '#64748B' : '#94A3B8'} fontSize={12} tickLine={false} axisLine={false} />
                            <Tooltip 
                              contentStyle={{ 
                                backgroundColor: isDarkMode ? '#1E293B' : '#FFF', 
                                borderRadius: '12px', 
                                border: isDarkMode ? '1px solid #334155' : '1px solid #E2E8F0',
                                boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                                color: isDarkMode ? '#F1F5F9' : '#1E293B'
                              }}
                              cursor={{ fill: 'rgba(0, 0, 0, 0.05)' }}
                            />
                            <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                              {barData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.fill} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    );
                  })()}

                  <div className="grid grid-cols-3 gap-2 text-xs pt-4 border-t border-slate-500/10">
                    <div>
                      <span className="opacity-50 block">Real News</span>
                      <span className="font-bold text-emerald-500">{analytics.verification_stats.real.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="opacity-50 block">Fake/Risky</span>
                      <span className="font-bold text-rose-500">{analytics.verification_stats.fake.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="opacity-50 block">Uncertain</span>
                      <span className="font-bold text-amber-500">{(analytics.verification_stats.uncertain || 0).toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          )
        )}
      </div>
      </>
      )}

      {/* MANAGE USERS TAB */}
      {activePage === 'users' && renderManageUsers()}

      {/* USER FEEDBACK TAB */}
      {activePage === 'feedback' && renderUserFeedback()}

      {/* DELETE USER CONFIRMATION MODAL */}
      {deleteUserId && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          onClick={() => !deleteLoading && setDeleteUserId(null)}
        >
          <div
            className={`max-w-sm w-full p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-2xl'}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-center space-y-3">
              <span className="text-4xl">⚠️</span>
              <h3 className="text-xl font-bold">Delete User Account?</h3>
              <p className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                This action permanently removes the account and is irreversible.
              </p>
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setDeleteUserId(null)}
                  disabled={deleteLoading}
                  className={`flex-1 py-2 rounded-xl font-bold text-sm transition-all ${isDarkMode ? 'bg-[#334155] hover:bg-[#3d4d63] text-white' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'}`}
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteUser}
                  disabled={deleteLoading}
                  className="flex-1 py-2 rounded-xl font-bold text-sm bg-red-500 hover:bg-red-600 text-white transition-all disabled:opacity-60"
                >
                  {deleteLoading ? 'Deleting...' : 'Confirm Delete'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminView;