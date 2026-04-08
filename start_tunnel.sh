#!/usr/bin/env bash
# =============================================================
# Lens Shtar — Cloudflare Tunnel Starter
# =============================================================
# Exposes your local backend publicly via Cloudflare Quick Tunnel.
# No account or login required for a temporary tunnel URL.
#
# Prerequisites:
#   cloudflared must be installed. See LOCAL_DEMO_SETUP.md.
#   Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
#
# Usage:
#   bash start_tunnel.sh          # tunnels port 8000
#   PORT=9000 bash start_tunnel.sh
#
# What this does:
#   1. Starts a Cloudflare Quick Tunnel to localhost:PORT
#   2. Prints the public tunnel URL
#   3. Optionally writes TUNNEL_ORIGINS to backend/.env
#   4. Optionally prints the frontend override URL you can open
# =============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { echo -e "${CYAN}[tunnel]${RESET} $*"; }
ok()    { echo -e "${GREEN}[tunnel]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[tunnel]${RESET} $*"; }
abort() { echo -e "${RED}[tunnel] FATAL:${RESET} $*"; exit 1; }

PORT="${PORT:-8000}"

# ── Check cloudflared is installed ───────────────────────────
if ! command -v cloudflared &>/dev/null; then
  abort "cloudflared is not installed.\n\nInstall it:\n  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb\n  sudo dpkg -i cloudflared-linux-amd64.deb\n\nOr see: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
fi

# ── Check backend is reachable ───────────────────────────────
info "Checking backend is running on port $PORT …"
if ! curl -sf "http://localhost:$PORT/api/health" >/dev/null 2>&1; then
  warn "Backend does not appear to be running on port $PORT."
  warn "Start it first with: bash start_backend.sh"
  warn "Proceeding anyway — tunnel will start but may not work until backend is up."
fi

info "Starting Cloudflare Quick Tunnel → localhost:${PORT} …"
info "This will print a public URL like: https://random-words.trycloudflare.com"
echo ""

# Capture cloudflared output and extract tunnel URL
TUNNEL_LOG=$(mktemp)

# Run cloudflared in background, capture output
cloudflared tunnel --url "http://localhost:${PORT}" --no-autoupdate 2>&1 | tee "$TUNNEL_LOG" &
CF_PID=$!

# Wait for the tunnel URL to appear (max 30 seconds)
TUNNEL_URL=""
ELAPSED=0
while [[ -z "$TUNNEL_URL" && $ELAPSED -lt 30 ]]; do
  sleep 1
  ELAPSED=$((ELAPSED + 1))
  # Look for the tunnel URL pattern in cloudflared output
  TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
done

if [[ -z "$TUNNEL_URL" ]]; then
  warn "Could not auto-detect tunnel URL from cloudflared output."
  warn "Check the output above for a URL ending in .trycloudflare.com"
  warn "Once you have the URL, set it manually:"
  warn "  In browser console: LensConfig.setApiBase('https://YOUR-URL.trycloudflare.com')"
  warn "  Or visit: https://lens-flow.shtar.space/?api_base=https://YOUR-URL.trycloudflare.com"
else
  echo ""
  echo -e "${BOLD}======================================================${RESET}"
  echo -e "${GREEN}  ✅ TUNNEL ACTIVE${RESET}"
  echo -e "${BOLD}======================================================${RESET}"
  echo ""
  echo -e "  ${BOLD}Public backend URL:${RESET}"
  echo -e "  ${GREEN}${TUNNEL_URL}${RESET}"
  echo ""
  echo -e "  ${BOLD}Frontend override URL (open this in browser):${RESET}"
  echo -e "  ${CYAN}https://lens-flow.shtar.space/?api_base=${TUNNEL_URL}${RESET}"
  echo ""
  echo -e "  ${BOLD}Or set via browser console:${RESET}"
  echo -e "  ${YELLOW}LensConfig.setApiBase('${TUNNEL_URL}')${RESET}"
  echo ""
  echo -e "${BOLD}======================================================${RESET}"
  echo ""

  # Optionally update backend .env with tunnel origins
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ENV_FILE="$SCRIPT_DIR/backend/.env"
  if [[ -f "$ENV_FILE" ]]; then
    # Update or add TUNNEL_ORIGINS in .env
    if grep -q '^TUNNEL_ORIGINS=' "$ENV_FILE"; then
      sed -i "s|^TUNNEL_ORIGINS=.*|TUNNEL_ORIGINS=${TUNNEL_URL}|" "$ENV_FILE"
    else
      echo "TUNNEL_ORIGINS=${TUNNEL_URL}" >> "$ENV_FILE"
    fi
    ok "Updated TUNNEL_ORIGINS in backend/.env to: $TUNNEL_URL"
    warn "NOTE: Restart backend for the new CORS origin to take effect."
    warn "  Kill start_backend.sh (Ctrl+C) and run it again in its terminal."
  fi
fi

rm -f "$TUNNEL_LOG"

# Keep running until Ctrl+C
wait $CF_PID
