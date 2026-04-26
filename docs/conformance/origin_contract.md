# Origin Contract

This file is generated from the package-owned Phase 5 origin metadata.

## Public surface

- Flag group: `static_path`
- Public API: `tigrcorn.StaticFilesApp, tigrcorn_static.static.mount_static_app`

## Path resolution

- `decode_order`: Percent-decode the request path once before mount-relative normalization.
- `dot_segments`: Reject any parent-reference ".." segment after decoding; ignore "." segments and repeated slashes.
- `separator_policy`: Treat "/" as the only valid request-path separator and reject segments containing "\" to keep behavior platform-neutral.
- `mount_root`: Resolve against the configured mount root and require the final candidate to remain under that root after symlink resolution.
- `symlink_policy`: Allow symlinks only when the fully resolved target stays within the mount root; deny escaping symlinks.
- `hidden_file_policy`: Hidden files and directories are treated as ordinary mount-relative names when they remain inside the mount root.
- `slash_redirects`: Do not synthesize slash redirects; a directory resolves to index content only when dir_to_file is enabled and the index file exists.

## File selection

- `index_behavior`: Directory requests map to index_file only when dir_to_file is true and index_file is configured.
- `missing_index`: Directory requests without a resolvable index return 404 rather than redirecting or listing.
- `mime_derivation`: Derive Content-Type from mimetypes.guess_type(candidate); fall back to application/octet-stream.
- `precompressed_sidecars`: When enabled and accepted, prefer .br or .gz sidecars for whole-response GET/HEAD paths; Range requests stay on the identity representation.
- `validator_generation`: Generate strong ETag values from the selected representation bytes and pair them with Last-Modified.

## HTTP semantics

- `head_parity`: HEAD preserves the would-be selected representation headers, validators, Content-Length, and range/conditional status while suppressing the body.
- `conditional_statuses`: Conditional evaluation may produce 304 Not Modified or 412 Precondition Failed before range processing.
- `range_statuses`: Range evaluation may produce 206 Partial Content, 200 full-response fallback, or 416 Range Not Satisfiable with Content-Range: bytes */length.
- `if_range`: If-Range accepts a matching strong ETag or sufficiently fresh Last-Modified value; otherwise the full representation is served.
- `content_coding_interaction`: Dynamic content coding is bypassed whenever Range is present so byte positions remain deterministic.

## ASGI pathsend

- `dispatch_requirements`: http.response.pathsend requires an absolute path to an existing regular file.
- `length_snapshot`: The server snapshots the file length when it accepts the pathsend event and uses that byte count for transfer planning.
- `growth_race`: Bytes appended after dispatch are not sent once the snapshot length has been fixed.
- `shrink_race`: If the file shrinks or disappears after dispatch, transfer may terminate early or abort because the response has already started.
- `disconnect_race`: Client disconnects end the in-flight transfer on a best-effort basis; the package does not retry, rewind, or re-dispatch the file.
- `zero_copy`: HTTP/1.1 may use best-effort sendfile when available; HTTP/2 and HTTP/3 stream the planned file segments.

## Path resolution table

| Request path | Decoded path | Normalized segments | Expected outcome |
|---|---|---|---|
| `/hello.txt` | `/hello.txt` | `hello.txt` | mount-relative file lookup |
| `/nested/./asset.txt` | `/nested/./asset.txt` | `nested/asset.txt` | dot segments are ignored |
| `/nested//asset.txt` | `/nested//asset.txt` | `nested/asset.txt` | repeated slashes collapse during PurePosixPath normalization |
| `/%2E%2E/secret.txt` | `/../secret.txt` | rejected | parent-reference segment rejected after percent-decoding |
| `/dir\\..\\secret.txt` | `/dir\\..\\secret.txt` | rejected | backslash-containing segment rejected to avoid platform-specific traversal |
