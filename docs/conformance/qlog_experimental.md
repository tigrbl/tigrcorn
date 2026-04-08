# Experimental qlog Contract

This file is generated from the package-owned Phase 6 observability metadata.

- `schema_version`: `tigrcorn.qlog.experimental.v1`
- `stability`: `experimental`
- `compatibility`: `best_effort_internal_artifact_only`
- `producer`: `tigrcorn.compat.interop_runner.generate_observer_qlog`

## Redaction rules

- `network_endpoints`: remote endpoint addresses are redacted from qlog output
- `connection_ids`: dcid/scid values are redacted in emitted packet summaries
- `payload_bytes`: raw packet payload bytes are not copied into qlog output

## Versioning

- `qlog_version`: 0.3
- `package_schema`: tigrcorn.qlog.experimental.v1
- `upgrade_rule`: schema_version changes when redaction fields, event envelopes, or emitted packet summary fields change incompatibly

## Experimental markers

- `experimental_marker`: `trace.common_fields.tigrcorn_qlog.experimental`
- `redaction_marker`: `trace.common_fields.tigrcorn_qlog.redaction`
