from __future__ import annotations

from tigrcorn.contract import (
    alt_svc_contract_map,
    contract_scope,
    http_response_body,
    http_response_start,
    unit_identity,
)


def build_response_contract(path: str = "/") -> dict[str, object]:
    scope = contract_scope("http", method="GET", path=path)
    unit = unit_identity("example-request", family="request", binding="http")
    alt_svc = alt_svc_contract_map('h3=":443"', max_age=60)

    return {
        "scope": scope,
        "unit": unit,
        "feature_map": alt_svc.as_dict(),
        "events": [
            http_response_start(unit.unit_id, status=200),
            http_response_body(unit.unit_id, body=b"contract example", more_body=False),
        ],
    }
