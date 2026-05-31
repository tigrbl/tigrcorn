# Optional dependency surface

This document records the declared installation paths for optional feature surfaces that are intentionally not part of the minimal base dependency set.

## Declared extras

| Extra | Installs | Public status in this checkpoint | Purpose |
| --- | --- | --- | --- |
| `tls-x509` | `cryptography` | supported | Enable package-owned TLS/X.509 validation, certificate handling, and OCSP/CRL helpers |
| `config-yaml` | `PyYAML` | supported | Enable `.yaml` / `.yml` config loading |
| `compression` | `brotli` | supported | Enable Brotli content coding and `.br` static sidecars |
| `runtime-uvloop` | `uvloop` | supported | Enable `--runtime uvloop` |
| `runtime-trio` | `trio` | declared but not publicly supported | Reserved dependency path for future/internal trio work |
| `full-featured` | `cryptography`, `PyYAML`, `brotli`, `uvloop` | supported | Aggregate the current public optional operator feature surface |
| `certification` | `cryptography`, `aioquic`, `h2`, `websockets`, `wsproto` | supported | Certification/interoperability tooling, TLS/X.509 validation, and preserved peer paths |
| `dev` | `pytest` plus the current public optional feature surface and certification extras | supported | Repository development and checkpoint validation |

## Installation commands

Minimal editable install:

```bash
python -m pip install -e .
```

Current public optional feature bundle:

```bash
python -m pip install -e ".[full-featured]"
```

Selective installs:

```bash
python -m pip install -e ".[tls-x509]"
python -m pip install -e ".[config-yaml]"
python -m pip install -e ".[compression]"
python -m pip install -e ".[runtime-uvloop]"
```

Certification / repository-development workflow:

```bash
python -m pip install -e ".[certification,dev]"
```

Reserved trio dependency path:

```bash
python -m pip install -e ".[runtime-trio]"
```

Declaring `runtime-trio` does **not** change the supported runtime contract for this checkpoint. The public runtime surface remains `auto`, `asyncio`, and `uvloop`.

## Runtime and feature notes

- TLS/X.509, certificate-chain validation, OCSP/CRL, and certificate-material helpers raise installation hints that point to `tigrcorn[tls-x509]` when `cryptography` is absent.
- YAML config loading raises an installation hint that points to `tigrcorn[config-yaml]` when `PyYAML` is absent.
- Brotli content coding raises an installation hint that points to `tigrcorn[compression]` when `brotli` is absent.
- `--runtime uvloop` raises an installation hint that points to `tigrcorn[runtime-uvloop]` when `uvloop` is absent.
- `--runtime trio` is intentionally not accepted by the CLI or config validators in this checkpoint.
