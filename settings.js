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
      window.LensConfig.navigate("index.html");
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
    
    try {
      console.log('Loading status from:', `${window.LensApp.apiBase}/api/settings/status`);
      const status = await window.LensApp.refreshStatus();
      console.log('Status response:', status);
      
      if (!status) {
        setStatus("Could not read API key status. Check backend reachability.", "error");
        return;
      }
      
      if (status.has_api_key) {
        setStatus("Gemini key is active in current session.", "ok");
      } else {
        setStatus("No Gemini key configured for this session.", "muted");
      }
    } catch (e) {
      console.error('Load status error:', e);
      if (e.name === 'TypeError' && e.message.includes('fetch')) {
        setStatus("Network error: Cannot reach backend. Check CORS configuration.", "error");
      } else if (e.message && e.message.includes('CORS')) {
        setStatus("CORS error: Backend not configured for this origin.", "error");
      } else {
        setStatus(`Backend error: ${e.message || 'Unknown error'}`, "error");
      }
    }
  }

  async function saveKey() {
    const value = (keyInput?.value || "").trim();
    if (!value) return setStatus("Please enter your Gemini API key.", "error");
    const token = window.LensApp?.session?.access_token;
    if (!token) return setStatus("Not authenticated. Please sign in first.", "error");
    
    setStatus("Saving key securely in session memory...", "muted");
    
    try {
      const apiBase = window.LensApp.apiBase;
      console.log('Saving API key to:', `${apiBase}/api/settings/set-api-key`);
      
      const res = await fetch(`${apiBase}/api/settings/set-api-key`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ gemini_api_key: value }),
      });
      
      console.log('Save response status:', res.status);
      
      if (!res.ok) {
        const body = await res.json();
        console.error('Save error response:', body);
        throw new Error(body.detail || `Server returned ${res.status}: ${res.statusText}`);
      }
      
      const body = await res.json();
      console.log('Save success:', body);
      
      keyInput.value = "";
      await loadStatus();
      setStatus("Gemini key saved in active session.", "ok");
    } catch (e) {
      console.error('Save key error:', e);
      if (e.name === 'TypeError' && e.message.includes('fetch')) {
        setStatus("Network error: Cannot reach backend. Check CORS configuration.", "error");
      } else if (e.message && e.message.includes('CORS')) {
        setStatus("CORS error: Backend not configured for this origin.", "error");
      } else {
        setStatus(e.message || "Save failed", "error");
      }
    }
  }

  async function clearKey() {
    const token = window.LensApp?.session?.access_token;
    if (!token) return setStatus("Not authenticated. Please sign in first.", "error");
    
    setStatus("Clearing key from session...", "muted");
    
    try {
      const apiBase = window.LensApp.apiBase;
      console.log('Clearing API key from:', `${apiBase}/api/settings/clear-api-key`);
      
      const res = await fetch(`${apiBase}/api/settings/clear-api-key`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      
      console.log('Clear response status:', res.status);
      
      if (!res.ok) {
        const body = await res.json();
        console.error('Clear error response:', body);
        throw new Error(body.detail || `Server returned ${res.status}: ${res.statusText}`);
      }
      
      const body = await res.json();
      console.log('Clear success:', body);
      
      await loadStatus();
      setStatus("Gemini key removed from current session.", "ok");
    } catch (e) {
      console.error('Clear key error:', e);
      if (e.name === 'TypeError' && e.message.includes('fetch')) {
        setStatus("Network error: Cannot reach backend. Check CORS configuration.", "error");
      } else if (e.message && e.message.includes('CORS')) {
        setStatus("CORS error: Backend not configured for this origin.", "error");
      } else {
        setStatus(e.message || "Clear failed", "error");
      }
    }
  }

  if (saveKeyBtn) saveKeyBtn.addEventListener("click", saveKey);
  if (clearKeyBtn) clearKeyBtn.addEventListener("click", clearKey);
  loadStatus();
})();

