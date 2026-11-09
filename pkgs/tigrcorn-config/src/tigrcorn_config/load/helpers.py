from __future__ import annotations

from typing import Any, Mapping


def listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[Any] = []
        for item in value:
            if isinstance(item, str) and "," in item:
                result.extend(part.strip() for part in item.split(",") if part.strip())
            else:
                result.append(item)
        return result
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def mapping_get(source: Mapping[str, Any], *path: str) -> Any:
    cursor: Any = source
    for segment in path:
        if not isinstance(cursor, Mapping):
            return None
        cursor = cursor.get(segment)
    return cursor
