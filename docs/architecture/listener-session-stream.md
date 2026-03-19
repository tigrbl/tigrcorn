# Listener / session / stream

A **listener** binds an address and accepts new work.

A **session** represents a transport-level conversation, such as:

- one TCP connection
- one Unix domain socket connection
- one QUIC UDP conversation

A **stream** represents a logical sub-channel within a session.

Examples:

- HTTP/1.1: one session, one active request stream at a time
- HTTP/2: one session, many concurrent streams
- HTTP/3 over the bundled QUIC transport: one session, many bidirectional or unidirectional streams
- raw framed custom transports: one session with protocol-defined message boundaries

This archive implements all of those structural layers today.
What is still missing is package-wide certification closure for the remaining HTTP/3 / QUIC surface gaps beyond the shipped OpenSSL QUIC handshake evidence.
