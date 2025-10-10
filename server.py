# ~/gyro_stream/server.py
import os
from dotenv import load_dotenv
import json
import argparse
from aiohttp import web

# Load .env file if present
load_dotenv()

# Use environment variables for token and ws url
AUTH_TOKEN = os.environ.get('GYRO_TOKEN')
WS_URL = os.environ.get('WS_URL')

# Store all connected WebSocket clients
clients = set()

async def websocket_handler(request):
    # Basic token check: require ?token=...
    token = request.rel_url.query.get('token')
    if token != AUTH_TOKEN:
        return web.Response(status=401, text='Unauthorized')

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    peer = request.remote
    print(f"[+] Client connected: {peer}")
    clients.add(ws)  # Add client to set

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                # Try parse JSON
                try:
                    data = json.loads(msg.data)
                    print("Gyro:", data)
                    # Broadcast data to all connected clients
                    for client in clients:
                        if not client.closed:
                            await client.send_json(data)
                except Exception:
                    print("Gyro (raw):", msg.data)
            elif msg.type == web.WSMsgType.ERROR:
                print('WebSocket connection closed with exception %s' % ws.exception())
    finally:
        print(f"[-] Client disconnected: {peer}")
        clients.discard(ws)  # Remove client on disconnect

    return ws

def create_app(static_dir: str):
    app = web.Application()
    app.router.add_get('/ws', websocket_handler)
    # Serve index.html at root explicitly and disable directory listings
    async def index_handler(request):
        index_path = os.path.join(static_dir, 'index.html')
        if os.path.exists(index_path):
            return web.FileResponse(index_path)
        return web.Response(status=404, text='Not found')

    app.router.add_get('/', index_handler)
    # if there's a sibling 'media' directory, expose it at /media so assets
    # stored outside the static folder (e.g. media/images) are reachable.
    media_dir = os.path.abspath(os.path.join(static_dir, '..', 'media'))
    if os.path.isdir(media_dir):
        app.router.add_static('/media', path=media_dir, show_index=False)
        print(f"Serving media files from: {media_dir} at /media")

    # mount static files but disable directory index listing for security/UX
    app.router.add_static('/', path=static_dir, show_index=False)

    # Add API endpoint to serve token
    async def token_handler(request):
        return web.json_response({'token': AUTH_TOKEN, 'ws_url': WS_URL})
    app.router.add_get('/api/token', token_handler)

    return app

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--static', default='static')
    args = parser.parse_args()

    static_path = os.path.abspath(args.static)
    if not os.path.isdir(static_path):
        os.makedirs(static_path, exist_ok=True)

    app = create_app(static_path)
    print(f"Serving static files from: {static_path}")
    print(f"WebSocket endpoint: /ws (token must equal env GYRO_TOKEN or default in script)")
    web.run_app(app, host=args.host, port=args.port)
