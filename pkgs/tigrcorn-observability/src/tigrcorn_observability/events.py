from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Event:
    name: str
    attrs: dict[str, object]


DOS_WARNING_EVENT = "tigrcorn.dos.warning"


def dos_warning(
    *,
    surface: str,
    reason: str,
    action: str,
    resource: str | None = None,
    limit: int | float | None = None,
    observed: int | float | None = None,
) -> Event:
    attrs: dict[str, object] = {
        "surface": surface,
        "reason": reason,
        "action": action,
    }
    if resource is not None:
        attrs["resource"] = resource
    if limit is not None:
        attrs["limit"] = limit
    if observed is not None:
        attrs["observed"] = observed
    return Event(DOS_WARNING_EVENT, attrs)
