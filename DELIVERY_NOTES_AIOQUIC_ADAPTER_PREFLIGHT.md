# Delivery notes — aioquic adapter preflight

This checkpoint adds a direct aioquic adapter preflight on top of the existing Phase 9I release-assembly repository.

What changed:

- added a reusable aioquic preflight module at `src/tigrcorn/compat/aioquic_preflight.py`
- added a runnable checkpoint tool at `tools/preflight_aioquic_adapters.py`
- added a preserved preflight bundle under the 0.3.8 working release root
- updated the release workflow and local wrapper so aioquic adapter preflight is now mandatory before Phase 9 checkpoint scripts run
- updated current-state documentation

Current result:

- preflight bundle root: `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-aioquic-adapter-preflight-bundle`
- all adapters passed: `True`
- no peer exit code 2: `True`
- strict target after preflight: `True`
- promotion target after preflight: `True`

This checkpoint proves the third-party aioquic adapter execution path is healthy in the observed environment. It does not by itself claim that the package is already strict-target green or promotable.
