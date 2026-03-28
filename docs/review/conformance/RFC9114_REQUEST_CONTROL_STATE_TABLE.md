# RFC 9114 request/control state tables

## Request-stream phase transitions

| Phase | Event | Result |
| --- | --- | --- |
| initial | HEADERS | data |
| initial | DATA | connection_error:H3_FRAME_UNEXPECTED |
| initial | PUSH_PROMISE(client_only) | initial |
| initial | fin_without_headers | stream_error:H3_REQUEST_INCOMPLETE |
| data | DATA | data |
| data | HEADERS | trailers |
| data | PUSH_PROMISE(client_only) | data |
| data | fin_with_matching_content_length | ready |
| data | fin_with_mismatched_content_length | stream_error:H3_MESSAGE_ERROR |
| trailers | DATA | connection_error:H3_FRAME_UNEXPECTED |
| trailers | HEADERS | connection_error:H3_FRAME_UNEXPECTED |
| trailers | fin | ready |
| ready | terminal | — |

## Control-stream and critical-stream rules

| Section | Rule | Requirement |
| --- | --- | --- |
| control_stream | first_frame | SETTINGS |
| control_stream | duplicate_settings | connection_error:H3_FRAME_UNEXPECTED |
| control_stream | goaway_monotonicity | non_increasing |
| control_stream | max_push_id_monotonicity | non_decreasing |
| control_stream | cancel_push_reference | must_be_known_and_within_peer_max_push_id |
| critical_uni_streams | control | single_remote_instance_required |
| critical_uni_streams | qpack_encoder | single_remote_instance_required |
| critical_uni_streams | qpack_decoder | single_remote_instance_required |
| critical_uni_streams | closed_critical_stream | connection_error:H3_CLOSED_CRITICAL_STREAM |
| request_stream | push_promise_on_server_request_stream | connection_error:H3_FRAME_UNEXPECTED |
| request_stream | frames_permitted | HEADERS, DATA, PUSH_PROMISE(client_only), unknown/reserved ignored |
