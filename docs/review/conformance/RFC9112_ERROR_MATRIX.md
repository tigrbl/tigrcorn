# RFC 9112 error matrix

This artifact enumerates the HTTP/1.1 request-parse and framing rejection surface locked by the local Phase 3 corpus.

| Section | Condition | Surface |
| --- | --- | --- |
| request_line | invalid_shape | ProtocolError |
| request_line | invalid_http_version_token | ProtocolError |
| request_line | invalid_method_token | ProtocolError |
| request_line | non_ascii_request_line | ProtocolError |
| request_line | unsupported_http_version | ProtocolError |
| request_target | invalid_origin_form | ProtocolError |
| request_target | invalid_absolute_form | ProtocolError |
| request_target | invalid_authority_form | ProtocolError |
| request_target | asterisk_form_non_options | ProtocolError |
| headers | invalid_header_field_name | ProtocolError |
| headers | invalid_header_field_value | ProtocolError |
| headers | obsolete_line_folding | ProtocolError |
| headers | malformed_header_line | ProtocolError |
| headers | missing_or_nonunique_host_http11 | ProtocolError |
| headers | invalid_content_length | ProtocolError |
| headers | conflicting_content_length | ProtocolError |
| headers | content_length_plus_chunked_transfer_encoding | ProtocolError |
| headers | repeated_chunked_transfer_encoding | ProtocolError |
| headers | nonfinal_chunked_transfer_encoding | ProtocolError |
| headers | unsupported_transfer_encoding | UnsupportedFeature |
| headers | request_head_oversize | ProtocolError |
| body | body_oversize | ProtocolError |
| body | unexpected_eof | ProtocolError |
| body | invalid_chunk_size | ProtocolError |
| body | invalid_chunk_terminator | ProtocolError |
| body | malformed_chunk_trailer | ProtocolError |

This matrix is intentionally scoped to the package-owned parser/runtime behavior and does not claim complete independent certification.
