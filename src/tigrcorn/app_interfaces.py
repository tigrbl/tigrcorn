from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from tigrcorn.compat.asgi3 import assert_asgi3_app, describe_app
from tigrcorn.types import ASGIApp, Message, Scope

AppInterface = Literal["auto", "tigr-asgi-contract", "asgi3"]
APP_INTERFACE_VALUES: tuple[AppInterface, ...] = ("auto", "tigr-asgi-contract", "asgi3")

Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


class AppInterfaceError(TypeError):
    """Raised when an app cannot be safely bound to the selected interface."""


@dataclass(slots=True)
class NativeContractApp:
    app: Any
    capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    interface: AppInterface = "tigr-asgi-contract"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        dispatcher = getattr(self.app, "dispatch", None) or getattr(self.app, "handle", None) or self.app
        result = dispatcher(scope, receive, send)
        if inspect.isawaitable(result):
            await result


@dataclass(frozen=True, slots=True)
class DispatchSelection:
    interface: Literal["tigr-asgi-contract", "asgi3"]
    app: ASGIApp
    native: bool


def native_contract_app(
    app: Any,
    *,
    capabilities: list[str] | tuple[str, ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> NativeContractApp:
    return NativeContractApp(
        app=app,
        capabilities=tuple(capabilities or ()),
        metadata=dict(metadata or {}),
    )


def mark_native_contract_app(
    app: Any,
    *,
    capabilities: list[str] | tuple[str, ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any:
    setattr(app, "__tigrcorn_app_interface__", "tigr-asgi-contract")
    setattr(app, "__tigrcorn_contract_capabilities__", tuple(capabilities or ()))
    setattr(app, "__tigrcorn_contract_metadata__", dict(metadata or {}))
    return app


def is_native_contract_app(app: Any) -> bool:
    return isinstance(app, NativeContractApp) or getattr(app, "__tigrcorn_app_interface__", None) == "tigr-asgi-contract"


def _as_native(app: Any) -> NativeContractApp:
    if isinstance(app, NativeContractApp):
        return app
    capabilities = getattr(app, "__tigrcorn_contract_capabilities__", ())
    metadata = getattr(app, "__tigrcorn_contract_metadata__", {})
    return native_contract_app(app, capabilities=capabilities, metadata=metadata)


def _is_unambiguous_asgi3(app: Any) -> bool:
    if not callable(app):
        return False
    signature = describe_app(app)
    return signature.parameter_count == 3


def resolve_app_dispatch(app: Any, interface: AppInterface = "auto") -> DispatchSelection:
    if interface not in APP_INTERFACE_VALUES:
        raise AppInterfaceError(f"unsupported app interface: {interface!r}")
    if interface == "tigr-asgi-contract":
        if not is_native_contract_app(app):
            raise AppInterfaceError("explicit tigr-asgi-contract selection requires a native contract app marker or wrapper")
        return DispatchSelection("tigr-asgi-contract", _as_native(app), True)
    if interface == "asgi3":
        try:
            assert_asgi3_app(app)
        except Exception as exc:
            raise AppInterfaceError("explicit asgi3 selection requires an ASGI 3 callable") from exc
        return DispatchSelection("asgi3", app, False)

    if is_native_contract_app(app):
        return DispatchSelection("tigr-asgi-contract", _as_native(app), True)
    if _is_unambiguous_asgi3(app):
        assert_asgi3_app(app)
        return DispatchSelection("asgi3", app, False)
    raise AppInterfaceError("ambiguous or unsupported application interface; select asgi3 or tigr-asgi-contract explicitly")
