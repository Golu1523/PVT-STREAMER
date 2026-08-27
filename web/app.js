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

async function login() {
  const pass = document.getElementById("admKey").value.trim();
  const err = document.getElementById("loginErr");
  const btn = document.getElementById("loginBtn");
  if (!pass) return;
  err.style.display = "none";
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Verifying...';
  try {
    const resp = await fetch(FIREBASE_URL + "users/" + pass + ".json", { cache: "no-store" });
    const data = await resp.json();
    if (data !== "unban") throw new Error("Invalid key");
  } catch (e) {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-lock"></i> Access System';
    err.style.display = "block";
    return;
  }
  hwid = pass;
  if (document.getElementById("rememberMe").checked) {
    localStorage.setItem("pvt_key", pass);
  } else {
    localStorage.removeItem("pvt_key");
  }
  document.getElementById("loginPage").classList.remove("show");
  document.getElementById("panel-page").classList.remove("hidden");
  document.getElementById("key-display").textContent = pass;
  connectWS();
}

function togglePass() {
  const inp = document.getElementById("admKey");
  const icon = document.getElementById("passIcon");
  if (inp.type === "password") { inp.type = "text"; icon.className = "fa-solid fa-eye-slash"; }
  else { inp.type = "password"; icon.className = "fa-solid fa-eye"; }
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

document.getElementById("admKey").addEventListener("keydown", function (e) {
  if (e.key === "Enter") login();
});

(function () {
  const saved = localStorage.getItem("pvt_key");
  if (saved) {
    document.getElementById("admKey").value = saved;
    document.getElementById("rememberMe").checked = true;
  }
})();
