# Parser, Handler, Connection, Worker, Loop, and WebSocket Package Matrix

Date: 2026-05-06

This matrix records the current Tigrcorn feature-row posture for parser, handler, connection, standalone worker, runtime loop, and WebSocket package surfaces.

The intent is to separate:

- package-owned Tigrcorn implementations
- supported third-party peer or certification packages
- explicitly unsupported or out-of-boundary selector surfaces

`implementation_status` is the feature-row value carried in `.ssot/registry.json`.

| feature_id | family | surface | tigrcorn implementation | external package or peer | implementation_status | boundary posture |
|---|---|---|---|---|---|---|
| `feat:http1-parser-owned` | parser | HTTP/1.1 request parser | `tigrcorn_protocols.http1.parser` | - | `implemented` | current |
| `feat:http1-parser-h11-peer-fixture` | parser | HTTP/1.1 peer fixture surface | - | `h11` | `implemented` | current |
| `feat:http1-parser-httptools-selector` | parser | selectable HTTP/1.1 parser backend | - | `httptools` | `absent` | out of bounds |
| `feat:http2-connection-handler-owned` | handler | HTTP/2 connection handler | `tigrcorn_protocols.http2.handler.HTTP2ConnectionHandler` | - | `implemented` | current |
| `feat:http2-connection-state-owned` | connection | HTTP/2 connection state | `tigrcorn_protocols.http2.state.H2ConnectionState` | - | `implemented` | current |
| `feat:http3-connection-core-owned` | connection | HTTP/3 connection core | `tigrcorn_protocols.http3.streams.HTTP3ConnectionCore` | - | `implemented` | current |
| `feat:http3-connection-state-owned` | connection | HTTP/3 connection state | `tigrcorn_protocols.http3.state.HTTP3ConnectionState` | - | `implemented` | current |
| `feat:quic-connection-owned` | connection | QUIC connection transport | `tigrcorn_transports.quic.connection.QuicConnection` | - | `implemented` | current |
| `feat:websocket-handler-owned` | handler | WebSocket connection handler | `tigrcorn_protocols.websocket.handler.WebSocketConnectionHandler` | - | `implemented` | current |
| `feat:websocket-h2-session-owned` | connection | WebSocket over HTTP/2 session | `tigrcorn_protocols.http2.websocket.H2WebSocketSession` | - | `implemented` | current |
| `feat:websocket-h3-session-owned` | connection | WebSocket over HTTP/3 session | `tigrcorn_protocols.http3.websocket.H3WebSocketSession` | - | `implemented` | current |
| `feat:runtime-loop-auto` | loop | runtime auto selector | `tigrcorn_runtime.server.bootstrap.run_coro_with_runtime` | optional `uvloop` preference | `implemented` | current |
| `feat:runtime-loop-asyncio` | loop | asyncio runtime loop | `tigrcorn_runtime.server.bootstrap.run_coro_with_runtime` | `asyncio` | `implemented` | current |
| `feat:runtime-loop-uvloop` | loop | uvloop runtime loop | `tigrcorn_runtime.server.bootstrap.run_coro_with_runtime` | `uvloop` | `implemented` | current |
| `feat:runtime-loop-trio` | loop | trio runtime loop | - | `trio` | `absent` | out of bounds |
| `feat:worker-class-local` | standalone worker | in-process local worker class | default `worker_class=local` runtime posture | - | `implemented` | current |
| `feat:worker-class-process-supervisor` | standalone worker | multi-process supervisor | `tigrcorn_runtime.server.supervisor.ServerSupervisor` and `tigrcorn_runtime.workers.supervisor.WorkerSupervisor` | - | `implemented` | current |
| `feat:worker-class-process-worker` | standalone worker | process worker instance | `tigrcorn_runtime.workers.process.ProcessWorker` | - | `implemented` | current |
| `feat:worker-reloader-polling` | standalone worker | reload child-process watcher | `tigrcorn_runtime.server.reloader.PollingReloader` | - | `implemented` | current |
| `feat:websocket-package-websockets-peer` | websocket package | independent peer client and certification tooling | - | `websockets` | `implemented` | current |
| `feat:websocket-package-wsproto-peer` | websocket package | independent peer codec and certification tooling | - | `wsproto` | `implemented` | current |
| `feat:websocket-package-websockets-sansio` | websocket package | selectable WebSocket engine surface | - | `websockets-sansio` | `absent` | out of bounds |

## Notes

- Tigrcorn owns the parser, handler, connection, and runtime implementations listed above where a module or class name is present in the `tigrcorn implementation` column.
- `h11`, `websockets`, and `wsproto` are preserved as external peer or certification tooling surfaces; they are not the public Tigrcorn runtime parser or WebSocket engine boundary.
- `httptools`, `websockets-sansio`, and `trio` are included here because they are relevant comparison or selector surfaces, but the current Tigrcorn boundary does not expose them as supported runtime choices.
