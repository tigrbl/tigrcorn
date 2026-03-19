from __future__ import annotations


def normalize_alpn(selected: str | None) -> str | None:
    if selected in {None, "", "http/1.1", "h2", "h3"}:
        return selected or None
    return selected
