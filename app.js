(() => {
  const SUPABASE_URL = "https://tgmvethwaquialwxenld.supabase.co";
  const SUPABASE_ANON_KEY = "sb_publishable_QVxcf5DEQufi3bdpxlNtYg_aT9kI4o3";
  // API base resolved at runtime by api-config.js (loaded before this script)
  // Priority: ?api_base= query param → localStorage override → localhost default
  const CALLBACK_URL = "https://lens-flow.shtar.space/callback.html";

  const supabase = window.supabase ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;
  const SESSION_KEY = "ls_supabase_session";

  const state = {
    session: null,
    user: null,
    settingsStatus: null,
  };

  function initials(name, email) {
    const src = (name || email || "LS").trim();
    const parts = src.split(/\s+/).filter(Boolean);
    if (parts.length > 1) return (parts[0][0] + parts[1][0]).toUpperCase();
    return src.slice(0, 2).toUpperCase();
  }

  function getStoredSession() {
    try {
      const raw = localStorage.getItem(SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function setStoredSession(session) {
    if (!session) {
      localStorage.removeItem(SESSION_KEY);
      return;
    }
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }

  async function refreshSettingsStatus() {
    if (!state.session) {
      console.log('No session, skipping settings status refresh');
      return null;
    }
    try {
      console.log('Fetching settings status from:', `${window.LensConfig.apiBase}/api/settings/status`);
      const res = await fetch(`${window.LensConfig.apiBase}/api/settings/status`, {
        headers: { Authorization: `Bearer ${state.session.access_token}` },
      });
      if (!res.ok) {
        console.error('Settings status fetch failed:', res.status, res.statusText);
        return null;
      }
      state.settingsStatus = await res.json();
      console.log('Settings status:', state.settingsStatus);
      return state.settingsStatus;
    } catch (err) {
      console.error('Settings status fetch error:', err);
      return null;
    }
  }

  function accountMenuHtml() {
    const user = state.user || {};
    const hasApi = state.settingsStatus && state.settingsStatus.has_api_key;
    return `
      <button id="accountMenuBtn" class="btn btn-outline" type="button">
        <span style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:999px;background:var(--surface);font-size:11px;font-weight:700">${initials(user.user_metadata?.full_name, user.email)}</span>
        Account
      </button>
      <div id="accountDropdown" class="card" style="display:none;position:absolute;top:52px;right:0;width:min(320px,92vw);z-index:120">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:12px">
          <div style="width:34px;height:34px;border-radius:999px;background:var(--surface);display:flex;align-items:center;justify-content:center;font-weight:700">${initials(user.user_metadata?.full_name, user.email)}</div>
          <div style="min-width:0">
            <div style="font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${user.user_metadata?.full_name || "Lens Shtar User"}</div>
            <div style="font-size:12px;color:var(--fg-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${user.email || ""}</div>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px;font-size:13px">
          <a href="dashboard.html" class="btn btn-outline" style="justify-content:flex-start">Dashboard</a>
          <a href="settings.html" class="btn btn-outline" style="justify-content:flex-start">Settings</a>
          <button type="button" class="btn btn-outline" style="justify-content:flex-start;pointer-events:none;opacity:.9">
            API Key: ${hasApi ? "Active in session" : "Not configured"}
          </button>
          <button type="button" class="btn btn-outline" style="justify-content:flex-start;pointer-events:none;opacity:.9">Uploads: History coming soon</button>
          <button id="signOutBtn" type="button" class="btn btn-primary" style="justify-content:center">Sign out</button>
        </div>
      </div>
    `;
  }

  function loginButtonHtml() {
    return `<button id="googleSignInBtn" class="btn btn-outline" type="button">Sign in with Google</button>`;
  }

  async function signIn() {
    if (!supabase) return;
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: CALLBACK_URL },
    });
    if (error) alert("Google sign-in could not start. Please try again.");
  }

  async function signOut() {
    if (supabase) await supabase.auth.signOut();
    setStoredSession(null);
    state.session = null;
    state.user = null;
    state.settingsStatus = null;
    if (window.location.pathname.includes("dashboard") || window.location.pathname.includes("settings")) {
      window.LensConfig.navigate("index.html");
    } else {
      renderAuthSlot();
    }
  }

  function wireAccountMenu() {
    const btn = document.getElementById("accountMenuBtn");
    const dd = document.getElementById("accountDropdown");
    const out = document.getElementById("signOutBtn");
    if (!btn || !dd) return;
    
    // Toggle dropdown
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = dd.style.display !== "none";
      dd.style.display = isOpen ? "none" : "block";
      
      // Close on escape key
      if (!isOpen) {
        const closeOnEscape = (e) => {
          if (e.key === "Escape") {
            dd.style.display = "none";
            document.removeEventListener("keydown", closeOnEscape);
          }
        };
        document.addEventListener("keydown", closeOnEscape);
      }
    });
    
    // Close on outside click
    document.addEventListener("click", (e) => {
      if (!dd.contains(e.target) && e.target !== btn) {
        dd.style.display = "none";
      }
    });
    
    // Sign out handler
    if (out) out.addEventListener("click", (e) => {
      e.stopPropagation();
      dd.style.display = "none";
      signOut();
    });
  }

  function renderAuthSlot() {
    const slot = document.getElementById("authActionSlot");
    if (!slot) return;
    slot.style.position = "relative";
    slot.innerHTML = state.session ? accountMenuHtml() : loginButtonHtml();
    const signInBtn = document.getElementById("googleSignInBtn");
    if (signInBtn) signInBtn.addEventListener("click", signIn);
    wireAccountMenu();
  }

  async function bootstrapSession() {
    // Initialize auth state with comprehensive error handling
    if (supabase) {
      try {
        // Get current session
        const { data, error } = await supabase.auth.getSession();
        
        if (!error && data && data.session) {
          // Validate session is not expired
          if (data.session.expires_at && data.session.expires_at * 1000 > Date.now()) {
            state.session = data.session;
            state.user = data.session.user;
            setStoredSession(data.session);
            console.log('Valid session restored:', data.session.user?.email);
          } else {
            console.log('Session expired, clearing stored session');
            setStoredSession(null);
            state.session = null;
            state.user = null;
          }
        } else {
          // Try fallback from localStorage
          const fallback = getStoredSession();
          if (fallback && fallback.access_token) {
            // Validate fallback session
            if (fallback.expires_at && fallback.expires_at * 1000 > Date.now()) {
              state.session = fallback;
              state.user = fallback.user || null;
              console.log('Valid fallback session restored');
            } else {
              console.log('Fallback session expired, clearing');
              setStoredSession(null);
              state.session = null;
              state.user = null;
            }
          }
        }
        
        // Listen for auth changes across tabs
        supabase.auth.onAuthStateChange(async (_evt, session) => {
          console.log('Auth state changed:', _evt, session?.user?.email);
          state.session = session;
          state.user = session ? session.user : null;
          setStoredSession(session);
          await refreshSettingsStatus();
          renderAuthSlot();
          
          // Update other tabs via localStorage event
          if (session) {
            localStorage.setItem('ls_auth_updated', Date.now().toString());
          } else {
            localStorage.removeItem('ls_auth_updated');
          }
        });
      } catch (err) {
        console.error('Auth initialization error:', err);
        const fallback = getStoredSession();
        if (fallback && fallback.expires_at && fallback.expires_at * 1000 > Date.now()) {
          state.session = fallback;
          state.user = fallback?.user || null;
        } else {
          state.session = null;
          state.user = null;
        }
      }
    } else {
      console.warn('Supabase client not available');
      const fallback = getStoredSession();
      if (fallback && fallback.expires_at && fallback.expires_at * 1000 > Date.now()) {
        state.session = fallback;
        state.user = fallback?.user || null;
      } else {
        state.session = null;
        state.user = null;
      }
    }
    
    // Listen for auth updates from other tabs
    window.addEventListener('storage', (e) => {
      if (e.key === 'ls_auth_updated') {
        console.log('Auth updated from another tab');
        bootstrapSession();
      }
    });
    
    // Refresh settings status and render UI
    await refreshSettingsStatus();
    renderAuthSlot();
  }

  function setupNavbarScroll() {
    const navbar = document.getElementById("navbar");
    if (!navbar) return;
    let prevY = window.scrollY;
    window.addEventListener("scroll", () => {
      const y = window.scrollY;
      if (y > prevY && y > 100) navbar.style.transform = "translateY(-110%)";
      else navbar.style.transform = "translateY(0)";
      prevY = y;
    });
  }

  window.LensApp = {
    get apiBase() { return (window.LensConfig && window.LensConfig.apiBase) || "http://localhost:8000"; },
    get session() { return state.session; },
    get user() { return state.user; },
    async refreshStatus() { return refreshSettingsStatus(); },
    async requireAuth() {
      if (!state.session) {
        await signIn();
        throw new Error("NOT_AUTHENTICATED");
      }
      return state.session;
    },
    async requireApiKey() {
      await refreshSettingsStatus();
      if (!state.settingsStatus || !state.settingsStatus.has_api_key) {
        window.LensConfig.navigate("settings.html?reason=api_key_required");
        throw new Error("API_KEY_REQUIRED");
      }
      return true;
    },
    signOut,
  };

  setupNavbarScroll();
  bootstrapSession();
})();

