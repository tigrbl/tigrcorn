const originInput = document.querySelector("#origin");
const assetPath = document.querySelector("#assetPath");
const rangeStart = document.querySelector("#rangeStart");
const rangeEnd = document.querySelector("#rangeEnd");
const trace = document.querySelector("#trace");
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

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
  });
}

function renderTrace(title, steps) {
  trace.innerHTML = `
    <div class="trace-title">${escapeHtml(title)}</div>
    <div class="step-grid">
      ${steps
        .map((step) => {
          return `
            <article class="step">
              <div class="step-head">
                <span>${escapeHtml(step.label)}</span>
                <strong>${escapeHtml(step.status)}</strong>
              </div>
              <dl>
                ${step.rows
                  .map((row) => {
                    return `<div><dt>${escapeHtml(row[0])}</dt><dd>${escapeHtml(row[1] ?? "")}</dd></div>`;
                  })
                  .join("")}
              </dl>
              ${step.body ? `<pre>${escapeHtml(step.body)}</pre>` : ""}
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

async function responseStep(label, response, bodyText = "") {
  return {
    label,
    status: `${response.status} ${response.statusText}`,
    rows: [
      ["url", response.url],
      ["content-type", response.headers.get("content-type")],
      ["content-length", response.headers.get("content-length")],
      ["content-range", response.headers.get("content-range")],
      ["accept-ranges", response.headers.get("accept-ranges")],
      ["etag", response.headers.get("etag")],
      ["last-modified", response.headers.get("last-modified")],
      ["cache-control", response.headers.get("cache-control")],
      ["content-encoding", response.headers.get("content-encoding")],
      ["vary", response.headers.get("vary")],
    ].filter((row) => row[1] !== null && row[1] !== ""),
    body: bodyText ? bodyText.slice(0, 1400) : "",
  };
}

async function runGet() {
  const response = await fetch(targetUrl());
  const text = await response.text();
  renderTrace("GET static asset", [await responseStep("GET", response, text)]);
}

async function runHead() {
  const response = await fetch(targetUrl(), { method: "HEAD" });
  renderTrace("HEAD static asset", [await responseStep("HEAD", response)]);
}

async function runRange() {
  const start = Number.parseInt(rangeStart.value, 10);
  const end = Number.parseInt(rangeEnd.value, 10);
  const safeStart = Number.isFinite(start) && start >= 0 ? start : 0;
  const safeEnd = Number.isFinite(end) && end >= safeStart ? end : safeStart + 31;
  const rangeHeader = `bytes=${safeStart}-${safeEnd}`;
  const response = await fetch(targetUrl(), { headers: { Range: rangeHeader } });
  const text = await response.text();
  const step = await responseStep(`GET with Range: ${rangeHeader}`, response, text);
  step.rows.unshift(["request header", `Range: ${rangeHeader}`]);
  step.rows.push(["returned chars", String(text.length)]);
  renderTrace("Range proof", [step]);
}

async function runEtagRoundtrip() {
  const first = await fetch(targetUrl());
  const etag = first.headers.get("etag");
  const firstText = await first.text();
  const second = await fetch(targetUrl(), { headers: etag ? { "If-None-Match": etag } : {} });
  const secondText = await second.text();
  const firstStep = await responseStep("1. GET asset and capture ETag", first, firstText);
  const secondStep = await responseStep("2. GET with If-None-Match", second, secondText);
  firstStep.rows.push(["captured etag", etag || "(none)"]);
  secondStep.rows.unshift(["request header", etag ? `If-None-Match: ${etag}` : "(etag missing)"]);
  secondStep.rows.push(["roundtrip result", second.status === 304 ? "validator matched; body intentionally empty" : "validator did not produce 304"]);
  renderTrace("ETag roundtrip proof", [firstStep, secondStep]);
}

function refreshFrame() {
  frame.src = targetUrl();
}

async function guard(action) {
  try {
    await action();
  } catch (error) {
    renderTrace("Experiment failed", [
      {
        label: "error",
        status: "failed",
        rows: [["message", String(error && error.message ? error.message : error)]],
        body: String(error && error.stack ? error.stack : ""),
      },
    ]);
  }
}

document.querySelector("#getBtn").addEventListener("click", () => guard(runGet));
document.querySelector("#headBtn").addEventListener("click", () => guard(runHead));
document.querySelector("#rangeBtn").addEventListener("click", () => guard(runRange));
document.querySelector("#etagBtn").addEventListener("click", () => guard(runEtagRoundtrip));
document.querySelector("#refreshFrame").addEventListener("click", refreshFrame);
document.querySelector("#clearBtn").addEventListener("click", () => {
  trace.innerHTML = '<div class="empty-state">Run Range proof or ETag roundtrip to see the request/response chain.</div>';
});
assetPath.addEventListener("change", refreshFrame);
originInput.addEventListener("change", refreshFrame);

refreshFrame();
