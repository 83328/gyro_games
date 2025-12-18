#!/usr/bin/env bash
set -euo pipefail

# Load environment variables safely
set -a
source .env
set +a

echo "Starting Cloudflare tunnel using token..."

# Start cloudflared using token from .env
nohup cloudflared tunnel run --token "$CLOUDFLARED_TOKEN" > cloudflared.log 2>&1 &

sleep 5
echo "Tunnel started. Logs are in cloudflared.log"
echo ""
echo "Starting server with uv..."
echo "Server will be accessible via:"
echo "  http://localhost:8080 (local development)"
echo "  https://games.arthurlimpens.com (external via tunnel)"
echo ""
echo "Press CTRL+C to stop"

# Run backend (bind to localhost)
uv run server.py \
  --host 127.0.0.1 \
  --port 8080 \
  --static ./static
