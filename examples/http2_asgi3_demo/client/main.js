const pathInput = document.querySelector("#path");
const bodyInput = document.querySelector("#body");
const statusEl = document.querySelector("#status");
const streamEl = document.querySelector("#stream");
const elapsedEl = document.querySelector("#elapsed");
const versionEl = document.querySelector("#version");
const responseEl = document.querySelector("#response");
const cardsEl = document.querySelector("#cards");

function setSummary(payload) {
  statusEl.textContent = payload.status ?? "n/a";
  streamEl.textContent = payload.stream_id ?? "-";
  elapsedEl.textContent = payload.elapsed_ms ? `${payload.elapsed_ms} ms` : "-";
  versionEl.textContent = payload.body_json?.http_version ?? "-";
  responseEl.textContent = JSON.stringify(payload, null, 2);
}

async function getRequest() {
  const response = await fetch(`/api/request?path=${encodeURIComponent(pathInput.value)}`);
  setSummary(await response.json());
}

async function postRequest() {
  const response = await fetch("/api/request", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ path: "/echo", body: bodyInput.value }),
  });
  setSummary(await response.json());
}

async function multiplex() {
  const response = await fetch("/api/multiplex?count=6&path=/scope");
  const payload = await response.json();
  cardsEl.replaceChildren(
    ...payload.requests
      .sort((a, b) => a.label.localeCompare(b.label))
      .map((item) => {
        const card = document.createElement("article");
        card.innerHTML = `
          <span>${item.label}</span>
          <strong>stream ${item.stream_id}</strong>
          <small>${item.status} / ${item.elapsed_ms} ms / h${item.body_json?.http_version ?? "?"}</small>
        `;
        return card;
      }),
  );
  responseEl.textContent = JSON.stringify(payload, null, 2);
}

document.querySelector("#get").addEventListener("click", getRequest);
document.querySelector("#post").addEventListener("click", postRequest);
document.querySelector("#multiplex").addEventListener("click", multiplex);
document.querySelector("#runAll").addEventListener("click", async () => {
  await getRequest();
  await postRequest();
  await multiplex();
});
