import React, { useState, useEffect } from 'react';
import { UserProfileResponse, updateUserProfile, changeUserPassword, getAdminUsers, AdminUserItem, deleteAdminUser } from '../services/apiService';
import { updateProfile, updatePassword, reauthenticateWithCredential, EmailAuthProvider, User } from 'firebase/auth';
import { auth, updateUserProfileFirestore } from '../services/firebase';

interface ProfileViewProps {
  isDarkMode: boolean;
  profile: UserProfileResponse | null;
  setProfile: (profile: UserProfileResponse | null) => void;
  setUser: (user: User | null) => void;
}

const ProfileView: React.FC<ProfileViewProps> = ({ isDarkMode, profile, setProfile, setUser }) => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [language, setLanguage] = useState('en');
  const [notifications, setNotifications] = useState(true);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [fullName, setFullName] = useState('');

  // Initialize fields on load
  useEffect(() => {
    if (profile) {
      setUsername(profile.username);
      setFullName(profile.name || profile.username);
      setEmail(profile.email);
      if (profile.preferences) {
        setLanguage(profile.preferences.language || 'en');
        setNotifications(profile.preferences.notifications !== false);
      }
    }
  }, [profile]);

  useEffect(() => {
    if (auth.currentUser) {
      setFullName(auth.currentUser.displayName || '');
    }
  }, [auth.currentUser]);

  // User Management State
  const [activeTab, setActiveTab] = useState<'profile' | 'users'>('profile');
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [usersPage, setUsersPage] = useState(1);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [limit] = useState(10);

  const [deleteUserId, setDeleteUserId] = useState<string | null>(null);
  const [deleteUsername, setDeleteUsername] = useState<string>('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const fetchUsers = async (pageIndex: number) => {
    setUsersLoading(true);
    setUsersError(null);
    try {
      const token = localStorage.getItem('access_token');
      if (!token) throw new Error("No active session. Please log in.");
      const adminToken = import.meta.env.VITE_ADMIN_TOKEN || "super_secret_admin_token_change_me";
      
      const newOffset = (pageIndex - 1) * limit;
      const response = await getAdminUsers(token, adminToken, limit, newOffset);
      setUsers(response.users);
      setTotalCount(response.total_count);
      setUsersPage(pageIndex);
    } catch (err: any) {
      console.error("Failed to fetch admin users:", err);
      setUsersError(err.message || "Failed to load user accounts.");
    } finally {
      setUsersLoading(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!deleteUserId) return;
    setDeleteLoading(true);
    setDeleteError(null);
    try {
      const token = localStorage.getItem('access_token');
      if (!token) throw new Error("No active session. Please log in.");
      const adminToken = import.meta.env.VITE_ADMIN_TOKEN || "super_secret_admin_token_change_me";
      
      await deleteAdminUser(token, adminToken, deleteUserId);
      setDeleteUserId(null);
      fetchUsers(usersPage);
    } catch (err: any) {
      console.error("Failed to delete user:", err);
      setDeleteError(err.message || "Failed to delete user account.");
    } finally {
      setDeleteLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'users' && profile?.role === 'admin') {
      fetchUsers(1);
    }
  }, [activeTab, profile]);

  const filteredUsers = users.filter(u => 
    u.username.toLowerCase().includes(searchTerm.toLowerCase()) || 
    u.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.role.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCopyApiKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };


  if (!profile) {
    return (
      <div className="text-center py-20 animate-fade-in">
        <div className="w-20 h-20 mx-auto bg-slate-200 dark:bg-slate-800 rounded-full flex items-center justify-center mb-4">
          <svg className="w-10 h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold">Sign In to View Profile</h2>
        <p className="opacity-50 mt-2">Please log in to edit your profile and preferences.</p>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // Validate password change inputs if filled
    if (newPassword || currentPassword || confirmPassword) {
      if (!currentPassword) {
        setError("Current password is required to change password.");
        return;
      }
      if (!newPassword) {
        setError("New password is required.");
        return;
      }
      if (newPassword.length < 6) {
        setError("New password must be at least 6 characters long.");
        return;
      }
      if (newPassword !== confirmPassword) {
        setError("New passwords do not match.");
        return;
      }
    }

    setLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      if (!token) throw new Error("No active session. Please log in again.");

      // 1. Update backend profile first (sends the edited display name)
      const result = await updateUserProfile(token, fullName, email, { language, notifications });
      
      // 2. Update backend password if requested
      if (newPassword) {
        await changeUserPassword(token, currentPassword, newPassword);
      }
      
      // 3. Synchronize Firebase Auth + Firestore profile
      const currentUser = auth.currentUser;
      if (currentUser) {
        // 3a. Update Firebase Auth displayName to the typed full name
        await updateProfile(currentUser, {
          displayName: fullName,
        });

        // 3b. Sync full name to Firestore 'users' collection (the source of truth for display)
        try {
          await updateUserProfileFirestore(currentUser.email!, {
            name: fullName,
            email: email,
          });
        } catch (firestoreErr) {
          console.warn("Firestore profile sync failed (non-fatal):", firestoreErr);
        }

        // 3c. Update Firebase password if changed (requires recent authentication)
        if (newPassword) {
          try {
            // Re-authenticate first — Firebase requires recent login for password changes
            const credential = EmailAuthProvider.credential(
              currentUser.email || email,
              currentPassword
            );
            await reauthenticateWithCredential(currentUser, credential);
            // Now safe to update password
            await updatePassword(currentUser, newPassword);
          } catch (authErr: any) {
            const code = authErr?.code || '';
            if (code === 'auth/wrong-password' || code === 'auth/invalid-credential') {
              throw new Error('Current password is incorrect. Please verify and try again.');
            } else if (code === 'auth/requires-recent-login') {
              throw new Error('Session expired. Please log out and log back in, then try changing your password again.');
            } else if (code === 'auth/weak-password') {
              throw new Error('New password is too weak. Please choose a stronger password.');
            }
            throw authErr;
          }
        }

        // 3d. Reload the user so the new displayName is reflected immediately
        await currentUser.reload();

        // Force refresh User state in App.tsx
        setUser(null);
        setTimeout(() => {
          setUser(auth.currentUser);
        }, 0);
      }

      setProfile(result.user);
      setSuccess("Profile updated successfully!");
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      console.error("Profile update error:", err);
      setError(err.message || "Failed to update profile.");
    } finally {
      setLoading(false);
    }
  };

  const cardClass = `p-8 rounded-3xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-xl shadow-slate-200/50'}`;
  const inputClass = `w-full px-4 py-3 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${
    isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'
  } disabled:opacity-50`;

  return (
    <div className={`${activeTab === 'users' ? 'max-w-5xl' : 'max-w-2xl'} mx-auto space-y-6 transition-all duration-300 animate-fade-in`}>
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">
            {activeTab === 'profile' ? 'Profile Settings' : 'User Accounts Directory'}
          </h2>
          <p className={isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'}>
            {activeTab === 'profile' 
              ? 'Configure your developer credentials and system preferences.'
              : 'View and manage all registered user accounts and their usage stats.'}
          </p>
        </div>
      </div>

      {profile.role === 'admin' && (
        <div className="flex border-b border-slate-500/10 pb-1 gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('profile')}
            className={`px-5 py-2.5 font-bold text-sm border-b-2 transition-all ${
              activeTab === 'profile'
                ? 'border-emerald-500 text-emerald-500'
                : isDarkMode ? 'border-transparent text-slate-400 hover:text-slate-200' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            👤 My Profile Settings
          </button>
        </div>
      )}

      {activeTab === 'profile' ? (
        <>
        <div className={cardClass}>
          {error && (
            <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs font-semibold flex items-center gap-2">
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              {error}
            </div>
          )}

          {success && (
            <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-xs font-semibold flex items-center gap-2">
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-semibold mb-2 ml-1">Full Name</label>
                <input
                  type="text"
                  required
                  disabled={loading}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="John Doe"
                  className={inputClass}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold mb-2 ml-1">Email Address</label>
              <input
                type="email"
                required
                disabled={loading}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="john@example.com"
                className={inputClass}
              />
            </div>

            <div className="border-t border-slate-500/10 pt-6 space-y-6">
              <h3 className="text-lg font-bold">Preferences</h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-semibold mb-2 ml-1">Preferred Language</label>
                  <select
                    disabled={loading}
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className={inputClass}
                  >
                    <option value="en">English (en)</option>
                    <option value="zh">Chinese (zh)</option>
                    <option value="ms">Malay (ms)</option>
                    <option value="all">All Languages</option>
                  </select>
                </div>

                <div className="flex items-center gap-3 pt-8 pl-1">
                  <input
                    type="checkbox"
                    id="notifications"
                    disabled={loading}
                    checked={notifications}
                    onChange={(e) => setNotifications(e.target.checked)}
                    className="w-4 h-4 accent-emerald-500 rounded focus:ring-emerald-500"
                  />
                  <label htmlFor="notifications" className="text-sm font-semibold select-none cursor-pointer">
                    Receive email notifications
                  </label>
                </div>
              </div>
            </div>

            <div className="border-t border-slate-500/10 pt-6 space-y-6">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-bold">Change Password</h3>
                <button
                  type="button"
                  onClick={() => setShowPasswords(!showPasswords)}
                  className="text-xs font-semibold text-emerald-500 hover:text-emerald-600 flex items-center gap-1.5"
                >
                  {showPasswords ? (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                      Hide passwords
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542 7z" /></svg>
                      Show passwords
                    </>
                  )}
                </button>
              </div>
              <p className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>Leave password fields blank if you do not want to change your password.</p>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold mb-2 ml-1">Current Password</label>
                  <input
                    type={showPasswords ? "text" : "password"}
                    disabled={loading}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Enter current password to verify identity"
                    className={inputClass}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-semibold mb-2 ml-1">New Password</label>
                    <input
                      type={showPasswords ? "text" : "password"}
                      disabled={loading}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Min 6 characters"
                      className={inputClass}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-semibold mb-2 ml-1">Confirm New Password</label>
                    <input
                      type={showPasswords ? "text" : "password"}
                      disabled={loading}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Confirm new password"
                      className={inputClass}
                    />
                  </div>
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-6 py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  Saving changes...
                </>
              ) : "Save Changes"}
            </button>
          </form>
        </div>

        <div className={`${cardClass} space-y-5`}>
          <div className="flex items-center gap-2">
            <span className="text-xl">🔑</span>
            <h3 className="text-lg font-bold">API Credentials</h3>
          </div>
          <p className={`text-xs ${isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'} -mt-2`}>
            Use this key in the <code className="px-1 py-0.5 rounded bg-slate-500/10 font-mono">X-API-Key</code> header to call the verification API from external applications. Keep it secret.
          </p>

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
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className={`text-[10px] font-bold px-2.5 py-1 rounded-lg border transition-all ${
                    isDarkMode ? 'border-[#334155] hover:bg-[#334155]' : 'border-[#E2E8F0] hover:bg-white'
                  }`}
                >
                  {showApiKey ? 'Hide' : 'Show'}
                </button>
                <button
                  type="button"
                  onClick={() => handleCopyApiKey(profile.api_key)}
                  className="bg-emerald-500 hover:bg-emerald-600 text-white text-[10px] font-bold px-3 py-1 rounded-lg transition-all"
                >
                  {copiedKey ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>
          </div>

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
                  profile.api_quota.daily_limit > 0 && (profile.api_quota.used_today / profile.api_quota.daily_limit) > 0.8
                    ? 'bg-rose-500'
                    : 'bg-emerald-500'
                }`}
                style={{ width: `${Math.min(100, profile.api_quota.daily_limit > 0 ? (profile.api_quota.used_today / profile.api_quota.daily_limit) * 100 : 0)}%` }}
              />
            </div>
            <div className="text-[10px] opacity-40 text-right mt-1">
              Resets at: {profile.api_quota.reset_at ? new Date(profile.api_quota.reset_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'N/A'}
            </div>
          </div>
        </div>
        </>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-4 justify-between items-stretch sm:items-center">
            {/* Search Input Box */}
            <div className="relative flex-1">
              <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none opacity-50">🔍</span>
              <input
                type="text"
                placeholder="Search users by name, email, or role..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className={`w-full pl-10 pr-4 py-2.5 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${
                  isDarkMode ? 'bg-[#1E293B] border-[#334155] text-white' : 'bg-white border-[#E2E8F0] shadow-sm'
                }`}
              />
            </div>
            
            {/* Sync button */}
            <button
              onClick={() => fetchUsers(usersPage)}
              disabled={usersLoading}
              className={`px-4 py-2.5 rounded-xl font-semibold border transition-all text-xs flex items-center justify-center gap-2 ${
                isDarkMode ? 'border-[#334155] bg-[#1E293B] hover:bg-[#2e3b4e] text-white' : 'border-[#E2E8F0] bg-white hover:bg-slate-50 shadow-sm'
              }`}
            >
              {usersLoading ? (
                <div className="w-3.5 h-3.5 border-2 border-slate-500 border-t-transparent rounded-full animate-spin"></div>
              ) : "🔄"} Refresh List
            </button>
          </div>

          {usersError && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs font-semibold">
              ⚠️ {usersError}
            </div>
          )}

          <div className={`rounded-3xl border overflow-hidden ${
            isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-xl shadow-slate-200/50'
          }`}>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className={`border-b text-xs font-bold uppercase tracking-wider opacity-60 ${
                    isDarkMode ? 'border-[#334155] bg-[#0F172A]/30' : 'border-[#E2E8F0] bg-slate-50'
                  }`}>
                    <th className="px-6 py-4">User Details</th>
                    <th className="px-6 py-4">Security Role</th>
                    <th className="px-6 py-4 text-center">Verifications</th>
                    <th className="px-6 py-4">Last Activity</th>
                    <th className="px-6 py-4">Registration Date</th>
                    <th className="px-6 py-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-500/10 text-sm">
                  {usersLoading && filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="text-center py-12">
                        <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                        <span className="opacity-50 text-xs">Querying user registry...</span>
                      </td>
                    </tr>
                  ) : filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="text-center py-12 opacity-50 text-xs">
                        No registered users match your criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map((u, idx) => (
                      <tr key={idx} className={isDarkMode ? 'hover:bg-[#243249]/50' : 'hover:bg-slate-50'}>
                        <td className="px-6 py-4">
                          <div className="font-bold text-slate-800 dark:text-white">{u.username}</div>
                          <div className="text-xs opacity-50 font-mono mt-0.5">{u.email}</div>
                          <div className="text-[10px] opacity-35 font-mono">ID: {u.user_id}</div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider ${
                            u.role === 'admin' 
                              ? 'bg-rose-500/15 text-rose-500 border border-rose-500/20' 
                              : 'bg-emerald-500/15 text-emerald-500 border border-emerald-500/20'
                          }`}>
                            {u.role}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className={`px-2.5 py-1 rounded-full font-black text-xs ${
                            u.verifications_count > 0 
                              ? isDarkMode ? 'bg-[#0F172A] text-emerald-400' : 'bg-slate-100 text-emerald-600'
                              : 'opacity-40'
                          }`}>
                            {u.verifications_count}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs opacity-75">
                          {u.last_login ? new Date(u.last_login).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'}) : 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs opacity-75">
                          {u.created_at ? new Date(u.created_at).toLocaleDateString(undefined, {dateStyle: 'medium'}) : 'N/A'}
                        </td>
                        <td className="px-6 py-4 text-center whitespace-nowrap">
                          {profile.user_id !== u.user_id ? (
                            <button
                              type="button"
                              onClick={() => {
                                setDeleteUserId(u.user_id);
                                setDeleteUsername(u.username);
                                setDeleteError(null);
                              }}
                              className="px-3 py-1.5 bg-rose-500 hover:bg-rose-600 text-white text-xs font-bold rounded-lg shadow-md hover:shadow-rose-500/20 transition-all active:scale-[0.98]"
                            >
                              Delete
                            </button>
                          ) : (
                            <span className="text-xs opacity-35 italic">Active Self</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Panel */}
            <div className={`p-4 border-t flex items-center justify-between gap-4 text-xs font-semibold ${
              isDarkMode ? 'border-[#334155] bg-[#0F172A]/20' : 'border-[#E2E8F0] bg-slate-50/50'
            }`}>
              <div className="opacity-60">
                Showing {Math.min(totalCount, (usersPage - 1) * limit + 1)}-{Math.min(totalCount, usersPage * limit)} of {totalCount} accounts
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => fetchUsers(usersPage - 1)}
                  disabled={usersPage <= 1 || usersLoading}
                  className={`px-3 py-1.5 rounded-lg border transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                    isDarkMode ? 'border-[#334155] bg-[#1E293B] hover:bg-[#2e3b4e] text-white' : 'border-[#E2E8F0] bg-white hover:bg-slate-50'
                  }`}
                >
                  Previous
                </button>
                <button
                  onClick={() => fetchUsers(usersPage + 1)}
                  disabled={usersPage * limit >= totalCount || usersLoading}
                  className={`px-3 py-1.5 rounded-lg border transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                    isDarkMode ? 'border-[#334155] bg-[#1E293B] hover:bg-[#2e3b4e] text-white' : 'border-[#E2E8F0] bg-white hover:bg-slate-50'
                  }`}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* User Deletion Confirmation Modal */}
      {deleteUserId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className={`w-full max-w-md p-6 rounded-3xl border shadow-2xl ${
            isDarkMode ? 'bg-[#1E293B] border-[#334155] text-white' : 'bg-white border-[#E2E8F0] text-slate-800'
          }`}>
            <h3 className="text-xl font-extrabold text-rose-500 flex items-center gap-2">
              ⚠️ Confirm User Deletion
            </h3>
            
            <p className="mt-3 text-sm opacity-90 leading-relaxed">
              Are you sure you want to permanently delete the user account for <strong>{deleteUsername}</strong>? 
              This action is irreversible and will permanently delete the profile data.
            </p>

            {deleteError && (
              <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs font-semibold">
                {deleteError}
              </div>
            )}

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                disabled={deleteLoading}
                onClick={() => setDeleteUserId(null)}
                className={`px-4 py-2 rounded-xl font-bold text-xs transition-all ${
                  isDarkMode ? 'bg-slate-800 hover:bg-slate-700' : 'bg-slate-100 hover:bg-slate-200'
                }`}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleteLoading}
                onClick={handleDeleteUser}
                className="px-4 py-2 bg-rose-500 hover:bg-rose-600 text-white font-bold text-xs rounded-xl transition-all flex items-center gap-2"
              >
                {deleteLoading ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    Deleting...
                  </>
                ) : "Delete Account"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfileView;
