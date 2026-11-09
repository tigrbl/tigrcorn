from __future__ import annotations

import argparse
import asyncio
import json
import os
import ssl
import sys
from dataclasses import dataclass
from typing import Any

import websockets


@dataclass(frozen=True)
class WebSocketProbeResult:
    url: str
    secure: bool
    sent_text: str
    received_text: str
    subprotocol: str | None
    close_code: int | None
    response_headers: tuple[tuple[str, str], ...]
    negotiated_extensions: tuple[str, ...]
    tls_cipher: tuple[str, str, int] | None
    selected_alpn_protocol: str | None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "secure": self.secure,
            "sent_text": self.sent_text,
            "received_text": self.received_text,
            "subprotocol": self.subprotocol,
            "close_code": self.close_code,
            "response_headers": [list(item) for item in self.response_headers],
            "negotiated_extensions": list(self.negotiated_extensions),
            "tls": {
                "cipher": list(self.tls_cipher) if self.tls_cipher is not None else None,
                "selected_alpn_protocol": self.selected_alpn_protocol,
            },
        }


def _response_header_items(websocket: Any) -> tuple[tuple[str, str], ...]:
    response_headers = getattr(websocket, "response_headers", None)
    if response_headers is None:
        response = getattr(websocket, "response", None)
        response_headers = getattr(response, "headers", None)
    if response_headers is None:
        return ()
    try:
        return tuple((str(name), str(value)) for name, value in response_headers.raw_items())
    except Exception:
        try:
            return tuple((str(name), str(value)) for name, value in response_headers.items())
        except Exception:
            return ()


def _extension_names(websocket: Any) -> tuple[str, ...]:
    return tuple(type(extension).__name__ for extension in getattr(websocket, "extensions", ()))


def _ssl_object(websocket: Any) -> ssl.SSLObject | None:
    transport = getattr(websocket, "transport", None)
    if transport is None:
        return None
    return transport.get_extra_info("ssl_object")


def build_client_ssl_context(cafile: str | None = None) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=cafile)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.set_alpn_protocols(["http/1.1"])
    return context


async def probe_ws_wss(
    host: str,
    port: int,
    *,
    path: str = "/ws",
    text: str = "hello-websocket",
    secure: bool = False,
    cafile: str | None = None,
    server_hostname: str | None = None,
    compression: str | None = None,
    subprotocols: list[str] | None = None,
    timeout: float = 5.0,
) -> WebSocketProbeResult:
    scheme = "wss" if secure else "ws"
    url = f"{scheme}://{host}:{port}{path}"
    ssl_context = build_client_ssl_context(cafile) if secure else None
    connect_kwargs: dict[str, Any] = {
        "compression": compression,
        "subprotocols": subprotocols,
        "ssl": ssl_context,
    }
    if secure and server_hostname:
        connect_kwargs["server_hostname"] = server_hostname

    async with websockets.connect(url, **connect_kwargs) as websocket:
        await asyncio.wait_for(websocket.send(text), timeout=timeout)
        received = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        ssl_obj = _ssl_object(websocket)
        tls_cipher = ssl_obj.cipher() if ssl_obj is not None else None
        selected_alpn = ssl_obj.selected_alpn_protocol() if ssl_obj is not None else None
        await asyncio.wait_for(websocket.close(), timeout=timeout)
        return WebSocketProbeResult(
            url=url,
            secure=secure,
            sent_text=text,
            received_text=str(received),
            subprotocol=getattr(websocket, "subprotocol", None),
            close_code=getattr(websocket, "close_code", None),
            response_headers=_response_header_items(websocket),
            negotiated_extensions=_extension_names(websocket),
            tls_cipher=tls_cipher,
            selected_alpn_protocol=selected_alpn,
        )


def _write_json(path_env: str, payload: dict[str, Any]) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)


async def _amain(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="ws/wss probe fixture")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--secure", action="store_true", default=os.environ.get("INTEROP_WS_SECURE") == "1")
    parser.add_argument("--path", default=os.environ.get("INTEROP_REQUEST_PATH", "/ws"))
    parser.add_argument("--text", default=os.environ.get("INTEROP_REQUEST_BODY", "hello-websocket"))
    parser.add_argument("--cafile", default=os.environ.get("INTEROP_CACERT"))
    parser.add_argument("--servername", default=os.environ.get("INTEROP_SERVER_NAME"))
    parser.add_argument("--compression", default=os.environ.get("INTEROP_WEBSOCKET_COMPRESSION") or None)
    args = parser.parse_args(argv)
    if args.version:
        print(f"websockets {websockets.__version__}")
        return 0

    host = os.environ["INTEROP_TARGET_HOST"]
    port = int(os.environ["INTEROP_TARGET_PORT"])
    result = await probe_ws_wss(
        host,
        port,
        path=args.path,
        text=args.text,
        secure=bool(args.secure),
        cafile=args.cafile,
        server_hostname=args.servername,
        compression=args.compression,
    )
    transcript = {
        "request": {"path": args.path, "text": args.text, "url": result.url},
        "response": result.to_jsonable(),
    }
    negotiation = {
        "implementation": "websockets",
        "protocol": "wss" if result.secure else "ws",
        "subprotocol": result.subprotocol,
        "negotiated_extensions": list(result.negotiated_extensions),
        "tls": result.secure,
        "selected_alpn_protocol": result.selected_alpn_protocol,
    }
    _write_json("INTEROP_TRANSCRIPT_PATH", transcript)
    _write_json("INTEROP_NEGOTIATION_PATH", negotiation)
    print(json.dumps({"transcript": transcript, "negotiation": negotiation}, sort_keys=True))
    return 0 if result.received_text == result.sent_text else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
