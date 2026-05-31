(function () {
  const endpoint = document.getElementById("endpoint");
  const room = document.getElementById("room");
  const clientName = document.getElementById("clientName");
  const statusText = document.getElementById("statusText");
  const stateBadge = document.getElementById("stateBadge");
  const log = document.getElementById("log");
  const message = document.getElementById("message");
  const subprotocol = document.getElementById("subprotocol");
  const messageCount = document.getElementById("messageCount");
  const latency = document.getElementById("latency");

  let socket = null;
  let sentAt = 0;
  let count = 0;

  endpoint.value = window.TIGRCORN_WSS_URL || "wss://localhost:8443/ws";

  function setState(state, detail) {
    stateBadge.textContent = state;
    stateBadge.dataset.state = state;
    statusText.textContent = detail || state;
  }

  function append(kind, payload) {
    const item = document.createElement("li");
    item.className = kind;
    const stamp = new Date().toLocaleTimeString();
    item.innerHTML = `<span>${stamp}</span><pre></pre>`;
    item.querySelector("pre").textContent =
      typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
    log.prepend(item);
    count += 1;
    messageCount.textContent = String(count);
  }

  function buildUrl() {
    const url = new URL(endpoint.value);
    url.searchParams.set("room", room.value || "lab");
    url.searchParams.set("name", clientName.value || "browser");
    return url.toString();
  }

  function connect() {
    if (socket && socket.readyState <= WebSocket.OPEN) {
      return;
    }
    setState("opening", "Opening WSS connection");
    socket = new WebSocket(buildUrl(), ["tigrcorn.lab.v1"]);
    socket.binaryType = "arraybuffer";
    socket.onopen = function () {
      subprotocol.textContent = socket.protocol || "-";
      setState("open", "Connected to Tigrcorn over WSS");
      append("system", { event: "open", url: socket.url, protocol: socket.protocol });
    };
    socket.onmessage = function (event) {
      if (sentAt) {
        latency.textContent = `${Math.round(performance.now() - sentAt)} ms`;
        sentAt = 0;
      }
      try {
        append("incoming", JSON.parse(event.data));
      } catch (_error) {
        append("incoming", event.data);
      }
    };
    socket.onerror = function () {
      setState("error", "WSS error. Accept the local TLS certificate, then reconnect.");
      append("error", "Browser rejected or lost the WSS connection.");
    };
    socket.onclose = function (event) {
      setState("closed", `Closed ${event.code || ""} ${event.reason || ""}`.trim());
      append("system", { event: "close", code: event.code, reason: event.reason });
    };
  }

  function sendText() {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      append("error", "Connect before sending.");
      return;
    }
    sentAt = performance.now();
    socket.send(message.value);
    append("outgoing", message.value);
  }

  document.getElementById("connect").addEventListener("click", connect);
  document.getElementById("disconnect").addEventListener("click", function () {
    if (socket) {
      socket.close(1000, "client disconnect");
    }
  });
  document.getElementById("send").addEventListener("click", sendText);
  document.getElementById("sendBytes").addEventListener("click", function () {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      append("error", "Connect before sending.");
      return;
    }
    sentAt = performance.now();
    const bytes = new TextEncoder().encode(message.value);
    socket.send(bytes);
    append("outgoing", { bytes: bytes.length });
  });
  document.getElementById("trustCert").addEventListener("click", function () {
    const healthUrl = new URL(endpoint.value);
    healthUrl.protocol = "https:";
    healthUrl.pathname = "/health";
    healthUrl.search = "";
    window.open(healthUrl.toString(), "_blank", "noopener,noreferrer");
  });
  message.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      sendText();
    }
  });
  setState("closed", "Disconnected");
})();
