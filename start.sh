#!/usr/bin/env bash
set -euo pipefail

# Load environment variables
export $(grep -v '^#' .env | xargs)

echo "Starting cloudflared tunnel in background..."
nohup cloudflared tunnel run --token "$CLOUDFLARED_TOKEN" > cloudflared.log 2>&1 &

sleep 1
echo "Tunnel started. Logs are in cloudflared.log"

echo "Starting server with uv..."
echo "Server will be accessible at http://localhost:8080"
echo "Press CTRL+C to stop"

# uv will automatically create venv and install dependencies if needed
uv run server.py --host 0.0.0.0 --port 8080 --static ./static
