/**
 * Lens Shtar — API Configuration
 * ================================
 * Single Source of Truth for backend API base resolution.
 *
 * Priority: 
 *   1. ?api_base=<url> query param
 *   2. sessionStorage override
 *   3. localStorage override (legacy fallback)
 *   4. Default fallback (http://localhost:8000)
 */

(function () {
  const STORAGE_KEY = "ls_api_base";
  const DEFAULT_API_BASE = "http://localhost:8000";

  function resolveApiBase() {
    // 1. Query param
    try {
      const params = new URLSearchParams(window.location.search);
      const qp = params.get("api_base");
      if (qp && qp.startsWith("http")) {
        try { sessionStorage.setItem(STORAGE_KEY, qp); } catch (_) {}
        return qp;
      }
    } catch (_) {}

    // 2. Session Storage
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored && stored.startsWith("http")) return stored;
    } catch (_) {}

    // 3. Local Storage (fallback if set previously)
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored && stored.startsWith("http")) {
        // Migrate to session storage
        try { sessionStorage.setItem(STORAGE_KEY, stored); } catch (_) {}
        return stored;
      }
    } catch (_) {}

    return DEFAULT_API_BASE;
  }

  const apiBase = resolveApiBase();

  window.LensConfig = {
    apiBase,

    /** Call this from the browser console during a demo to switch backends instantly */
    setApiBase(url) {
      if (!url || !url.startsWith("http")) {
        console.error("Invalid URL. Must start with http.");
        return;
      }
      try {
        sessionStorage.setItem(STORAGE_KEY, url);
        window.location.reload();
      } catch (e) {
        console.error("Could not save to storage:", e);
      }
    },

    clearApiBase() {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem(STORAGE_KEY);
        window.location.reload();
      } catch (e) {}
    },

    /** 
     * Appends the current api_base to a given path so it never gets lost 
     * during navigation.
     */
    navUrl(path) {
      if (!this.apiBase || this.apiBase === DEFAULT_API_BASE) return path;
      try {
        // Handle absolute URLs to same origin or root paths
        const base = window.location.origin + window.location.pathname;
        const url = new URL(path, base);
        url.searchParams.set("api_base", this.apiBase);
        // Exclude the origin to retain relative routing flexibility
        return url.pathname + url.search + url.hash;
      } catch (e) {
        const separator = path.includes('?') ? '&' : '?';
        return path + separator + "api_base=" + encodeURIComponent(this.apiBase);
      }
    },

    /** Programmatic navigation helper */
    navigate(path, replace = false) {
      const target = this.navUrl(path);
      if (replace) {
        window.location.replace(target);
      } else {
        window.location.href = target;
      }
    }
  };

  // ============================================
  // AUTO INTERCEPTOR
  // ============================================
  // Automatically attaches api_base to all internal links
  window.addEventListener('DOMContentLoaded', () => {
    if (window.LensConfig.apiBase === DEFAULT_API_BASE) return;
    
    document.body.addEventListener('click', (e) => {
      // Find closest anchor tag
      const a = e.target.closest('a');
      if (!a) return;

      const href = a.getAttribute('href');
      // Skip external links, pure anchors, and mailto
      if (!href || href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('javascript:')) {
        return;
      }
      
      // If it's a pure hash link on the same page, let normal behavior happen
      if (href.startsWith('#')) return;

      e.preventDefault();
      window.LensConfig.navigate(href);
    });
  });

})();
