#!/usr/bin/env bash
# =============================================================
# Lens Shtar — ONE-COMMAND DEMO STARTER
# =============================================================
# Usage:
#   bash start_all.sh           # start backend + tunnel
#   bash start_all.sh --no-tunnel   # backend only (no public tunnel)
#   bash start_all.sh --port 9000   # use custom port
#
# What this does:
#   1. Validates your .env setup
#   2. Starts the FastAPI backend in a background process
#   3. Waits for backend to be healthy
#   4. Starts a Cloudflare Quick Tunnel
#   5. Prints the public URL and exactly what to do next
#   6. Shows a live log stream
#   7. Cleans up all processes on Ctrl+C
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

# ── Colour helpers ───────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
BLUE='\033[0;34m'

info()  { echo -e "${CYAN}[lens-shtar]${RESET} $*"; }
ok()    { echo -e "${GREEN}[lens-shtar]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[lens-shtar]${RESET} $*"; }
abort() { echo -e "${RED}[lens-shtar] FATAL:${RESET} $*"; cleanup; exit 1; }
head_line() { echo -e "${BOLD}${BLUE}$*${RESET}"; }

# ── CLI args ─────────────────────────────────────────────────
USE_TUNNEL=true
PORT=8000
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-tunnel)   USE_TUNNEL=false; shift ;;
    --port)        PORT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: bash start_all.sh [--no-tunnel] [--port PORT]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Cleanup on exit ──────────────────────────────────────────
BACKEND_PID=""
TUNNEL_PID=""
cleanup() {
  echo ""
  info "Shutting down …"
  [[ -n "$TUNNEL_PID" ]] && kill "$TUNNEL_PID" 2>/dev/null && ok "Tunnel stopped."
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null && ok "Backend stopped."
  ok "All processes stopped. Goodbye."
}
trap cleanup EXIT INT TERM

# ── Banner ────────────────────────────────────────────────────
echo ""
head_line "╔══════════════════════════════════════════════════════╗"
head_line "║        Lens Shtar — Local Demo Architecture          ║"
head_line "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Validate backend dir ──────────────────────────────────────
[[ -d "$BACKEND_DIR" ]] || abort "backend/ directory not found."
cd "$BACKEND_DIR"

# ── Validate .env ─────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.local.example" ]]; then
    warn ".env not found — copying from .env.local.example …"
    cp ".env.local.example" ".env"
  else
    abort ".env file missing. See LOCAL_DEMO_SETUP.md."
  fi
fi

JWT_SECRET=$(grep -E '^SUPABASE_JWT_SECRET=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs || true)
if [[ -z "$JWT_SECRET" || "$JWT_SECRET" == "your-jwt-secret-here" ]]; then
  abort "SUPABASE_JWT_SECRET not set in backend/.env\n\nGet it from:\n  Supabase → Project Settings → JWT Settings → JWT Secret\n\nEdit: $BACKEND_DIR/.env"
fi
ok "✓ .env looks good"

# ── Set up Python venv ────────────────────────────────────────
if [[ ! -d ".venv" ]]; then
  info "Creating Python virtual environment …"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"

info "Installing/verifying Python dependencies …"
pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "✓ Python dependencies ready"

# ── Start backend ─────────────────────────────────────────────
info "Starting FastAPI backend on port $PORT …"
BACKEND_LOG=$(mktemp)
PORT="$PORT" python start.py > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Wait for health check (max 30 seconds)
ELAPSED=0
HEALTHY=false
while [[ $ELAPSED -lt 30 ]]; do
  sleep 1
  ELAPSED=$((ELAPSED + 1))
  if curl -sf "http://localhost:$PORT/api/health" >/dev/null 2>&1; then
    HEALTHY=true
    break
  fi
  # Check if backend process died
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "--- Backend log ---"
    cat "$BACKEND_LOG"
    abort "Backend process died unexpectedly."
  fi
done

if [[ "$HEALTHY" == false ]]; then
  echo "--- Backend log ---"
  cat "$BACKEND_LOG"
  abort "Backend did not become healthy within 30 seconds."
fi

ok "✓ Backend is healthy at http://localhost:$PORT"

# ── Start tunnel ──────────────────────────────────────────────
TUNNEL_URL=""
if [[ "$USE_TUNNEL" == true ]]; then
  if ! command -v cloudflared &>/dev/null; then
    warn "cloudflared not found. Skipping tunnel."
    warn "To install: wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && sudo dpkg -i cloudflared-linux-amd64.deb"
    USE_TUNNEL=false
  else
    info "Starting Cloudflare Quick Tunnel …"
    TUNNEL_LOG=$(mktemp)
    cloudflared tunnel --url "http://localhost:${PORT}" --no-autoupdate > "$TUNNEL_LOG" 2>&1 &
    TUNNEL_PID=$!

    # Wait for tunnel URL (max 30 seconds)
    ELAPSED=0
    while [[ -z "$TUNNEL_URL" && $ELAPSED -lt 30 ]]; do
      sleep 1
      ELAPSED=$((ELAPSED + 1))
      TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
    done

    if [[ -n "$TUNNEL_URL" ]]; then
      ok "✓ Tunnel active: $TUNNEL_URL"

      # Update TUNNEL_ORIGINS in .env
      if grep -q '^TUNNEL_ORIGINS=' .env; then
        sed -i "s|^TUNNEL_ORIGINS=.*|TUNNEL_ORIGINS=${TUNNEL_URL}|" .env
      else
        echo "TUNNEL_ORIGINS=${TUNNEL_URL}" >> .env
      fi
      ok "✓ TUNNEL_ORIGINS written to backend/.env"
    else
      warn "Could not auto-detect tunnel URL."
      warn "Check above output or look for a .trycloudflare.com URL."
    fi
  fi
fi

# ── Final instructions ────────────────────────────────────────
echo ""
head_line "╔══════════════════════════════════════════════════════╗"
head_line "║              ✅ DEMO SERVER READY                    ║"
head_line "╚══════════════════════════════════════════════════════╝"
echo ""
echo -e "  ${BOLD}Local backend:${RESET}  http://localhost:${PORT}"
echo -e "  ${BOLD}Health check:${RESET}   http://localhost:${PORT}/api/health"

if [[ -n "$TUNNEL_URL" ]]; then
  echo ""
  echo -e "  ${BOLD}Public tunnel:${RESET}  ${GREEN}${TUNNEL_URL}${RESET}"
  echo ""
  echo -e "  ${BOLD}▶  OPEN THIS URL in your browser to use the live demo:${RESET}"
  echo -e "  ${CYAN}  https://lens-flow.shtar.space/?api_base=${TUNNEL_URL}${RESET}"
  echo ""
  echo -e "  ${BOLD}This URL sets the backend to your tunnel automatically.${RESET}"
  echo -e "  ${BOLD}It persists across page reloads for this browser session.${RESET}"
else
  echo ""
  echo -e "  ${YELLOW}No tunnel active.${RESET} Frontend will only work from your machine."
  echo -e "  Open: ${CYAN}http://localhost:8080${RESET} (if serving frontend locally)"
fi

echo ""
echo -e "  ${BOLD}To stop everything:${RESET} Press Ctrl+C here"
echo ""
head_line "════════════════════════════════════════════════════════"
echo ""

# ── Keep alive and stream backend logs ───────────────────────
info "Streaming backend logs (Ctrl+C to stop all) …"
echo ""
tail -f "$BACKEND_LOG" &
TAIL_PID=$!

# Wait for backend or tunnel to exit
while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$TAIL_PID" 2>/dev/null || true
    abort "Backend process exited unexpectedly."
  fi
  if [[ "$USE_TUNNEL" == true ]] && ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    warn "Tunnel process exited. Frontend may stop working externally."
    warn "Restart with: bash start_all.sh"
  fi
  sleep 5
done
