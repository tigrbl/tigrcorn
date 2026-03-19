from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TraceDiff:
    missing_left: list[str] = field(default_factory=list)
    missing_right: list[str] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing_left or self.missing_right or self.mismatches)


def normalize_scope(scope: dict[str, Any]) -> dict[str, Any]:
    scope = dict(scope)
    scope.pop('state', None)
    return scope


def normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    message = dict(message)
    if 'headers' in message:
        message['headers'] = list(message['headers'])
    return message


def compare_sequence(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> TraceDiff:
    diff = TraceDiff()
    for idx in range(max(len(left), len(right))):
        if idx >= len(left):
            diff.missing_left.append(f'left missing event[{idx}]')
            continue
        if idx >= len(right):
            diff.missing_right.append(f'right missing event[{idx}]')
            continue
        if normalize_message(left[idx]) != normalize_message(right[idx]):
            diff.mismatches.append(f'event[{idx}] {normalize_message(left[idx])!r} != {normalize_message(right[idx])!r}')
    return diff
