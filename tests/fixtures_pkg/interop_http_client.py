from __future__ import annotations

import http.client
import json
import os
import sys



def _write_json(path_env: str, payload: dict) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle)



def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if '--version' in argv:
        print('interop-http-client 1.0')
        return 0
    host = os.environ['INTEROP_TARGET_HOST']
    port = int(os.environ['INTEROP_TARGET_PORT'])
    body = os.environ.get('INTEROP_REQUEST_BODY', 'hello-interop').encode('utf-8')
    conn = http.client.HTTPConnection(host, port, timeout=5.0)
    conn.request('POST', '/interop', body=body, headers={'Connection': 'close'})
    response = conn.getresponse()
    payload = response.read()
    transcript = {
        'request': {'method': 'POST', 'path': '/interop', 'body': body.decode('utf-8')},
        'response': {
            'status': response.status,
            'reason': response.reason,
            'body': payload.decode('utf-8', errors='replace'),
            'headers': response.getheaders(),
        },
    }
    negotiation = {'alpn': 'http/1.1'}
    _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
    _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
    print(json.dumps(transcript, sort_keys=True))
    return 0 if response.status == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
