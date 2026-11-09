# Certification Explicit Surfaces

`bnd:certification-explicit-surfaces` freezes the explicit certification
surfaces that sit outside the already promoted package-wide boundary but are
now concrete, named, and testable. The boundary covers TLS, X.509, QUIC,
HTTP/3, operator field posture, observability, and negative-corpus surfaces.

This document is paired with:

- `certification_explicit_surfaces.json` for the machine-readable closure
  manifest.
- `tigrcorn_certification.explicit_surfaces` for the packaged runtime catalog.
- `tests/test_certification_explicit_surfaces_boundary.py` for executable
  agreement checks.

The boundary closes only when the manifest, packaged catalog,
`.ssot/registry.json`, and preserved release evidence agree on the same feature
set.
