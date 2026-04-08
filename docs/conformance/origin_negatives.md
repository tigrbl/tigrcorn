# Origin Negative Corpus

This file is generated from the package-owned Phase 5 origin metadata.

| Case | Surface | Request path | Expected status | Expected outcome |
|---|---|---|---|---|
| `encoded-parent-segment` | `path_resolution` | `/%2e%2e/secret.txt` | `404` | `deny_after_single_decode` |
| `backslash-separator-segment` | `path_resolution` | `/dir\\..\\secret.txt` | `404` | `deny_platform_specific_separator` |
| `escaping-symlink` | `path_resolution` | `/escape.txt` | `404` | `deny_symlink_escape` |
| `directory-without-index` | `file_selection` | `/docs/` | `404` | `deny_directory_listing_or_redirect` |
| `unsatisfied-range` | `http_semantics` | `` | `416` | `content-range-bytes-star-length` |
| `stale-if-range` | `http_semantics` | `` | `200` | `full_representation_fallback` |
| `pathsend-relative-path` | `pathsend` | `relative.bin` |  | `asgi_protocol_error` |
| `pathsend-missing-file` | `pathsend` | `/missing/file.bin` |  | `asgi_protocol_error` |
| `pathsend-growth-race` | `pathsend` | `/payload.bin` | `200` | `transfer_capped_to_dispatch_snapshot_length` |
| `pathsend-disconnect` | `pathsend` | `/payload.bin` |  | `best_effort_termination_without_retry` |
