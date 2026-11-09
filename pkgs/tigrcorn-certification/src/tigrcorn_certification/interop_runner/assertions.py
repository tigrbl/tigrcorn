from __future__ import annotations

from .imports import *
from .helpers import *

def evaluate_assertions(assertions: list[dict[str, Any]], observed: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for index, assertion in enumerate(assertions):
        path = assertion.get('path')
        if not isinstance(path, str):
            failures.append(f'assertion[{index}] missing path')
            continue
        try:
            actual = _resolve_path(observed, path)
        except KeyError:
            failures.append(f'assertion[{index}] path not found: {path}')
            continue
        if 'equals' in assertion and actual != assertion['equals']:
            failures.append(f'assertion[{index}] {path} expected {assertion["equals"]!r}, got {actual!r}')
        if 'not_equals' in assertion and actual == assertion['not_equals']:
            failures.append(f'assertion[{index}] {path} unexpectedly equals {assertion["not_equals"]!r}')
        if 'contains' in assertion:
            expected = assertion['contains']
            if isinstance(actual, (str, bytes)):
                if expected not in actual:
                    failures.append(f'assertion[{index}] {path} does not contain {expected!r}')
            elif isinstance(actual, Mapping):
                if expected not in actual:
                    failures.append(f'assertion[{index}] {path} missing key {expected!r}')
            elif isinstance(actual, Iterable):
                if expected not in actual:
                    failures.append(f'assertion[{index}] {path} does not contain item {expected!r}')
            else:
                failures.append(f'assertion[{index}] {path} is not containable')
        if 'regex' in assertion and not re.search(str(assertion['regex']), str(actual)):
            failures.append(f'assertion[{index}] {path} does not match /{assertion["regex"]}/')
        if 'greater_or_equal' in assertion and actual < assertion['greater_or_equal']:
            failures.append(f'assertion[{index}] {path} expected >= {assertion["greater_or_equal"]!r}, got {actual!r}')
        if 'less_or_equal' in assertion and actual > assertion['less_or_equal']:
            failures.append(f'assertion[{index}] {path} expected <= {assertion["less_or_equal"]!r}, got {actual!r}')
        if 'in' in assertion and actual not in assertion['in']:
            failures.append(f'assertion[{index}] {path} expected one of {assertion["in"]!r}, got {actual!r}')
    return failures
def _resolve_path(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split('.'):
        if isinstance(current, Mapping):
            if part not in current:
                raise KeyError(path)
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            try:
                current = current[index]
            except IndexError as exc:
                raise KeyError(path) from exc
        else:
            raise KeyError(path)
    return current

__all__ = [name for name in globals() if not name.startswith('__')]
