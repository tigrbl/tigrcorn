from __future__ import annotations

ORIGIN_CONTRACT = {
    'flag_group': 'static_path',
    'public_api': ['tigrcorn.StaticFilesApp', 'tigrcorn.static.mount_static_app'],
    'path_resolution': {
        'decode_order': 'Percent-decode the request path once before mount-relative normalization.',
        'dot_segments': 'Reject any parent-reference ".." segment after decoding; ignore "." segments and repeated slashes.',
        'separator_policy': 'Treat "/" as the only valid request-path separator and reject segments containing "\\" to keep behavior platform-neutral.',
        'mount_root': 'Resolve against the configured mount root and require the final candidate to remain under that root after symlink resolution.',
        'symlink_policy': 'Allow symlinks only when the fully resolved target stays within the mount root; deny escaping symlinks.',
        'hidden_file_policy': 'Hidden files and directories are treated as ordinary mount-relative names when they remain inside the mount root.',
        'slash_redirects': 'Do not synthesize slash redirects; a directory resolves to index content only when dir_to_file is enabled and the index file exists.',
    },
    'file_selection': {
        'index_behavior': 'Directory requests map to index_file only when dir_to_file is true and index_file is configured.',
        'missing_index': 'Directory requests without a resolvable index return 404 rather than redirecting or listing.',
        'mime_derivation': 'Derive Content-Type from mimetypes.guess_type(candidate); fall back to application/octet-stream.',
        'precompressed_sidecars': 'When enabled and accepted, prefer .br or .gz sidecars for whole-response GET/HEAD paths; Range requests stay on the identity representation.',
        'validator_generation': 'Generate strong ETag values from the selected representation bytes and pair them with Last-Modified.',
    },
    'http_semantics': {
        'head_parity': 'HEAD preserves the would-be selected representation headers, validators, Content-Length, and range/conditional status while suppressing the body.',
        'conditional_statuses': 'Conditional evaluation may produce 304 Not Modified or 412 Precondition Failed before range processing.',
        'range_statuses': 'Range evaluation may produce 206 Partial Content, 200 full-response fallback, or 416 Range Not Satisfiable with Content-Range: bytes */length.',
        'if_range': 'If-Range accepts a matching strong ETag or sufficiently fresh Last-Modified value; otherwise the full representation is served.',
        'content_coding_interaction': 'Dynamic content coding is bypassed whenever Range is present so byte positions remain deterministic.',
    },
    'pathsend': {
        'dispatch_requirements': 'http.response.pathsend requires an absolute path to an existing regular file.',
        'length_snapshot': 'The server snapshots the file length when it accepts the pathsend event and uses that byte count for transfer planning.',
        'growth_race': 'Bytes appended after dispatch are not sent once the snapshot length has been fixed.',
        'shrink_race': 'If the file shrinks or disappears after dispatch, transfer may terminate early or abort because the response has already started.',
        'disconnect_race': 'Client disconnects end the in-flight transfer on a best-effort basis; the package does not retry, rewind, or re-dispatch the file.',
        'zero_copy': 'HTTP/1.1 may use best-effort sendfile when available; HTTP/2 and HTTP/3 stream the planned file segments.',
    },
}


PATH_RESOLUTION_CASES = [
    {
        'request_path': '/hello.txt',
        'decoded_path': '/hello.txt',
        'normalized_segments': ['hello.txt'],
        'expected': 'mount-relative file lookup',
    },
    {
        'request_path': '/nested/./asset.txt',
        'decoded_path': '/nested/./asset.txt',
        'normalized_segments': ['nested', 'asset.txt'],
        'expected': 'dot segments are ignored',
    },
    {
        'request_path': '/nested//asset.txt',
        'decoded_path': '/nested//asset.txt',
        'normalized_segments': ['nested', 'asset.txt'],
        'expected': 'repeated slashes collapse during PurePosixPath normalization',
    },
    {
        'request_path': '/%2E%2E/secret.txt',
        'decoded_path': '/../secret.txt',
        'normalized_segments': None,
        'expected': 'parent-reference segment rejected after percent-decoding',
    },
    {
        'request_path': '/dir\\\\..\\\\secret.txt',
        'decoded_path': '/dir\\\\..\\\\secret.txt',
        'normalized_segments': None,
        'expected': 'backslash-containing segment rejected to avoid platform-specific traversal',
    },
]


ORIGIN_NEGATIVE_CORPUS = [
    {
        'id': 'encoded-parent-segment',
        'surface': 'path_resolution',
        'request_path': '/%2e%2e/secret.txt',
        'expected_status': 404,
        'expected_result': 'deny_after_single_decode',
    },
    {
        'id': 'backslash-separator-segment',
        'surface': 'path_resolution',
        'request_path': '/dir\\\\..\\\\secret.txt',
        'expected_status': 404,
        'expected_result': 'deny_platform_specific_separator',
    },
    {
        'id': 'escaping-symlink',
        'surface': 'path_resolution',
        'request_path': '/escape.txt',
        'expected_status': 404,
        'expected_result': 'deny_symlink_escape',
    },
    {
        'id': 'directory-without-index',
        'surface': 'file_selection',
        'request_path': '/docs/',
        'expected_status': 404,
        'expected_result': 'deny_directory_listing_or_redirect',
    },
    {
        'id': 'unsatisfied-range',
        'surface': 'http_semantics',
        'request_headers': {'range': 'bytes=999-1000'},
        'expected_status': 416,
        'expected_result': 'content-range-bytes-star-length',
    },
    {
        'id': 'stale-if-range',
        'surface': 'http_semantics',
        'request_headers': {'range': 'bytes=0-4', 'if-range': 'stale-validator'},
        'expected_status': 200,
        'expected_result': 'full_representation_fallback',
    },
    {
        'id': 'pathsend-relative-path',
        'surface': 'pathsend',
        'request_path': 'relative.bin',
        'expected_status': None,
        'expected_result': 'asgi_protocol_error',
    },
    {
        'id': 'pathsend-missing-file',
        'surface': 'pathsend',
        'request_path': '/missing/file.bin',
        'expected_status': None,
        'expected_result': 'asgi_protocol_error',
    },
    {
        'id': 'pathsend-growth-race',
        'surface': 'pathsend',
        'request_path': '/payload.bin',
        'expected_status': 200,
        'expected_result': 'transfer_capped_to_dispatch_snapshot_length',
    },
    {
        'id': 'pathsend-disconnect',
        'surface': 'pathsend',
        'request_path': '/payload.bin',
        'expected_status': None,
        'expected_result': 'best_effort_termination_without_retry',
    },
]


STATIC_OPERATOR_SURFACE = [
    {
        'surface': '--static-path-route',
        'config_path': 'static.route',
        'runtime_effect': 'Mount the package-owned static origin contract under the chosen route prefix.',
    },
    {
        'surface': '--static-path-mount',
        'config_path': 'static.mount',
        'runtime_effect': 'Select the filesystem root used for mount-relative path resolution and symlink containment checks.',
    },
    {
        'surface': '--static-path-dir-to-file',
        'config_path': 'static.dir_to_file',
        'runtime_effect': 'Enable directory-to-index resolution instead of returning 404 for directory requests.',
    },
    {
        'surface': '--static-path-index-file',
        'config_path': 'static.index_file',
        'runtime_effect': 'Choose the index file name used when directory-to-index resolution is enabled.',
    },
    {
        'surface': '--static-path-expires',
        'config_path': 'static.expires',
        'runtime_effect': 'Emit Cache-Control and Expires based on the configured TTL; zero or negative means no-store.',
    },
    {
        'surface': 'http.response.pathsend',
        'config_path': 'ASGI extension',
        'runtime_effect': 'Stream an absolute file path with a dispatch-time size snapshot and protocol-specific transfer strategy.',
    },
]


__all__ = ['ORIGIN_CONTRACT', 'ORIGIN_NEGATIVE_CORPUS', 'PATH_RESOLUTION_CASES', 'STATIC_OPERATOR_SURFACE']
