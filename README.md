# PVT STREAMER PANEL

Remote control panel for Streamer. WebSocket relay based. Fast control (~50-100ms) via Render (Singapore region).

## Architecture

```
Admin Website (Render Static) --WebSocket--> Relay Server (Render Web Service) --WebSocket--> Streamer.exe (User PC)
        login with HWID key                        command relay                        executes scan/aimbot/close
```

## Folder Structure

```
├── server/          -> Render WEB SERVICE  (WebSocket relay)
│   ├── server.py
│   └── requirements.txt
├── web/             -> Render STATIC SITE  (admin panel - red theme)
│   ├── index.html
│   ├── style.css
│   └── app.js
└── client/          -> Streamer.exe source (PyInstaller build)
    ├── Streamer.py
    ├── beyondmem.py
    ├── aob.txt
    └── RuntimeBroker.spec
```

## Deploy on Render

### 1. WebSocket Relay Server (Web Service)

1. Render -> New -> Web Service -> connect this GitHub repo
2. Root Directory: `server`
3. Runtime: Python 3
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python server.py`
6. Instance Type: Free
7. Region: **Singapore** (fastest for India clients)
8. Deploy -> note the URL e.g. `https://xxx.onrender.com`

### 2. Admin Website (Static Site)

1. Render -> New -> Static Site -> connect this GitHub repo
2. Root Directory: `web`
3. Region: **Singapore**
4. Deploy -> note the URL e.g. `https://xxx.onrender.com`

## Setup After Deploy

### 1. Update admin website URL

In `web/app.js`:
```js
const WS_URL = "wss://xxx.onrender.com/";
```
Update, commit, push. Render auto-redeploys.

### 2. Update Streamer.py URL

In `client/Streamer.py`:
```python
WS_URL = "wss://xxx.onrender.com/"
```
Then build the exe with PyInstaller.

### 3. Firebase

User keys are verified against Firebase `users/{hwid}` == `"unban"`. Admin (owner) sets users to `"unban"` in Firebase to activate them.

## Admin Token

`server.py` and `web/app.js` contain:
```
ADMIN_TOKEN = "STREAMER-PANEL-ADMIN-KEY"
```
Change it if needed (must match on both sides).

## How it works

- Streamer.exe connects to WebSocket server as `client` (role), registers with HWID
- Admin website connects as `admin` (role), sends commands for a specific HWID
- Server relays commands to the right client: `scan`, `aimbot on/off`, `close`
- Client sends status back (online, aimbot state) which shows on the panel
- Heartbeat every 15s keeps the Render free service awake (no sleep)

## Old Hotkeys

F5/F6/F10 hotkeys have been removed. Control is now via the website only.
