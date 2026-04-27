# WebTransport mTLS ASGI3 Demo

This demo runs three containers:

- `tigrcorn-wt-local`: Tigrcorn serving the ASGI3 app over UDP, HTTP/3, and
  WebTransport without client-certificate enforcement for local browser tests.
- `tigrcorn-wt-mtls`: Tigrcorn serving the same ASGI3 app over UDP, HTTP/3,
  WebTransport, and strict mTLS.
- `tigrcorn-wt-client`: a small static UI for opening a browser WebTransport
  session, stream, and datagram.

The demo generates a shared short-lived localhost certificate in the `wt-certs`
compose volume at startup. The UI reads `/cert-hash.json` and passes that value
through the browser WebTransport `serverCertificateHashes` option so the local
handshake does not depend on the browser trust store.

Browser JavaScript cannot directly provide a client certificate, so strict mTLS
experiments require importing the client certificate into the browser or OS
certificate store. Without that, the strict mTLS handshake is expected to fail
before ASGI dispatch. Use the local endpoint when validating the browser
WebTransport handshake itself.

## Run

```powershell
docker compose -f examples/webtransport_mtls_demo/docker-compose.yml up --build -d
```

Open:

- UI: `http://localhost:8088`
- local WebTransport endpoint: `https://localhost:8444/wt`
- strict mTLS WebTransport endpoint: `https://localhost:8443/wt`

## Stop

```powershell
docker compose -f examples/webtransport_mtls_demo/docker-compose.yml down
```
