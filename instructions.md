# Instructions to run the server

## Prerequisites
Install `uv` (fast Python package installer):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Quick start (recommended)
Just run the startup script - `uv` will automatically handle dependencies:
```bash
./start.sh
```

This will:
1. Start cloudflared tunnel in the background
2. Install dependencies automatically (if needed)
3. Start the server at http://localhost:8080

When cloudflared is running, `games.arthurlimpens.com` will route to your local server.

## Alternative: Manual commands

### Run the server only (without cloudflared):
```bash
uv run server.py --host 0.0.0.0 --port 8080 --static ./static
```

## Stop the server and cloudflared
- To stop the server, press `CTRL + C` in the terminal where the server is running.
- To stop cloudflared, press `CTRL + C` in the terminal where cloudflared is running, or use `pkill cloudflared`.
