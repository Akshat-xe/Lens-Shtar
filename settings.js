(() => {
  const accountSummary = document.getElementById("accountSummary");
  const sessionStatus = document.getElementById("sessionStatus");
  const keyStatusText = document.getElementById("keyStatusText");
  const saveKeyBtn = document.getElementById("saveKeyBtn");
  const clearKeyBtn = document.getElementById("clearKeyBtn");
  const keyInput = document.getElementById("geminiKeyInput");

  function setStatus(msg, tone) {
    if (!keyStatusText) return;
    keyStatusText.textContent = msg;
    keyStatusText.style.color = tone === "error" ? "var(--red)" : tone === "ok" ? "var(--green)" : "var(--fg-muted)";
  }

  async function loadStatus() {
    if (!window.LensApp || !window.LensApp.session) {
      window.location.href = "/index.html";
      return;
    }
    const user = window.LensApp.user;
    if (accountSummary) {
      accountSummary.textContent = `${user?.user_metadata?.full_name || "Lens Shtar User"} • ${user?.email || ""}`;
    }
    if (sessionStatus) {
      const expires = window.LensApp.session.expires_at
        ? new Date(window.LensApp.session.expires_at * 1000).toLocaleString()
        : "Unknown";
      sessionStatus.textContent = `Authenticated. Session expiry: ${expires}.`;
    }
    const status = await window.LensApp.refreshStatus();
    if (!status) {
      setStatus("Could not read API key status. Check backend reachability.", "error");
      return;
    }
    if (status.has_api_key) setStatus("Gemini key is active in current session.", "ok");
    else setStatus("No Gemini key configured for this session.", "muted");
  }

  async function saveKey() {
    const value = (keyInput?.value || "").trim();
    if (!value) return setStatus("Please enter your Gemini API key.", "error");
    const token = window.LensApp?.session?.access_token;
    if (!token) return;
    setStatus("Saving key securely in session memory...", "muted");
    try {
      const res = await fetch(`${window.LensApp.apiBase}/api/settings/set-api-key`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ gemini_api_key: value }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Unable to save API key.");
      keyInput.value = "";
      await loadStatus();
      setStatus("Gemini key saved in active session.", "ok");
    } catch (e) {
      setStatus(e.message || "Save failed", "error");
    }
  }

  async function clearKey() {
    const token = window.LensApp?.session?.access_token;
    if (!token) return;
    setStatus("Clearing key from session...", "muted");
    try {
      const res = await fetch(`${window.LensApp.apiBase}/api/settings/clear-api-key`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Unable to clear key.");
      await loadStatus();
      setStatus("Gemini key removed from current session.", "ok");
    } catch (e) {
      setStatus(e.message || "Clear failed", "error");
    }
  }

  if (saveKeyBtn) saveKeyBtn.addEventListener("click", saveKey);
  if (clearKeyBtn) clearKeyBtn.addEventListener("click", clearKey);
  loadStatus();
})();

