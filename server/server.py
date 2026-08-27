import asyncio
import json
import os
import time

import websockets
from websockets.exceptions import ConnectionClosed

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
                    if c and c["ws"].open:
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


async def main():
    port = int(os.environ.get("PORT", 8000))
    print(f"[SERVER] WebSocket relay started on port {port}", flush=True)
    async with websockets.serve(handler, "0.0.0.0", port, ping_interval=20, ping_timeout=120):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
