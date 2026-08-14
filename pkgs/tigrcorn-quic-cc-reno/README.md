<div align="center">
<h1>tigrcorn-quic-cc-reno</h1>

<p><strong>Default Reno congestion-controller provider for Tigrcorn QUIC transports.</strong></p>

<a href="https://pypi.org/project/tigrcorn-quic-cc-reno/"><img alt="PyPI version for tigrcorn-quic-cc-reno" src="https://img.shields.io/pypi/v/tigrcorn-quic-cc-reno?label=PyPI"></a>
<a href="https://pepy.tech/project/tigrcorn-quic-cc-reno"><img alt="Downloads" src="https://static.pepy.tech/badge/tigrcorn-quic-cc-reno"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-quic-cc-reno/README.md"><img alt="Hits" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-quic-cc-reno/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python versions" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
</div>

## Install

```bash
pip install tigrcorn-quic-cc-reno
```

## What It Owns

This package owns Reno congestion policy only: the initial congestion window,
slow start, congestion avoidance, congestion-event reduction, persistent
congestion collapse, and pacing-rate decisions.

Tigrcorn transports retain RFC 9002 loss detection, RTT and PTO calculation,
packet accounting, pacing enforcement, retransmission, and socket ownership.

## Use It When

Use this provider when you want Tigrcorn's default and compatibility-preserving
QUIC congestion-control behavior as an independently installable package.

## Import Surface

```python
import tigrcorn_quic_cc_reno

print(tigrcorn_quic_cc_reno.factory.metadata.algorithm_id)
```

## Options

- `initial_window_packets` defaults to `10`.
- `initial_window_cap_bytes` defaults to `14720`.
- `pacing_gain` defaults to `1.0`.

Invalid or unknown options fail listener startup. The factory is registered as
`reno` in the `tigrcorn.quic_cc.v1` entry-point group.

## Related Packages

- [tigrcorn](https://pypi.org/project/tigrcorn/)
- [tigrcorn-core](https://pypi.org/project/tigrcorn-core/)
- [tigrcorn-config](https://pypi.org/project/tigrcorn-config/)
- [tigrcorn-quic-cc](https://pypi.org/project/tigrcorn-quic-cc/)
- [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/)
- [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-quic-cc](https://pypi.org/project/tigrcorn-quic-cc/) | [tigrcorn-quic-cc-reno](https://pypi.org/project/tigrcorn-quic-cc-reno/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

`tigrcorn-quic-cc-reno` depends only on the public congestion-control contract.
The transport installs it as the default while alternate providers remain
separate distributions selected through configuration.

## Best Practices

- Keep Reno as the default unless a separately governed decision changes it.
- Validate behavior with deterministic ACK, loss, and persistent traces.
- Compare performance using distributions and declared latency envelopes.
- Never move loss detection or socket operations into the provider.

## License

Apache-2.0
