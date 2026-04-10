#!/usr/bin/env bash
# =============================================================
# Lens Shtar — LOCAL DEMO STARTER
# =============================================================
# Usage:
#   bash start_all.sh           # start backend on port 8000
#   bash start_all.sh --port 9000   # use custom port
#
# What this does:
#   1. Validates your .env setup
#   2. Starts the local FastAPI backend (http://localhost:8000)
#   3. Shows logs directly to the console
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
abort() { echo -e "${RED}[lens-shtar] FATAL:${RESET} $*"; exit 1; }
head_line() { echo -e "${BOLD}${BLUE}$*${RESET}"; }

# ── CLI args ─────────────────────────────────────────────────
PORT=8000
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)        PORT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: bash start_all.sh [--port PORT]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Banner ────────────────────────────────────────────────────
echo ""
head_line "╔══════════════════════════════════════════════════════╗"
head_line "║        Lens Shtar — Local Backend Architecture       ║"
head_line "║                 welcome to eclipse                   ║"
head_line "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Validate backend dir ──────────────────────────────────────
[[ -d "$BACKEND_DIR" ]] || abort "backend/ directory not found."
cd "$BACKEND_DIR"

# ── Validate .env ─────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    warn ".env not found — copying from .env.example …"
    cp ".env.example" ".env"
  else
    abort ".env file missing."
  fi
fi

JWT_SECRET=$(grep -E '^SUPABASE_JWT_SECRET=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs || true)
if [[ -z "$JWT_SECRET" || "$JWT_SECRET" == "your-jwt-secret-here" ]]; then
  abort "SUPABASE_JWT_SECRET not set in backend/.env"
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
echo ""
echo -e "  ${BOLD}Local backend:${RESET}  http://localhost:${PORT}"
echo -e "  ${BOLD}Health check:${RESET}   http://localhost:${PORT}/api/health"
echo -e "  ${BOLD}Live Demo:${RESET}      https://lens-flow.shtar.space"
echo ""
echo -e "  ${BOLD}To stop everything:${RESET} Press Ctrl+C here"
echo ""
head_line "════════════════════════════════════════════════════════"
echo ""

PORT="$PORT" python start.py
