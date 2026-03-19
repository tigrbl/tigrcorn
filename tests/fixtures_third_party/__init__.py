"""Third-party interop adapters used by the certification matrices.

These modules intentionally avoid importing tigrcorn internals. They are wrappers
around independently maintained HTTP/3 tooling so the certification matrix can
separate true third-party peers from same-stack replay fixtures.
"""
