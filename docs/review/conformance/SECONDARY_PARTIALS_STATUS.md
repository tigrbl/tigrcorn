
# Secondary partials status

The authoritative package-wide certification target remains `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

This status file tracks repository-strengthening items that remain outside the current canonical blocker set.

## Current secondary-status summary

- the package continues to ship the production scheduler integrated in `src/tigrcorn/scheduler/runtime.py`
- QUIC / HTTP/3 flow-control now has a minimum independent evidence root under `docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-minimum-certified-flow-control-matrix/`
- the older provisional flow-control gap bundle remains preserved as a historical non-certifying review bundle
- the repository now preserves a minimum certified intermediary / proxy-adjacent corpus under `docs/review/conformance/intermediary_proxy_corpus_minimum_certified/`
- the older seed intermediary / proxy corpus remains preserved under `docs/review/conformance/intermediary_proxy_corpus/`

## Honest scope note

These additions materially improve repository completeness, but they do not by themselves close the stricter all-surfaces-independent overlay.
That stricter overlay still depends on preserved third-party artifacts for RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960.

## What improved in this checkpoint

- flow-control no longer depends only on a provisional same-stack review root
- the intermediary / proxy evidence posture is no longer only a seed corpus
- the repository now has explicit minimum certified roots for both domains while keeping the historical provisional / seed roots for provenance
