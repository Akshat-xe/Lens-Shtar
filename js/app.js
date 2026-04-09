/**
 * Lens Shtar — SPA Core Engine v3
 * Deep financial dashboard: 6-category analysis, multi-line chart, transaction table.
 * Auth, routing, settings and upload flows preserved from v1.
 */
(() => {
  // ── CONFIG ──────────────────────────────────────────────────────────────────
  const CONFIG = {
    DEFAULT_API_BASE: "http://localhost:8000",
    SUPABASE_URL: "https://tgmvethwaquialwxenld.supabase.co",
    SUPABASE_ANON_KEY: "sb_publishable_QVxcf5DEQufi3bdpxlNtYg_aT9kI4o3",
    STORAGE_KEY_API_BASE: "ls_api_base",
    TX_PAGE_SIZE: 20,
  };

  function resolveApiBase() {
    try {
      const s = localStorage.getItem(CONFIG.STORAGE_KEY_API_BASE);
      if (s && s.startsWith("http")) return s;
    } catch (_) { }
    return CONFIG.DEFAULT_API_BASE;
  }
  const API_BASE = resolveApiBase();
  const supabase = window.supabase ? window.supabase.createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_ANON_KEY) : null;

  const state = {
    session: null, user: null, hasApiKey: false,
    dashboardData: null,
    txPage: 1, txAll: [], txFiltered: [],
    charts: { trend: null, donut: null, payment: null },
  };

  // ── ROUTER ──────────────────────────────────────────────────────────────────
  function handleRoute() {
    const hash = window.location.hash.replace("#", "") || "home";
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    let target = document.getElementById(`view-${hash}`);
    if (!target) { window.location.hash = "home"; target = document.getElementById("view-home"); }
    target.classList.add("active");
    document.querySelectorAll(".nav-links a").forEach(a =>
      a.classList.toggle("active", a.getAttribute("href") === `#${hash}`)
    );
    window.scrollTo(0, 0);
    if (hash === "dashboard") renderDashboard();
    if (hash === "settings") updateSettingsUI();
  }
  window.addEventListener("hashchange", handleRoute);

  // ── AUTH ────────────────────────────────────────────────────────────────────
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
    Object.assign(state, { session: null, user: null, hasApiKey: false });
    updateAuthUI(); updateSettingsUI();
    window.location.hash = "home";
  }

  function updateAuthUI() {
    const slot = document.getElementById("authActionSlot");
    if (!slot) return;
    if (state.session) {
      const init = getInitials(state.user?.user_metadata?.full_name, state.user?.email);
      slot.innerHTML = `
        <div style="position:relative">
          <button id="accountBtn" class="btn btn-outline btn-sm" style="border-radius:99px;padding:4px 14px 4px 4px;gap:8px">
            <span style="display:flex;align-items:center;justify-content:center;width:26px;height:26px;background:linear-gradient(135deg,var(--primary),var(--accent));border-radius:50%;font-size:11px;font-weight:700;color:#fff">${init}</span>
            Account
          </button>
          <div id="accountDropdown" style="display:none">
            <div style="font-weight:700;font-size:14px;margin-bottom:2px">${state.user?.user_metadata?.full_name || "Authorized User"}</div>
            <div style="font-size:12px;color:var(--fg-muted);margin-bottom:16px">${state.user?.email}</div>
            <button id="signOutBtn" class="btn btn-primary btn-sm" style="width:100%">Sign Out</button>
          </div>
        </div>`;
      const accBtn = document.getElementById("accountBtn");
      const drop = document.getElementById("accountDropdown");
      accBtn.addEventListener("click", e => { e.stopPropagation(); drop.style.display = drop.style.display === "none" ? "block" : "none"; });
      document.addEventListener("click", e => { if (!drop.contains(e.target) && e.target !== accBtn) drop.style.display = "none"; });
      document.getElementById("signOutBtn").addEventListener("click", signOut);
    } else {
      slot.innerHTML = `<button id="googleSignInBtn" class="btn btn-primary btn-sm">Sign in</button>`;
      document.getElementById("googleSignInBtn").addEventListener("click", signIn);
    }
  }

  async function checkServerSettingsStatus() {
    if (!state.session) { state.hasApiKey = false; return; }
    try {
      const res = await fetch(`${API_BASE}/api/settings/status`, {
        headers: { Authorization: `Bearer ${state.session.access_token}` },
      });
      if (res.ok) { const d = await res.json(); state.hasApiKey = d.has_api_key; }
    } catch (_) { }
    updateSettingsUI();
  }

  // ── SETTINGS ────────────────────────────────────────────────────────────────
  function updateSettingsUI() {
    const sum = document.getElementById("settingsAccountSummary");
    const statusText = document.getElementById("keyStatusText");
    if (!sum || !statusText) return;
    if (state.session) {
      sum.textContent = `${state.user.email} — Authenticated ✓`;
      statusText.textContent = state.hasApiKey ? "✅ Gemini key active in session." : "⚠️ No key configured. Upload analysis disabled.";
      statusText.style.color = state.hasApiKey ? "var(--green)" : "var(--fg-muted)";
    } else {
      sum.textContent = "Not signed in.";
      statusText.textContent = "Sign in to configure.";
      statusText.style.color = "var(--fg-muted)";
    }
  }

  async function saveApiKey() {
    if (!state.session) return alert("Sign in first.");
    const val = document.getElementById("geminiKeyInput")?.value.trim();
    if (!val) return alert("Enter a valid key.");
    document.getElementById("keyStatusText").textContent = "Saving…";
    try {
      const res = await fetch(`${API_BASE}/api/settings/set-api-key`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${state.session.access_token}` },
        body: JSON.stringify({ gemini_api_key: val }),
      });
      if (res.ok) {
        document.getElementById("geminiKeyInput").value = "";
        await checkServerSettingsStatus();
      } else {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Invalid key format or server error");
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
        method: "POST", headers: { Authorization: `Bearer ${state.session.access_token}` },
      });
      await checkServerSettingsStatus();
    } catch (_) { }
  }

  // ── UPLOAD ──────────────────────────────────────────────────────────────────
  function initUploadUI() {
    const input = document.getElementById("realUploadInput");
    const browse = document.getElementById("browseUploadBtn");
    const box = document.getElementById("uploadBox");
    const heroBtn = document.getElementById("heroUploadBtn");
    if (heroBtn) heroBtn.addEventListener("click", () => {
      document.getElementById("uploadSection")?.scrollIntoView({ behavior: "smooth" });
    });
    if (browse && input) browse.addEventListener("click", () => input.click());
    if (input) input.addEventListener("change", () => { if (input.files[0]) handleUpload(input.files[0]); });
    if (box) {
      box.addEventListener("dragover", e => { e.preventDefault(); box.style.borderColor = "var(--primary)"; box.style.boxShadow = "var(--shadow-glow)"; });
      box.addEventListener("dragleave", () => { box.style.borderColor = ""; box.style.boxShadow = ""; });
      box.addEventListener("drop", e => {
        e.preventDefault(); box.style.borderColor = ""; box.style.boxShadow = "";
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
    if (!state.session) { alert("Please sign in to upload files."); window.scrollTo(0, 0); return; }
    if (!state.hasApiKey) { alert("Please configure your Gemini API Key in Settings first."); window.location.hash = "settings"; return; }
    if (file.size > 50 * 1024 * 1024) return alert("File too large (>50MB).");

    setUploadState("processing", "Encrypting payload…", 8);
    const fd = new FormData();
    fd.append("file", file);

    const steps = [
      [15, "Sending to AI engine…"],
      [30, "Gemini is reading your statement…"],
      [55, "Extracting transactions & profiling income…"],
      [70, "Categorizing expenses & detecting patterns…"],
      [82, "Building financial health report…"],
      [92, "Generating AI analyst summary…"],
    ];
    let stepIdx = 0;
    const stepTimer = setInterval(() => {
      if (stepIdx < steps.length) {
        setUploadState("processing", steps[stepIdx][1], steps[stepIdx][0]);
        stepIdx++;
      }
    }, 3500);

    try {
      const res = await fetch(`${API_BASE}/api/upload?include_ai_summary=true`, {
        method: "POST",
        headers: { Authorization: `Bearer ${state.session.access_token}` },
        body: fd,
      });
      clearInterval(stepTimer);
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || "Upload failed"); }
      const upData = await res.json();

      setUploadState("processing", "Fetching complete dashboard…", 96);
      const dashRes = await fetch(`${API_BASE}/api/dashboard/${upData.file_id}`, {
        headers: { Authorization: `Bearer ${state.session.access_token}` },
      });
      if (!dashRes.ok) throw new Error("Could not retrieve dashboard data");

      state.dashboardData = await dashRes.json();
      setUploadState("processing", "Analysis complete! Opening dashboard…", 100);
      setTimeout(() => { window.location.hash = "dashboard"; setUploadState("idle"); }, 700);
    } catch (e) {
      clearInterval(stepTimer);
      setUploadState("idle");
      alert(e.message);
    }
  }

  // ── FORMATTERS ───────────────────────────────────────────────────────────────
  const fmtINR = v => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(v || 0);
  const fmtNum = v => new Intl.NumberFormat("en-IN").format(v || 0);

  // ── DASHBOARD RENDER ─────────────────────────────────────────────────────────
  function renderDashboard() {
    const d = state.dashboardData;
    if (!d) return;

    const k = d.kpis || {};
    const profile = d.profile || {};
    const incomeProfile = d.income_profile || {};
    const stressInd = d.stress_indicators || {};
    const beh = d.behavioral_insights || {};
    const ci = d.charts || {};

    // ── Title & Period ────────────────────────────────────────────────────────
    const el = id => document.getElementById(id);
    el("dashTitle").textContent = `Financial Overview`;
    el("dashboardSubtitle").textContent = `Deep analysis of ${d.filename || "your statement"}`;

    if (profile.statement_from || profile.statement_to) {
      const pb = el("dashPeriodBadge");
      pb.textContent = `${profile.statement_from || "?"} → ${profile.statement_to || "?"}`;
      pb.style.display = "inline-flex";
    }

    // ── Profile Card ──────────────────────────────────────────────────────────
    const profileSec = el("profileSection");
    if (profile.account_holder_name || profile.bank_name) {
      profileSec.style.display = "block";
      const name = profile.account_holder_name || "Account Holder";
      const initials = name.split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase() || "?";
      el("profileAvatar").textContent = initials;
      el("profileName").textContent = name;
      el("profileBank").textContent = [profile.bank_name, profile.account_number_masked].filter(Boolean).join(" · ") || "—";
      el("profileAccType").textContent = profile.account_type || "—";
      el("profileIFSC").textContent = profile.ifsc || "—";
      el("profilePeriod").textContent = [profile.statement_from, profile.statement_to].filter(Boolean).join(" → ") || "—";
      el("profileIncomeType").textContent = incomeProfile.income_consistency || incomeProfile.primary_frequency || "—";
    }

    // ── KPIs ──────────────────────────────────────────────────────────────────
    const income = k.total_income ?? k.income ?? 0;
    const expenses = k.total_expenses ?? k.expenses ?? 0;
    const savings = k.net_savings ?? k.savings ?? 0;

    el("dashIncome").textContent = fmtINR(income);
    el("dashIncomeSource").textContent = incomeProfile.primary_source
      ? `${incomeProfile.primary_source} · ${incomeProfile.primary_frequency || "monthly"}`
      : `${fmtNum(k.transaction_count || 0)} transactions`;

    el("dashExpenses").textContent = fmtINR(expenses);
    el("dashFixedVar").textContent = k.fixed_ratio_pct != null
      ? `Fixed ${k.fixed_ratio_pct}% · Variable ${k.variable_ratio_pct ?? (100 - k.fixed_ratio_pct)}%`
      : "—";

    el("dashNet").textContent = fmtINR(savings);
    el("dashNet").style.color = savings >= 0 ? "var(--green)" : "var(--red)";
    el("dashSavingsRate").textContent = k.savings_rate_pct != null ? `${k.savings_rate_pct}% savings rate` : "—";

    el("dashInvest").textContent = fmtINR(k.investment_total ?? 0);
    el("dashInvestRate").textContent = k.investment_rate_pct != null ? `${k.investment_rate_pct}% of income` : "No investments detected";

    el("dashEMI").textContent = fmtINR(k.emi_total ?? 0);
    if (k.emi_total && income > 0) {
      const emiratio = ((k.emi_total / income) * 100).toFixed(0);
      el("dashEMIRatio").textContent = `${emiratio}% of income`;
      el("dashEMIRatio").style.color = emiratio > 40 ? "var(--red)" : emiratio > 30 ? "var(--yellow)" : "var(--fg-muted)";
    }

    el("dashTxCount").textContent = fmtNum(k.transaction_count ?? 0);
    el("dashCashPct").textContent = k.cash_reliance_pct != null
      ? `${k.cash_reliance_pct}% cash reliance`
      : `UPI: ${fmtINR(k.upi_spend ?? 0)}`;

    // ── AI Summary ────────────────────────────────────────────────────────────
    if (d.ai_summary) {
      el("aiSummaryCard").style.display = "block";
      el("aiSummaryText").textContent = d.ai_summary;
    }

    // ── Charts ────────────────────────────────────────────────────────────────
    setupTrendChart(ci.monthly_flow);
    setupDonutChart(ci.category_breakdown);
    setupPaymentChart(ci.payment_distribution);
    renderTopMerchants(ci.top_merchants);

    // ── Insights ─────────────────────────────────────────────────────────────
    renderLeaks(d.leaks || []);
    renderSuggestions(d.suggestions || {});
    renderRecurring(d.recurring || []);
    renderBehavioral(beh, stressInd, k);

    // ── Transaction Table ─────────────────────────────────────────────────────
    state.txAll = d.transactions || [];
    state.txFiltered = [...state.txAll];
    buildCategoryFilter(state.txAll);
    state.txPage = 1;
    renderTxTable();
    bindTxFilters();
  }

  // ── CHARTS ──────────────────────────────────────────────────────────────────
  const CHART_DEFAULTS = () => {
    Chart.defaults.color = "#7a7a8a";
    Chart.defaults.borderColor = "hsla(0,0%,100%,0.06)";
    Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
  };

  const PALETTE = [
    "#e85d26", "#3b82f6", "#22c55e", "#a855f7", "#f59e0b",
    "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1",
    "#14b8a6", "#ef4444",
  ];

  function setupTrendChart(flow) {
    const ctx = document.getElementById("trendChart");
    if (!ctx || !flow || !flow.labels?.length) return;
    if (state.charts.trend) state.charts.trend.destroy();
    CHART_DEFAULTS();

    const labels = flow.labels;
    const incomeData = flow.income || [];
    const expData = flow.expenses || [];
    const savingsData = flow.savings || incomeData.map((v, i) => v - (expData[i] || 0));

    // Render legend
    const legend = document.getElementById("trendLegend");
    if (legend) legend.innerHTML = [
      { color: "#22c55e", label: "Income" },
      { color: "#ef4444", label: "Expenses" },
      { color: "#e85d26", label: "Savings" },
    ].map(l => `<div class="legend-item"><div class="legend-dot" style="background:${l.color}"></div>${l.label}</div>`).join("");

    state.charts.trend = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Income",
            data: incomeData,
            borderColor: "#22c55e",
            backgroundColor: "hsla(142,70%,48%,0.08)",
            borderWidth: 2.5,
            pointRadius: 5,
            pointHoverRadius: 8,
            pointBackgroundColor: "#22c55e",
            pointBorderColor: "#030305",
            pointBorderWidth: 2,
            fill: true,
            tension: 0.4,
          },
          {
            label: "Expenses",
            data: expData,
            borderColor: "#ef4444",
            backgroundColor: "hsla(0,72%,55%,0.08)",
            borderWidth: 2.5,
            pointRadius: 5,
            pointHoverRadius: 8,
            pointBackgroundColor: "#ef4444",
            pointBorderColor: "#030305",
            pointBorderWidth: 2,
            fill: true,
            tension: 0.4,
          },
          {
            label: "Net Savings",
            data: savingsData,
            borderColor: "#e85d26",
            backgroundColor: "hsla(24,90%,52%,0.08)",
            borderWidth: 2,
            borderDash: [6, 3],
            pointRadius: 4,
            pointHoverRadius: 7,
            pointBackgroundColor: "#e85d26",
            pointBorderColor: "#030305",
            pointBorderWidth: 2,
            fill: false,
            tension: 0.4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "hsla(240,6%,10%,0.95)",
            borderColor: "hsla(0,0%,100%,0.1)",
            borderWidth: 1,
            padding: 14,
            titleFont: { family: "'Space Grotesk', sans-serif", weight: "700", size: 13 },
            bodyFont: { size: 13 },
            callbacks: {
              label: ctx => ` ${ctx.dataset.label}: ${fmtINR(ctx.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: "hsla(0,0%,100%,0.04)" },
            ticks: { font: { size: 12 } },
          },
          y: {
            grid: { color: "hsla(0,0%,100%,0.04)" },
            ticks: {
              font: { size: 12 },
              callback: v => "₹" + (v >= 100000 ? (v / 100000).toFixed(1) + "L" : v >= 1000 ? (v / 1000).toFixed(0) + "k" : v),
            },
          },
        },
      },
    });
  }

  function setupDonutChart(breakdown) {
    const ctx = document.getElementById("donutChart");
    if (!ctx || !breakdown?.length) return;
    if (state.charts.donut) state.charts.donut.destroy();
    CHART_DEFAULTS();
    const top = breakdown.slice(0, 10);
    state.charts.donut = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: top.map(b => b.category),
        datasets: [{
          data: top.map(b => b.amount),
          backgroundColor: PALETTE.slice(0, top.length),
          borderWidth: 2,
          borderColor: "#030305",
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: {
          legend: {
            position: "right",
            labels: { font: { size: 12 }, padding: 14, usePointStyle: true, pointStyleWidth: 10 },
          },
          tooltip: {
            backgroundColor: "hsla(240,6%,10%,0.95)",
            borderColor: "hsla(0,0%,100%,0.1)",
            borderWidth: 1,
            callbacks: {
              label: ctx => ` ${fmtINR(ctx.parsed)} (${breakdown[ctx.dataIndex]?.pct || 0}%)`,
            },
          },
        },
      },
    });
  }

  function setupPaymentChart(paymentDist) {
    const ctx = document.getElementById("paymentChart");
    if (!ctx || !paymentDist?.length) return;
    if (state.charts.payment) state.charts.payment.destroy();
    CHART_DEFAULTS();
    state.charts.payment = new Chart(ctx, {
      type: "bar",
      data: {
        labels: paymentDist.map(p => p.method),
        datasets: [{
          label: "Transactions",
          data: paymentDist.map(p => p.count),
          backgroundColor: PALETTE.map(c => c + "cc"),
          borderColor: PALETTE,
          borderWidth: 1,
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "hsla(240,6%,10%,0.95)",
            borderColor: "hsla(0,0%,100%,0.1)",
            borderWidth: 1,
            callbacks: { label: ctx => ` ${ctx.parsed.x} transactions (${paymentDist[ctx.dataIndex]?.pct || 0}%)` },
          },
        },
        scales: {
          x: { grid: { color: "hsla(0,0%,100%,0.04)" }, ticks: { font: { size: 11 } } },
          y: { grid: { display: false }, ticks: { font: { size: 11 } } },
        },
      },
    });
  }

  function renderTopMerchants(merchants) {
    const el = document.getElementById("topMerchantsList");
    if (!el || !merchants?.length) return;
    const max = merchants[0]?.amount || 1;
    el.innerHTML = merchants.slice(0, 8).map(m => `
      <div class="merchant-row">
        <span class="merchant-name">${m.merchant}</span>
        <div class="merchant-bar-wrap"><div class="merchant-bar" style="width:${Math.round(m.amount / max * 100)}%"></div></div>
        <span class="merchant-amt">${fmtINR(m.amount)}</span>
      </div>`).join("");
  }

  // ── INSIGHTS RENDERERS ───────────────────────────────────────────────────────
  function renderLeaks(leaks) {
    const el = document.getElementById("leaksList");
    if (!leaks.length) { el.innerHTML = `<p class="text-muted" style="font-size:14px">✅ No significant leaks detected.</p>`; return; }
    const icons = { high: "🔴", medium: "🟡", low: "⚪" };
    el.innerHTML = leaks.map(l => `
      <div class="leak-card ${l.severity}">
        <span class="leak-severity">${icons[l.severity] || "🟡"}</span>
        <div class="leak-body">
          <div class="leak-title">${l.title}</div>
          <div class="leak-detail">${l.detail}</div>
          ${l.estimated_monthly_impact_inr ? `<div class="leak-impact">Impact: ${fmtINR(l.estimated_monthly_impact_inr)}</div>` : ""}
        </div>
      </div>`).join("");
  }

  function renderSuggestions(suggestions) {
    const el = document.getElementById("suggestionsList");
    const all = [
      ...(suggestions.quick_wins || []),
      ...(suggestions.monthly_optimization || []),
      ...(suggestions.long_term || []),
    ];
    if (!all.length) { el.innerHTML = `<p class="text-muted" style="font-size:14px">Upload a statement to see personalized suggestions.</p>`; return; }
    el.innerHTML = all.map(s => `
      <div class="suggestion-card">
        <div class="leak-body">
          <div class="suggestion-bucket">${s.bucket || ""}</div>
          <div class="suggestion-title">${s.title}</div>
          <div class="suggestion-detail">${s.detail}</div>
          ${s.impact_inr_month_estimate ? `<div class="suggestion-impact">Save ~${fmtINR(s.impact_inr_month_estimate)}/mo</div>` : ""}
        </div>
      </div>`).join("");
  }

  function renderRecurring(recurring) {
    const el = document.getElementById("recurringList");
    if (!recurring.length) { el.innerHTML = `<p class="text-muted" style="font-size:14px">No recurring patterns detected.</p>`; return; }
    el.innerHTML = recurring.slice(0, 10).map(r => {
      const typeColor = r.is_investment ? "var(--green)" : r.is_subscription ? "var(--purple)" : "var(--accent)";
      const typeLabel = r.is_investment ? "Investment" : r.is_subscription ? "Subscription" : "Recurring";
      return `
      <div class="recurring-card">
        <div class="leak-body">
          <div class="recurring-merchant">${r.merchant}</div>
          <div class="recurring-meta">~${fmtINR(r.avg_amount)} · ${r.occurrences}× over ${r.months_spanned} month${r.months_spanned > 1 ? "s" : ""}</div>
          <span class="recurring-badge" style="background:${typeColor}22;color:${typeColor}">${typeLabel}</span>
        </div>
      </div>`;
    }).join("");
  }

  function renderBehavioral(beh, stressInd, k) {
    const el = document.getElementById("behavioralPanel");
    if (!Object.keys(beh).length && !Object.keys(stressInd).length) {
      el.innerHTML = `<p class="text-muted" style="font-size:14px">Behavioral data extracted from PDF only.</p>`;
      return;
    }
    const items = [
      { label: "Post-Payday Splurge", val: beh.post_payday_splurge ? "⚠️ Detected" : "✅ Not detected", color: beh.post_payday_splurge ? "var(--yellow)" : "var(--green)" },
      { label: "Cash Reliance", val: `${beh.cash_reliance_pct ?? k?.cash_reliance_pct ?? 0}%`, color: (beh.cash_reliance_pct ?? 0) > 20 ? "var(--yellow)" : "var(--green)" },
      { label: "Stress Events", val: stressInd.overdraft_events != null ? `${(stressInd.overdraft_events || 0) + (stressInd.bounced_transactions || 0) + (stressInd.late_payment_fees || 0)} events` : "0 events", color: stressInd.overdraft_events ? "var(--red)" : "var(--green)" },
      { label: "Income Stability", val: beh.spending_pattern ? beh.spending_pattern.slice(0, 50) + (beh.spending_pattern.length > 50 ? "…" : "") : "—" },
    ];

    const topVendors = beh.top_vendors?.length
      ? `<div class="beh-item" style="grid-column:1/-1"><div class="beh-label">Top Vendors</div><div class="beh-val" style="font-size:13px;font-weight:500;white-space:normal">${beh.top_vendors.slice(0, 5).join(" · ")}</div></div>`
      : "";

    el.innerHTML = `<div class="behavioral-grid">
      ${items.map(i => `<div class="beh-item"><div class="beh-label">${i.label}</div><div class="beh-val" style="color:${i.color || "var(--fg)"}">${i.val}</div></div>`).join("")}
      ${topVendors}
    </div>`;

    if (stressInd.notes) {
      el.innerHTML += `<div style="margin-top:10px;padding:10px 12px;background:hsla(0,72%,55%,0.08);border-radius:var(--radius);font-size:13px;color:var(--fg-muted)">${stressInd.notes}</div>`;
    }
  }

  // ── TRANSACTION TABLE ────────────────────────────────────────────────────────
  function buildCategoryFilter(txs) {
    const cats = [...new Set(txs.map(t => t.category).filter(Boolean))].sort();
    const sel = document.getElementById("txFilterCat");
    if (!sel) return;
    sel.innerHTML = `<option value="">All Categories</option>` + cats.map(c => `<option value="${c}">${c}</option>`).join("");
  }

  function bindTxFilters() {
    ["txFilterFlow", "txFilterCat", "txSearch"].forEach(id => {
      document.getElementById(id)?.addEventListener("input", applyTxFilters);
    });
  }

  function applyTxFilters() {
    const flow = document.getElementById("txFilterFlow")?.value || "";
    const cat = document.getElementById("txFilterCat")?.value || "";
    const q = (document.getElementById("txSearch")?.value || "").toLowerCase();
    state.txFiltered = state.txAll.filter(t => {
      if (flow && t.flow !== flow) return false;
      if (cat && t.category !== cat) return false;
      if (q && !(`${t.merchant} ${t.description} ${t.category}`).toLowerCase().includes(q)) return false;
      return true;
    });
    state.txPage = 1;
    renderTxTable();
  }

  function renderTxTable() {
    const body = document.getElementById("txTableBody");
    if (!body) return;
    const ps = CONFIG.TX_PAGE_SIZE;
    const total = state.txFiltered.length;
    const start = (state.txPage - 1) * ps;
    const page = state.txFiltered.slice(start, start + ps);

    if (!page.length) {
      body.innerHTML = `<tr><td colspan="6" class="text-muted" style="text-align:center;padding:32px">No transactions match your filters.</td></tr>`;
      document.getElementById("txPagination").innerHTML = "";
      return;
    }

    body.innerHTML = page.map(t => {
      const flags = [
        t.is_emi ? `<span class="tx-flag" title="EMI">🏦</span>` : "",
        t.is_investment ? `<span class="tx-flag" title="Investment">📈</span>` : "",
        t.is_insurance ? `<span class="tx-flag" title="Insurance">🛡️</span>` : "",
        t.is_recurring ? `<span class="tx-flag" title="Recurring">🔁</span>` : "",
        t.stress_flag ? `<span class="tx-flag" title="Stress">⚠️</span>` : "",
      ].join("");
      return `<tr>
        <td style="color:var(--fg-muted);font-size:12px">${t.date}</td>
        <td><div class="tx-merchant" title="${t.merchant_raw || t.merchant}">${t.merchant}</div></td>
        <td><span class="tx-cat-badge">${t.category}</span></td>
        <td style="color:var(--fg-muted);font-size:12px">${t.payment_method}</td>
        <td class="${t.flow === "credit" ? "tx-amount-credit" : "tx-amount-debit"}">${t.flow === "credit" ? "+" : "-"}${fmtINR(t.amount)}</td>
        <td>${flags || "—"}</td>
      </tr>`;
    }).join("");

    // Pagination
    const totalPages = Math.ceil(total / ps);
    const pag = document.getElementById("txPagination");
    if (totalPages <= 1) { pag.innerHTML = ""; return; }
    let btns = "";
    for (let p = 1; p <= Math.min(totalPages, 7); p++) {
      btns += `<button class="page-btn ${p === state.txPage ? "active" : ""}" data-page="${p}">${p}</button>`;
    }
    if (totalPages > 7) btns += `<span style="color:var(--fg-muted);font-size:13px">…${totalPages} pages</span>`;
    pag.innerHTML = btns;
    pag.querySelectorAll(".page-btn").forEach(btn => {
      btn.addEventListener("click", () => { state.txPage = parseInt(btn.dataset.page); renderTxTable(); window.scrollTo({ top: document.getElementById("txTable").offsetTop - 80, behavior: "smooth" }); });
    });
  }

  // ── BOOT ─────────────────────────────────────────────────────────────────────
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

    document.getElementById("saveKeyBtn")?.addEventListener("click", saveApiKey);
    document.getElementById("clearKeyBtn")?.addEventListener("click", clearApiKey);

    initUploadUI();
    handleRoute();
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
