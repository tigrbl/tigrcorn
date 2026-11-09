from __future__ import annotations

from urllib.parse import urlsplit

from tigrcorn_core.errors import ProtocolError

from .models import RequestTargetForm


def _parse_request_target(method: str, target: str) -> tuple[str, bytes, bytes, RequestTargetForm]:
    method_upper = method.upper()
    if target == '*':
        if method_upper != 'OPTIONS':
            raise ProtocolError('asterisk-form request-target is only valid for OPTIONS')
        return '*', b'*', b'', 'asterisk'

    if method_upper == 'CONNECT':
        if '://' in target or '/' in target or '?' in target or '#' in target or not target:
            raise ProtocolError('invalid authority-form request-target')
        return target, target.encode('ascii'), b'', 'authority'

    if target.startswith('http://') or target.startswith('https://'):
        split = urlsplit(target)
        if not split.scheme or not split.netloc:
            raise ProtocolError('invalid absolute-form request-target')
        path = split.path or '/'
        return path, path.encode('utf-8'), split.query.encode('ascii'), 'absolute'

    if not target.startswith('/'):
        raise ProtocolError('invalid origin-form request-target')
    split = urlsplit(target)
    path = split.path or '/'
    return path, path.encode('utf-8'), split.query.encode('ascii'), 'origin'
