<div align="center">
<h1>@tigrcorn/wt-peer-probes</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>Browser WebTransport peer probes for validating Tigrcorn HTTP/3, QUIC, datagram, and stream behavior across desktop and mobile peers.</strong></p>

<a href="https://www.npmjs.com/package/@tigrcorn/wt-peer-probes"><img alt="npm version for @tigrcorn/wt-peer-probes" src="https://img.shields.io/npm/v/%40tigrcorn%2Fwt-peer-probes?label=npm"></a>
<a href="https://www.npmjs.com/package/@tigrcorn/wt-peer-probes"><img alt="@tigrcorn/wt-peer-probes package on npm" src="https://img.shields.io/badge/package-npm-cb3837"></a>
<a href="https://www.npmjs.com/package/@tigrcorn/wt-peer-probes"><img alt="npm downloads for @tigrcorn/wt-peer-probes" src="https://img.shields.io/npm/dm/%40tigrcorn%2Fwt-peer-probes?label=downloads"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/packages/wt-peer-probes/README.md"><img alt="Hits for wt-peer-probes README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/packages/wt-peer-probes/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="package.json"><img alt="TypeScript ESM browser package" src="https://img.shields.io/badge/runtime-TypeScript%20ESM-3178c6"></a>
<a href="https://www.npmjs.com/package/@tigrcorn/wt-peer-probes"><img alt="webtransport probes role package" src="https://img.shields.io/badge/role-webtransport_probes-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## Install

```bash
npm install @tigrcorn/wt-peer-probes
```

Use the root [tigrcorn](https://github.com/tigrbl/tigrcorn) repository when you want the full Python server, SSOT, certification, and operator surfaces. Install <code>@tigrcorn/wt-peer-probes</code> directly when you want only the browser-side WebTransport peer probe package and its declared npm dependencies.

## What It Owns

<code>@tigrcorn/wt-peer-probes</code> owns the browser probe client, probe-stage reporting, Playwright peer-matrix entrypoints, and the reusable TypeScript contract for Tigrcorn WebTransport validation runs. Its published entrypoint is the npm package <code>@tigrcorn/wt-peer-probes</code>, and its browser-facing export surface is the <code>runTigrcornWTPeerProbe</code> entrypoint in <code>dist/index.js</code> with matching types in <code>dist/index.d.ts</code>.

This package page is written for developers searching for Tigrcorn WebTransport probes, browser peer validation, HTTP/3 and QUIC interoperability checks, desktop and mobile peer matrices, and Apache 2.0 licensed test infrastructure.

## Use It When

Use <code>@tigrcorn/wt-peer-probes</code> when you need a browser-controlled WebTransport client that can verify Tigrcorn's bidirectional streams, unidirectional streams, datagrams, ready-state transitions, and close behavior against the same live protocol contract used by Tigrcorn's SSOT and Playwright evidence rails.

## Import Surface

```ts
import { runTigrcornWTPeerProbe } from "@tigrcorn/wt-peer-probes";

const report = await runTigrcornWTPeerProbe({
  peerId: "chrome-desktop-01",
  wtUrl: "https://api.example.com/__tigrcorn/probe/wt",
  reportUrl: "https://api.example.com/__tigrcorn/probe/wt/report",
  timeoutMs: 5000,
});

console.log(report.ok, report);
```

The package exposes its supported public surface through the npm import <code>@tigrcorn/wt-peer-probes</code>. The root Tigrcorn repo keeps the Python server, docs, SSOT, and workflow rails that this browser package validates.

## Probe Contract

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

## Expected Tigrcorn Behavior

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

## Playwright Peer Matrix

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

The peer API protocol test runs the package's browser entrypoint against a WebTransport-compatible peer harness and verifies the same Tigrcorn protocol messages used by the live endpoint: <code>probe.bidi.echo</code>, <code>probe.unidi.send</code>, and <code>probe.datagram.echo</code>.

Live endpoint probes are available when Tigrcorn is serving WebTransport:

```bash
TIGRCORN_WT_LIVE=1 TIGRCORN_ORIGIN=https://api.example.com npm run probe:playwright
```

Safari/WebKit failures are recorded as WT failures, not hidden behind WSS fallback.

## Package Graph

[tigrcorn repo](https://github.com/tigrbl/tigrcorn) | [tigrcorn PyPI package](https://pypi.org/project/tigrcorn/) | [@tigrcorn/wt-peer-probes on npm](https://www.npmjs.com/package/@tigrcorn/wt-peer-probes) | [SSOT registry](https://github.com/tigrbl/tigrcorn/blob/master/.ssot/registry.json) | [publish workflow](https://github.com/tigrbl/tigrcorn/blob/master/.github/workflows/publish-all-packages.yml)
