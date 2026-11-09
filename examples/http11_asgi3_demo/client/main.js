const output = document.querySelector("#output");
const statusNode = document.querySelector("#status");
const titleNode = document.querySelector("#output-title");
const baseUrlInput = document.querySelector("#base-url");
const bodyInput = document.querySelector("#body-text");
const tokenInput = document.querySelector("#custom-token");

function baseUrl() {
  return baseUrlInput.value.replace(/\/+$/, "");
}

function write(title, status, value) {
  titleNode.textContent = title;
  statusNode.textContent = status;
  output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function inspect() {
  const response = await fetch(`${baseUrl()}/inspect`, {
    headers: {"x-demo-token": tokenInput.value}
  });
  write("ASGI Scope", `${response.status} ${response.statusText}`, await response.json());
}

async function echo() {
  const response = await fetch(`${baseUrl()}/echo`, {
    method: "POST",
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "x-demo-token": tokenInput.value
    },
    body: bodyInput.value
  });
  write("POST Echo", `${response.status} ${response.statusText}`, await response.json());
}

async function stream() {
  const response = await fetch(`${baseUrl()}/stream?count=6`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let body = "";
  write("Chunked Stream", `${response.status} ${response.statusText}`, "");
  while (true) {
    const {done, value} = await reader.read();
    if (done) {
      break;
    }
    body += decoder.decode(value, {stream: true});
    output.textContent = body;
  }
}

async function raw(path, title) {
  const response = await fetch(`/raw?path=${encodeURIComponent(path)}`);
  const payload = await response.json();
  write(title, "raw socket", `${payload.request}\n--- response ---\n${payload.response}`);
}

const actions = {
  inspect,
  echo,
  stream,
  trailers: () => raw("/trailers", "HTTP/1.1 Trailers"),
  early: () => raw("/early-hints", "HTTP 103 Early Hints")
};

document.querySelector(".toolbar").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }
  write("Response", "running", "");
  try {
    await actions[button.dataset.action]();
  } catch (error) {
    write("Error", "failed", error.stack || String(error));
  }
});

inspect().catch((error) => write("Startup Error", "failed", error.stack || String(error)));
