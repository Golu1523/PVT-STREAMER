import ctypes
import sys
import subprocess
import time
import os
import threading
import winreg
import hashlib
import requests
import json
import websocket

DEBUG_LOG = os.path.join(os.environ.get("TEMP", os.getcwd()), "streamer_debug.log")

def dlog(msg):
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except:
        pass

# ---------- HIDE CONSOLE ----------
if sys.platform == "win32":
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

# ---------- FIREBASE CONFIG ----------
FIREBASE_URL = "https://streamer-panel-1-default-rtdb.firebaseio.com/"

# ---------- GITHUB CONFIG (raw link - AOB + offsets yahi se aayenge) ----------
GITHUB_URL = "https://raw.githubusercontent.com/Golu1523/files/main/aob.txt"

# ---------- WEBSOCKET CONTROL SERVER (Render par deploy hoga) ----------
# Render server ka URL yahan daalo, e.g. wss://yourapp.onrender.com
WS_URL = "wss://pvt-streamer.onrender.com/"
WS_HEARTBEAT_INTERVAL = 15

# ---------- FUNCTION TO HIDE A FOLDER ----------
def hide_folder(path):
    try:
        ctypes.windll.kernel32.SetFileAttributesW(path, 0x04 | 0x02)
    except:
        pass

# ---------- CONFIG (sab GitHub se aayega, kuch hardcoded nahi) ----------
PROCESS_NAME = "HD-Player.exe"

mem = None
running = True
stored_data = []
aimbot_on = False
ws_conn = None

# ========== HWID via Registry ==========
def get_hwid():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        guid = winreg.QueryValueEx(key, "MachineGuid")[0]
        winreg.CloseKey(key)
        return hashlib.sha256(guid.encode()).hexdigest()
    except Exception:
        return "UNKNOWN_HWID"

# ========== Firebase Helpers (Verification) ==========
def firebase_get(path):
    try:
        url = f"{FIREBASE_URL}{path}.json"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def firebase_put(path, data):
    try:
        url = f"{FIREBASE_URL}{path}.json"
        requests.put(url, json.dumps(data), timeout=5)
        return True
    except:
        return False

# ========== Verification ==========
def verify_and_register():
    hwid = get_hwid()
    dlog(f"verify_and_register hwid={hwid}")
    status = firebase_get(f"users/{hwid}")
    if status is None:
        dlog(f"user not found, registering as 'none'")
        firebase_put(f"users/{hwid}", "none")
        return False
    else:
        dlog(f"user status = {status}")
        return status == "unban"

# ========== GitHub Fetch (aob.txt se AOB + offsets) ==========
def fetch_config_from_github():
    try:
        resp = requests.get(GITHUB_URL, timeout=8)
        if resp.status_code != 200:
            return None, None, None
        aob = None
        w_off = 0
        t_off = 0
        for line in resp.text.splitlines():
            line = line.strip()
            low = line.lower()
            if low.startswith("aob"):
                aob = line.split(":", 1)[1].strip()
            elif low.startswith("write_offset"):
                w_off = int(line.split("=", 1)[1].strip(), 16)
            elif low.startswith("target_offset"):
                t_off = int(line.split("=", 1)[1].strip(), 16)
        if aob:
            return aob, w_off, t_off
    except:
        pass
    return None, None, None

# ========== Aimbot Logic ==========
def init_mem():
    global mem
    try:
        from beyondmem import MemFurqan
        mem = MemFurqan()
    except:
        pass

def find_emulator():
    try:
        output = subprocess.check_output(
            "tasklist /FI \"IMAGENAME eq HD-Player.exe\"",
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        ).decode()
        return "HD-Player.exe" in output
    except:
        return False

def scan_and_store():
    global stored_data, aimbot_on
    if not find_emulator():
        dlog("scan: emulator not found")
        return False
    if mem is None:
        init_mem()
    if not mem.open_process_by_name(PROCESS_NAME):
        dlog("scan: open_process failed")
        return False
    found = mem.AoBScan(0x10000, 0x7FFFFFEFFFF, AIMBOT_AOB)
    if not found:
        dlog("scan: AOB not found")
        return False

    stored_data = []
    for base in found:
        try:
            original = mem.read_bytes(base + WRITE_OFFSET, 4)
            target = mem.read_bytes(base + TARGET_OFFSET, 4)
            if original is not None and target is not None:
                stored_data.append((base, original, target))
        except:
            continue

    if stored_data:
        for base, orig, target in stored_data:
            try:
                mem._write_raw(base + WRITE_OFFSET, target)
            except:
                pass
        aimbot_on = True
        dlog(f"scan: SUCCESS - {len(stored_data)} addresses patched")
        return True
    dlog("scan: no valid addresses found")
    return False

def toggle_aimbot():
    global aimbot_on
    if not stored_data:
        return
    if mem is None:
        init_mem()
    if not mem.open_process_by_name(PROCESS_NAME):
        return
    if aimbot_on:
        for base, original, target in stored_data:
            try:
                mem._write_raw(base + WRITE_OFFSET, original)
            except:
                pass
        aimbot_on = False
    else:
        for base, original, target in stored_data:
            try:
                mem._write_raw(base + WRITE_OFFSET, target)
            except:
                pass
        aimbot_on = True

def exit_program():
    global running
    running = False
    sys.exit(0)   # PyInstaller will clean up temp folder

def send_status():
    global ws_conn
    if ws_conn is None:
        return
    try:
        ws_conn.send(json.dumps({"type": "status", "aimbot": aimbot_on}))
    except:
        pass

def ws_listen():
    global running, aimbot_on, ws_conn
    last_ping = 0
    while running:
        try:
            dlog(f"connecting to {WS_URL}")
            ws_conn = websocket.create_connection(WS_URL, timeout=15)
            ws_conn.send(json.dumps({"type": "register", "role": "client", "hwid": get_hwid()}))
            dlog("connected + registered")
            send_status()
            last_ping = time.time()
            while running:
                try:
                    if time.time() - last_ping >= WS_HEARTBEAT_INTERVAL:
                        ws_conn.send(json.dumps({"type": "ping"}))
                        last_ping = time.time()
                    msg = ws_conn.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not msg:
                    continue
                try:
                    data = json.loads(msg)
                except:
                    continue
                mtype = data.get("type")
                if mtype == "cmd":
                    action = data.get("action")
                    dlog(f"command received: {action} state={data.get('state')}")
                    if action == "scan":
                        scan_and_store()
                        send_status()
                    elif action == "aimbot":
                        want = data.get("state")
                        if want is not None and want != aimbot_on:
                            toggle_aimbot()
                        send_status()
                        dlog(f"aimbot now: {aimbot_on}")
                    elif action == "close":
                        dlog("close command")
                        exit_program()
                elif mtype == "ping":
                    ws_conn.send(json.dumps({"type": "pong"}))
        except Exception as e:
            dlog(f"ws error: {e}")
            ws_conn = None
            time.sleep(3)

# ---------- MAIN ----------
if __name__ == "__main__":
    dlog("=== STREAMER STARTED ===")
    if not verify_and_register():
        dlog("VERIFY FAILED - exiting")
        sys.exit(0)

    AIMBOT_AOB, WRITE_OFFSET, TARGET_OFFSET = fetch_config_from_github()
    if not AIMBOT_AOB:
        dlog("CONFIG FETCH FAILED - exiting")
        sys.exit(0)
    dlog(f"AOB loaded, write_off={hex(WRITE_OFFSET)} target_off={hex(TARGET_OFFSET)}")

    # Hide the default PyInstaller temporary extraction folder
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        hide_folder(sys._MEIPASS)

    threading.Thread(target=ws_listen, daemon=True).start()

    try:
        while running:
            time.sleep(0.5)
    except:
        pass
    finally:
        exit_program()