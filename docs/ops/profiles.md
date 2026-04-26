# Blessed Deployment Profiles

This page is the operator-facing reference for the Phase 1 blessed deployment profiles.

These profiles do not widen the current certification boundary. They freeze explicit in-bound posture inside the existing T/P/A/D/R package surface.

| Profile | RFC targets | Protocol posture | Trusted proxy behavior | Static serving | Early data | QUIC/H3 | Description |
|---|---|---|---|---|---|---|---|
| `default` | RFC 9112 | `http1-only` | `disabled` | `disabled` | `deny_or_not_applicable` | `disabled` | Safe zero-config baseline with a single TCP HTTP/1.1 listener and deny-by-default transport posture. |
| `strict-h1-origin` | RFC 9112, RFC 7232, RFC 7233 | `http1-origin` | `deny_untrusted_forwarded_headers` | `disabled_until_mount_configured` | `not_applicable` | `disabled` | Conservative HTTP/1.1 origin posture with explicit host validation, static disabled unless mounted, and no proxy trust by default. |
| `strict-h2-origin` | RFC 9112, RFC 7232, RFC 7233, RFC 9113, RFC 8446, RFC 7301 | `h2-origin` | `deny_untrusted_forwarded_headers` | `disabled_until_mount_configured` | `not_applicable` | `disabled` | TLS-backed HTTP/2 origin posture with explicit ALPN and h2-only protocol selection. |
| `strict-h3-edge` | RFC 9112, RFC 7232, RFC 7233, RFC 9113, RFC 8446, RFC 7301, RFC 9114, RFC 9000, RFC 9001, RFC 9002, RFC 7838 Section 3 | `h2-h3-edge` | `deny_untrusted_forwarded_headers` | `disabled_until_mount_configured` | `deny` | `enabled` | Dual TCP+UDP edge posture with explicit HTTP/3 and QUIC listeners, automatic Alt-Svc, Retry, and default 0-RTT denial. |
| `strict-mtls-origin` | RFC 9112, RFC 7232, RFC 7233, RFC 9113, RFC 8446, RFC 7301, RFC 5280 | `h2-mtls-origin` | `deny_untrusted_forwarded_headers` | `disabled_until_mount_configured` | `not_applicable` | `disabled` | HTTP/2 TLS origin posture with mandatory client certificates and explicit trust-store requirements. |
| `static-origin` | RFC 9112, RFC 7232, RFC 7233, RFC 9110 Section 8 | `http1-static-origin` | `deny_untrusted_forwarded_headers` | `enabled_when_mount_present` | `not_applicable` | `disabled` | Static origin posture with explicit mounted delivery, index handling, validators, range support, and no proxy trust by default. |

## Consumption

- Use `tigrcorn --config src/tigrcorn/profiles/default.profile.json` for the boring safe baseline.
- Use `tigrcorn --config src/tigrcorn/profiles/strict-h3-edge.profile.json --ssl-certfile cert.pem --ssl-keyfile key.pem` for the explicit H3 edge posture.
- Use `app.profile` in a config file or `build_config(profile=...)` in code when you want the runtime to resolve the blessed profile before applying overrides.

## Required overrides

- `strict-h2-origin`: `tls.certfile`, `tls.keyfile`
- `strict-h3-edge`: `tls.certfile`, `tls.keyfile`
- `strict-mtls-origin`: `tls.certfile`, `tls.keyfile`, `tls.ca_certs`
- `static-origin`: `static.mount`

## Conformance bundles

- Machine-readable profile bundles: `docs/conformance/profile_bundles.json`
- Runtime artifacts: `src/tigrcorn/profiles/*.profile.json`
