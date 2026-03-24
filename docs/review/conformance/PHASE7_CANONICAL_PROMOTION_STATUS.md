# Phase 7 canonical promotion status

## Result

Canonical promotion was **not** performed in this checkpoint.

The current authoritative canonical boundary remains `docs/review/conformance/certification_boundary.json`, and the current canonical release root remains `docs/review/conformance/releases/0.3.6/release-0.3.6/`.

A **candidate** next release root has been frozen at:

- `docs/review/conformance/releases/0.3.7/release-0.3.7/`

That candidate root now contains:

- independent certification bundle
- same-stack replay bundle
- mixed compatibility bundle
- flag-surface certification bundle
- operator-surface certification bundle
- performance certification bundle

## Why promotion is blocked

The strict all-surfaces-independent profile is still explicitly non-green:

- `strict_profile_release_gate_eligible = False`
- blocking RFCs: RFC 7692, RFC 9110 §9.3.6, RFC 9110 §6.5, RFC 9110 §8, RFC 6960
- blocking scenario count: 13

Missing independent scenarios:

- `websocket-http11-server-websockets-client-permessage-deflate`
- `websocket-http2-server-h2-client-permessage-deflate`
- `websocket-http3-server-aioquic-client-permessage-deflate`
- `http11-connect-relay-curl-client`
- `http2-connect-relay-h2-client`
- `http3-connect-relay-aioquic-client`
- `http11-trailer-fields-curl-client`
- `http2-trailer-fields-h2-client`
- `http3-trailer-fields-aioquic-client`
- `http11-content-coding-curl-client`
- `http2-content-coding-curl-client`
- `http3-content-coding-aioquic-client`
- `tls-server-ocsp-validation-openssl-client`

## Honest Phase 7 conclusion

Phase 7 cannot honestly replace `certification_boundary.json` with the stricter profile yet.

Doing so now would misrepresent the evidence because the stricter profile still depends on provisional / planning artifacts for the remaining strict-profile scenarios.

## What this checkpoint does land

- a frozen candidate release root under `releases/0.3.7/release-0.3.7/`
- candidate flag/operator/performance certification bundles for that root
- updated repository-state documentation explaining why canonical promotion is blocked
- a machine-readable status snapshot in `phase7_canonical_promotion_status.current.json`

## What must be true before promotion becomes honest

All of the following must become true first:

1. all required RFCs in the strict profile are green at the strict target tier
2. every RFC-scoped flag is documented, validated, tested, and backed by preserved evidence
3. every hybrid flag is validated under load and shown not to regress RFC behavior
4. every pure operator flag has smoke, deployment, and failure-mode coverage
5. every deployment profile has benchmark artifacts and threshold pass results
6. the remaining strict-profile independent scenarios above are preserved as true third-party artifacts
