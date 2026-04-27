const originInput = document.querySelector("#origin");
const assetPath = document.querySelector("#assetPath");
const output = document.querySelector("#output");
const frame = document.querySelector("#frame");

function targetUrl(path = assetPath.value) {
  return `${originInput.value.replace(/\/$/, "")}${path}`;
}

function selectedHeaders(headers) {
  const names = [
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "etag",
    "last-modified",
    "cache-control",
    "expires",
    "content-encoding",
    "vary",
  ];
  return Object.fromEntries(names.map((name) => [name, headers.get(name)]).filter(([, value]) => value !== null));
}

async function showResponse(label, response, bodyText) {
  output.textContent = JSON.stringify(
    {
      label,
      url: response.url,
      status: response.status,
      ok: response.ok,
      headers: selectedHeaders(response.headers),
      body_preview: bodyText ? bodyText.slice(0, 1200) : "",
    },
    null,
    2,
  );
}

async function runGet() {
  const response = await fetch(targetUrl());
  const text = await response.text();
  await showResponse("GET", response, text);
}

async function runHead() {
  const response = await fetch(targetUrl(), { method: "HEAD" });
  await showResponse("HEAD", response, "");
}

async function runRange() {
  const response = await fetch(targetUrl(), { headers: { Range: "bytes=0-31" } });
  const text = await response.text();
  await showResponse("Range bytes=0-31", response, text);
}

async function runEtagRoundtrip() {
  const first = await fetch(targetUrl());
  const etag = first.headers.get("etag");
  const second = await fetch(targetUrl(), { headers: etag ? { "If-None-Match": etag } : {} });
  await showResponse("ETag roundtrip", second, await second.text());
}

function refreshFrame() {
  frame.src = targetUrl();
}

async function guard(action) {
  try {
    await action();
  } catch (error) {
    output.textContent = String(error && error.stack ? error.stack : error);
  }
}

document.querySelector("#getBtn").addEventListener("click", () => guard(runGet));
document.querySelector("#headBtn").addEventListener("click", () => guard(runHead));
document.querySelector("#rangeBtn").addEventListener("click", () => guard(runRange));
document.querySelector("#etagBtn").addEventListener("click", () => guard(runEtagRoundtrip));
document.querySelector("#refreshFrame").addEventListener("click", refreshFrame);
document.querySelector("#clearBtn").addEventListener("click", () => {
  output.textContent = "Ready.";
});
assetPath.addEventListener("change", refreshFrame);
originInput.addEventListener("change", refreshFrame);

refreshFrame();
