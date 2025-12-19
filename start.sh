#!/usr/bin/env bash
set -euo pipefail

PORT=${PORT:-8080}

# Load environment variables safely if .env exists
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

# Create venv if missing and install deps
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
# Ensure pip exists in the venv (fixes macOS "pip: command not found")
if ! command -v pip >/dev/null 2>&1; then
  python3 -m ensurepip --upgrade || true
fi

# Install Python dependencies using the venv's interpreter
python3 -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt

# Start Cloudflare tunnel (best-effort) if token present
if [[ -n "${CLOUDFLARED_TOKEN:-}" ]]; then
  echo "Starting Cloudflare tunnel using token..."
  # Lower priority and quiet logs to reduce CPU contention on macOS
  CLOUDFLARED_ARGS=${CLOUDFLARED_ARGS:---no-autoupdate --loglevel warn}
  nohup nice -n 10 cloudflared tunnel run --token "$CLOUDFLARED_TOKEN" $CLOUDFLARED_ARGS > cloudflared.log 2>&1 &
  sleep 5
  echo "Tunnel started. Logs are in cloudflared.log"
else
  echo "CLOUDFLARED_TOKEN not set; skipping tunnel startup"
fi

echo ""
echo "Starting server..."
echo "Server will be accessible via:"
echo "  http://localhost:${PORT} (local development)"
echo "  https://games.arthurlimpens.com (external via tunnel if running)"
echo ""
echo "Press CTRL+C to stop"

# Keep Mac awake to avoid App Nap / timer coalescing stutters
USE_CAFFEINATE=${USE_CAFFEINATE:-1}
IS_DARWIN=0; [[ "$(uname -s)" == "Darwin" ]] && IS_DARWIN=1 || true

CMD=( python server.py --host 0.0.0.0 --port "${PORT}" --static ./static )
if [[ ${IS_DARWIN} -eq 1 && ${USE_CAFFEINATE} -eq 1 && -x "$(command -v caffeinate || true)" ]]; then
  exec caffeinate -dims "${CMD[@]}"
else
  exec "${CMD[@]}"
fi
