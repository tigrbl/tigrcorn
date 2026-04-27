const readyPill = document.querySelector("#ready-pill");
const startupCount = document.querySelector("#startup-count");
const shutdownCount = document.querySelector("#shutdown-count");
const requestCount = document.querySelector("#request-count");
const uptime = document.querySelector("#uptime");
const output = document.querySelector("#state-output");
const eventList = document.querySelector("#event-list");
const autopoll = document.querySelector("#autopoll");

function secondsSince(epochSeconds) {
  if (!epochSeconds) {
    return "0s";
  }
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

function formatClock(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function render(state) {
  readyPill.textContent = state.ready ? "ready" : "not ready";
  readyPill.classList.toggle("online", Boolean(state.ready));
  readyPill.classList.toggle("offline", !state.ready);
  startupCount.textContent = state.startup_count;
  shutdownCount.textContent = state.shutdown_count;
  requestCount.textContent = state.request_count;
  uptime.textContent = secondsSince(state.started_at);
  output.textContent = JSON.stringify(state, null, 2);

  eventList.replaceChildren(...state.events.slice().reverse().map((entry) => {
    const item = document.createElement("li");
    const label = document.createElement("span");
    const time = document.createElement("time");
    label.textContent = entry.event;
    time.textContent = formatClock(entry.at);
    item.append(label, time);
    return item;
  }));
}

async function refreshState() {
  try {
    const response = await fetch("/state", {cache: "no-store"});
    render(await response.json());
  } catch (error) {
    readyPill.textContent = "offline";
    readyPill.classList.remove("online");
    readyPill.classList.add("offline");
    output.textContent = error.stack || String(error);
  }
}

document.querySelector("#refresh").addEventListener("click", refreshState);

setInterval(() => {
  if (autopoll.checked) {
    refreshState();
  }
}, 1500);

refreshState();
