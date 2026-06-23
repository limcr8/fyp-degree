import { VerificationResult } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const verifyNewsContent = async (
  text: string,
  language?: string,
  platform?: string,
  accessToken?: string
): Promise<VerificationResult> => {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      text,
      language: language || undefined,
      platform: platform || undefined,
    }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Verification request failed.");
  }

  return response.json() as Promise<VerificationResult>;
};


export interface SearchParams {
  q?: string;
  language?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  platform?: string;
  limit?: number;
  offset?: number;
}


export interface SearchResultItem {
  article_id: string;
  text: string;
  title?: string;
  classification: {
    verdict: string;
    confidence: number;
    riskLevel: string;
    explanation: string;
  };
  created_at: string;
  platform: string;
  language: string;
}


export interface SearchResponse {
  results: SearchResultItem[];
  total_count: number;
  page: number;
  per_page: number;
}


export const searchVerifiedArticles = async (params: SearchParams): Promise<SearchResponse> => {
  const query = new URLSearchParams();
  if (params.q) query.append("q", params.q);
  if (params.language) query.append("language", params.language);
  if (params.status) query.append("status", params.status);
  if (params.date_from) query.append("date_from", params.date_from);
  if (params.date_to) query.append("date_to", params.date_to);
  if (params.platform) query.append("platform", params.platform);
  if (params.limit !== undefined) query.append("limit", params.limit.toString());
  if (params.offset !== undefined) query.append("offset", params.offset.toString());

  const response = await fetch(`${API_BASE_URL}/api/v1/search?${query.toString()}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Search request failed.");
  }
  return response.json() as Promise<SearchResponse>;
};


export const getArticleById = async (id: string): Promise<VerificationResult> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/article/${id}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to retrieve article details.");
  }
  return response.json() as Promise<VerificationResult>;
};


export interface BackendRegisterResponse {
  user_id: string;
  username: string;
  email: string;
  role: string;
  api_key: string;
  message: string;
}


export const registerBackendUser = async (
  username: string,
  email: string,
  password: string,
  firebaseUid?: string
): Promise<BackendRegisterResponse> => {
  const body: Record<string, string> = { email, password };
  if (username && username.trim()) body.username = username.trim();
  if (firebaseUid) body.firebase_uid = firebaseUid;
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Registration request failed.");
  }

  return response.json() as Promise<BackendRegisterResponse>;
};


export interface BackendLoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    user_id: string;
    username: string;
    role: string;
  };
}


export const loginBackendUser = async (
  email: string,
  password: string
): Promise<BackendLoginResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Login request failed.");
  }

  return response.json() as Promise<BackendLoginResponse>;
};


export interface BackendRefreshResponse {
  access_token: string;
  expires_in: number;
}


export const refreshBackendAccessToken = async (
  refreshToken: string
): Promise<BackendRefreshResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${refreshToken}`,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Token refresh failed.");
  }

  return response.json() as Promise<BackendRefreshResponse>;
};


export interface TrendingTopicItem {
  topic: string;
  mentions: number;
  fake_count: number;
  articles: SearchResultItem[];
}


export interface TrendingResponse {
  trending: TrendingTopicItem[];
}


export const getTrendingTopics = async (
  language: string = "all",
  limit: number = 10
): Promise<TrendingResponse> => {
  const query = new URLSearchParams();
  if (language !== "all") query.append("language", language);
  query.append("limit", limit.toString());

  const response = await fetch(`${API_BASE_URL}/api/v1/trending?${query.toString()}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to retrieve trending topics.");
  }
  return response.json() as Promise<TrendingResponse>;
};


export const getValidAccessToken = async (): Promise<string | null> => {
  const accessToken = localStorage.getItem('access_token');
  const refreshToken = localStorage.getItem('refresh_token');

  if (!accessToken || !refreshToken) {
    return null;
  }

  try {
    const parts = accessToken.split('.');
    if (parts.length === 3) {
      const base64Url = parts[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      
      const payload = JSON.parse(jsonPayload);
      const expiry = payload.exp * 1000;
      const now = Date.now();
      
      if (expiry - now < 5 * 60 * 1000) {
        const refreshData = await refreshBackendAccessToken(refreshToken);
        localStorage.setItem('access_token', refreshData.access_token);
        return refreshData.access_token;
      }
    }
  } catch (err) {
    console.error("Failed to parse or refresh token:", err);
  }

  return accessToken;
};


export interface BackendLogoutResponse {
  message: string;
}


export const logoutBackendUser = async (
  accessToken: string
): Promise<BackendLogoutResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Logout request failed.");
  }

  return response.json() as Promise<BackendLogoutResponse>;
};


export interface UserProfileResponse {
  user_id: string;
  username: string;
  email: string;
  role: string;
  api_key: string;
  api_quota: {
    daily_limit: number;
    used_today: number;
    reset_at: string;
  };
  created_at: string;
  last_login: string;
}


export const getUserProfile = async (
  accessToken: string
): Promise<UserProfileResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to retrieve user profile.");
  }

  return response.json() as Promise<UserProfileResponse>;
};


export interface BackendUpdateProfileResponse {
  message: string;
  user: UserProfileResponse;
}


export const updateUserProfile = async (
  accessToken: string,
  username: string,
  email: string,
  preferences: { language: string; notifications: boolean }
): Promise<BackendUpdateProfileResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ username, email, preferences }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Profile update failed.");
  }

  return response.json() as Promise<BackendUpdateProfileResponse>;
};


export interface BackendChangePasswordResponse {
  message: string;
}


export const changeUserPassword = async (
  accessToken: string,
  oldPassword: string,
  newPassword: string
): Promise<BackendChangePasswordResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${accessToken}`,
    },
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Password change failed.");
  }

  return response.json() as Promise<BackendChangePasswordResponse>;
};


export interface BackendHistoryItem {
  article_id: string;
  text: string;
  classification: {
    verdict: string;
    confidence: number;
    riskLevel: string;
    explanation: string;
  };
  verified_at: string;
  explanation?: {
    shapData: { word: string; weight: number }[];
    summary: string;
    topFactors: string[];
  };
  verification?: {
    sources: { name: string; confirmed: boolean; url?: string }[];
    verificationScore: number;
    explanation: string;
  };
  finalAssessment?: {
    score: number;
    label: string;
    reasoning: string;
  };
  blockchain?: {
    transactionHash: string;
    blockNumber: number;
    timestamp: string;
    ipfsHash: string;
    network: string;
  };
  processingTimeMs?: number;
  platform?: string;
  language?: string;
}

export interface BackendHistoryResponse {
  history: BackendHistoryItem[];
  total_count: number;
  page: number;
}

export const getUserHistory = async (
  accessToken: string,
  limit: number = 20,
  offset: number = 0
): Promise<BackendHistoryResponse> => {
  const query = new URLSearchParams();
  query.append("limit", limit.toString());
  query.append("offset", offset.toString());

  const response = await fetch(`${API_BASE_URL}/api/v1/users/history?${query.toString()}`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to retrieve user history.");
  }

  return response.json() as Promise<BackendHistoryResponse>;
};


export interface AdminDashboardResponse {
  total_verifications: number;
  daily_verifications: number;
  model_accuracy: number;
  api_health: string;
  active_users: number;
  pending_reviews: number;
  system_uptime_percent: number;
}

export const getAdminDashboard = async (
  accessToken: string,
  adminToken: string
): Promise<AdminDashboardResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/dashboard`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "X-Admin-Token": adminToken,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to retrieve admin dashboard stats.");
  }

  return response.json() as Promise<AdminDashboardResponse>;
};


export interface ApiUsageStats {
  total_requests: number;
  daily_average: number;
  peak_daily: number;
}

export interface VerificationStats {
  total: number;
  fake: number;
  real: number;
  uncertain: number;
}

export interface ModelPerformanceStats {
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
}

export interface CostAnalysisStats {
  google_api_cost: number;
  ipfs_storage_gb: number;
  total_monthly: number;
}

export interface AdminAnalyticsResponse {
  period: string;
  api_usage: ApiUsageStats;
  verification_stats: VerificationStats;
  model_performance: ModelPerformanceStats;
  cost_analysis: CostAnalysisStats;
}

export const getAdminAnalytics = async (
  accessToken: string,
  adminToken: string,
  period: string = "30d"
): Promise<AdminAnalyticsResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/analytics?period=${period}`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "X-Admin-Token": adminToken,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to retrieve admin analytics stats.");
  }

  return response.json() as Promise<AdminAnalyticsResponse>;
};


export interface AdminTrendPoint {
  date: string;
  count: number;
}

export interface AdminTrendResponse {
  days: number;
  trend: AdminTrendPoint[];
}

export const getAdminTrend = async (
  accessToken: string,
  adminToken: string,
  days: number = 7
): Promise<AdminTrendResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/trend?days=${days}`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "X-Admin-Token": adminToken,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to retrieve verification trend.");
  }

  return response.json() as Promise<AdminTrendResponse>;
};


export interface SystemHealthResponse {
  status: string;
  timestamp: string;
  services: {
    api: string;
    database: string;
    bert_model: string;
    cache: string;
  };
  version: string;
  uptime_seconds: number;
}

export const getSystemHealth = async (): Promise<SystemHealthResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/health`, {
    method: "GET",
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to retrieve system health.");
  }

  return response.json() as Promise<SystemHealthResponse>;
};


export interface SystemStatusResponse {
  overall_status: string;
  components: {
    api_server: { status: string; response_time_ms: number };
    database: { status: string; connection_pool: string };
    ml_models: { status: string; bert_loaded: boolean; average_inference_time_ms: number };
    external_apis: { google_search: string; twitter: string; redis: string };
  };
  last_checked: string;
}

export const getSystemStatus = async (): Promise<SystemStatusResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/status`, {
    method: "GET",
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to retrieve system status.");
  }

  return response.json() as Promise<SystemStatusResponse>;
};


export interface AdminUserItem {
  user_id: string;
  username: string;
  email: string;
  role: string;
  created_at: string;
  last_login: string;
  verifications_count: number;
}

export interface AdminUsersResponse {
  users: AdminUserItem[];
  total_count: number;
  page: number;
}

export const getAdminUsers = async (
  accessToken: string,
  adminToken: string,
  limit: number = 50,
  offset: number = 0
): Promise<AdminUsersResponse> => {
  const query = new URLSearchParams();
  query.append("limit", limit.toString());
  query.append("offset", offset.toString());

  const response = await fetch(`${API_BASE_URL}/api/v1/admin/users?${query.toString()}`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "X-Admin-Token": adminToken,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to retrieve user accounts registry.");
  }

  return response.json() as Promise<AdminUsersResponse>;
};

export interface AdminUserDeleteResponse {
  message: string;
  user_id: string;
}

export const deleteAdminUser = async (
  accessToken: string,
  adminToken: string,
  userId: string
): Promise<AdminUserDeleteResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/users/${userId}`, {
    method: "DELETE",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "X-Admin-Token": adminToken,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to delete user account.");
  }

  return response.json() as Promise<AdminUserDeleteResponse>;
};

export interface FeedbackRequest {
  article_id: string;
  feedback_type: string;
  message: string;
  user_email: string;
}

export interface FeedbackResponse {
  feedback_id: string;
  status: string;
  message: string;
}

export const submitUserFeedback = async (
  request: FeedbackRequest
): Promise<FeedbackResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to submit feedback.");
  }

  return response.json() as Promise<FeedbackResponse>;
};

export interface FeedbackItem {
  feedback_id: string;
  article_id: string;
  feedback_type: string;
  message: string;
  user_email: string;
  submitted_at?: string;
  created_at?: string;
  status?: string;
}

export interface FeedbackListResponse {
  count: number;
  feedback: FeedbackItem[];
}

export const getAdminFeedback = async (): Promise<FeedbackListResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/feedback`, {
    method: "GET",
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to retrieve user feedback.");
  }

  return response.json() as Promise<FeedbackListResponse>;
};

export const downloadArticlePdf = async (
  accessToken: string,
  articleId: string
): Promise<Blob> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/export/pdf/${articleId}`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to download PDF report.");
  }

  return response.blob();
};

export const exportSearchCsv = async (
  accessToken: string,
  params: SearchParams
): Promise<Blob> => {
  const query = new URLSearchParams();
  if (params.q) query.append("q", params.q);
  if (params.language) query.append("language", params.language);
  if (params.status) query.append("status", params.status);
  if (params.date_from) query.append("date_from", params.date_from);
  if (params.date_to) query.append("date_to", params.date_to);
  if (params.platform) query.append("platform", params.platform);
  query.append("limit", (params.limit || 1000).toString());
  if (params.offset !== undefined) query.append("offset", params.offset.toString());

  const response = await fetch(`${API_BASE_URL}/api/v1/export/csv?${query.toString()}`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || await response.text();
    throw new Error(message || "Failed to export CSV report.");
  }

  return response.blob();
};






