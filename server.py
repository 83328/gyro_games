# ~/gyro_stream/server.py
import os
from dotenv import load_dotenv
import json
import struct
import argparse
import asyncio
from aiohttp import web

# Load .env file if present
load_dotenv()

# Use environment variables for token and ws url
AUTH_TOKEN = os.environ.get('GYRO_TOKEN')
WS_URL = os.environ.get('WS_URL')


# Store clients per room: {room_id: set(ws)}
rooms = {}
# Store pending motion state per room: {room_id: {role_name: motion_msg}}
room_states = {}
# Store lightweight room metadata (e.g., playerCount) per room: {room_id: {playerCount: int, ...}}
room_meta = {}
# Aggregation settings
AGGREGATION_INTERVAL = 0.033  # ~30 FPS broadcast rate (33ms)
message_count = 0  # Counter for throttled logging
binary_count = 0
# throttle settings for noisy binary frames
BINARY_LOG_EVERY = 50
BINARY_LARGE_THRESHOLD = 512

# Pre-encoded room-meta messages cache: {room_id: json_str}
room_meta_cache = {}

# Helper: safe global counter increment
def increment_counter():
    global binary_count
    binary_count = (binary_count + 1) % 1000000  # Prevent overflow

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
        room_states[room_id] = {}
    rooms[room_id].add(ws)

    # If we already have metadata for this room (e.g., playerCount), push it to the newcomer
    try:
        if room_meta.get(room_id):
            await ws.send_str(json.dumps({ 'type': 'room-meta', **room_meta[room_id] }))
    except Exception:
        pass

    try:
        async for msg in ws:
            try:
                if msg.type == web.WSMsgType.TEXT:
                    global message_count
                    message_count += 1

                    # Best-effort JSON parse to handle room-meta/request-meta; fall back to relay
                    payload = None
                    try:
                        payload = json.loads(msg.data)
                    except Exception:
                        payload = None

                    handled = False
                    if isinstance(payload, dict) and payload.get('type'):
                        mtype = payload.get('type')

                        if mtype == 'room-meta':
                            # Sanitize and store meta (currently only playerCount)
                            pc = payload.get('playerCount')
                            try:
                                pc_int = int(pc)
                                if 2 <= pc_int <= 8:
                                    room_meta[room_id] = { 'playerCount': pc_int }
                                    # Update cached JSON to avoid re-serialization
                                    room_meta_cache[room_id] = json.dumps({'type': 'room-meta', 'playerCount': pc_int})
                                else:
                                    room_meta.setdefault(room_id, {})
                                    room_meta_cache.pop(room_id, None)
                            except Exception:
                                room_meta.setdefault(room_id, {})
                                room_meta_cache.pop(room_id, None)

                            # Broadcast the meta to everyone in the room (including sender)
                            meta_msg = room_meta_cache.get(room_id, json.dumps({'type': 'room-meta'}))
                            disconnected = []
                            for client in rooms.get(room_id, set()):
                                if client.closed:
                                    disconnected.append(client)
                                    continue
                                try:
                                    await client.send_str(meta_msg)
                                except Exception as e:
                                    print(f"[!] Failed to send room-meta: {e}")
                                    disconnected.append(client)
                            # Clean up disconnected clients in batch
                            for client in disconnected:
                                rooms[room_id].discard(client)
                            handled = True

                        elif mtype == 'request-meta':
                            # Reply only to the requester with current meta if available
                            if room_meta.get(room_id):
                                try:
                                    await ws.send_str(json.dumps({'type': 'room-meta', **room_meta[room_id]}))
                                except Exception:
                                    pass
                            # Also fan out a meta request to all peers in the room so that
                            # any client that knows the playerCount can answer.
                            try:
                                for client in list(rooms.get(room_id, [])):
                                    if client is ws:
                                        continue
                                    if client.closed:
                                        rooms[room_id].discard(client)
                                        continue
                                    await client.send_str(json.dumps({'type': 'request-meta', 'from': 'server'}))
                            except Exception:
                                pass
                            handled = True

                    if handled:
                        continue

                    if message_count % 1000 == 0:
                        print(f"[RX TEXT #{message_count}] from {peer} room={room_id}: {msg.data[:100]}...")
                    # Relay only to clients in the same room
                    disconnected = []
                    for client in rooms.get(room_id, set()):
                        if client.closed:
                            disconnected.append(client)
                            continue
                        try:
                            await client.send_str(msg.data)
                        except Exception as e:
                            print(f"[!] Failed to send TEXT: {e}")
                            disconnected.append(client)
                    # Clean up disconnected clients in batch
                    for client in disconnected:
                        rooms[room_id].discard(client)
                elif msg.type == web.WSMsgType.BINARY:
                    data = msg.data
                    increment_counter()
                    should_log = False
                    if len(data) > BINARY_LARGE_THRESHOLD:
                        should_log = True
                    elif (binary_count % BINARY_LOG_EVERY) == 0:
                        should_log = True
                    if should_log and len(data) >= 1 and data[0] != 1:
                        should_log = True
                    if should_log:
                        print(f"[RX BINARY] from {peer} room={room_id}: {len(data)} bytes (count={binary_count})")

                    # Try to decode our compact motion frame format (client-side gyro binary)
                    # Format (client, little-endian):
                    # [0] uint8 message type (1=motion)
                    # [1] uint8 role index (0..7)
                    # [2..5] uint32 timestamp (ms modulo 2^32)
                    # [6..] N float32 values (we expect 8: beta,gamma,orientA,orientB,orientG,ax,ay,az)
                    if len(data) >= 6 and data[0] == 1:
                        try:
                            role_idx = data[1]
                            ts = int.from_bytes(data[2:6], 'little', signed=False)
                            payload = data[6:]
                            floats = []
                            if len(payload) >= 4 and (len(payload) % 4) == 0:
                                cnt = len(payload) // 4
                                fmt = '<' + 'f' * cnt
                                try:
                                    floats = list(struct.unpack(fmt, payload))
                                except struct.error:
                                    pass
                            # map role index to name when possible
                            roles = ['blue','red','yellow','green','orange','purple','cyan','magenta']
                            role_name = roles[role_idx] if (isinstance(role_idx, int) and 0 <= role_idx < len(roles)) else None
                            motion_msg = {
                                'type': 'motion',
                                'role': role_name,
                                't': ts,
                            }
                            # Provide legacy-friendly keys so existing game clients
                            # that expect named fields (beta/gamma/orientBeta/etc.) continue to work.
                            if len(floats) >= 1:
                                motion_msg['beta'] = floats[0]
                            if len(floats) >= 2:
                                motion_msg['gamma'] = floats[1]
                            if len(floats) >= 3:
                                motion_msg['orientAlpha'] = floats[2]
                            if len(floats) >= 4:
                                motion_msg['orientBeta'] = floats[3]
                            if len(floats) >= 5:
                                motion_msg['orientGamma'] = floats[4]
                            if len(floats) >= 6:
                                motion_msg['ax'] = floats[5]
                            if len(floats) >= 7:
                                motion_msg['ay'] = floats[6]
                            if len(floats) >= 8:
                                motion_msg['az'] = floats[7]
                            # Store the decoded motion state for aggregation
                            if room_id not in room_states:
                                room_states[room_id] = {}
                            room_states[room_id][role_name] = motion_msg
                        except Exception as e:
                            print(f"[!] Failed to decode binary motion frame: {e}")
                elif msg.type == web.WSMsgType.ERROR:
                    print('WebSocket connection closed with exception %s' % ws.exception())
#                else:
#                    print(f"[RX] msg.type={msg.type} from {peer} room={room_id}")
            except Exception as inner:
                print(f"[!] Error processing message from {peer} room={room_id}: {inner}")
    except asyncio.CancelledError:
        print(f"[!] WebSocket task cancelled for {peer} room={room_id}")
    finally:
        print(f"[-] Client disconnected: {peer} room={room_id} code={getattr(ws, 'close_code', None)}")
        rooms[room_id].discard(ws)
        if not rooms[room_id]:
            del rooms[room_id]
            if room_id in room_states:
                del room_states[room_id]
            if room_id in room_meta:
                del room_meta[room_id]
            if room_id in room_meta_cache:
                del room_meta_cache[room_id]

    return ws

async def broadcast_aggregated_state():
    """Background task that periodically broadcasts aggregated state to all rooms."""
    # Cache for pre-serialized aggregated messages per room
    serialized_cache = {}
    
    while True:
        try:
            await asyncio.sleep(AGGREGATION_INTERVAL)
            
            # Iterate through all rooms
            for room_id in list(rooms.keys()):
                clients_set = rooms.get(room_id)
                if not clients_set or len(clients_set) == 0:
                    continue
                
                # Get current state for this room
                state = room_states.get(room_id, {})
                if not state:
                    continue
                
                # Create aggregated message with all player states
                aggregated_msg = {
                    'type': 'batch',
                    'players': list(state.values())
                }
                if room_id in room_meta and isinstance(room_meta[room_id], dict):
                    aggregated_msg.update(room_meta[room_id])
                
                # Serialize once and broadcast to all clients in this room
                text = json.dumps(aggregated_msg)
                
                # Use gather for concurrent sends to avoid blocking on individual clients
                disconnected = set()
                tasks = []
                for client in clients_set:
                    if client.closed:
                        disconnected.add(client)
                    else:
                        tasks.append(client.send_str(text))
                
                # Execute all sends concurrently and capture failures
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, client in enumerate([c for c in clients_set if not c.closed]):
                        if i < len(results) and isinstance(results[i], Exception):
                            disconnected.add(client)
                
                # Clean up disconnected clients in batch
                for client in disconnected:
                    clients_set.discard(client)
        except Exception as e:
            print(f"[!] Error in broadcast_aggregated_state: {e}")
            await asyncio.sleep(1)  # Back off on error

def create_app(static_dir: str):
    app = web.Application()
    app.router.add_get('/ws', websocket_handler)
    
    # Start background task for aggregated broadcasting
    async def start_background_tasks(app):
        app['broadcast_task'] = asyncio.create_task(broadcast_aggregated_state())
    
    async def cleanup_background_tasks(app):
        app['broadcast_task'].cancel()
        await app['broadcast_task']
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
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

    # Add API endpoint to serve token (MUST be before static route!)
    async def token_handler(request):
        # 1. Get the host (e.g. 'games.arthurlimpens.com' or 'localhost:8080')
        host_header = request.headers.get('Host', request.host)
        
        # 2. Check if we are behind the Cloudflare Tunnel (HTTPS)
        # Cloudflare sends 'https' in the X-Forwarded-Proto header.
        is_secure = request.headers.get('X-Forwarded-Proto') == 'https'
        
        # 3. Use wss:// for Cloudflare, ws:// for local/unsecured
        protocol = 'wss' if is_secure else 'ws'
        
        # 4. Fallback to env variable
        if WS_URL:
            ws_url = WS_URL
        else:
            ws_url = f'{protocol}://{host_header}/ws'

        print(f"[Token API] Protocol: {protocol} | Host: {host_header} → {ws_url}")
        return web.json_response({'token': AUTH_TOKEN, 'ws_url': ws_url})
    app.router.add_get('/api/token', token_handler)

    # mount static files but disable directory index listing for security/UX
    app.router.add_static('/', path=static_dir, show_index=False)

    return app

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
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
