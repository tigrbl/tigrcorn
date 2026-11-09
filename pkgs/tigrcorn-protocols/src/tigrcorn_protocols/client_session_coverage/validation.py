from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from .models import (
    BEHAVIOR_AXIS_VALUES,
    CLIENT_TOPOLOGY_VALUES,
    DISPOSITION_VALUES,
    GOVERNED_IDENTIFIER_FIELDS,
    INTERNAL_ONLY_FIELDS,
    PROTOCOL_CARRIER_DEFAULT_SCOPES,
    PROTOCOL_CARRIER_VALUES,
    REQUIRED_MATRIX_AXES,
    SESSION_SCOPE_VALUES,
    BehaviorAxis,
    SessionScope,
)


def _enum_value(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _normalized(value: object) -> str:
    return str(value).strip().lower().replace("-", "_").replace(".", "_")


def classify_default_session_scope(protocol_carrier: object) -> SessionScope:
    carrier = _normalized(_enum_value(protocol_carrier))
    try:
        return PROTOCOL_CARRIER_DEFAULT_SCOPES[carrier]
    except KeyError as exc:
        raise ValueError(f"unknown protocol carrier: {protocol_carrier!r}") from exc


def validate_no_internal_lane(record: Mapping[str, Any]) -> None:
    if INTERNAL_ONLY_FIELDS.intersection(record):
        raise ValueError("lane is protocol-internal and not a governed proof field")


def validate_governed_identifiers(record: Mapping[str, Any]) -> None:
    validate_no_internal_lane(record)
    for field in GOVERNED_IDENTIFIER_FIELDS:
        if field in record and record[field] is None:
            raise ValueError(f"{field} must be omitted or populated")


def validate_matrix_row(row: Mapping[str, Any]) -> None:
    validate_governed_identifiers(row)
    missing = sorted(REQUIRED_MATRIX_AXES.difference(row))
    if missing:
        raise ValueError(f"client-session matrix row missing axes: {missing}")

    carrier = _normalized(row["protocol_carrier"])
    if carrier not in PROTOCOL_CARRIER_VALUES:
        raise ValueError(f"unknown protocol carrier: {row['protocol_carrier']!r}")

    topology = _enum_value(row["client_topology"])
    if topology not in CLIENT_TOPOLOGY_VALUES:
        raise ValueError(f"unknown client topology: {topology!r}")

    scope = _enum_value(row["session_scope"])
    if scope not in SESSION_SCOPE_VALUES:
        raise ValueError(f"unknown session scope: {scope!r}")

    disposition = _enum_value(row["disposition"])
    if disposition not in DISPOSITION_VALUES:
        raise ValueError(f"unknown disposition: {disposition!r}")

    for axis in BehaviorAxis:
        axis_value = _enum_value(row[axis.value])
        if axis_value not in DISPOSITION_VALUES:
            raise ValueError(f"{axis.value} must be a coverage disposition")
