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


# Store clients per room: {room_id: set(ws)}
rooms = {}
message_count = 0  # Counter for throttled logging

async def websocket_handler(request):

    # Basic token check: require ?token=...
    token = request.rel_url.query.get('token')
    room_id = request.rel_url.query.get('room')
    if token != AUTH_TOKEN:
        print(f"[!] WebSocket auth failed from {request.remote} - token={token!r} expected={AUTH_TOKEN!r}")
        return web.Response(status=401, text='Unauthorized')
    if not room_id or not isinstance(room_id, str) or len(room_id) != 3:
        return web.Response(status=400, text='Missing or invalid room id')

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    peer = request.remote
    print(f"[+] Client connected: {peer} room={room_id}")
    # Add client to room
    if room_id not in rooms:
        rooms[room_id] = set()
    rooms[room_id].add(ws)

    try:
        async for msg in ws:
            try:
                if msg.type == web.WSMsgType.TEXT:
                    global message_count
                    message_count += 1
                    if message_count % 50 == 0:
                        print(f"[RX TEXT #{message_count}] from {peer} room={room_id}: {msg.data[:100]}...")
                    # Relay only to clients in the same room
                    for client in list(rooms.get(room_id, [])):
                        if client.closed:
                            rooms[room_id].discard(client)
                            continue
                        try:
                            await client.send_str(msg.data)
                        except Exception as e:
                            print(f"[!] Failed to send TEXT to client {client}: {e}")
                elif msg.type == web.WSMsgType.BINARY:
                    print(f"[RX BINARY] from {peer} room={room_id}: {len(msg.data)} bytes")
                    for client in list(rooms.get(room_id, [])):
                        if client.closed:
                            rooms[room_id].discard(client)
                            continue
                        try:
                            await client.send_bytes(msg.data)
                        except Exception as e:
                            print(f"[!] Failed to send BINARY to client {client}: {e}")
                elif msg.type == web.WSMsgType.ERROR:
                    print('WebSocket connection closed with exception %s' % ws.exception())
                else:
                    print(f"[RX] msg.type={msg.type} from {peer} room={room_id}")
            except Exception as inner:
                print(f"[!] Error processing message from {peer} room={room_id}: {inner}")
    finally:
        print(f"[-] Client disconnected: {peer} room={room_id} code={getattr(ws, 'close_code', None)}")
        rooms[room_id].discard(ws)
        if not rooms[room_id]:
            del rooms[room_id]

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
