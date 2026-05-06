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
npm run test:peer-api
```

Projects included:

Umbrella SSOT feature: `feat:webtransport-peer-apis`.

| Browser peer | SSOT feature | Runnable test |
| --- | --- | --- |
| Chromium | `feat:webtransport-peer-probe-chromium` | `npm run test:peer-api -- --project=chromium` |
| Firefox | `feat:webtransport-peer-probe-firefox` | `npm run test:peer-api -- --project=firefox` |
| WebKit/Safari | `feat:webtransport-peer-probe-webkit` | `npm run test:peer-api -- --project=webkit` |
| Mobile Chrome | `feat:webtransport-peer-probe-mobile-chrome` | `npm run test:peer-api -- --project=mobile-chrome` |
| Mobile Safari | `feat:webtransport-peer-probe-mobile-safari` | `npm run test:peer-api -- --project=mobile-safari` |

The peer API protocol test runs the package's browser entrypoint against a WebTransport-compatible peer harness and verifies the same Tigrcorn protocol messages used by the live endpoint: `probe.bidi.echo`, `probe.unidi.send`, and `probe.datagram.echo`.

Live endpoint probes are available when Tigrcorn is serving WebTransport:

```bash
TIGRCORN_WT_LIVE=1 TIGRCORN_ORIGIN=https://api.example.com npm run probe:playwright
```

Safari/WebKit failures are recorded as WT failures, not hidden behind WSS fallback.
