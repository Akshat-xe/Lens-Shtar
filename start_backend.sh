#!/usr/bin/env bash
# =============================================================
# Lens Shtar — Backend Starter
# =============================================================
# Starts the FastAPI backend locally inside the venv.
#
#   bash start_backend.sh
#   PORT=9000 bash start_backend.sh
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

# ── Colour helpers ───────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { echo -e "${CYAN}[backend]${RESET} $*"; }
ok()    { echo -e "${GREEN}[backend]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[backend]${RESET} $*"; }
abort() { echo -e "${RED}[backend] FATAL:${RESET} $*"; exit 1; }

# ── Validate backend directory ───────────────────────────────
[[ -d "$BACKEND_DIR" ]] || abort "backend/ directory not found at $BACKEND_DIR"
cd "$BACKEND_DIR"

# ── Check for .env ───────────────────────────────────────────
if [[ ! -f ".env" ]]; then
  warn ".env not found. Copying from .env.local.example …"
  if [[ -f ".env.local.example" ]]; then
    cp ".env.local.example" ".env"
    warn "Created .env — PLEASE fill in SUPABASE_JWT_SECRET before continuing."
    warn "Edit: $BACKEND_DIR/.env"
    echo ""
    abort "Fill in SUPABASE_JWT_SECRET in .env, then re-run."
  else
    abort ".env.local.example not found either. Check your project setup."
  fi
fi

# ── Check SUPABASE_JWT_SECRET is set ────────────────────────
JWT_SECRET=$(grep -E '^SUPABASE_JWT_SECRET=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs || true)
if [[ -z "$JWT_SECRET" || "$JWT_SECRET" == "your-jwt-secret-here" ]]; then
  abort "SUPABASE_JWT_SECRET is not set in $BACKEND_DIR/.env\nGet it from: Supabase → Project Settings → JWT Settings"
fi

# ── Activate or create venv ──────────────────────────────────
if [[ ! -d ".venv" ]]; then
  info "Creating Python virtual environment …"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"

# ── Install / update dependencies ────────────────────────────
info "Installing/verifying Python dependencies …"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# ── Launch backend ───────────────────────────────────────────
PORT="${PORT:-8000}"
ok "Starting Lens Shtar backend on port $PORT …"
echo ""
RELOAD="${RELOAD:-false}" PORT="$PORT" python start.py
