# Delivery notes for the pyproject metadata and development dependency update

This checkpoint updates packaging metadata and developer-environment dependency provisioning.

## Changes applied

- updated the package author metadata in `pyproject.toml` to **Jacob Stewart** (`jacob@swarmauri.com`)
- added a `dev` optional dependency extra in `pyproject.toml`
- retained the existing `certification` optional dependency extra unchanged

The new `dev` extra contains:

- `pytest>=8.0`
- `aioquic>=1.3.0`
- `h2>=4.1.0`
- `websockets>=12.0`
- `wsproto>=1.3.0`

## Intended installation path

Use the following command to provision a contributor / certification-oriented development environment:

```bash
pip install -e ".[dev]"
```

The existing certification-only installation path remains valid:

```bash
pip install -e ".[certification]"
```

## Current repository state after this update

This update improves packaging and development-environment readiness for the remaining strict-certification work, especially the preserved HTTP/3 third-party scenarios that require `aioquic` and `wsproto`.

It does **not** by itself make the package certifiably fully featured under the stricter non-authoritative promotion target, and it does **not** by itself make the package certifiably fully RFC compliant under that stricter target.

The repository still has the same four preserved-but-non-passing HTTP/3 `aioquic` strict-target scenarios documented in `CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/STRICT_PROFILE_TARGET.md`:

- `websocket-http3-server-aioquic-client-permessage-deflate`
- `http3-connect-relay-aioquic-client`
- `http3-trailer-fields-aioquic-client`
- `http3-content-coding-aioquic-client`

Those scenarios still need to execute successfully and be preserved as passing independent artifacts before the strict target can honestly turn green.
