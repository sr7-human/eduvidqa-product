#!/bin/bash
# ============================================================
#  Run EduVidQA locally — the WHOLE app (backend + frontend),
#  like `npm run dev` but one double-click. Opens in your browser.
#
#  Bonus: because the backend runs on YOUR Mac (home IP), video
#  ingestion here is reliable — no YouTube datacenter block.
# ============================================================
cd "$(dirname "$0")"

echo "🎓  Starting EduVidQA locally…"
echo ""

# 1) Backend — FastAPI on http://localhost:8000
./.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# 2) Frontend — Vite dev server on http://localhost:5173
#    (frontend/.env.local already points VITE_API_URL at localhost:8000)
( cd frontend && npm run dev ) &
FRONTEND_PID=$!

# Stop both servers when this window closes or you press Ctrl+C
cleanup() {
  echo ""
  echo "🛑  Stopping EduVidQA…"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  exit 0
}
trap cleanup EXIT INT TERM

# Give the servers a moment, then open the browser
sleep 6
open "http://localhost:5173" 2>/dev/null

echo ""
echo "✅  EduVidQA is running locally:"
echo "      App:     http://localhost:5173"
echo "      Backend: http://localhost:8000"
echo ""
echo "   Keep this window open. Close it (or press Ctrl+C) to stop."
echo ""

wait
