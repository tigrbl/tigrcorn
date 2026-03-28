# RFC 9113 state transition table

Explicit HTTP/2 stream lifecycle transitions used for the Phase 3 transport-core checkpoint.

| State | Action | Next state |
| --- | --- | --- |
| idle | open_remote | open |
| idle | reserve_local | reserved-local |
| reserved-local | open_local_reserved | half-closed-remote |
| reserved-local | mark_reset_received | closed |
| reserved-local | mark_reset_sent | closed |
| reserved-remote | mark_reset_received | closed |
| reserved-remote | mark_reset_sent | closed |
| open | receive_end_stream | half-closed-remote |
| open | send_end_stream | half-closed-local |
| open | mark_reset_received | closed |
| open | mark_reset_sent | closed |
| half-closed-local | receive_end_stream | closed |
| half-closed-local | mark_reset_received | closed |
| half-closed-local | mark_reset_sent | closed |
| half-closed-remote | send_end_stream | closed |
| half-closed-remote | mark_reset_received | closed |
| half-closed-remote | mark_reset_sent | closed |
| closed | terminal | — |
