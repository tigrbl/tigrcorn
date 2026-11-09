from __future__ import annotations

from typing import Any

from .models import ClientTopology, CoverageDisposition, ProtocolCarrier, SessionScope
from .validation import _enum_value, _normalized, classify_default_session_scope, validate_matrix_row


def build_matrix_row(
    *,
    protocol_carrier: ProtocolCarrier | str,
    client_topology: ClientTopology | str,
    session_scope: SessionScope | str | None = None,
    disposition: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    lifecycle_behavior: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    identity_isolation: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    ordering_behavior: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    pressure_mode: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    fault_mode: CoverageDisposition | str = CoverageDisposition.REQUIRED,
    **identifiers: Any,
) -> dict[str, Any]:
    carrier = _normalized(_enum_value(protocol_carrier))
    row: dict[str, Any] = {
        "protocol_carrier": carrier,
        "client_topology": _enum_value(client_topology),
        "session_scope": _enum_value(session_scope or classify_default_session_scope(carrier)),
        "lifecycle_behavior": _enum_value(lifecycle_behavior),
        "identity_isolation": _enum_value(identity_isolation),
        "ordering_behavior": _enum_value(ordering_behavior),
        "pressure_mode": _enum_value(pressure_mode),
        "fault_mode": _enum_value(fault_mode),
        "disposition": _enum_value(disposition),
    }
    row.update(identifiers)
    validate_matrix_row(row)
    return row
