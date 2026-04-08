# Static Origin Operator Guide

This file is generated from the package-owned Phase 5 origin metadata and the public CLI parser.

## Operator controls

| Surface | Config path | Help | Runtime effect |
|---|---|---|---|
| `--static-path-route` | `static.route` | HTTP route prefix served from the mounted static directory | Mount the package-owned static origin contract under the chosen route prefix. |
| `--static-path-mount` | `static.mount` | Filesystem directory mounted at --static-path-route | Select the filesystem root used for mount-relative path resolution and symlink containment checks. |
| `--static-path-dir-to-file` | `static.dir_to_file` | directory index resolution for the mounted static path | Enable directory-to-index resolution instead of returning 404 for directory requests. |
| `--static-path-index-file` | `static.index_file` | Index file name served when directory index resolution is enabled | Choose the index file name used when directory-to-index resolution is enabled. |
| `--static-path-expires` | `static.expires` | Static-response cache TTL in seconds; 0 disables caching headers | Emit Cache-Control and Expires based on the configured TTL; zero or negative means no-store. |
| `http.response.pathsend` | `ASGI extension` |  | Stream an absolute file path with a dispatch-time size snapshot and protocol-specific transfer strategy. |

## Frozen behaviors

- Percent-decoding happens once before mount-relative normalization.
- Parent-reference segments and backslash-separated segments are denied.
- Directory requests do not redirect; they either resolve to the configured index file or return 404.
- Range requests bypass dynamic content coding and stay on the identity representation.
- `http.response.pathsend` snapshots file length at dispatch and does not stream bytes appended later.
