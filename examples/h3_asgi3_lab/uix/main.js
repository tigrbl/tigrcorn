const pathInput = document.querySelector("#path");
const state = document.querySelector("#state");
const request = document.querySelector("#session");
const events = document.querySelector("#events");
const send = document.querySelector("#send");

function renderState(value) {
  state.textContent = value;
  state.dataset.state = value;
}

function renderRequest(value) {
  request.textContent = JSON.stringify(value, null, 2);
}

function log(label, value) {
  const suffix = value === undefined ? "" : ` ${JSON.stringify(value, null, 2)}`;
  events.textContent += `[${new Date().toISOString()}] ${label}${suffix}\n`;
  events.scrollTop = events.scrollHeight;
}

async function sendProbe() {
  renderState("sending");
  send.disabled = true;
  const path = pathInput.value.trim() || "/inspect";
  renderRequest({ path, protocol: "h3/quic" });
  const response = await fetch(`/h3-probe?path=${encodeURIComponent(path)}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`probe failed: HTTP ${response.status}`);
  }
  return response.json();
}

send.addEventListener("click", async () => {
  events.textContent = "";
  try {
    const result = await sendProbe();
    renderState(result.ok ? "received" : "failed");
    log("h3 response", result);
  } catch (error) {
    renderState("failed");
    log("probe failed", String(error));
  } finally {
    send.disabled = false;
  }
});

renderRequest({ path: pathInput.value, protocol: "h3/quic" });
