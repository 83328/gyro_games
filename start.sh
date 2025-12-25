#!/usr/bin/env bash
set -euo pipefail

#######################################
# Config
#######################################
PORT=${PORT:-8080}

#######################################
# Load environment variables
#######################################
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

#######################################
# Sanity checks
#######################################
command -v cloudflared >/dev/null || {
  echo "❌ cloudflared not found in PATH"
  exit 1
}

#######################################
# Kill any lingering process on PORT
#######################################
if lsof -ti :${PORT} >/dev/null 2>&1; then
  echo "⚠️  Killing lingering process on port ${PORT}..."
  lsof -ti :${PORT} | xargs kill -9 2>/dev/null || true
  sleep 1
fi

#######################################
# Python venv & deps
#######################################
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

python3 -m ensurepip --upgrade >/dev/null 2>&1 || true
python3 -m pip install \
  --disable-pip-version-check \
  --no-cache-dir \
  -r requirements.txt

#######################################
# Cleanup handler
#######################################
cleanup() {
  echo ""
  echo "Stopping services..."
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null || true
  [[ -n "${CF_PID:-}" ]] && kill "$CF_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  echo "Stopped cleanly."
}
trap cleanup INT TERM EXIT

#######################################
# Start backend FIRST
#######################################
echo "Starting backend on port ${PORT}..."

python server.py \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --static ./static &

SERVER_PID=$!

sleep 1

#######################################
# Start Cloudflare tunnel (token mode)
#######################################
if [[ -z "${CLOUDFLARED_TOKEN:-}" ]]; then
  echo "❌ CLOUDFLARED_TOKEN not set in .env"
  exit 1
fi

echo "Starting Cloudflare tunnel..."

cloudflared tunnel \
  --no-autoupdate \
  --loglevel warn \
  run \
  --token "$CLOUDFLARED_TOKEN" \
  > cloudflared.log 2>&1 &

CF_PID=$!

#######################################
# Wait for tunnel readiness
#######################################
echo -n "Waiting for tunnel to connect"
for _ in {1..10}; do
  if grep -q "Connected to Cloudflare" cloudflared.log 2>/dev/null; then
    echo " ✅"
    break
  fi
  echo -n "."
  sleep 1
done

#######################################
# Info
#######################################
echo ""
echo "====================================="
echo "🚀 Server running"
echo "Local:   http://localhost:${PORT}"
echo "Public:  https://games.arthurlimpens.com"
echo "Logs:    cloudflared.log"
echo "====================================="
echo "Press CTRL+C to stop"
echo ""

#######################################
# macOS: prevent App Nap
#######################################
if [[ "$(uname -s)" == "Darwin" ]] && command -v caffeinate >/dev/null; then
  exec caffeinate -dims wait
else
  wait
fi
