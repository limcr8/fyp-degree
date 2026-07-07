const API_BASE = "http://localhost:8000";

const textInput = document.getElementById("textInput");
const verifyBtn = document.getElementById("verifyBtn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const verdictBadge = document.getElementById("verdictBadge");
const confidenceVal = document.getElementById("confidenceVal");
const summaryEl = document.getElementById("summary");
const factorEl = document.getElementById("factor");
const authWarn = document.getElementById("authWarn");

document.getElementById("settingsBtn").onclick = () => chrome.runtime.openOptionsPage();
document.getElementById("openSettings").onclick = (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); };
document.getElementById("webPortalLink").onclick = (e) => {
  e.preventDefault();
  chrome.tabs.create({ url: "http://localhost:3000" });
};

async function hasCredential() {
  const { authMethod, apiKey, accessToken } = await chrome.storage.local.get(["authMethod", "apiKey", "accessToken"]);
  return (authMethod === "apikey" && apiKey) || (authMethod === "login" && accessToken);
}

async function buildHeaders() {
  const { authMethod, apiKey, accessToken } = await chrome.storage.local.get(["authMethod", "apiKey", "accessToken"]);
  const headers = { "Content-Type": "application/json" };
  if (authMethod === "apikey" && apiKey) {
    headers["X-API-Key"] = apiKey;
  } else if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  return headers;
}

async function refreshToken() {
  const { refreshToken } = await chrome.storage.local.get(["refreshToken"]);
  if (!refreshToken) return null;
  const resp = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${refreshToken}` }
  });
  if (!resp.ok) return null;
  const data = await resp.json();
  await chrome.storage.local.set({ accessToken: data.access_token });
  return data.access_token;
}

async function verify(text) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  let headers = await buildHeaders();
  let resp;
  try {
    resp = await fetch(`${API_BASE}/analyze`, {
      method: "POST", headers, body: JSON.stringify({ text }), signal: controller.signal
    });
  } finally {
    clearTimeout(timeout);
  }
  if (resp.status === 401) {
    const newToken = await refreshToken();
    if (newToken) {
      headers = await buildHeaders();
      resp = await fetch(`${API_BASE}/analyze`, { method: "POST", headers, body: JSON.stringify({ text }) });
    }
  }
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${resp.status})`);
  }
  return resp.json();
}

function verdictClass(verdict) {
  const v = (verdict || "").toUpperCase();
  if (v.includes("REAL")) return "real";
  if (v.includes("FAKE")) return "fake";
  return "uncertain";
}

function render(data) {
  const verdict = data.classification?.verdict || data.finalAssessment?.label || "UNCERTAIN";
  const confidence = data.classification?.confidence ?? data.finalAssessment?.score ?? 0;
  const summary = data.finalAssessment?.reasoning || data.verification?.summary || "";
  const topFactor = data.explanation?.topFactors?.[0];
  verdictBadge.textContent = verdict.replace("_", " ").toUpperCase();
  verdictBadge.className = `badge ${verdictClass(verdict)}`;
  confidenceVal.textContent = `${Math.round(confidence * 100)}%`;
  summaryEl.textContent = summary;
  if (topFactor) {
    factorEl.textContent = `Key signal: ${topFactor}`;
    factorEl.classList.remove("hidden");
  } else {
    factorEl.classList.add("hidden");
  }
  resultEl.classList.remove("hidden");
}

async function handleVerify() {
  const text = textInput.value.trim();
  if (!text) return;
  verifyBtn.disabled = true;
  statusEl.className = "status";
  statusEl.innerHTML = '<span class="spinner"></span> Analyzing… (keep this open)';
  statusEl.classList.remove("hidden");
  resultEl.classList.add("hidden");
  try {
    const data = await verify(text);
    await chrome.storage.local.set({ lastResult: data });
    statusEl.classList.add("hidden");
    render(data);
  } catch (err) {
    statusEl.className = "status error";
    statusEl.textContent = err.message || "Verification failed.";
  } finally {
    verifyBtn.disabled = false;
  }
}

verifyBtn.onclick = handleVerify;

async function init() {
  if (!(await hasCredential())) {
    authWarn.classList.remove("hidden");
  }
  const { lastResult } = await chrome.storage.local.get(["lastResult"]);
  if (lastResult) render(lastResult);
  const { pendingSelection } = await chrome.storage.session.get(["pendingSelection"]);
  if (pendingSelection) {
    textInput.value = pendingSelection;
    await chrome.storage.session.remove(["pendingSelection"]);
    return;
  }
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.id) {
      const [{ result } = {}] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => window.getSelection().toString().trim()
      });
      if (result) textInput.value = result;
    }
  } catch (_) {}
}

init();