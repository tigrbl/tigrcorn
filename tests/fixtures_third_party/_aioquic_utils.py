from __future__ import annotations

import inspect
import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

SETTING_ENABLE_CONNECT_PROTOCOL = 0x08
H3_FRAME_TYPE_GOAWAY = 0x07


def write_json(path_env: str, payload: dict[str, Any]) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def path_status(path: Any) -> dict[str, Any]:
    if path in (None, ""):
        return {
            "path": None,
            "exists": False,
            "is_file": False,
        }
    resolved = Path(str(path))
    return {
        "path": str(resolved),
        "exists": resolved.exists(),
        "is_file": resolved.is_file(),
    }


def certificate_input_status(*, cacert: Any, client_cert: Any = None, client_key: Any = None) -> dict[str, Any]:
    ca = path_status(cacert)
    cert = path_status(client_cert)
    key = path_status(client_key)
    client_material_requested = bool(client_cert or client_key)
    client_material_ready = (not client_material_requested) or (cert["exists"] and key["exists"])
    return {
        "ca_cert": ca,
        "client_cert": cert,
        "client_key": key,
        "client_material_requested": client_material_requested,
        "client_material_ready": client_material_ready,
        "ready": ca["exists"] and client_material_ready,
    }


def env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def header_pairs_to_text(headers: Iterable[tuple[Any, Any]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw_name, raw_value in headers:
        if isinstance(raw_name, bytes):
            name = raw_name.decode("latin1", errors="replace")
        else:
            name = str(raw_name)
        if isinstance(raw_value, bytes):
            value = raw_value.decode("latin1", errors="replace")
        else:
            value = str(raw_value)
        pairs.append((name, value))
    return pairs


def header_map(headers: Iterable[tuple[Any, Any]]) -> dict[str, str]:
    return {name: value for name, value in header_pairs_to_text(headers)}


def quic_varint_encode(value: int) -> bytes:
    if value < 0:
        raise ValueError("QUIC varint values must be non-negative")
    if value < (1 << 6):
        return bytes([value])
    if value < (1 << 14):
        return bytes([
            0x40 | ((value >> 8) & 0x3F),
            value & 0xFF,
        ])
    if value < (1 << 30):
        return bytes([
            0x80 | ((value >> 24) & 0x3F),
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
        ])
    if value < (1 << 62):
        return bytes([
            0xC0 | ((value >> 56) & 0x3F),
            (value >> 48) & 0xFF,
            (value >> 40) & 0xFF,
            (value >> 32) & 0xFF,
            (value >> 24) & 0xFF,
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
        ])
    raise ValueError("QUIC varint values must be smaller than 2**62")


def encode_http3_frame(frame_type: int, payload: bytes) -> bytes:
    body = bytes(payload)
    return quic_varint_encode(frame_type) + quic_varint_encode(len(body)) + body


def encode_goaway_frame(identifier: int) -> bytes:
    return encode_http3_frame(H3_FRAME_TYPE_GOAWAY, quic_varint_encode(identifier))


def make_udp_socket(host: str = "127.0.0.1") -> socket.socket:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    if family == socket.AF_INET6:
        sock.bind((host, 0, 0, 0))
    else:
        sock.bind((host, 0))
    sock.settimeout(0.2)
    return sock


def call_with_optional_now(fn: Any, *args: Any, now: float) -> Any:
    signature = None
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        signature = None

    if signature is not None and "now" in signature.parameters:
        return fn(*args, now=now)

    keyword_error: Exception | None = None
    try:
        return fn(*args, now=now)
    except TypeError as exc:
        keyword_error = exc

    positional_error: Exception | None = None
    try:
        return fn(*args, now)
    except TypeError as exc:
        positional_error = exc

    try:
        return fn(*args)
    except TypeError:
        if positional_error is not None:
            raise positional_error
        if keyword_error is not None:
            raise keyword_error
        raise


def connect_quic(quic: Any, target: tuple[str, int]) -> None:
    call_with_optional_now(quic.connect, target, now=time.time())


def flush_pending_datagrams(sock: socket.socket, quic: Any, fallback_target: tuple[str, int]) -> None:
    now = time.time()
    pending = call_with_optional_now(quic.datagrams_to_send, now=now)
    for item in pending:
        if isinstance(item, tuple) and len(item) == 2:
            data, target = item
        else:
            data, target = item, fallback_target
        sock.sendto(data, target)


def receive_datagram(sock: socket.socket, quic: Any) -> tuple[bytes, tuple[str, int]]:
    data, addr = sock.recvfrom(65536)
    call_with_optional_now(quic.receive_datagram, data, addr, now=time.time())
    return data, addr


def handle_due_timer(quic: Any) -> bool:
    timer_at = getattr(quic, "get_timer", lambda: None)()
    if timer_at is None:
        return False
    now = time.time()
    if float(timer_at) > now:
        return False
    call_with_optional_now(quic.handle_timer, now=now)
    return True


def send_ping_if_supported(quic: Any) -> bool:
    sender = getattr(quic, "send_ping", None)
    if not callable(sender):
        return False
    try:
        signature = inspect.signature(sender)
    except (TypeError, ValueError):
        signature = None

    try:
        if signature is not None and len(signature.parameters) == 0:
            sender()
        else:
            sender(0)
        return True
    except TypeError:
        try:
            sender()
            return True
        except TypeError:
            return False


def session_ticket_allows_early_data(ticket: Any) -> bool:
    if ticket is None:
        return False
    if isinstance(ticket, Mapping):
        for candidate in (
            "max_early_data_size",
            "early_data_size",
            "early_data_size_limit",
            "max_early_data",
        ):
            value = ticket.get(candidate)
            if value is None:
                continue
            try:
                return int(value) > 0
            except (TypeError, ValueError):
                return bool(value)
        return True
    for candidate in (
        "max_early_data_size",
        "early_data_size",
        "early_data_size_limit",
        "max_early_data",
    ):
        value = getattr(ticket, candidate, None)
        if value is None:
            continue
        try:
            return int(value) > 0
        except (TypeError, ValueError):
            return bool(value)
    return True


def snapshot_object_state(obj: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    if hasattr(obj, "__dict__"):
        snapshot.update(vars(obj))
    for name in dir(obj):
        if name.startswith("__") or name in snapshot:
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if callable(value):
            continue
        snapshot[name] = value
    return snapshot


# Backwards-compatible internal alias for the helper name used in older tests.
def snapshot_http3_state(http: Any) -> dict[str, Any]:
    return snapshot_object_state(http)


def _truthy_transport_state(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    if isinstance(value, (bytes, bytearray, str)):
        return len(value) > 0
    if value is None:
        return False
    if isinstance(value, (tuple, list, dict, set, frozenset)):
        return len(value) > 0
    return True


def detect_retry_observed(quic: Any) -> bool:
    snapshot = snapshot_object_state(quic)
    for candidate in ("_retry_count", "retry_count"):
        value = snapshot.get(candidate)
        if isinstance(value, int) and value > 0:
            return True

    for candidate in (
        "_retry_source_connection_id",
        "retry_source_connection_id",
        "_retry_token",
        "retry_token",
        "_received_retry",
        "received_retry",
        "retry_received",
    ):
        if _truthy_transport_state(snapshot.get(candidate)):
            return True

    for name, value in snapshot.items():
        lname = name.lower()
        if "retry" not in lname:
            continue
        if _truthy_transport_state(value):
            return True
    return False


def _looks_like_stream_id(value: Any) -> bool:
    return isinstance(value, int) and value >= 0


def detect_local_control_stream_id(http: Any) -> int | None:
    snapshot = snapshot_http3_state(http)
    for candidate in (
        "_local_control_stream_id",
        "local_control_stream_id",
        "_control_stream_id",
        "control_stream_id",
    ):
        value = snapshot.get(candidate)
        if _looks_like_stream_id(value):
            return int(value)
    for name, value in snapshot.items():
        lname = name.lower()
        if _looks_like_stream_id(value) and "control_stream" in lname and "local" in lname:
            return int(value)
    return None


def detect_peer_qpack_streams(http: Any) -> tuple[bool, bool]:
    snapshot = snapshot_http3_state(http)
    encoder_seen = False
    decoder_seen = False

    encoder_candidates = (
        "_peer_qpack_encoder_stream_id",
        "peer_qpack_encoder_stream_id",
        "_remote_qpack_encoder_stream_id",
        "remote_qpack_encoder_stream_id",
        "_decoder_stream_id",
        "decoder_stream_id",
    )
    decoder_candidates = (
        "_peer_qpack_decoder_stream_id",
        "peer_qpack_decoder_stream_id",
        "_remote_qpack_decoder_stream_id",
        "remote_qpack_decoder_stream_id",
        "_encoder_stream_id",
        "encoder_stream_id",
    )
    for candidate in encoder_candidates:
        if _looks_like_stream_id(snapshot.get(candidate)):
            encoder_seen = True
            break
    for candidate in decoder_candidates:
        if _looks_like_stream_id(snapshot.get(candidate)):
            decoder_seen = True
            break

    if not encoder_seen or not decoder_seen:
        for name, value in snapshot.items():
            if not _looks_like_stream_id(value):
                continue
            lname = name.lower()
            if "qpack" not in lname and "encoder_stream" not in lname and "decoder_stream" not in lname:
                continue
            if "remote" in lname or "peer" in lname or lname.startswith("_decoder_stream"):
                encoder_seen = True
            if "remote" in lname or "peer" in lname or lname.startswith("_encoder_stream"):
                decoder_seen = True

    return encoder_seen, decoder_seen


def received_settings(http: Any) -> dict[int, int]:
    settings = getattr(http, "received_settings", None)
    if isinstance(settings, dict):
        return {int(key): int(value) for key, value in settings.items()}
    return {}
