import { createServer, type Server } from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.resolve(__dirname, "..");

let server: Server;
let origin: string;

test.beforeAll(async () => {
  server = createServer(async (request, response) => {
    try {
      const requestUrl = new URL(request.url ?? "/", "http://127.0.0.1");
      const relativePath = decodeURIComponent(requestUrl.pathname).replace(/^\/+/, "") || "examples/browser.html";
      const filePath = path.resolve(packageRoot, relativePath);
      if (!filePath.startsWith(packageRoot)) {
        response.writeHead(403).end("forbidden");
        return;
      }

      const body = await readFile(filePath);
      const contentType = filePath.endsWith(".js")
        ? "text/javascript"
        : filePath.endsWith(".html")
          ? "text/html"
          : "application/octet-stream";
      response.writeHead(200, { "content-type": contentType });
      response.end(body);
    } catch {
      response.writeHead(404).end("not found");
    }
  });

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("Static probe server did not expose a TCP address.");
  }
  origin = `http://127.0.0.1:${address.port}`;
});

test.afterAll(async () => {
  await new Promise<void>((resolve, reject) => {
    server.close((error) => (error ? reject(error) : resolve()));
  });
});

test("browser peer API validates tigrcorn WebTransport protocol messages", async ({ page }, testInfo) => {
  await page.addInitScript({
    content: `
      (() => {
        const events = [];
        class AsyncQueue {
          constructor() {
            this.items = [];
            this.waiters = [];
          }
          push(value) {
            const waiter = this.waiters.shift();
            if (waiter) {
              waiter({ value, done: false });
              return;
            }
            this.items.push(value);
          }
          read() {
            const value = this.items.shift();
            if (value !== undefined) {
              return Promise.resolve({ value, done: false });
            }
            return new Promise((resolve) => this.waiters.push(resolve));
          }
        }

        const encoder = new TextEncoder();
        const decoder = new TextDecoder();
        const encode = (value) => encoder.encode(JSON.stringify(value));
        const decode = (value) => JSON.parse(decoder.decode(value));
        const oneChunkReadable = (chunk) => {
          let read = false;
          return {
            getReader() {
              return {
                read: async () => {
                  if (read) {
                    return { done: true };
                  }
                  read = true;
                  return { value: chunk, done: false };
                },
                releaseLock() {}
              };
            }
          };
        };

        class FakeWebTransport {
          constructor(url) {
            this.url = url;
            this.incoming = new AsyncQueue();
            this.datagramsIn = new AsyncQueue();
            this.ready = Promise.resolve();
            this.closed = new Promise((resolve) => {
              this.resolveClosed = resolve;
            });
            this.incomingUnidirectionalStreams = {
              getReader: () => ({
                read: () => this.incoming.read(),
                releaseLock() {}
              })
            };
            this.datagrams = {
              writable: {
                getWriter: () => ({
                  write: async (chunk) => {
                    const message = decode(chunk);
                    events.push(message);
                    this.datagramsIn.push(encode({
                      type: "probe.datagram.echo.ok",
                      id: message.id,
                      runId: message.runId,
                      peerId: message.peerId
                    }));
                  },
                  close: async () => {},
                  releaseLock() {}
                })
              },
              readable: {
                getReader: () => ({
                  read: () => this.datagramsIn.read(),
                  releaseLock() {}
                })
              }
            };
          }

          async createBidirectionalStream() {
            const responses = new AsyncQueue();
            let message;
            return {
              writable: {
                getWriter: () => ({
                  write: async (chunk) => {
                    message = decode(chunk);
                    events.push(message);
                  },
                  close: async () => {
                    responses.push(encode({
                      type: "probe.bidi.echo.ok",
                      id: message.id,
                      runId: message.runId,
                      peerId: message.peerId
                    }));
                  },
                  releaseLock() {}
                })
              },
              readable: {
                getReader: () => ({
                  read: () => responses.read(),
                  releaseLock() {}
                })
              }
            };
          }

          async createUnidirectionalStream() {
            let message;
            return {
              getWriter: () => ({
                write: async (chunk) => {
                  message = decode(chunk);
                  events.push(message);
                },
                close: async () => {
                  this.incoming.push(oneChunkReadable(encode({
                    type: "probe.unidi.ack",
                    id: message.id,
                    runId: message.runId,
                    peerId: message.peerId
                  })));
                },
                releaseLock() {}
              })
            };
          }

          close(closeInfo) {
            events.push({ type: "close", closeInfo });
            this.resolveClosed({
              closeCode: closeInfo?.closeCode ?? 0,
              reason: closeInfo?.reason ?? ""
            });
          }
        }

        Object.defineProperty(globalThis, "WebTransport", {
          value: FakeWebTransport,
          configurable: true
        });
        globalThis.__tigrcornPeerProbeEvents = events;
      })();
    `,
  });

  const peerId = testInfo.project.name;
  const wtUrl = "https://peer.example.test/__tigrcorn/probe/wt";
  const url = `${origin}/examples/browser.html?peerId=${encodeURIComponent(peerId)}&wt=${encodeURIComponent(wtUrl)}&report=`;

  await page.goto(url);
  await page.waitForFunction(() => {
    const output = document.querySelector("#out")?.textContent ?? "";
    return output.trim().startsWith("{");
  });
  const output = await page.locator("#out").textContent({ timeout: 10_000 });
  const report = JSON.parse(output ?? "{}");
  const events = await page.evaluate(() => globalThis.__tigrcornPeerProbeEvents);

  expect(report.ok, JSON.stringify(report, null, 2)).toBe(true);
  expect(report.probe).toBe("tigrcorn.wt.peer");
  expect(report.peerId).toBe(peerId);
  expect(report.wtUrl).toBe(wtUrl);
  expect(report.userAgent).toBeTruthy();

  for (const stage of ["api", "ready", "bidi", "unidi", "datagram", "close"]) {
    expect(report.stages[stage], `${peerId} ${stage}`).toBe("pass");
  }

  expect(events).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ type: "probe.bidi.echo", peerId }),
      expect.objectContaining({ type: "probe.unidi.send", peerId }),
      expect.objectContaining({ type: "probe.datagram.echo", peerId }),
      expect.objectContaining({ type: "close" }),
    ]),
  );
});
