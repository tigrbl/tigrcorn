import type { WTPeerProbeOptions, WTPeerProbeReport } from "./types";

const enc = new TextEncoder();
const dec = new TextDecoder();

function browserHints(): Record<string, unknown> | undefined {
  const nav = navigator as Navigator & {
    userAgentData?: { toJSON?: () => Record<string, unknown> };
  };
  return nav.userAgentData?.toJSON?.();
}

async function timeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  return Promise.race([
    p,
    new Promise<T>((_, reject) => {
      globalThis.setTimeout(() => reject(new Error(`${label} timeout after ${ms}ms`)), ms);
    }),
  ]);
}

function newReport(opts: Required<Pick<WTPeerProbeOptions, "peerId" | "wtUrl">>): WTPeerProbeReport {
  return {
    probe: "tigrcorn.wt.peer",
    version: 1,
    peerId: opts.peerId,
    runId: crypto.randomUUID(),
    wtUrl: opts.wtUrl,
    userAgent: navigator.userAgent,
    platform: navigator.platform,
    browserHints: browserHints(),
    stages: {
      api: "fail",
      ready: "skip",
      bidi: "skip",
      unidi: "skip",
      datagram: "skip",
      close: "skip",
    },
    timingsMs: {},
    errors: {},
    ok: false,
  };
}

export async function runTigrcornWTPeerProbe(opts: WTPeerProbeOptions): Promise<WTPeerProbeReport> {
  const timeoutMs = opts.timeoutMs ?? 5_000;
  const requireDatagram = opts.requireDatagram ?? true;
  const report = newReport({ peerId: opts.peerId, wtUrl: opts.wtUrl });
  const mark = () => performance.now();

  if (!("WebTransport" in globalThis)) {
    report.errors.api = "WebTransport API unavailable";
    await postReportMaybe(opts.reportUrl, report);
    return report;
  }

  report.stages.api = "pass";

  let wt: WebTransport | undefined;

  try {
    let t0 = mark();
    wt = new WebTransport(opts.wtUrl);
    await timeout(wt.ready, timeoutMs, "wt.ready");
    report.timingsMs.ready = mark() - t0;
    report.stages.ready = "pass";

    t0 = mark();
    await probeBidi(wt, report.runId, opts.peerId, timeoutMs);
    report.timingsMs.bidi = mark() - t0;
    report.stages.bidi = "pass";

    t0 = mark();
    await probeUnidi(wt, report.runId, opts.peerId, timeoutMs);
    report.timingsMs.unidi = mark() - t0;
    report.stages.unidi = "pass";

    t0 = mark();
    try {
      await probeDatagram(wt, report.runId, opts.peerId, timeoutMs);
      report.timingsMs.datagram = mark() - t0;
      report.stages.datagram = "pass";
    } catch (err) {
      report.stages.datagram = requireDatagram ? "fail" : "skip";
      report.errors.datagram = err instanceof Error ? err.message : String(err);
      if (requireDatagram) throw err;
    }

    t0 = mark();
    wt.close({ closeCode: 0, reason: "probe complete" });
    await timeout(wt.closed, timeoutMs, "wt.closed");
    report.timingsMs.close = mark() - t0;
    report.stages.close = "pass";

    report.ok =
      report.stages.api === "pass" &&
      report.stages.ready === "pass" &&
      report.stages.bidi === "pass" &&
      report.stages.unidi === "pass" &&
      (report.stages.datagram === "pass" || (!requireDatagram && report.stages.datagram === "skip")) &&
      report.stages.close === "pass";
  } catch (err) {
    const failed =
      report.stages.ready !== "pass" ? "ready" :
      report.stages.bidi !== "pass" ? "bidi" :
      report.stages.unidi !== "pass" ? "unidi" :
      report.stages.datagram !== "pass" && requireDatagram ? "datagram" :
      "close";

    report.stages[failed] = "fail";
    report.errors[failed] = err instanceof Error ? err.message : String(err);

    try {
      wt?.close({ closeCode: 1, reason: "probe failed" });
    } catch {
      // ignored: closing a failed transport can itself throw in browser implementations
    }
  }

  await postReportMaybe(opts.reportUrl, report);
  return report;
}

async function probeBidi(wt: WebTransport, runId: string, peerId: string, timeoutMs: number): Promise<void> {
  const stream = await timeout(wt.createBidirectionalStream(), timeoutMs, "createBidirectionalStream");
  const id = crypto.randomUUID();
  const payload = { type: "probe.bidi.echo", id, runId, peerId, ts: Date.now() };

  const writer = stream.writable.getWriter();
  const reader = stream.readable.getReader();

  try {
    await writer.write(enc.encode(JSON.stringify(payload)));
    await writer.close();

    const read = await timeout(reader.read(), timeoutMs, "bidi read");
    const body = read.value ? JSON.parse(dec.decode(read.value)) : null;

    if (body?.id !== id || body?.type !== "probe.bidi.echo.ok") {
      throw new Error("invalid bidi echo response");
    }
  } finally {
    writer.releaseLock();
    reader.releaseLock();
  }
}

async function probeUnidi(wt: WebTransport, runId: string, peerId: string, timeoutMs: number): Promise<void> {
  const stream = await timeout(wt.createUnidirectionalStream(), timeoutMs, "createUnidirectionalStream");
  const id = crypto.randomUUID();
  const payload = { type: "probe.unidi.send", id, runId, peerId, ts: Date.now() };

  const writer = stream.getWriter();
  try {
    await writer.write(enc.encode(JSON.stringify(payload)));
    await writer.close();
  } finally {
    writer.releaseLock();
  }

  const incomingReader = wt.incomingUnidirectionalStreams.getReader();
  try {
    const serverStream = await timeout(incomingReader.read(), timeoutMs, "incoming unidi ack");
    if (!serverStream.value) throw new Error("missing unidi ack stream");

    const ackReader = serverStream.value.getReader();
    try {
      const ack = await timeout(ackReader.read(), timeoutMs, "unidi ack read");
      const body = ack.value ? JSON.parse(dec.decode(ack.value)) : null;

      if (body?.id !== id || body?.type !== "probe.unidi.ack") {
        throw new Error("invalid unidi ack");
      }
    } finally {
      ackReader.releaseLock();
    }
  } finally {
    incomingReader.releaseLock();
  }
}

async function probeDatagram(wt: WebTransport, runId: string, peerId: string, timeoutMs: number): Promise<void> {
  const id = crypto.randomUUID();
  const payload = { type: "probe.datagram.echo", id, runId, peerId, ts: Date.now() };

  const writer = wt.datagrams.writable.getWriter();
  const reader = wt.datagrams.readable.getReader();

  try {
    await writer.write(enc.encode(JSON.stringify(payload)));

    const read = await timeout(reader.read(), timeoutMs, "datagram read");
    const body = read.value ? JSON.parse(dec.decode(read.value)) : null;

    if (body?.id !== id || body?.type !== "probe.datagram.echo.ok") {
      throw new Error("invalid datagram echo response");
    }
  } finally {
    writer.releaseLock();
    reader.releaseLock();
  }
}

async function postReportMaybe(url: string | undefined, report: WTPeerProbeReport): Promise<void> {
  if (!url) return;

  await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(report),
    keepalive: true,
  });
}
