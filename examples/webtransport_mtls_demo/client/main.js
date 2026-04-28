const endpoint = document.querySelector("#endpoint");
const payload = document.querySelector("#payload");
const statusEl = document.querySelector("#status");
const sessionEl = document.querySelector("#session");
const eventsEl = document.querySelector("#events");
const connectButton = document.querySelector("#connect");
const streamButton = document.querySelector("#stream");
const datagramButton = document.querySelector("#datagram");
const closeButton = document.querySelector("#close");
const modeButtons = Array.from(document.querySelectorAll(".mode-switch button"));

let transport;
const encoder = new TextEncoder();
const decoder = new TextDecoder();
let certificateHash;

function log(message, data) {
  const stamp = new Date().toISOString();
  const suffix = data === undefined ? "" : ` ${JSON.stringify(data, null, 2)}`;
  eventsEl.textContent += `[${stamp}] ${message}${suffix}\n`;
  eventsEl.scrollTop = eventsEl.scrollHeight;
}

function setStatus(value) {
  statusEl.textContent = value;
}

function setConnected(value) {
  streamButton.disabled = !value;
  datagramButton.disabled = !value;
  closeButton.disabled = !value;
  connectButton.disabled = value;
}

function selectMode(button) {
  modeButtons.forEach((item) => item.classList.toggle("selected", item === button));
  endpoint.value = button.dataset.endpoint;
  sessionEl.textContent = JSON.stringify({ endpoint: endpoint.value, mode: button.textContent }, null, 2);
}

function base64ToArrayBuffer(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes.buffer;
}

function webTransportOptions() {
  if (!certificateHash) {
    return {};
  }
  return {
    serverCertificateHashes: [
      {
        algorithm: certificateHash.algorithm,
        value: base64ToArrayBuffer(certificateHash.value),
      },
    ],
  };
}

async function loadCertificateHash() {
  const response = await fetch("/cert-hash.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`certificate hash unavailable: HTTP ${response.status}`);
  }
  certificateHash = await response.json();
  log("certificate hash loaded", { algorithm: certificateHash.algorithm });
}

async function readDatagrams(reader) {
  while (true) {
    const { value, done } = await reader.read();
    if (done) return;
    log("datagram received", decoder.decode(value));
  }
}

modeButtons.forEach((button) => {
  button.addEventListener("click", () => selectMode(button));
});
selectMode(modeButtons[0]);

connectButton.addEventListener("click", async () => {
  eventsEl.textContent = "";
  if (!("WebTransport" in window)) {
    log("WebTransport is not available in this browser");
    setStatus("unsupported");
    return;
  }

  try {
    setStatus("connecting");
    await loadCertificateHash();
    transport = new WebTransport(endpoint.value, webTransportOptions());
    await transport.ready;
    setConnected(true);
    setStatus("connected");
    sessionEl.textContent = JSON.stringify({ endpoint: endpoint.value, state: "connected" }, null, 2);
    log("connected");
    readDatagrams(transport.datagrams.readable.getReader()).catch((error) => log("datagram reader failed", String(error)));
    transport.closed.then(
      () => {
        setConnected(false);
        setStatus("closed");
        log("closed");
      },
      (error) => {
        setConnected(false);
        setStatus("closed with error");
        log("closed with error", String(error));
      },
    );
  } catch (error) {
    setConnected(false);
    setStatus("failed");
    log("connect failed", String(error));
  }
});

streamButton.addEventListener("click", async () => {
  try {
    const stream = await transport.createBidirectionalStream();
    const writer = stream.writable.getWriter();
    const reader = stream.readable.getReader();
    await writer.write(encoder.encode(payload.value));
    await writer.close();
    const chunks = [];
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      chunks.push(value);
    }
    const total = chunks.reduce((size, chunk) => size + chunk.byteLength, 0);
    const merged = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      merged.set(chunk, offset);
      offset += chunk.byteLength;
    }
    log("stream response", decoder.decode(merged));
  } catch (error) {
    log("stream failed", String(error));
  }
});

datagramButton.addEventListener("click", async () => {
  try {
    const writer = transport.datagrams.writable.getWriter();
    await writer.write(encoder.encode(payload.value));
    writer.releaseLock();
    log("datagram sent", payload.value);
  } catch (error) {
    log("datagram failed", String(error));
  }
});

closeButton.addEventListener("click", () => {
  transport?.close();
});
