# aioquic adapter preflight bundle

This bundle preserves the direct third-party aioquic HTTP/3 adapter preflight runs used before strict-target certification checkpoints.

## Exit-criteria status

- all adapters passed: `True`
- no peer exit code 2: `True`
- negotiation metadata emitted: `True`
- transcript metadata emitted: `True`
- ALPN h3 observed for every run: `True`
- QUIC handshakes complete: `True`
- certificate inputs ready: `True`

## Scenarios

- `http3-server-aioquic-client-post` → passed=`True`, peer_exit=`0`, protocol=`h3`, handshake_complete=`True`
- `websocket-http3-server-aioquic-client` → passed=`True`, peer_exit=`0`, protocol=`h3`, handshake_complete=`True`

