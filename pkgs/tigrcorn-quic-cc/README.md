<div align="center">
<h1>tigrcorn-quic-cc</h1>

<p><strong>Versioned congestion-controller contracts and provider discovery for Tigrcorn QUIC transports.</strong></p>

<a href="https://pypi.org/project/tigrcorn-quic-cc/"><img alt="PyPI version for tigrcorn-quic-cc" src="https://img.shields.io/pypi/v/tigrcorn-quic-cc?label=PyPI"></a>
<a href="https://pepy.tech/project/tigrcorn-quic-cc"><img alt="Downloads" src="https://static.pepy.tech/badge/tigrcorn-quic-cc"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-quic-cc/README.md"><img alt="Hits" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-quic-cc/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python versions" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
</div>

## Install

```bash
pip install tigrcorn-quic-cc
```

## What It Owns

This dependency-light package owns the public QUIC congestion-control API,
immutable event and decision models, entry-point discovery, validation, and
provider compliance helpers. It does not own sockets, packet encoding, loss
detection, retransmission, flow control, pacing enforcement, or wire ordering.

## Use It When

Use this package when authoring a standalone Tigrcorn congestion-control
provider or embedding a provider factory into a controlled QUIC integration.

## Import Surface

```python
import tigrcorn_quic_cc

print(tigrcorn_quic_cc.API_VERSION)
```

Providers implement `CongestionControllerFactory`, validate their options, and
create one controller per QUIC network path. Controllers receive immutable
events and return validated `SendLimits` values.

## Provider Discovery

Publish factories through the `tigrcorn.quic_cc.v1` entry-point group. The
registry imports only the explicitly selected provider and rejects missing,
duplicate, or incompatible providers.

## Compliance Helpers

`DeterministicClock`, `collect_send_limits`, and the public validators support
repeatable trace and invariant tests without importing Tigrcorn transports.

## Related Packages

- [tigrcorn](https://pypi.org/project/tigrcorn/)
- [tigrcorn-core](https://pypi.org/project/tigrcorn-core/)
- [tigrcorn-config](https://pypi.org/project/tigrcorn-config/)
- [tigrcorn-quic-cc-reno](https://pypi.org/project/tigrcorn-quic-cc-reno/)
- [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/)
- [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-quic-cc](https://pypi.org/project/tigrcorn-quic-cc/) | [tigrcorn-quic-cc-reno](https://pypi.org/project/tigrcorn-quic-cc-reno/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

`tigrcorn-quic-cc` is a layer-zero contract. Algorithm packages depend on it;
the transport depends on the contract and its default provider; runtime and
protocol packages consume the transport-owned enforcement surface.

## Best Practices

- Keep controller state path-local.
- Treat event times as monotonic seconds and rates as bytes per second.
- Return finite, positive pacing rates and safe congestion windows.
- Keep packet loss detection, retransmission, and wire scheduling in Tigrcorn.

## License

Apache-2.0
