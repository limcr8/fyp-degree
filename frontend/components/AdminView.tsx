
import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';

const data = [
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
}

const AdminView: React.FC<AdminViewProps> = ({ isDarkMode }) => {
  const cardClass = `p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`;

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
          { label: 'Today', val: '342', trend: '+12%' },
          { label: 'Week', val: '2,156', trend: '+8%' },
          { label: 'Month', val: '8,934', trend: '+15%' },
          { label: 'Total', val: '12,543', trend: '+22%' }
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
            <span className="px-3 py-1 bg-emerald-500/10 text-emerald-500 rounded-full text-xs font-bold border border-emerald-500/20">Active</span>
          </div>
          <div className="grid grid-cols-3 gap-6 mb-8">
             <div>
               <div className="text-3xl font-black text-emerald-500">84.3%</div>
               <div className="text-xs font-medium opacity-50 uppercase mt-1">Accuracy Score</div>
             </div>
             <div>
               <div className="text-3xl font-black">0.82</div>
               <div className="text-xs font-medium opacity-50 uppercase mt-1">F1 Harmonic Mean</div>
             </div>
             <div>
               <div className="text-3xl font-black">Dec 15</div>
               <div className="text-xs font-medium opacity-50 uppercase mt-1">Last Trained</div>
             </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data}>
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
               Est. Monthly Cost: $0 (Free Tiers)
             </div>
          </div>

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
                  <div className="opacity-70 mt-0.5">15 items pending manual classification</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminView;
