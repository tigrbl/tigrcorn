from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class InteropVector:
    name: str
    protocol: str
    rfc: str
    description: str
    fixture: str


@dataclass(slots=True)
class InteropResult:
    vector: str
    passed: bool
    runner: str
    notes: str = ''


def load_vectors(path: str | Path) -> list[InteropVector]:
    payload = json.loads(Path(path).read_text())
    return [InteropVector(**entry) for entry in payload['vectors']]


def load_results(path: str | Path) -> list[InteropResult]:
    payload = json.loads(Path(path).read_text())
    return [InteropResult(**entry) for entry in payload['results']]


def summarize_results(results: list[InteropResult]) -> dict[str, int]:
    return {
        'total': len(results),
        'passed': sum(1 for item in results if item.passed),
        'failed': sum(1 for item in results if not item.passed),
    }
