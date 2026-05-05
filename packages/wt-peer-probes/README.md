# tigrcorn WebTransport Peer Probes

Browser peer probes for validating tigrcorn WebTransport support directly, without capability discovery.

## Probe contract

Endpoint:

```txt
https://api.example.com/__tigrcorn/probe/wt
```

Report endpoint:

```txt
https://api.example.com/__tigrcorn/probe/wt/report
```

Required pass stages:

```txt
api -> ready -> bidi -> unidi -> datagram -> close
```

## Install

```bash
npm install @tigrcorn/wt-peer-probes
```

## Use from TS/JS

```ts
import { runTigrcornWTPeerProbe } from "@tigrcorn/wt-peer-probes";

const report = await runTigrcornWTPeerProbe({
  peerId: "chrome-desktop-01",
  wtUrl: "https://api.example.com/__tigrcorn/probe/wt",
  reportUrl: "https://api.example.com/__tigrcorn/probe/wt/report",
  timeoutMs: 5000
});

console.log(report.ok, report);
```

## Expected tigrcorn behavior

On bidirectional stream:

```json
{ "type": "probe.bidi.echo", "id": "...", "runId": "...", "peerId": "..." }
```

Reply on the same stream:

```json
{ "type": "probe.bidi.echo.ok", "id": "...", "runId": "...", "peerId": "..." }
```

On client unidirectional stream:

```json
{ "type": "probe.unidi.send", "id": "...", "runId": "...", "peerId": "..." }
```

Reply on a server-created unidirectional stream:

```json
{ "type": "probe.unidi.ack", "id": "...", "runId": "...", "peerId": "..." }
```

On datagram:

```json
{ "type": "probe.datagram.echo", "id": "...", "runId": "...", "peerId": "..." }
```

Reply via datagram:

```json
{ "type": "probe.datagram.echo.ok", "id": "...", "runId": "...", "peerId": "..." }
```

## Playwright peer matrix

```bash
TIGRCORN_ORIGIN=https://api.example.com npm run probe:playwright
```

Projects included:

```txt
chromium
firefox
webkit
mobile-chrome
mobile-safari
```

Safari/WebKit failures are recorded as WT failures, not hidden behind WSS fallback.
