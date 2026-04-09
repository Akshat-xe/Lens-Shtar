/**
 * Lens Shtar — API Configuration
 * ================================
 * Configured for Local Laptop Demo Architecture.
 * 
 * Frontend is hosted on public domain (https://lens-flow.shtar.space).
 * Backend ALWAYS points to local python server (http://localhost:8000).
 */

(function () {
  const STORAGE_KEY = "ls_api_base";
  const DEFAULT_API_BASE = "http://localhost:8000";

  function resolveApiBase() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored && stored.startsWith("http")) return stored;
    } catch (_) { }
    return DEFAULT_API_BASE;
  }

  const apiBase = resolveApiBase();

  window.LensConfig = {
    apiBase,

    /** Call this from console to test another local port */
    setApiBase(url) {
      if (!url || !url.startsWith("http")) {
        console.error("Invalid URL.");
        return;
      }
      try {
        localStorage.setItem(STORAGE_KEY, url);
        window.location.reload();
      } catch (e) { }
    },

    clearApiBase() {
      try {
        localStorage.removeItem(STORAGE_KEY);
        window.location.reload();
      } catch (e) { }
    },

    /** Programmatic navigation helper */
    navigate(path, replace = false) {
      if (replace) {
        window.location.replace(path);
      } else {
        window.location.href = path;
      }
    }
  };

})();
