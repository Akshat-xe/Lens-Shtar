/**
 * Lens Shtar - SPA Core Engine
 * Handles State, Auth, Routing, Settings, API Comm, and UI rendering natively.
 */

(() => {
  // --- 1. CONFIGURATION ---
  const CONFIG = {
    DEFAULT_API_BASE: "http://localhost:8000",
    SUPABASE_URL: "https://tgmvethwaquialwxenld.supabase.co",
    SUPABASE_ANON_KEY: "sb_publishable_QVxcf5DEQufi3bdpxlNtYg_aT9kI4o3",
    STORAGE_KEY_API_BASE: "ls_api_base",
  };

  // Resolve API Base
  function resolveApiBase() {
    try {
      const stored = localStorage.getItem(CONFIG.STORAGE_KEY_API_BASE);
      if (stored && stored.startsWith("http")) return stored;
    } catch (_) {}
    return CONFIG.DEFAULT_API_BASE;
  }
  const API_BASE = resolveApiBase();

  const supabase = window.supabase ? window.supabase.createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_ANON_KEY) : null;
  
  // App State
  const state = {
    session: null,
    user: null,
    hasApiKey: false,
    dashboardData: null,
  };

  // --- 2. ROUTER ---
  function handleRoute() {
    const hash = window.location.hash.replace("#", "") || "home";
    document.querySelectorAll(".view").forEach(v => {
      v.classList.remove("active");
    });
    
    // Fallback to home if view doesn't exist
    let target = document.getElementById(`view-${hash}`);
    if (!target) {
      window.location.hash = "home";
      target = document.getElementById('view-home');
    }
    target.classList.add("active");

    // Update nav links
    document.querySelectorAll(".nav-links a").forEach(a => {
      a.classList.toggle("active", a.getAttribute("href") === `#${hash}`);
    });

    // Scroll to top
    window.scrollTo(0, 0);

    // Contextual renders
    if (hash === "dashboard") renderDashboard();
  }
  window.addEventListener("hashchange", handleRoute);

  // --- 3. AUTHENTICATION & SESSION ---
  function getInitials(name, email) {
    const src = (name || email || "LS").trim();
    const parts = src.split(/\s+/).filter(Boolean);
    if (parts.length > 1) return (parts[0][0] + parts[1][0]).toUpperCase();
    return src.slice(0, 2).toUpperCase();
  }

  async function signIn() {
    if (!supabase) return;
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin + window.location.pathname },
    });
    if (error) alert("Sign-in error. Try again.");
  }

  async function signOut() {
    if (supabase) await supabase.auth.signOut();
    state.session = null;
    state.user = null;
    state.hasApiKey = false;
    updateAuthUI();
    updateSettingsUI();
    window.location.hash = "home";
  }

  function updateAuthUI() {
    const slot = document.getElementById("authActionSlot");
    if (!slot) return;
    if (state.session) {
      const init = getInitials(state.user?.user_metadata?.full_name, state.user?.email);
      slot.innerHTML = `
        <button id="accountBtn" class="btn btn-outline" style="border-radius: 99px; padding: 4px 16px 4px 4px;">
          <span style="display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; background: var(--surface); border-radius: 50%; margin-right: 8px;">${init}</span>
          Account
        </button>
        <div id="accountDropdown" style="display: none;">
          <div style="font-weight: 600; font-size: 14px; margin-bottom: 2px;">${state.user?.user_metadata?.full_name || "Authorized User"}</div>
          <div style="font-size: 13px; color: var(--fg-muted); margin-bottom: 16px;">${state.user?.email}</div>
          <button id="signOutBtn" class="btn btn-primary" style="width: 100%;">Sign Out</button>
        </div>
      `;
      // Dropdown wire-up
      const accBtn = document.getElementById("accountBtn");
      const drop = document.getElementById("accountDropdown");
      const outBtn = document.getElementById("signOutBtn");
      accBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        drop.style.display = drop.style.display === "none" ? "block" : "none";
      });
      document.addEventListener("click", (e) => {
        if (!drop.contains(e.target) && e.target !== accBtn) drop.style.display = "none";
      });
      outBtn.addEventListener("click", signOut);
    } else {
      slot.innerHTML = `<button id="googleSignInBtn" class="btn btn-primary">Sign in</button>`;
      document.getElementById("googleSignInBtn").addEventListener("click", signIn);
    }
  }

  async function checkServerSettingsStatus() {
    if (!state.session) {
      state.hasApiKey = false;
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/settings/status`, {
        headers: { Authorization: `Bearer ${state.session.access_token}` },
      });
      if (res.ok) {
        const data = await res.json();
        state.hasApiKey = data.has_api_key;
      }
    } catch (_) {}
    updateSettingsUI();
  }

  // --- 4. SETTINGS VIEW LOGIC ---
  function updateSettingsUI() {
    const sum = document.getElementById("settingsAccountSummary");
    const statusText = document.getElementById("keyStatusText");
    if (!sum || !statusText) return;

    if (state.session) {
      sum.textContent = `${state.user.email} (Authenticated)`;
      statusText.textContent = state.hasApiKey ? "✅ Gemini key is active in session memory." : "⚠️ No key configured. Analysis disabled.";
      statusText.style.color = state.hasApiKey ? "var(--green)" : "var(--fg-muted)";
    } else {
      sum.textContent = "Not signed in. Please sign in to configure API.";
      statusText.textContent = "Waiting for authentication...";
      statusText.style.color = "var(--fg-muted)";
    }
  }

  async function saveApiKey() {
    if (!state.session) return alert("Sign in first.");
    const val = document.getElementById("geminiKeyInput")?.value.trim();
    if (!val) return alert("Enter a valid key.");
    
    document.getElementById("keyStatusText").textContent = "Saving...";
    try {
      const res = await fetch(`${API_BASE}/api/settings/set-api-key`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${state.session.access_token}`,
        },
        body: JSON.stringify({ gemini_api_key: val }),
      });
      if (res.ok) {
        document.getElementById("geminiKeyInput").value = "";
        await checkServerSettingsStatus();
      } else {
        throw new Error("Invalid key format or server error");
      }
    } catch (e) {
      alert("Failed to save key: " + e.message);
      document.getElementById("keyStatusText").textContent = "Error saving key.";
    }
  }

  async function clearApiKey() {
    if (!state.session) return;
    try {
      await fetch(`${API_BASE}/api/settings/clear-api-key`, {
        method: "POST",
        headers: { Authorization: `Bearer ${state.session.access_token}` },
      });
      await checkServerSettingsStatus();
    } catch (_) {}
  }

  // --- 5. UPLOAD FLOW ---
  function initUploadUI() {
    const input = document.getElementById("realUploadInput");
    const browse = document.getElementById("browseUploadBtn");
    const box = document.getElementById("uploadBox");
    const heroBtn = document.getElementById("heroUploadBtn");

    if(heroBtn) heroBtn.addEventListener("click", () => {
      document.getElementById("uploadSection").scrollIntoView({ behavior: "smooth" });
    });

    if (browse && input) browse.addEventListener("click", () => input.click());
    if (input) input.addEventListener("change", () => {
      if (input.files[0]) handleUpload(input.files[0]);
    });
    if (box) {
      box.addEventListener("dragover", e => { e.preventDefault(); box.style.borderColor = "var(--primary)"; });
      box.addEventListener("dragleave", () => { box.style.borderColor = ""; });
      box.addEventListener("drop", e => {
        e.preventDefault();
        box.style.borderColor = "";
        if (e.dataTransfer.files[0]) handleUpload(e.dataTransfer.files[0]);
      });
    }
  }

  function setUploadState(view, text = "", pct = 0) {
    document.getElementById("stateIdle").classList.toggle("active", view === "idle");
    document.getElementById("stateProcessing").classList.toggle("active", view === "processing");
    if (view === "processing") {
      document.getElementById("uploadStatusText").textContent = text;
      document.getElementById("uploadProgressBar").style.width = `${pct}%`;
    }
  }

  async function handleUpload(file) {
    if (!state.session) {
      alert("Please sign in to upload files.");
      window.scrollTo(0,0);
      return;
    }
    if (!state.hasApiKey && file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please configure your Gemini API Key in Settings to process PDFs.");
      window.location.hash = "settings";
      return;
    }
    
    if (file.size > 50 * 1024 * 1024) return alert("File too large (>50MB).");

    setUploadState("processing", "Encrypting payload...", 10);
    const fd = new FormData();
    fd.append("file", file);

    try {
      setUploadState("processing", "Sending to financial AI engine...", 40);
      const res = await fetch(`${API_BASE}/api/upload?include_ai_summary=true`, {
        method: "POST",
        headers: { Authorization: `Bearer ${state.session.access_token}` },
        body: fd
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }

      const upData = await res.json();
      setUploadState("processing", "Fetching deep analytical payload...", 80);

      // Fetch dashboard
      const dashRes = await fetch(`${API_BASE}/api/dashboard/${upData.file_id}`, {
        headers: { Authorization: `Bearer ${state.session.access_token}` }
      });
      if (!dashRes.ok) throw new Error("Could not retrieve dashboard data");

      const dashData = await dashRes.json();
      state.dashboardData = dashData;
      
      setUploadState("processing", "Analysis Complete! Opening Dashboard...", 100);
      setTimeout(() => {
        window.location.hash = "dashboard";
        setUploadState("idle");
      }, 700);

    } catch (e) {
      setUploadState("idle");
      alert(e.message);
    }
  }

  // --- 6. DASHBOARD RENDERING ---
  const fmtInr = (val) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val || 0);

  let trendChartInstance = null;
  let donutChartInstance = null;

  function renderDashboard() {
    if (!state.dashboardData) return;
    const d = state.dashboardData;

    document.getElementById("dashboardSubtitle").textContent = `Analysis of ${d.filename}`;

    // KPIs
    document.getElementById("dashIncome").textContent = fmtInr(d.kpis?.total_income);
    document.getElementById("dashExpenses").textContent = fmtInr(d.kpis?.total_expenses);
    document.getElementById("dashNet").textContent = fmtInr(d.kpis?.net_savings);
    document.getElementById("dashTxCount").textContent = d.transactions?.length || 0;

    // AI summary & Leaks
    const aiList = document.getElementById("aiInsightsList");
    if (d.ai_summary) {
      aiList.innerHTML = `<div class="insight-card"><div class="insight-dot info">🧠</div><p>${d.ai_summary.replace(/\\n/g, "<br/>")}</p></div>`;
    } else {
      aiList.innerHTML = `<p class="text-muted">No text summary generated.</p>`;
    }

    const leakList = document.getElementById("leaksList");
    if (d.leaks && d.leaks.length > 0) {
      leakList.innerHTML = d.leaks.map(l => `
        <div class="insight-card">
          <div class="insight-dot alert">🚨</div>
          <div style="flex:1;">
            <div style="font-weight:600; font-size:14px; margin-bottom:4px">${l.leak_type}</div>
            <p>${l.description}</p>
          </div>
          <div style="font-weight:700; color:var(--red)">-${fmtInr(l.annualized_cost)}/yr</div>
        </div>
      `).join('');
    } else {
      leakList.innerHTML = `<p class="text-muted">No specific leaks detected. Great job!</p>`;
    }

    // Charts
    setupCharts(d.charts);
  }

  function setupCharts(charts) {
    if (!charts || !window.Chart) return;
    Chart.defaults.color = '#888';
    Chart.defaults.borderColor = 'hsla(0,0%,100%,0.08)';

    const trend = charts.monthly_trend || [];
    const tCtx = document.getElementById('trendChart');
    if (tCtx && trend.length > 0) {
      if(trendChartInstance) trendChartInstance.destroy();
      trendChartInstance = new Chart(tCtx, {
        type: 'line',
        data: {
          labels: trend.map(t => t.month),
          datasets: [
            { label: 'Income', data: trend.map(t => t.income), borderColor: 'hsl(220,90%,60%)', backgroundColor: 'hsla(220,90%,60%,0.1)', fill: true, tension: 0.4 },
            { label: 'Expenses', data: trend.map(t => t.expenses), borderColor: 'hsl(24,85%,50%)', backgroundColor: 'hsla(24,85%,50%,0.1)', fill: true, tension: 0.4 }
          ]
        },
        options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
      });
    }

    const brk = charts.category_breakdown || [];
    const dCtx = document.getElementById('donutChart');
    if (dCtx && brk.length > 0) {
      if(donutChartInstance) donutChartInstance.destroy();
      const defaultColors = ["#e11d48", "#f97316", "#fde047", "#22c55e", "#0ea5e9", "#6366f1", "#a855f7", "#ec4899"];
      donutChartInstance = new Chart(dCtx, {
        type: 'doughnut',
        data: {
          labels: brk.map(b => b.category),
          datasets: [{
            data: brk.map(b => b.amount),
            backgroundColor: defaultColors.slice(0, brk.length),
            borderWidth: 0
          }]
        },
        options: { responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { position: 'right' } } }
      });
    }
  }

  // --- 7. BOOTSTRAP ---
  async function boot() {
    if (supabase) {
      const { data } = await supabase.auth.getSession();
      state.session = data?.session || null;
      state.user = data?.session?.user || null;
      
      supabase.auth.onAuthStateChange((evt, session) => {
        state.session = session;
        state.user = session?.user;
        updateAuthUI();
        if (session) checkServerSettingsStatus();
      });
    }
    
    updateAuthUI();
    if (state.session) await checkServerSettingsStatus();
    
    // Bind buttons
    document.getElementById("saveKeyBtn")?.addEventListener("click", saveApiKey);
    document.getElementById("clearKeyBtn")?.addEventListener("click", clearApiKey);

    initUploadUI();
    handleRoute(); // initial routing
  }

  // Run
  document.addEventListener("DOMContentLoaded", boot);

})();
