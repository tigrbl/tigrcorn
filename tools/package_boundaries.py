from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PackageBoundary:
    distribution: str
    import_name: str
    layer: int
    owns: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()


PACKAGE_BOUNDARIES: tuple[PackageBoundary, ...] = (
    PackageBoundary(
        distribution="tigrcorn-core",
        import_name="tigrcorn_core",
        layer=0,
        owns=("constants", "errors", "types", "utils primitives"),
    ),
    PackageBoundary(
        distribution="tigrcorn-config",
        import_name="tigrcorn_config",
        layer=1,
        owns=("config models", "normalization", "validation", "profiles", "env and file loading"),
        depends_on=("tigrcorn-core",),
        optional_dependencies=("PyYAML",),
    ),
    PackageBoundary(
        distribution="tigrcorn-http",
        import_name="tigrcorn_http",
        layer=1,
        owns=("structured fields", "range requests", "entity validators", "alt-svc", "early hints"),
        depends_on=("tigrcorn-core",),
        optional_dependencies=("brotli",),
    ),
    PackageBoundary(
        distribution="tigrcorn-asgi",
        import_name="tigrcorn_asgi",
        layer=1,
        owns=("ASGI scopes", "ASGI events", "receive/send channels", "extensions", "connection state"),
        depends_on=("tigrcorn-core",),
    ),
    PackageBoundary(
        distribution="tigrcorn-contract",
        import_name="tigrcorn_contract",
        layer=2,
        owns=("native contract app markers", "contract scope validation", "contract event validation", "boundary classification"),
        depends_on=("tigrcorn-core", "tigrcorn-asgi", "tigr-asgi-contract"),
    ),
    PackageBoundary(
        distribution="tigrcorn-transports",
        import_name="tigrcorn_transports",
        layer=2,
        owns=("listener registry", "tcp", "udp", "unix", "pipe", "inproc", "quic transport primitives"),
        depends_on=("tigrcorn-core", "tigrcorn-config"),
    ),
    PackageBoundary(
        distribution="tigrcorn-security",
        import_name="tigrcorn_security",
        layer=2,
        owns=("tls", "tls13", "x509", "alpn", "cipher policy", "certificate helpers"),
        depends_on=("tigrcorn-core", "tigrcorn-config"),
        optional_dependencies=("cryptography",),
    ),
    PackageBoundary(
        distribution="tigrcorn-protocols",
        import_name="tigrcorn_protocols",
        layer=3,
        owns=(
            "http1",
            "http2",
            "http3",
            "websocket",
            "lifespan",
            "rawframed",
            "custom protocols",
            "flow control",
            "scheduler primitives",
            "sessions",
            "streams",
        ),
        depends_on=("tigrcorn-core", "tigrcorn-config", "tigrcorn-asgi", "tigrcorn-http", "tigrcorn-transports"),
    ),
    PackageBoundary(
        distribution="tigrcorn-static",
        import_name="tigrcorn_static",
        layer=3,
        owns=("static origin", "pathsend", "file-send behavior"),
        depends_on=("tigrcorn-core", "tigrcorn-asgi", "tigrcorn-http"),
    ),
    PackageBoundary(
        distribution="tigrcorn-observability",
        import_name="tigrcorn_observability",
        layer=3,
        owns=("logging", "metrics", "tracing", "evidence metadata export"),
        depends_on=("tigrcorn-core", "tigrcorn-config"),
    ),
    PackageBoundary(
        distribution="tigrcorn-runtime",
        import_name="tigrcorn_runtime",
        layer=4,
        owns=("server runner", "app loading", "bootstrap", "signals", "shutdown", "workers", "embedding", "cli"),
        depends_on=(
            "tigrcorn-core",
            "tigrcorn-config",
            "tigrcorn-asgi",
            "tigrcorn-transports",
            "tigrcorn-protocols",
            "tigrcorn-security",
        ),
        optional_dependencies=("uvloop", "trio"),
    ),
    PackageBoundary(
        distribution="tigrcorn-compat",
        import_name="tigrcorn_compat",
        layer=5,
        owns=("uvicorn interop", "hypercorn interop", "ASGI3 probes", "conformance helpers", "interop cli support"),
        depends_on=("tigrcorn-core", "tigrcorn-asgi", "tigrcorn-runtime"),
    ),
    PackageBoundary(
        distribution="tigrcorn-certification",
        import_name="tigrcorn_certification",
        layer=6,
        owns=("release gates", "certification environment", "external peer matrices", "strict promotion checks"),
        depends_on=("tigrcorn-compat", "tigrcorn-runtime"),
        optional_dependencies=("aioquic", "h2", "websockets", "wsproto", "cryptography"),
    ),
)


PACKAGE_BY_DISTRIBUTION = {boundary.distribution: boundary for boundary in PACKAGE_BOUNDARIES}


def workspace_distributions() -> tuple[str, ...]:
    return tuple(boundary.distribution for boundary in PACKAGE_BOUNDARIES)
