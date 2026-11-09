from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.http.structured_fields import parse_structured_field, serialize_structured_value

ROOT = Path(__file__).resolve().parents[1]


def test_rfc9651_vectors_round_trip_deterministically():
    bundle = json.loads((ROOT / 'docs/conformance/sf9651.json').read_text(encoding='utf-8'))
    assert bundle['baseline_rfc'] == 'RFC 9651'
    for row in bundle['vectors']:
        parsed = parse_structured_field(row['field_name'], row['wire_value'])
        canonical = serialize_structured_value(parsed)
        assert canonical == row['canonical']
        reparsed = parse_structured_field(row['field_name'], canonical)
        assert serialize_structured_value(reparsed) == canonical


def test_registry_aware_field_type_dispatch_is_explicit():
    priority = parse_structured_field('priority', 'u=1, i')
    assert isinstance(priority, dict)
    assert serialize_structured_value(priority) == 'u=1, i'


def test_stale_predecessor_references_are_linted_outside_allowlist():
    bundle = json.loads((ROOT / 'docs/conformance/sf9651.json').read_text(encoding='utf-8'))
    assert bundle['stale_reference_lint']['violations'] == []
