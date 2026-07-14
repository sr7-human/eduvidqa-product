#!/bin/bash
# ============================================================================
#  Double-click this file whenever YouTube downloads / live frames stop working.
#  It updates the YouTube downloader (yt-dlp), its JS challenge-solver
#  (yt-dlp-ejs), and the deno runtime — the three things that break when
#  YouTube changes its anti-bot system. Plain English results at the end.
# ============================================================================

cd "$(dirname "$0")" || exit 1

PY=".venv/bin/python"
PIP=".venv/bin/pip"

echo ""
echo "=========================================="
echo "  EduVidQA — Updating the YouTube downloader"
echo "=========================================="
echo ""

if [ ! -x "$PY" ]; then
  echo "❌ Could not find the project's Python (.venv/bin/python)."
  echo "   Make sure you're running this from the eduvidqa-product folder."
  echo ""
  read -n1 -r -p "Press any key to close…"
  exit 1
fi

# 1) Update yt-dlp + the JS challenge solver -------------------------------
echo "1/3  Updating yt-dlp and yt-dlp-ejs …"
"$PIP" install -U --quiet yt-dlp yt-dlp-ejs 2>&1 | grep -vi "notice" || true
YTDLP_VER=$("$PY" -m yt_dlp --version 2>/dev/null)
echo "     yt-dlp is now: ${YTDLP_VER:-unknown}"
echo ""

# 2) Make sure deno (the JS runtime) is installed --------------------------
echo "2/3  Checking the deno JS runtime …"
export PATH="$HOME/.deno/bin:$PATH"
if command -v deno >/dev/null 2>&1; then
  echo "     deno is installed: $(deno --version | head -1)"
else
  echo "     deno not found — installing it now …"
  curl -fsSL https://deno.land/install.sh | sh -s -- -y >/dev/null 2>&1
  export PATH="$HOME/.deno/bin:$PATH"
  if command -v deno >/dev/null 2>&1; then
    echo "     ✅ deno installed: $(deno --version | head -1)"
  else
    echo "     ⚠️  deno install failed — please tell your assistant."
  fi
fi
echo ""

# 3) Quick self-test: can we still read YouTube formats? -------------------
echo "3/3  Testing a real YouTube video (this takes ~15s) …"
TEST_URL="https://www.youtube.com/watch?v=Vfo5le26IhY"
if "$PY" -m yt_dlp --no-update --remote-components ejs:github \
      --cookies-from-browser chrome -F "$TEST_URL" 2>/dev/null | grep -q "1280x720"; then
  echo "     ✅ SUCCESS — 720p video formats are available. Everything works."
  RESULT_OK=1
else
  echo "     ⚠️  Could not fetch 720p formats."
  echo "        This may be a temporary YouTube block, or the update didn't fully"
  echo "        fix it. Try once more; if it keeps failing, tell your assistant."
  RESULT_OK=0
fi

echo ""
echo "=========================================="
if [ "${RESULT_OK}" = "1" ]; then
  echo "  ✅ ALL GOOD — live frames & ingest will work."
else
  echo "  ⚠️  Update ran, but the test did not pass."
fi
echo "=========================================="
echo ""
read -n1 -r -p "Press any key to close this window…"
echo ""
