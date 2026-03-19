# ADR 0003 — scheduler and backpressure are separate concerns

Decision: concurrency and flow control belong in explicit scheduler and flow modules.

Reason: protocol handlers should not encode ad-hoc concurrency policy.
