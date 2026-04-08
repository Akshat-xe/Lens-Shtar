# Lens Shtar — Local Demo Setup Guide

> **Architecture:** Frontend on GitHub Pages → Your Laptop Backend → Cloudflare Tunnel → Public Internet

---

## Quick Start (30 seconds after setup)

```bash
cd "lens shtar_"
bash start_all.sh
```

Then open the URL printed in the terminal.

---

## One-Time Setup

### Step 1 — Get your Supabase JWT Secret

1. Go to [https://supabase.com](https://supabase.com) and open your project
2. Navigate to: **Project Settings → JWT Settings**
3. Copy the **JWT Secret** value

### Step 2 — Configure the backend

```bash
cd backend
cp .env.local.example .env
```

Open `.env` and set:
```
SUPABASE_JWT_SECRET=your-copied-secret-here
```

Everything else is already pre-filled for your project.

### Step 3 — Install cloudflared (Cloudflare Tunnel)

**Ubuntu/Debian (recommended):**
```bash
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
cloudflared --version
```

**Verify:**
```bash
cloudflared --version
# Should print: cloudflared version X.X.X
```

No account, no login, no config needed. Cloudflare Quick Tunnels are free.

### Step 4 — Make scripts executable (one-time)

```bash
chmod +x start_all.sh start_backend.sh start_tunnel.sh
```

---

## Starting the Demo

### Option A — Full (backend + tunnel, recommended)

```bash
bash start_all.sh
```

This will:
1. Validate your `.env`
2. Start the FastAPI backend on port 8000
3. Wait for it to be healthy
4. Start a Cloudflare Quick Tunnel
5. Print the public tunnel URL
6. Show you the exact URL to open

**Output looks like:**
```
╔══════════════════════════════════════════════════════╗
║              ✅ DEMO SERVER READY                    ║
╚══════════════════════════════════════════════════════╝

  Local backend:  http://localhost:8000
  Health check:   http://localhost:8000/api/health

  Public tunnel:  https://random-words.trycloudflare.com

  ▶  OPEN THIS URL in your browser to use the live demo:
    https://lens-flow.shtar.space/?api_base=https://random-words.trycloudflare.com
```

Open that URL. Done. The app uses your laptop as the backend.

### Option B — Backend only (no tunnel, local testing only)

```bash
bash start_all.sh --no-tunnel
# OR
bash start_backend.sh
```

Frontend at `http://localhost:8080` will work (open `index.html` with Live Server or similar).

### Option C — Custom port

```bash
bash start_all.sh --port 9000
```

---

## Stopping the Demo

Press **Ctrl+C** in the terminal where `start_all.sh` is running.

This stops the backend AND the tunnel simultaneously and cleans up all processes.

---

## How the Frontend Picks the Backend URL

`api-config.js` runs on every page load and resolves the API base using this priority order:

| Priority | Method | Example |
|----------|--------|---------|
| 1st | `?api_base=` query param | `https://lens-flow.shtar.space/?api_base=https://abc.trycloudflare.com` |
| 2nd | `localStorage["ls_api_base"]` | Persists across page loads |
| 3rd | Default fallback | `http://localhost:8000` |

The query param method **persists** — it saves to localStorage so you don't need to keep appending it.

### Switching tunnel URLs mid-demo

If your tunnel URL changes, open the browser console on any page and run:

```javascript
LensConfig.setApiBase("https://new-tunnel.trycloudflare.com")
// Saves to localStorage and reloads the page
```

### Clearing the override

```javascript
LensConfig.clearApiBase()
// Reverts to localhost:8000 default
```

---

## CORS Notes

The backend is pre-configured to allow:
- `https://lens-flow.shtar.space` (your live frontend)
- `http://localhost:3000`, `http://localhost:5173`, `http://localhost:8080` (local dev)

When `start_all.sh` detects the tunnel URL, it automatically writes `TUNNEL_ORIGINS=https://your-tunnel.trycloudflare.com` to `backend/.env`.

> **Important:** After the tunnel URL is written, **restart the backend** for CORS to pick it up.
> 
> Shortcut: Use the CORS escape hatch during demos if you don't want to restart:
> ```
> # In backend/.env
> CORS_ALLOW_ALL=true
> ```
> This disables origin checking entirely. Fine for interviews. Not for production.

---

## Supabase Auth Notes

- **Google Sign-In** redirects to: `https://lens-flow.shtar.space/callback.html`
- The `callback.html` exchanges the OAuth code for a session and stores it in `localStorage`
- This works correctly from GitHub Pages with no changes needed

**If auth isn't working**, check:
1. Supabase → Authentication → URL Configuration → Site URL = `https://lens-flow.shtar.space`
2. Redirect URLs must include: `https://lens-flow.shtar.space/callback.html`

---

## Architecture Diagram

```
Browser (anywhere)
        │
        ▼
https://lens-flow.shtar.space   ← GitHub Pages (static, always up)
        │
        │  API calls go to tunnel URL
        ▼
https://xxxx.trycloudflare.com  ← Cloudflare Quick Tunnel (free, no account)
        │
        ▼
localhost:8000                  ← Your laptop running FastAPI
        │
        ├── /api/health
        ├── /api/settings/set-api-key
        ├── /api/settings/status
        ├── /api/settings/clear-api-key
        ├── /api/upload
        └── /api/dashboard/{file_id}
```

---

## Troubleshooting

### "Backend unreachable" on the frontend

1. Is `start_all.sh` still running? Check terminal.
2. Did you open the correct URL with `?api_base=...`?
3. Run `LensConfig.apiBase` in browser console to see what URL is being used.

### CORS error in browser console

1. Check that `TUNNEL_ORIGINS` is set in `backend/.env` with your current tunnel URL.
2. Restart the backend after updating `.env`.
3. Or temporarily set `CORS_ALLOW_ALL=true` in `.env` and restart.

### Tunnel URL keeps changing

Cloudflare Quick Tunnels assign a random URL each time. This is expected.
Each time you run `start_all.sh`, a new URL is generated.
Just open the printed URL — it auto-configures the frontend via `?api_base=`.

### JWT error / 401 on API calls

- Your `SUPABASE_JWT_SECRET` in `.env` may be wrong.
- Get it from: Supabase → Project Settings → JWT Settings → JWT Secret.

### Backend crashes on startup

Check `backend/.env` exists and has all required values:
```bash
cat backend/.env | grep -E 'SUPABASE_(URL|JWT)'
```

---

## Demo Checklist (Before Interview)

- [ ] `bash start_all.sh` starts without errors
- [ ] Backend health check passes: `curl http://localhost:8000/api/health`
- [ ] Tunnel URL is printed and accessible from phone/another device
- [ ] `https://lens-flow.shtar.space/?api_base=TUNNEL_URL` loads the app
- [ ] Google Sign-In works and redirects to dashboard
- [ ] Settings page shows "No Gemini key configured"
- [ ] Paste Gemini key, click Save — shows "Gemini key is active"
- [ ] Upload a small PDF or CSV bank statement
- [ ] Dashboard loads with real transaction data
- [ ] Money Leaks section shows detected issues

---

## Software You Need Installed

| Tool | Version | Install |
|------|---------|---------|
| Python | ≥ 3.10 | `sudo apt install python3 python3-venv` |
| cloudflared | latest | See Step 3 above |
| curl | any | `sudo apt install curl` |

Everything else (pip, FastAPI, uvicorn, etc.) is auto-installed by `start_all.sh`.

---

## Known Limitations of This Architecture

1. **No backend persistence** — if you restart your laptop mid-demo, the session (including Gemini key) is lost. User must re-enter their key.
2. **Tunnel URL changes** — every `start_all.sh` gives a different URL. You can't bookmark it.
3. **Latency** — requests travel: Browser → Cloudflare → Your laptop. Expect ~50–200ms extra.
4. **No uptime guarantee** — if your laptop sleeps or loses WiFi, the app stops.
5. **Single user** — the backend is single-process. Fine for demos but not for concurrent real users.
6. **Gemini key is session-scoped** — each restart requires re-entering the key (by design, for security).

All of these are acceptable for interview/demo/prototype purposes.
