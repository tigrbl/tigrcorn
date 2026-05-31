from __future__ import annotations

import importlib.util
from collections.abc import Generator
from typing import Any

from benchmarks.common import measure_sync
from tigrcorn.protocols.websocket.frames import decode_frame, encode_frame

_TEXT = b"hello-websocket-peer"
_MASK_KEY = b"\x01\x02\x03\x04"


def _tigrcorn_frame_roundtrip(payload: bytes) -> dict[str, object]:
    data = encode_frame(0x1, payload, masked=True, mask_key=_MASK_KEY)
    frame = decode_frame(data, expect_masked=True)
    return {
        "backend": "tigrcorn",
        "encoded_bytes": len(data),
        "payload_bytes": len(payload),
        "frame_opcode": int(frame.opcode),
        "frame_payload": bytes(frame.payload),
        "frame_fin": bool(frame.fin),
    }


def _wsproto_frame_roundtrip(payload: bytes) -> dict[str, object]:
    import wsproto.frame_protocol as ws_frames  # type: ignore

    sender = ws_frames.FrameProtocol(client=True, extensions=[])
    receiver = ws_frames.FrameProtocol(client=False, extensions=[])
    data = bytes(sender.send_data(payload.decode("utf-8"), fin=True))
    receiver.receive_bytes(data)
    frame = next(iter(receiver.received_frames()))
    frame_payload = frame.payload
    if isinstance(frame_payload, str):
        frame_payload = frame_payload.encode("utf-8")
    return {
        "backend": "wsproto",
        "encoded_bytes": len(data),
        "payload_bytes": len(payload),
        "frame_opcode": int(frame.opcode),
        "frame_payload": bytes(frame_payload),
        "frame_fin": bool(frame.frame_finished),
    }


def _generator_read_exact_factory(payload: bytes) -> Any:
    remaining = memoryview(payload)

    def read_exact(amount: int) -> Generator[None, None, bytes]:
        nonlocal remaining
        if amount > len(remaining):
            raise EOFError(f"short websocket frame payload: need {amount}, have {len(remaining)}")
        chunk = bytes(remaining[:amount])
        remaining = remaining[amount:]
        if False:  # pragma: no cover - preserve generator shape for yield from
            yield None
        return chunk

    return read_exact


def _run_generator_coroutine(generator: Generator[None, None, Any]) -> Any:
    while True:
        try:
            next(generator)
        except StopIteration as exc:
            return exc.value


def _websockets_frame_roundtrip(payload: bytes) -> dict[str, object]:
    import websockets.frames as ws_frames  # type: ignore

    data = ws_frames.Frame(ws_frames.Opcode.TEXT, payload).serialize(mask=True)
    frame = _run_generator_coroutine(
        ws_frames.Frame.parse(
            _generator_read_exact_factory(data),
            mask=True,
            max_size=None,
            extensions=[],
        )
    )
    return {
        "backend": "websockets",
        "encoded_bytes": len(data),
        "payload_bytes": len(payload),
        "frame_opcode": int(frame.opcode),
        "frame_payload": bytes(frame.data),
        "frame_fin": bool(frame.fin),
    }


def websocket_peer_frame_driver(profile, *, source_root):
    backend = str(profile.driver_config.get("backend", "tigrcorn"))
    payload = bytes(str(profile.driver_config.get("text", _TEXT.decode("utf-8"))), "utf-8")

    def operation():
        if backend == "tigrcorn":
            result = _tigrcorn_frame_roundtrip(payload)
        elif backend == "wsproto":
            result = _wsproto_frame_roundtrip(payload)
        elif backend == "websockets":
            result = _websockets_frame_roundtrip(payload)
        else:
            raise RuntimeError(f"unsupported websocket peer benchmark backend: {backend!r}")
        return {
            "connections": 1,
            "streams": 1,
            "correctness": {
                "backend_matches": str(result["backend"]) == backend,
                "payload_roundtrip": bytes(result["frame_payload"]) == payload,
                "text_opcode": int(result["frame_opcode"]) == 0x1,
                "final_frame": bool(result["frame_fin"]),
                "encoded_nonempty": int(result["encoded_bytes"]) > 0,
            },
            "metadata": {
                "backend": backend,
                "payload_bytes": len(payload),
                "encoded_bytes": int(result["encoded_bytes"]),
                "websockets_available": importlib.util.find_spec("websockets") is not None,
                "wsproto_available": importlib.util.find_spec("wsproto") is not None,
            },
        }

    return measure_sync(
        operation,
        iterations=profile.iterations,
        warmups=profile.warmups,
        units_per_iteration=profile.units_per_iteration,
        correctness_note="peer-comparison benchmark checks identical masked text frame roundtrip semantics across Tigrcorn, wsproto, and websockets",
    )
