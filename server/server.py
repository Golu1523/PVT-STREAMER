import asyncio
import json
import logging
import os
import time

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Headers, Request, Response, parse_line, parse_headers
from websockets.protocol import State


def ws_open(conn):
    try:
        return conn.state is State.OPEN
    except Exception:
        return True

# ---------- PATCH: allow HEAD requests to reach process_request ----------
# Render's health checker sends HEAD requests. websockets' Request.parse rejects
# any non-GET method before process_request is called, so we patch it to treat
# HEAD like GET (it never carries a body).
_original_parse = Request.parse


@classmethod
def _lenient_parse(cls, read_line):
    request_line = yield from parse_line(read_line)
    method, raw_path, protocol = request_line.split(b" ", 2)
    if protocol != b"HTTP/1.1":
        raise ValueError(f"unsupported protocol; expected HTTP/1.1")
    if method == b"HEAD":
        method = b"GET"
    if method != b"GET":
        raise ValueError(f"unsupported HTTP method; expected GET; got {method!r}")
    path = raw_path.decode("ascii", "surrogateescape")
    headers = yield from parse_headers(read_line)
    if "Transfer-Encoding" in headers:
        raise NotImplementedError("transfer codings aren't supported")
    if "Content-Length" in headers:
        raise ValueError("unsupported request body")
    return cls(path, headers)


Request.parse = _lenient_parse

ADMIN_TOKEN = "STREAMER-PANEL-ADMIN-KEY"

clients = {}
admins = {}
last_seen = {}


def now():
    return time.time()


async def send(ws, obj):
    try:
        await ws.send(json.dumps(obj))
    except Exception:
        pass


async def broadcast_admin(hwid, obj):
    for ws in list(admins.get(hwid, [])):
        await send(ws, obj)


async def handler(ws):
    hwid = None
    role = None
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            mtype = msg.get("type")

            if mtype == "register":
                role = msg.get("role")
                hwid = (msg.get("hwid") or "").strip()

                if role == "admin":
                    token = msg.get("token") or ""
                    if token != ADMIN_TOKEN:
                        await send(ws, {"type": "error", "message": "Invalid admin token"})
                        role = None
                        hwid = None
                        continue
                    admins.setdefault(hwid, []).append(ws)
                    online = hwid in clients
                    aimbot = clients.get(hwid, {}).get("aimbot", False) if online else False
                    await send(ws, {"type": "status", "hwid": hwid, "online": online, "aimbot": aimbot})
                elif role == "client":
                    clients[hwid] = {"ws": ws, "aimbot": False}
                    last_seen[hwid] = now()
                    await broadcast_admin(hwid, {"type": "status", "hwid": hwid, "online": True, "aimbot": False})
                continue

            if role == "client":
                last_seen[hwid] = now()
                if mtype == "status":
                    if clients.get(hwid):
                        clients[hwid]["aimbot"] = bool(msg.get("aimbot", False))
                    await broadcast_admin(hwid, {"type": "status", "hwid": hwid, "online": True, "aimbot": bool(msg.get("aimbot", False))})
                elif mtype == "ping":
                    await send(ws, {"type": "pong"})
                continue

            if role == "admin":
                if mtype == "cmd":
                    action = msg.get("action")
                    target = hwid
                    c = clients.get(target)
                    if c and ws_open(c["ws"]):
                        await send(c["ws"], {"type": "cmd", "action": action, "state": msg.get("state")})
                    else:
                        await send(ws, {"type": "status", "hwid": target, "online": False, "aimbot": False})
                elif mtype == "ping":
                    await send(ws, {"type": "pong"})
    except ConnectionClosed:
        pass
    finally:
        if role == "admin" and hwid:
            arr = admins.get(hwid, [])
            if ws in arr:
                arr.remove(ws)
            if not arr:
                admins.pop(hwid, None)
        elif role == "client" and hwid:
            if clients.get(hwid, {}).get("ws") is ws:
                clients.pop(hwid, None)
            await broadcast_admin(hwid, {"type": "status", "hwid": hwid, "online": False, "aimbot": False})


async def handle_http(connection, request):
    upgrade = request.headers.get("Upgrade", "").lower()
    if upgrade == "websocket":
        return None
    return Response(200, "OK", Headers({"Content-Length": "0"}), b"")


async def main():
    port = int(os.environ.get("PORT", 8000))
    ws_logger = logging.getLogger("websockets.server")
    ws_logger.addHandler(logging.NullHandler())
    ws_logger.propagate = False
    ws_logger.setLevel(logging.CRITICAL)
    print(f"[SERVER] WebSocket relay starting on port {port}", flush=True)
    async with serve(
        handler,
        "0.0.0.0",
        port,
        process_request=handle_http,
        ping_interval=20,
        ping_timeout=120,
        logger=ws_logger,
    ):
        print(f"[SERVER] Ready", flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
