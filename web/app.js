const FIREBASE_URL = "https://streamer-panel-1-default-rtdb.firebaseio.com/";
const WS_URL = "wss://pvt-streamer.onrender.com/";
const ADMIN_TOKEN = "STREAMER-PANEL-ADMIN-KEY";

let ws = null;
let hwid = "";
let aimbotOn = false;
let online = false;
let reconnectAttempts = 0;

function log(msg, cls) {
  const box = document.getElementById("log-box");
  const el = document.createElement("div");
  el.className = "log-entry " + (cls || "");
  el.textContent = "[PANEL] " + msg;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

async function connect() {
  const key = document.getElementById("key-input").value.trim();
  const err = document.getElementById("login-error");
  err.textContent = "";
  if (!key) {
    err.textContent = "Please enter a key";
    return;
  }
  document.getElementById("connect-btn").disabled = true;
  try {
    const resp = await fetch(FIREBASE_URL + "users/" + key + ".json", { cache: "no-store" });
    const data = await resp.json();
    if (data !== "unban") {
      err.textContent = "Invalid key";
      document.getElementById("connect-btn").disabled = false;
      return;
    }
  } catch (e) {
    err.textContent = "Verification failed. Check network.";
    document.getElementById("connect-btn").disabled = false;
    return;
  }
  hwid = key;
  document.getElementById("login-page").classList.add("hidden");
  document.getElementById("panel-page").classList.remove("hidden");
  document.getElementById("key-display").textContent = key;
  connectWS();
}

function connectWS() {
  try {
    ws = new WebSocket(WS_URL);
  } catch (e) {
    log("WebSocket connect error: " + e.message, "red");
    return;
  }

  ws.onopen = function () {
    reconnectAttempts = 0;
    ws.send(JSON.stringify({ type: "register", role: "admin", hwid: hwid, token: ADMIN_TOKEN }));
    log("Connected to server", "green");
  };

  ws.onmessage = function (evt) {
    let msg;
    try {
      msg = JSON.parse(evt.data);
    } catch (e) {
      return;
    }
    if (msg.type === "status") {
      online = !!msg.online;
      if (typeof msg.aimbot !== "undefined") aimbotOn = !!msg.aimbot;
      updateStatusUI();
    } else if (msg.type === "pong") {
      // keep alive
    } else if (msg.type === "error") {
      log("Error: " + msg.message, "red");
    }
  };

  ws.onclose = function () {
    online = false;
    updateStatusUI();
    log("Disconnected. Reconnecting...", "red");
    scheduleReconnect();
  };

  ws.onerror = function () {
    log("Connection error", "red");
  };
}

function scheduleReconnect() {
  if (!hwid) return;
  const delay = Math.min(5000, 1000 * Math.pow(2, reconnectAttempts));
  reconnectAttempts++;
  setTimeout(connectWS, delay);
}

function sendCmd(action) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    log("Not connected", "red");
    return;
  }
  ws.send(JSON.stringify({ type: "cmd", action: action }));
  if (action === "scan") log("SCAN command sent", "orange");
  if (action === "close") log("CLOSE command sent", "red");
}

function sendAimbot(state) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    log("Not connected", "red");
    return;
  }
  ws.send(JSON.stringify({ type: "cmd", action: "aimbot", state: state }));
  log(state ? "AIMBOT ON command sent" : "AIMBOT OFF command sent", state ? "green" : "red");
}

function updateStatusUI() {
  const onlineVal = document.getElementById("online-status").querySelector(".status-value");
  const aimbotVal = document.getElementById("aimbot-status").querySelector(".status-value");
  onlineVal.textContent = online ? "ONLINE" : "OFFLINE";
  onlineVal.className = "status-value " + (online ? "online" : "offline");
  aimbotVal.textContent = aimbotOn ? "ON" : "OFF";
  aimbotVal.className = "status-value " + (aimbotOn ? "on" : "off");
}

document.getElementById("key-input").addEventListener("keydown", function (e) {
  if (e.key === "Enter") connect();
});
