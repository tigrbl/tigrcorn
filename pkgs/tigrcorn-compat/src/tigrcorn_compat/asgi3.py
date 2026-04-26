from __future__ import annotations

import inspect
from dataclasses import dataclass

from tigrcorn.types import ASGIApp, Message, Scope


@dataclass(slots=True)
class ASGI3Signature:
    parameter_count: int
    is_async: bool


def describe_app(app: ASGIApp) -> ASGI3Signature:
    target = app.__call__ if not inspect.iscoroutinefunction(app) and hasattr(app, '__call__') else app
    try:
        sig = inspect.signature(target)
    except (TypeError, ValueError):
        return ASGI3Signature(parameter_count=3, is_async=True)
    is_async = inspect.iscoroutinefunction(target)
    return ASGI3Signature(parameter_count=len(sig.parameters), is_async=is_async)


def assert_asgi3_app(app: ASGIApp) -> None:
    if not callable(app):
        raise TypeError('application object must be callable')
    signature = describe_app(app)
    if signature.parameter_count != 3:
        raise TypeError('ASGI 3 application must accept exactly (scope, receive, send)')


def is_http_scope(scope: Scope) -> bool:
    return scope.get('type') == 'http'


def is_websocket_scope(scope: Scope) -> bool:
    return scope.get('type') == 'websocket'


def is_lifespan_scope(scope: Scope) -> bool:
    return scope.get('type') == 'lifespan'


def is_http_event(message: Message) -> bool:
    return str(message.get('type', '')).startswith('http.')
