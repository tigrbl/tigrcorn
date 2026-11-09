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

Use the root [tigrcorn](https://github.com/tigrbl/tigrcorn) repository when you want the full Python server, SSOT, certification, and operator surfaces. Install `@tigrcorn/wt-peer-probes` directly when you want only the browser-side WebTransport peer probe package and its declared npm dependencies.

## What It Owns

`@tigrcorn/wt-peer-probes` owns the browser probe client, probe-stage reporting, Playwright peer-matrix entrypoints, and the reusable TypeScript contract for Tigrcorn WebTransport validation runs. Its published entrypoint is the npm package `@tigrcorn/wt-peer-probes`, and its browser-facing export surface is the `runTigrcornWTPeerProbe` entrypoint in `dist/index.js` with matching types in `dist/index.d.ts`.

This package page is written for developers searching for Tigrcorn WebTransport probes, browser peer validation, HTTP/3 and QUIC interoperability checks, desktop and mobile peer matrices, and Apache 2.0 licensed test infrastructure.

## Why Use This?

Use `@tigrcorn/wt-peer-probes` when you need a browser-controlled WebTransport client that checks the same protocol contract Tigrcorn uses for SSOT-backed probe evidence. It is the package to reach for when you want to validate browser readiness, bidirectional streams, unidirectional streams, datagrams, and close behavior without pulling the Python runtime into the test client itself.

## FAQ

### What does this package export?

It exports `runTigrcornWTPeerProbe` plus the probe report and option types through the `@tigrcorn/wt-peer-probes` npm import.

### Which workflows does it cover?

It covers browser-side WebTransport probe execution, stage-by-stage readiness reporting, Playwright-driven peer validation, and live probe submission back to Tigrcorn report endpoints.

### What does it intentionally avoid?

It does not own Tigrcorn's server runtime, SSOT registry, HTTP routing, or release-gate logic. It is a browser peer package that verifies those surfaces from the outside.

## Features

- Runs a single reusable WebTransport probe flow across Chromium, Firefox, WebKit/Safari, and mobile peer projects.
- Verifies the `api -> ready -> bidi -> unidi -> datagram -> close` probe progression used by Tigrcorn's live WebTransport endpoint.
- Ships typed ESM exports for browser and Playwright consumers.
- Keeps peer evidence aligned with Tigrcorn SSOT feature rows and Playwright matrix workflows.
- Publishes through npm with a small browser-facing surface instead of bundling server code.

## Use It When

Use `@tigrcorn/wt-peer-probes` when you need a portable browser package for WebTransport compatibility checks, regression probes, or live-endpoint evidence collection. It is the npm boundary that complements Tigrcorn's Python runtime and certification packages.

## Import Surface

```ts
import { runTigrcornWTPeerProbe } from "@tigrcorn/wt-peer-probes";

const report = await runTigrcornWTPeerProbe({
  peerId: "chrome-desktop-01",
  wtUrl: "https://api.example.com/__tigrcorn/probe/wt",
  reportUrl: "https://api.example.com/__tigrcorn/probe/wt/report",
  timeoutMs: 5000,
});

console.log(report.ok, report.stageResults);
```

The package exposes its supported public surface through the npm import `@tigrcorn/wt-peer-probes`. The root Tigrcorn repo keeps the Python server, docs, SSOT, and workflow rails that this browser package validates.

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

## Usage

### Run the Playwright peer matrix

```bash
npm run test:peer-api
```

Projects included:

| Browser peer | SSOT feature | Runnable test |
| --- | --- | --- |
| Chromium | `feat:webtransport-peer-probe-chromium` | `npm run test:peer-api -- --project=chromium` |
| Firefox | `feat:webtransport-peer-probe-firefox` | `npm run test:peer-api -- --project=firefox` |
| WebKit/Safari | `feat:webtransport-peer-probe-webkit` | `npm run test:peer-api -- --project=webkit` |
| Mobile Chrome | `feat:webtransport-peer-probe-mobile-chrome` | `npm run test:peer-api -- --project=mobile-chrome` |
| Mobile Safari | `feat:webtransport-peer-probe-mobile-safari` | `npm run test:peer-api -- --project=mobile-safari` |

### Run against a live Tigrcorn WebTransport endpoint

```bash
TIGRCORN_WT_LIVE=1 TIGRCORN_ORIGIN=https://api.example.com npm run probe:playwright
```

Safari and WebKit failures are recorded as WebTransport failures, not hidden behind WebSocket fallback.

## Related Packages

- [tigrcorn](https://pypi.org/project/tigrcorn/)
- [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)
- [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/)
- [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/)

## Package Graph

[tigrcorn repo](https://github.com/tigrbl/tigrcorn) | [tigrcorn on PyPI](https://pypi.org/project/tigrcorn/) | [@tigrcorn/wt-peer-probes on npm](https://www.npmjs.com/package/@tigrcorn/wt-peer-probes) | [SSOT registry](https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json) | [publish workflow](https://github.com/tigrbl/tigrcorn/blob/master/.github/workflows/publish-all-packages.yml)

## Best Practices

- Keep the probe message contract aligned with the server-side WebTransport probe endpoint before changing browser tests.
- Treat peer-matrix failures as compatibility evidence, not as reasons to silently widen fallback behavior.
- Publish browser-facing API changes together with matching Playwright coverage and SSOT feature updates.

## License

Apache-2.0
