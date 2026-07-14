#!/bin/bash
# ============================================================================
#  Double-click this whenever the LOCAL app is stuck on "Loading…" or the
#  backend is frozen. It force-kills any stuck backend on port 8000 and starts
#  a fresh one. You never need to restart your computer for this.
#
#  Keep this window OPEN while you use the app locally — closing it stops the
#  backend. To stop the backend, just close this window (or press Ctrl-C).
# ============================================================================

cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.deno/bin:$PATH"   # deno = JS runtime for YouTube downloads

echo ""
echo "=========================================="
echo "  EduVidQA — Restarting the local backend"
echo "=========================================="
echo ""

# 1) Kill any process currently holding port 8000 (the frozen backend) --------
PIDS=$(lsof -ti tcp:8000 2>/dev/null)
if [ -n "$PIDS" ]; then
  echo "Stopping the old/frozen backend (PID $PIDS)…"
  # shellcheck disable=SC2086
  kill -9 $PIDS 2>/dev/null
  sleep 1
  echo "  done."
else
  echo "No old backend was running on port 8000."
fi
echo ""

# 2) Start a fresh backend ----------------------------------------------------
if [ ! -x ".venv/bin/python" ]; then
  echo "❌ Could not find .venv/bin/python — run this from the eduvidqa-product folder."
  read -n1 -r -p "Press any key to close…"
  exit 1
fi

echo "Starting a fresh backend on http://127.0.0.1:8000 …"
echo "(Leave this window open. Reload the app in your browser once it says 'Application startup complete'.)"
echo ""

exec .venv/bin/python -m uvicorn backend.app:app \
  --host 127.0.0.1 --port 8000 \
  --app-dir "$(pwd)"
