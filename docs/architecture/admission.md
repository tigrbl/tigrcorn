# Transport admission

Tigrcorn owns connection, protocol-session, and transport-stream limits. Tigrbl separately
owns authenticated logical-subscription quotas.

```toml
# server.toml
[admission]
max_connections_per_source = 8
max_connections_per_instance = 1024
max_sessions_per_connection = 4
max_sessions_per_instance = 1024
max_active_streams_per_connection = 64
max_active_streams_per_session = 32
max_active_streams_per_source = 128
max_active_streams_per_instance = 4096
stream_open_rate_per_source = 40
stream_open_burst_per_source = 80
stream_open_rate_per_instance = 1000
stream_open_burst_per_instance = 2000
```

```powershell
$env:TIGRCORN_MAX_ACTIVE_STREAMS_PER_SOURCE = '96'
tigrcorn app:app --config server.toml --max-active-streams-per-source 128
```

Every public `AdmissionConfig` field has a matching TOML key, kebab-case flag, and
`TIGRCORN_<UPPER_SNAKE_NAME>` variable. CLI overrides environment, then TOML, then defaults.
Caps/bursts must be positive integers; rates must be finite and positive and require a
burst. New limits default unset for compatibility; configure finite values explicitly.
Existing HTTP/2, QUIC, and WebTransport protocol limits still apply independently.

```python
from tigrcorn import run
from tigrcorn_config import AdmissionConfig, ServerConfig

config = ServerConfig(admission=AdmissionConfig(
    max_active_streams_per_source=128,
    max_active_streams_per_instance=4096,
    stream_open_rate_per_source=40, stream_open_burst_per_source=80,
))
run(app, config=config)
```

Typed configuration is authoritative. Python callers can use `build_config_from_sources`
to merge file/environment/explicit mappings. Multiple workers require an importable target:
`run("app:app", config=config)` or the CLI process launcher.

Connection caps apply per source/instance; session caps per connection/source/instance;
stream caps additionally support protocol-session scope. Opening-rate/burst fields use
the same applicable scopes. A close/reset returns terminal active capacity but never
refunds opening tokens. Bidirectional half-close alone does not return capacity.

HTTP/1.1 accounts request/message-body lifetimes; HTTP/2 and QUIC refuse excess streams
before application dispatch. HTTP/1.1 uses 429 for source pressure or 503 for instance
pressure, HTTP/2 uses stream refusal, and QUIC uses legal stop/reset events. HTTP/3
control/QPACK streams have a bounded separate reservation. WebTransport child attachment
does not charge connection/source/instance stream capacity twice.

Source identity is the canonical socket peer without ephemeral port. QUIC accounting stays
bound to the original connection across migration. Forwarded HTTP headers cannot bypass
peer budgets. Clients behind a proxy/NAT share the transport peer budget; authenticated
application quotas provide finer fairness.

All workers share a SQLite coordinator with atomic budget/rate transactions. Owner
generations distinguish replacements; only confirmed dead workers are reclaimed. A TTL
alone never reclaims live transport resources. Coordination failure refuses new work.
Windows workers receive transferred sockets and use selector loops for shared listeners.
Instance scope does not mean deployment-wide transport coordination.

`max_tracking_entries` bounds opening-bucket storage and HTTP/3 stream history. Outstanding
token debt is never evicted to grant unmetered access. At QUIC history exhaustion the
connection closes; reconnect remains subject to opening rates. HTTP/2 compacts closed IDs
while preserving high-water marks so old stream IDs cannot reopen.

`server.admission_snapshot()` reports effective policy, counts, attempts, admissions, and
refusals without source IDs, credentials, internal paths, or owner-generation tokens.
