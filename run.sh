#!/usr/bin/env bash
set -euo pipefail

export $(grep -v '^#' .env | xargs)

echo "Starting cloudflared tunnel with token..."
nohup cloudflared tunnel run --token "$CLOUDFLARED_TOKEN" > cloudflared.log 2>&1 &

sleep 1
echo "Tunnel started. Logs are in cloudflared.log"
tail -n 10 cloudflared.log
