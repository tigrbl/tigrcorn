from __future__ import annotations

def quic_recovery_rule_table() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in QUIC_RECOVERY_RULES)



def supported_recovery_pressure_certification_scopes() -> tuple[str, ...]:
    return RECOVERY_PRESSURE_CERTIFICATION_SCOPES
