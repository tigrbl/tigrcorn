# Tigrcorn 0.3.19

This patch release adds HTTP request-body rejection and transport admission controls.

## HTTP request bodies

- HTTP/1.1 returns 413 when a declared body or a chunked body exceeds the configured limit.
- HTTP/2 counts DATA payload bytes throughout ASGI streaming and rejects the affected stream without interrupting sibling requests.
- HTTP/3 applies the body limit independently of its 64 KiB parse-buffer guard and stops the rejected upload on its stream.

## Transport admission

- Configure connection, session, and active stream caps and open rates through the CLI, TOML, environment, or Python configuration.
- Enforce instance-wide limits across workers and reclaim leases from confirmed dead workers.
- Admission refusal stays scoped to the affected connection, session, or stream as appropriate.

These changes were merged in [PR #60](https://github.com/tigrbl/tigrcorn/pull/60).
