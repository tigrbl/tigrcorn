from __future__ import annotations


def custom_event(event_type: str, **payload) -> dict:
    return {"type": event_type, **payload}


def stream_receive(data: bytes, *, more_data: bool = False) -> dict:
    return custom_event("tigrcorn.stream.receive", data=data, more_data=more_data)


def stream_send(data: bytes, *, more_data: bool = False) -> dict:
    return custom_event("tigrcorn.stream.send", data=data, more_data=more_data)
