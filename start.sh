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
pip install --disable-pip-version-check --no-cache-dir -r requirements.txt

# Start Cloudflare tunnel (best-effort) if token present
if [[ -n "${CLOUDFLARED_TOKEN:-}" ]]; then
  echo "Starting Cloudflare tunnel using token..."
  nohup cloudflared tunnel run --token "$CLOUDFLARED_TOKEN" > cloudflared.log 2>&1 &
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

python server.py \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --static ./static
