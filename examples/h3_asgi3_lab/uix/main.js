const endpoint = document.querySelector("#endpoint");
const payload = document.querySelector("#payload");
const state = document.querySelector("#state");
const session = document.querySelector("#session");
const events = document.querySelector("#events");
const connect = document.querySelector("#connect");
const stream = document.querySelector("#stream");
const datagram = document.querySelector("#datagram");
const close = document.querySelector("#close");

const encoder = new TextEncoder();
const decoder = new TextDecoder();
let transport;
let certificateHash;

function renderState(value) {
  state.textContent = value;
  state.dataset.state = value;
}

function renderSession(value) {
  session.textContent = JSON.stringify(value, null, 2);
}

function log(label, value) {
  const suffix = value === undefined ? "" : ` ${JSON.stringify(value, null, 2)}`;
  events.textContent += `[${new Date().toISOString()}] ${label}${suffix}\n`;
  events.scrollTop = events.scrollHeight;
}

function setConnected(value) {
  connect.disabled = value;
  stream.disabled = !value;
  datagram.disabled = !value;
  close.disabled = !value;
}

function base64ToArrayBuffer(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes.buffer;
}

async function loadCertificateHash() {
  const response = await fetch("/cert-hash.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`certificate hash unavailable: HTTP ${response.status}`);
  }
  certificateHash = await response.json();
  return {
    serverCertificateHashes: [
      {
        algorithm: certificateHash.algorithm,
        value: base64ToArrayBuffer(certificateHash.value),
      },
    ],
  };
}

async function readDatagrams(reader) {
  while (true) {
    const { value, done } = await reader.read();
    if (done) return;
    log("datagram received", decoder.decode(value));
  }
}

connect.addEventListener("click", async () => {
  events.textContent = "";
  if (!("WebTransport" in window)) {
    renderState("unsupported");
    log("WebTransport is not available in this browser");
    return;
  }

  try {
    renderState("connecting");
    const options = await loadCertificateHash();
    transport = new WebTransport(endpoint.value, options);
    await transport.ready;
    renderState("connected");
    setConnected(true);
    renderSession({ endpoint: endpoint.value, certificateHash: certificateHash.algorithm });
    log("connected");
    readDatagrams(transport.datagrams.readable.getReader()).catch((error) => {
      log("datagram reader failed", String(error));
    });
    transport.closed.then(
      () => {
        setConnected(false);
        renderState("closed");
        log("closed");
      },
      (error) => {
        setConnected(false);
        renderState("closed with error");
        log("closed with error", String(error));
      },
    );
  } catch (error) {
    setConnected(false);
    renderState("failed");
    log("connect failed", String(error));
  }
});

stream.addEventListener("click", async () => {
  try {
    const bidi = await transport.createBidirectionalStream();
    const writer = bidi.writable.getWriter();
    const reader = bidi.readable.getReader();
    await writer.write(encoder.encode(payload.value));
    await writer.close();

    const chunks = [];
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      chunks.push(value);
    }
    const length = chunks.reduce((total, chunk) => total + chunk.byteLength, 0);
    const merged = new Uint8Array(length);
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

datagram.addEventListener("click", async () => {
  try {
    const writer = transport.datagrams.writable.getWriter();
    await writer.write(encoder.encode(payload.value));
    writer.releaseLock();
    log("datagram sent", payload.value);
  } catch (error) {
    log("datagram failed", String(error));
  }
});

close.addEventListener("click", () => {
  transport?.close();
});

renderSession({ endpoint: endpoint.value });

