const output = document.querySelector("#output");
const statusNode = document.querySelector("#status");
const titleNode = document.querySelector("#title");
const baseUrlInput = document.querySelector("#base-url");
const headersNode = document.querySelector("#headers");

function baseUrl() {
  return baseUrlInput.value.replace(/\/+$/, "");
}

function write(title, status, value) {
  titleNode.textContent = title;
  statusNode.textContent = status;
  output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function showHeaders(response) {
  const interesting = ["etag", "last-modified", "accept-ranges", "content-range", "content-encoding", "vary", "alt-svc", "trailer", "x-demo-feature"];
  headersNode.replaceChildren();
  for (const name of interesting) {
    const value = response.headers.get(name);
    if (!value) continue;
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = name;
    dd.textContent = value;
    headersNode.append(dt, dd);
  }
}

async function fetchJson(path, init) {
  const response = await fetch(`${baseUrl()}${path}`, init);
  showHeaders(response);
  write(path, `${response.status} ${response.statusText}`, await response.json());
}

async function fetchResource() {
  const response = await fetch(`${baseUrl()}/resource`);
  showHeaders(response);
  write("/resource", `${response.status} ${response.statusText}`, await response.text());
}

async function probe(feature) {
  const response = await fetch(`/probe?feature=${encodeURIComponent(feature)}`);
  const payload = await response.json();
  const transcript = payload.error || `${payload.request}\n--- response ---\n${payload.response}`;
  write(feature, response.ok ? "raw socket" : "failed", transcript);
}

document.querySelector(".controls").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-feature]");
  if (!button) return;
  write(button.textContent, "running", "");
  try {
    await probe(button.dataset.feature);
  } catch (error) {
    write("Error", "failed", error.stack || String(error));
  }
});

document.querySelector("#inspect").addEventListener("click", () => {
  fetchJson("/inspect", {headers: {"x-demo-token": "browser-uix"}}).catch((error) => write("Error", "failed", error.stack || String(error)));
});

document.querySelector("#fetch-resource").addEventListener("click", () => {
  fetchResource().catch((error) => write("Error", "failed", error.stack || String(error)));
});

fetchJson("/").catch((error) => write("Startup Error", "failed", error.stack || String(error)));
