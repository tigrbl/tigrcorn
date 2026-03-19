# Current repository state

The canonical package-wide certification target is defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

A current gate snapshot is also published in `docs/review/conformance/RELEASE_GATE_STATUS.md` and `docs/review/conformance/release_gate_status.current.json`.

A focused status document for the now-completed third-party HTTP/3 and RFC 9220 closure work lives in `docs/review/conformance/INDEPENDENT_HTTP3_CERTIFICATION_STATE.md`.

The policy decision that resolved the earlier local-tier documentation mismatch is recorded in `docs/review/conformance/CERTIFICATION_POLICY_ALIGNMENT.md`.

Historical offline-planning artifacts remain documented in `docs/review/conformance/OFFLINE_COMPLETION_ATTEMPT.md`, `docs/review/conformance/offline_completion_state.json`, `docs/review/conformance/ALL_SURFACES_INDEPENDENT_STATUS.md`, `docs/review/conformance/all_surfaces_independent_state.json`, `docs/review/conformance/FLOW_CONTROL_CERTIFICATION_STATUS.md`, `docs/review/conformance/SECONDARY_PARTIALS_STATUS.md`, and `docs/review/conformance/secondary_partials_state.json`.

## Completed in this update

- The package-owned TCP/TLS listener path remains package-owned and does not delegate the release-critical listener path to `ssl.create_default_context`.
- The canonical release evidence remains consolidated under `docs/review/conformance/releases/0.3.6/release-0.3.6/`.
- `docs/review/conformance/external_matrix.release.json` now has preserved passing third-party artifacts for all declared `aioquic` HTTP/3 and RFC 9220 scenarios, and those scenarios are enabled in the canonical independent matrix.
- The canonical independent bundle now includes preserved passing artifacts for 17 enabled independent-certification scenarios.
- The package now preserves passing third-party `aioquic` evidence for:
  - HTTP/3 request/response
  - mTLS
  - Retry
  - resumption
  - 0-RTT
  - migration
  - GOAWAY / QPACK observation
  - RFC 9220 WebSocket-over-HTTP/3
- The runtime fixes required to make those preserved artifacts honest are now committed in-tree, including:
  - correct QUIC Initial receive-key derivation across Retry / server-client directions
  - correct HTTP/3 server control-stream / SETTINGS emission during handshake completion
  - RFC-correct QUIC STREAM frame parsing for LEN / OFF flag combinations
  - compact QUIC session-ticket payload encoding for third-party resumption interop
  - ClientHello PSK binder hashing against the original-length handshake bytes
- The third-party RFC 9220 adapter now decodes server-to-client frames in client mode and drives the CONNECT stream in the same one-message / wait-for-echo pattern as the package-owned H3 WebSocket client.
- The provisional bundles remain preserved in-tree, but they are now historical / planning aids rather than the primary explanation for the package state.

## Authoritative certification result

Under the authoritative certification boundary in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`, this repository is now **certifiably fully RFC compliant**.

The release-gate result is green:

- `evaluate_release_gates('.')` → `passed=True`
- `failure_count=0`

The six RFCs that were previously blocked at the independent tier are now satisfied at `independent_certification`:

- RFC 9114
- RFC 9000
- RFC 9001
- RFC 9002
- RFC 9204
- RFC 9220

The boundary intentionally keeps the following RFC surfaces at `local_conformance` in the current authoritative policy:

- RFC 7692
- RFC 9110 §9.3.6 (CONNECT)
- RFC 9110 §6.5 (trailers)
- RFC 9110 §8 (content coding)
- RFC 6960

Those surfaces remain part of the required RFC surface and are satisfied at the tier required by the authoritative boundary.

## Remaining non-blocking follow-on work

The repository still preserves stricter and broader follow-on work that is **not** part of the authoritative current release-gate blocker set:

- the non-authoritative all-surfaces-independent overlay still lacks additional third-party artifacts for RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960
- the provisional QUIC / HTTP/3 flow-control review bundle remains a review aid rather than a promoted independent-certification bundle
- the intermediary / proxy corpus is still a seed corpus rather than a broad third-party interoperability certification program

Those items matter for future strengthening, but they do not invalidate the current passing release-gate result.

## Validation snapshot for this checkpoint

The repository was revalidated with the release-gate evaluator after promoting the missing `aioquic` artifacts.

A machine-readable copy of the current gate state is stored in `docs/review/conformance/release_gate_status.current.json`.
