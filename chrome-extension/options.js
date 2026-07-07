const API_BASE = "http://localhost:8000";

const apiKeyPanel = document.getElementById("apikeyPanel");
const loginPanel = document.getElementById("loginPanel");
const statusEl = document.getElementById("status");
const currentMethod = document.getElementById("currentMethod");
const logoutBtn = document.getElementById("logoutBtn");

document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const isApi = tab.dataset.tab === "apikey";
    apiKeyPanel.classList.toggle("hidden", !isApi);
    loginPanel.classList.toggle("hidden", isApi);
    statusEl.classList.add("hidden");
  };
});

function showStatus(msg, ok = true) {
  statusEl.textContent = msg;
  statusEl.className = `status ${ok ? "ok" : "err"}`;
  statusEl.classList.remove("hidden");
}

async function refreshCurrent() {
  const { authMethod, apiKey, accessToken } = await chrome.storage.local.get(["authMethod", "apiKey", "accessToken"]);
  if (authMethod === "apikey" && apiKey) {
    currentMethod.textContent = `API Key (${apiKey.substring(0, 12)}…)`;
    logoutBtn.classList.remove("hidden");
  } else if (authMethod === "login" && accessToken) {
    const { email } = await chrome.storage.local.get(["email"]);
    currentMethod.textContent = `Logged in${email ? ` as ${email}` : ""}`;
    logoutBtn.classList.remove("hidden");
  } else {
    currentMethod.textContent = "None";
    logoutBtn.classList.add("hidden");
  }
}

document.getElementById("saveKeyBtn").onclick = async () => {
  const key = document.getElementById("apiKeyInput").value.trim();
  if (!key.startsWith("sk_live_")) {
    showStatus("Invalid key — it should start with sk_live_", false);
    return;
  }
  await chrome.storage.local.set({ authMethod: "apikey", apiKey: key });
  await chrome.storage.local.remove(["accessToken", "refreshToken", "email"]);
  showStatus("API key saved. You're ready to verify.");
  refreshCurrent();
};

document.getElementById("loginBtn").onclick = async () => {
  const email = document.getElementById("emailInput").value.trim();
  const password = document.getElementById("passwordInput").value;
  if (!email || !password) {
    showStatus("Enter your email and password.", false);
    return;
  }
  const btn = document.getElementById("loginBtn");
  btn.disabled = true;
  try {
    const resp = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    if (!resp.ok) {
      const detail = await resp.json().catch(() => ({}));
      throw new Error(detail.detail || "Login failed");
    }
    const data = await resp.json();
    await chrome.storage.local.set({
      authMethod: "login",
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      email
    });
    await chrome.storage.local.remove(["apiKey"]);
    showStatus("Logged in successfully. You're ready to verify.");
    refreshCurrent();
  } catch (err) {
    showStatus(err.message || "Login failed.", false);
  } finally {
    btn.disabled = false;
  }
};

logoutBtn.onclick = async () => {
  await chrome.storage.local.remove(["authMethod", "apiKey", "accessToken", "refreshToken", "email"]);
  showStatus("Signed out.", true);
  refreshCurrent();
};

refreshCurrent();

document.getElementById("websiteLink").onclick = (e) => {
  e.preventDefault();
  chrome.tabs.create({ url: "http://localhost:3000" });
};