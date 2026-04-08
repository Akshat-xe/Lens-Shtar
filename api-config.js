/**
 * Lens Shtar — API Configuration
 * ================================
 * Resolves the backend API base URL at runtime using this priority chain:
 *
 *   1. ?api_base=<url>  query param  (one-shot override, stores to localStorage)
 *   2. localStorage["ls_api_base"]   (persisted override, e.g. your tunnel URL)
 *   3. Default fallback              (hardcoded localhost for local dev)
 *
 * IMPORTANT:
 *   - Only the backend URL may be stored in localStorage.
 *   - The Gemini API key is NEVER stored in localStorage — it lives in backend session memory only.
 *
 * HOW TO USE DURING A DEMO:
 *   Option A (query param — one-shot that persists):
 *     https://lens-flow.shtar.space/?api_base=https://abc123.trycloudflare.com
 *
 *   Option B (browser console — lasting until cleared):
 *     localStorage.setItem("ls_api_base", "https://abc123.trycloudflare.com");
 *     location.reload();
 *
 *   Option C (clear override, revert to local dev):
 *     localStorage.removeItem("ls_api_base");
 *     location.reload();
 */

(function () {
  const STORAGE_KEY = "ls_api_base";
  const DEFAULT_API_BASE = "http://localhost:8000"; // local dev / demo fallback

  function resolveApiBase() {
    // 1. Check query param ?api_base=...
    try {
      const params = new URLSearchParams(window.location.search);
      const qp = params.get("api_base");
      if (qp && qp.startsWith("http")) {
        // Persist to localStorage so subsequent page navigations keep the override
        try {
          localStorage.setItem(STORAGE_KEY, qp);
          console.info("[LensConfig] API base set from query param:", qp);
        } catch (_) {}
        return qp;
      }
    } catch (_) {}

    // 2. Check localStorage override
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored && stored.startsWith("http")) {
        console.info("[LensConfig] API base loaded from localStorage:", stored);
        return stored;
      }
    } catch (_) {}

    // 3. Default
    console.info("[LensConfig] Using default API base:", DEFAULT_API_BASE);
    return DEFAULT_API_BASE;
  }

  const apiBase = resolveApiBase();

  // Expose globally — app.js and other scripts read window.LensConfig.apiBase
  window.LensConfig = {
    apiBase,

    /** Call this from the browser console during a demo to switch backends instantly */
    setApiBase(url) {
      if (!url || !url.startsWith("http")) {
        console.error("[LensConfig] Invalid URL. Must start with http.");
        return;
      }
      try {
        localStorage.setItem(STORAGE_KEY, url);
        console.info("[LensConfig] API base updated to:", url, "— reloading…");
        window.location.reload();
      } catch (e) {
        console.error("[LensConfig] Could not save to localStorage:", e);
      }
    },

    /** Clear the stored override and revert to default */
    clearApiBase() {
      try {
        localStorage.removeItem(STORAGE_KEY);
        console.info("[LensConfig] API base override cleared — reloading…");
        window.location.reload();
      } catch (e) {
        console.error("[LensConfig] Could not clear localStorage:", e);
      }
    },
  };
})();
