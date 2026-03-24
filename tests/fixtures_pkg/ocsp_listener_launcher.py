from __future__ import annotations

import os
import sys

from tigrcorn.cli import main as tigrcorn_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        raise SystemExit('usage: python -m tests.fixtures_pkg.ocsp_listener_launcher <bind_host> <bind_port>')
    bind_host, bind_port = args
    app_target = os.environ.get('INTEROP_OCSP_APP', 'examples.echo_http.app:app')
    certfile = os.environ['INTEROP_OCSP_CERTFILE']
    keyfile = os.environ['INTEROP_OCSP_KEYFILE']
    ca_certs = os.environ['INTEROP_OCSP_CA_CERTS']
    ocsp_mode = os.environ.get('INTEROP_OCSP_MODE', 'require')
    ocsp_max_age = os.environ.get('INTEROP_OCSP_MAX_AGE', '300')
    revocation_fetch = os.environ.get('INTEROP_OCSP_REVOCATION_FETCH', 'on')
    return tigrcorn_main(
        [
            app_target,
            '--host', bind_host,
            '--port', bind_port,
            '--protocol', 'http1',
            '--disable-websocket',
            '--no-access-log',
            '--lifespan', 'off',
            '--ssl-certfile', certfile,
            '--ssl-keyfile', keyfile,
            '--ssl-ca-certs', ca_certs,
            '--ssl-require-client-cert',
            '--ssl-ocsp-mode', ocsp_mode,
            '--ssl-ocsp-max-age', ocsp_max_age,
            '--ssl-revocation-fetch', revocation_fetch,
        ]
    )


if __name__ == '__main__':
    raise SystemExit(main())
