# Gyro Games — local multiplayer phone-as-controller demos
![Pong demo](media/images/pong.png)

Lightweight local demo that uses phones as motion controllers and a small Python aiohttp server to broadcast motion events to browser game pages. The idea behind this project is to see how old phones can be repurposed as motion controllers for simple local multiplayer games, without requiring any app installation.

Features
- Phone streamer page (`/gyro.html`) — streams DeviceMotion / DeviceOrientation and acceleration to the server via WebSocket.
- Several game pages under `static/` that consume streamed events:
	- `maze.html` — grid-maze runner (2–4 players, corner starts/goals)
	- `lander.html` — two-player Moon Lander demo
	- `pong.html` — paddle demo
- Simple token-based WebSocket API (dev-friendly anonymous mode when no token configured).

Quick start (Linux / macOS)

1. Create & activate a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install minimal dependencies:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install aiohttp python-dotenv
```

3. (Optional) Create a .env file with a token to require clients to present the same token when connecting:

```
GYRO_TOKEN=some-secret-token
# Optionally set a public ws_url if you're using a tunnel service
# WS_URL=wss://xxxx.ngrok.io/ws
```

4. Run the server:

```bash
python3 server.py
```

5. Open the pages in your browser (or expose the server with ngrok and open the forwarded URL on phones):

- Host machine: http://localhost:8080/ (the server serves `static/index.html`)
- Phone (streamer): http://<your-host>:8080/gyro.html
- Game selector page: http://<your-host>:8080/index.html

How it works (short)
- A phone opens `/gyro.html`, selects a role (blue/red/yellow/green), and starts streaming. The page requests device motion/orientation permissions on iOS and sends compact JSON payloads over WebSocket.
- The server forwards messages to all connected clients. Game pages listen on the same WebSocket and apply incoming telemetry to the matching player role.

Controls & calibration
- Prefer orientation angles (deviceorientation) when available; otherwise the streamer falls back to rotationRate integration.
- `maze.html` contains a small "Calibrate" button (saves neutral orientation to localStorage). Calibration persists across reloads.
- `lander.html` and other game pages include small HUDs and invert toggles to adjust device sign conventions per phone.

Development notes
- The server is a minimal aiohttp app in `server.py`. It serves files from `static/` and implements `/api/token` and `/ws` endpoints.
- If you get a ModuleNotFoundError for `dotenv`, install `python-dotenv` or remove the `.env` usage in `server.py`.

Troubleshooting
- WebSocket fails to connect: check server console for handshake logs. If you set `GYRO_TOKEN` then the client must pass the same token (see `/api/token` response). If you see malformed ws URLs like `wss://https//...` check any `WS_URL` you configured.
- iOS motion permission: Safari requires a user gesture to request motion/orientation permission. Open `/gyro.html` and tap Start; if the page doesn't prompt, check the Safari settings and ensure HTTPS/localhost and a user gesture.
- Virtualenv pip wrapper broken: recreate the venv using `python3 -m venv .venv` and reinstall packages with `python -m pip install ...`.

Extending
- Add new game pages by creating static HTML/JS that listens to the same WebSocket and implements role-based input handling.
- Persist per-player preferences (invert toggles, sensitivity) in localStorage to remember settings across sessions.

License & credits
- This project is released under a non-commercial license: Creative Commons
	Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).

	In short: you are free to copy, modify, and redistribute the source code and
	documentation for non-commercial purposes, provided you give proper attribution
	to the original author. Any distribution (including derivative works) must be
	for non-commercial use only. The full license text is available from the
	Creative Commons website and a copy or reference is provided in the `LICENSE` file.

	Key points:
	- You may use, modify and redistribute this project for non-commercial purposes.
	- You must provide attribution to the original project when redistributing.
	- Commercial use (selling, licensing, or redistributing for direct commercial gain)
		is not permitted under this license. For commercial use please contact the project owner
		to arrange a separate commercial license.
	- The software is provided WITHOUT ANY WARRANTY; without even the implied warranty of
		MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the full license for details.

	If you want to use this code commercially or include it in a project that will be
	distributed commercially, please contact the project owner to discuss a commercial
	licensing arrangement.
