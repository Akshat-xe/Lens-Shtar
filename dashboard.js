(() => {
  function inr(v) {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
      Number(v || 0)
    );
  }

  function getData() {
    try {
      const raw = localStorage.getItem("lens_last_dashboard");
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  function setKpis(k) {
    const cards = document.querySelectorAll(".metric-card");
    if (cards.length < 4) return;
    cards[0].querySelector(".metric-label").textContent = "Total Income";
    cards[0].querySelector(".metric-val").textContent = inr(k.income);
    cards[1].querySelector(".metric-label").textContent = "Total Expenses";
    cards[1].querySelector(".metric-val").textContent = inr(k.expenses);
    cards[2].querySelector(".metric-label").textContent = "Net Savings";
    cards[2].querySelector(".metric-val").textContent = inr(k.savings);
    cards[3].querySelector(".metric-label").textContent = "UPI Spend";
    cards[3].querySelector(".metric-val").textContent = inr(k.upi_spend);
  }

  function renderLeaks(leaks) {
    const el = document.getElementById("leaksList");
    if (!el) return;
    if (!leaks || !leaks.length) {
      el.innerHTML = `<div class="leak-card"><p class="leak-desc">No clear leaks detected in this statement window.</p></div>`;
      return;
    }
    el.innerHTML = leaks
      .map(
        (l) => `<div class="leak-card">
      <div class="leak-top"><span class="leak-title">${l.title} <span class="severity ${l.severity || "low"}">${l.severity || "low"}</span></span><span class="leak-save">${inr(
          l.estimated_monthly_impact_inr || 0
        )}</span></div>
      <p class="leak-desc">${l.detail || ""}</p></div>`
      )
      .join("");
  }

  function renderSuggestions(s) {
    const el = document.getElementById("savingsList");
    if (!el) return;
    const list = [...(s?.quick_wins || []), ...(s?.monthly_optimization || []), ...(s?.long_term || [])];
    if (!list.length) {
      el.innerHTML = `<div class="save-card"><p class="save-desc">Suggestions will appear after more statement history.</p></div>`;
      return;
    }
    el.innerHTML = list
      .map(
        (x) => `<div class="save-card"><div class="save-top"><div><span class="save-title">${x.title} <span class="save-badge">${x.bucket || "Suggestion"}</span></span><p class="save-desc">${x.detail || ""}</p></div><span class="save-impact">${x.impact_inr_month_estimate ? inr(x.impact_inr_month_estimate) : "—"
          }</span></div></div>`
      )
      .join("");
  }

  function renderTransactions(tx) {
    const el = document.getElementById("txList");
    if (!el) return;
    if (!tx || !tx.length) {
      el.innerHTML = `<div class="tx-row"><div class="tx-info"><div class="tx-merchant">No transactions yet</div></div></div>`;
      return;
    }
    el.innerHTML = tx
      .slice(0, 20)
      .map((t) => {
        const pos = t.flow === "credit";
        return `<div class="tx-row"><div class="tx-avatar">${(t.merchant || "X").charAt(0).toUpperCase()}</div><div class="tx-info"><div class="tx-merchant">${t.merchant || "Unknown"}</div><div class="tx-meta">${t.category || "Other"} · ${t.date || ""}</div></div><span class="tx-amount ${pos ? "positive" : ""
          }">${pos ? "+" : "-"}${inr(t.amount || 0)}</span></div>`;
      })
      .join("");
  }

  function renderAI(summary) {
    if (!summary) return;
    const p = document.querySelector(".ai-panel .insight-card p");
    if (p) p.textContent = summary;
  }

  function hideDemoChartsNotice() {
    const subtitle = document.getElementById("dashboardSubtitle");
    if (subtitle) subtitle.textContent = "Live analysis from your uploaded statement";
  }

  async function bootstrap() {
    if (!window.LensApp || !window.LensApp.session) {
      window.LensConfig.navigate("index.html");
      return;
    }
    const data = getData();
    if (!data) {
      const subtitle = document.getElementById("dashboardSubtitle");
      if (subtitle) subtitle.textContent = "No file analyzed yet. Upload a statement to see live insights.";
      return;
    }
    hideDemoChartsNotice();
    if (data.kpis) setKpis(data.kpis);
    renderLeaks(data.leaks || []);
    renderSuggestions(data.suggestions || {});
    renderTransactions(data.transactions || []);
    renderAI(data.ai_summary);
  }
  bootstrap();
})();

