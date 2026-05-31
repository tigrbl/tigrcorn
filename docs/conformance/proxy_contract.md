# Proxy Contract

This file is generated from the runtime proxy contract metadata and the current parser/default surface.

## Trust model

- `enabled_flag`: --proxy-headers
- `allowlist_flag`: --forwarded-allow-ips
- `default_trust_behavior`: ignore proxy identity headers unless proxy handling is enabled and the immediate peer is trusted
- `empty_allowlist_behavior`: when proxy handling is enabled and no allowlist is configured, only loopback peers are trusted
- `allowlist_tokens`: `*, localhost, unix, single_ip, cidr`
- `untrusted_peer_result`: preserve socket-derived client/server/scheme and the configured root_path; ignore Forwarded and X-Forwarded-* inputs

## Precedence table

| Field | Sources | Resolution |
|---|---|---|
| `client` | `Forwarded.for, X-Forwarded-For, socket peer` | first available source from a trusted immediate peer |
| `scheme` | `Forwarded.proto, X-Forwarded-Proto, listener scheme` | Forwarded beats X-Forwarded-Proto when both are present |
| `server` | `Forwarded.host, X-Forwarded-Host, listener server tuple` | Forwarded host beats X-Forwarded-Host when both are present |
| `root_path` | `configured root_path, Forwarded.path, X-Forwarded-Prefix, X-Script-Name` | configured root_path is the base prefix; trusted forwarded prefix data is normalized and appended when distinct |

## Normalization contract

- Forwarded processing uses only the first forwarded-element entry.
- X-Forwarded-* processing uses only the first CSV token.
- Host values normalize bracketed IPv6 host:port forms.
- Root paths normalize to leading-slash form and strip trailing slashes except for /.
- When both configured root_path and a trusted forwarded prefix are present, Tigrcorn composes them into a single normalized root_path.
- Scope path/raw_path stripping occurs only after the effective root_path is finalized.
