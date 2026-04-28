const urlInput = document.querySelector("#urlInput");
const nameInput = document.querySelector("#nameInput");
const messageInput = document.querySelector("#messageInput");
const connectBtn = document.querySelector("#connectBtn");
const disconnectBtn = document.querySelector("#disconnectBtn");
const renameBtn = document.querySelector("#renameBtn");
const sendBtn = document.querySelector("#sendBtn");
const echoBtn = document.querySelector("#echoBtn");
const pingBtn = document.querySelector("#pingBtn");
const binaryBtn = document.querySelector("#binaryBtn");
const clearBtn = document.querySelector("#clearBtn");
const statusDot = document.querySelector("#statusDot");
const statusText = document.querySelector("#statusText");
const eventLog = document.querySelector("#eventLog");
const connectedCount = document.querySelector("#connectedCount");
const totalConnections = document.querySelector("#totalConnections");
const totalMessages = document.querySelector("#totalMessages");
const lastRtt = document.querySelector("#lastRtt");
const peerList = document.querySelector("#peerList");

let socket = null;
let lastPing = null;
let refreshTimer = null;

function setConnected(isConnected) {
  statusDot.classList.toggle("online", isConnected);
  statusText.textContent = isConnected ? "Connected" : "Disconnected";
  connectBtn.disabled = isConnected;
  disconnectBtn.disabled = !isConnected;
  renameBtn.disabled = !isConnected;
  sendBtn.disabled = !isConnected;
  echoBtn.disabled = !isConnected;
  pingBtn.disabled = !isConnected;
  binaryBtn.disabled = !isConnected;
}

function appendLog(kind, payload) {
  const item = document.createElement("li");
  const time = new Date().toLocaleTimeString();
  item.className = `event ${kind}`;
  item.innerHTML = `<span>${time}</span><strong>${kind}</strong><code></code>`;
  item.querySelector("code").textContent =
    typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  eventLog.prepend(item);
  while (eventLog.children.length > 80) {
    eventLog.lastElementChild.remove();
  }
}

function sendJson(payload) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }
  socket.send(JSON.stringify(payload));
  appendLog("send", payload);
}

function backendBaseUrl() {
  const wsUrl = new URL(urlInput.value);
  wsUrl.protocol = wsUrl.protocol === "wss:" ? "https:" : "http:";
  wsUrl.pathname = "";
  wsUrl.search = "";
  wsUrl.hash = "";
  return wsUrl.toString().replace(/\/$/, "");
}

async function refreshState() {
  try {
    const response = await fetch(`${backendBaseUrl()}/state`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`state ${response.status}`);
    }
    renderState(await response.json());
  } catch (error) {
    appendLog("state", String(error));
  }
}

function renderState(state) {
  connectedCount.textContent = String(state.connected ?? 0);
  totalConnections.textContent = String(state.total_connections ?? 0);
  totalMessages.textContent = String(state.total_messages ?? 0);
  peerList.replaceChildren();
  for (const peer of state.peers ?? []) {
    const item = document.createElement("li");
    item.innerHTML = `<strong></strong><span></span>`;
    item.querySelector("strong").textContent = peer.name;
    item.querySelector("span").textContent = `${peer.message_count} messages`;
    peerList.append(item);
  }
}

function connect() {
  socket = new WebSocket(urlInput.value);
  socket.binaryType = "arraybuffer";
  appendLog("open", urlInput.value);

  socket.addEventListener("open", () => {
    setConnected(true);
    sendJson({ action: "rename", name: nameInput.value });
    refreshState();
    refreshTimer = window.setInterval(refreshState, 1500);
  });

  socket.addEventListener("message", (event) => {
    if (typeof event.data !== "string") {
      appendLog("recv", { binary: true, bytes: event.data.byteLength });
      return;
    }
    const payload = JSON.parse(event.data);
    if (payload.event === "pong" && lastPing) {
      lastRtt.textContent = `${performance.now() - lastPing}ms`.replace(/\.\d+ms$/, "ms");
    }
    appendLog("recv", payload);
    if (payload.state) {
      renderState(payload.state);
    } else if (payload.event === "presence" || payload.event === "message") {
      refreshState();
    }
  });

  socket.addEventListener("close", (event) => {
    setConnected(false);
    window.clearInterval(refreshTimer);
    refreshTimer = null;
    appendLog("close", { code: event.code, reason: event.reason });
  });

  socket.addEventListener("error", () => {
    appendLog("error", "WebSocket error");
  });
}

connectBtn.addEventListener("click", connect);
disconnectBtn.addEventListener("click", () => socket?.close(1000, "client closed"));
renameBtn.addEventListener("click", () => sendJson({ action: "rename", name: nameInput.value }));
sendBtn.addEventListener("click", () => sendJson({ action: "broadcast", text: messageInput.value }));
echoBtn.addEventListener("click", () => sendJson({ action: "echo", text: messageInput.value }));
pingBtn.addEventListener("click", () => {
  lastPing = performance.now();
  sendJson({ action: "ping", ts: Date.now() });
});
binaryBtn.addEventListener("click", () => {
  const data = new TextEncoder().encode(messageInput.value);
  socket?.send(data);
  appendLog("send", { binary: true, bytes: data.byteLength });
});
clearBtn.addEventListener("click", () => eventLog.replaceChildren());

setConnected(false);
refreshState();

