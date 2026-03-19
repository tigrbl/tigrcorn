# ADR 0002 — separate transport and protocol

Decision: transport code and protocol code live in separate module trees.

Reason: TCP, UDP, QUIC, Unix sockets, and in-process transports should be reusable beneath
HTTP/1.1, HTTP/2, HTTP/3, WebSocket, raw framed, and custom protocols.
