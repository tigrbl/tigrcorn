# Custom transports

TigrCorn reserves a native extension surface for custom transports and scope types.

Examples:

- raw framed RPC over TCP
- raw framed RPC over QUIC
- in-process transports for test harnesses
- custom stream and datagram scope types

These extensions must not change the standard ASGI behavior for HTTP, WebSocket, or lifespan.
