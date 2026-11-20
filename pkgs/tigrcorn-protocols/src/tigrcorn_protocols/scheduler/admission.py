"""Atomic, instance-scoped transport admission, shared by all server workers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import ipaddress
import os
import sqlite3
import tempfile
import time
from uuid import uuid4


class AdmissionDenied(RuntimeError):
    def __init__(self, reason, resource, scope, retry_after=None):
        self.reason, self.resource, self.scope = reason, resource, scope
        self.retry_after = retry_after
        super().__init__(f"transport {resource} admission {reason} ({scope})")


@dataclass
class AdmissionLease:
    controller: object
    id: str
    released: bool = False

    def release(self):
        if not self.released:
            self.controller.release(self.id)
            self.released = True


def source_key(peer):
    value = str(peer[0] if isinstance(peer, tuple) else peer or "local")
    try:
        address = ipaddress.ip_address(value)
        value = str(getattr(address, "ipv4_mapped", None) or address)
    except ValueError:
        pass
    return hashlib.sha256(value.encode()).hexdigest()


class AdmissionController:
    """SQLite serializes multi-budget transactions across threads and processes.

    Leases have no TTL: only terminal resource events or confirmed worker death may
    reclaim capacity. Coordinator failure refuses admission instead of falling back.
    """

    def __init__(self, config, *, path=None, owner=None, clock=time.monotonic):
        self.config, self.clock = config, clock
        self._closed = False
        self._owns_path = path is None and config.coordinator_path is None
        self.owner = owner or config.owner_generation or f"{os.getpid()}:{uuid4().hex}"
        self.path = path or config.coordinator_path
        if self.path is None:
            fd, self.path = tempfile.mkstemp(prefix="tigrcorn-admission-", suffix=".db")
            os.close(fd)
        self.db = sqlite3.connect(
            self.path, timeout=0.05, isolation_level=None, check_same_thread=False
        )
        # Per-controller calls are serialized too; a connection cannot run two transactions.
        import threading

        self.lock = threading.RLock()
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS leases(id TEXT PRIMARY KEY, owner TEXT, kind TEXT, source TEXT, connection_id TEXT, session_id TEXT);
        CREATE INDEX IF NOT EXISTS lease_kind ON leases(kind);
        CREATE INDEX IF NOT EXISTS lease_owner ON leases(owner);
        CREATE INDEX IF NOT EXISTS lease_source ON leases(kind,source);
        CREATE INDEX IF NOT EXISTS lease_connection ON leases(kind,connection_id);
        CREATE INDEX IF NOT EXISTS lease_session ON leases(kind,session_id);
        CREATE TABLE IF NOT EXISTS buckets(key TEXT PRIMARY KEY, tokens REAL, updated REAL, rate REAL, burst INTEGER);
        CREATE INDEX IF NOT EXISTS bucket_updated ON buckets(updated);
        CREATE TABLE IF NOT EXISTS counters(key TEXT PRIMARY KEY, value INTEGER);
        """)

    def _cleanup_buckets(self, now):
        self.db.execute(
            "DELETE FROM buckets WHERE key IN (SELECT key FROM (SELECT * FROM buckets ORDER BY updated LIMIT 32) WHERE tokens+(?-updated)*rate>=burst)",
            (now,),
        )

    def _count(self, key):
        self.db.execute(
            "INSERT INTO counters VALUES(?,1) ON CONFLICT(key) DO UPDATE SET value=value+1",
            (key,),
        )

    def acquire(
        self, kind, *, source, connection_id="", session_id="", client_initiated=True
    ):
        if self._closed:
            raise AdmissionDenied("coordinator_unavailable", kind, "instance")
        if kind not in {"connection", "session", "stream"}:
            raise ValueError("unknown admission resource")
        source = source_key(source)
        scopes = [("source", source), ("instance", "all")]
        if kind != "connection":
            scopes.insert(0, ("connection", connection_id))
        if kind == "stream" and session_id:
            scopes.insert(1, ("session", session_id))
        now = self.clock()
        denied = None
        lease_id = uuid4().hex
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                self._count(kind + ".attempts")
                if client_initiated:
                    # Check all applicable buckets before charging, then charge them once.
                    buckets = []
                    new_bucket_count = 0
                    for scope, key in scopes:
                        rate = getattr(
                            self.config, f"{kind}_open_rate_per_{scope}", None
                        )
                        burst = getattr(
                            self.config, f"{kind}_open_burst_per_{scope}", None
                        )
                        if rate is None:
                            continue
                        bucket = f"{kind}:{scope}:{key}"
                        row = self.db.execute(
                            "SELECT tokens,updated FROM buckets WHERE key=?", (bucket,)
                        ).fetchone()
                        tokens = (
                            burst
                            if row is None
                            else min(burst, row[0] + max(0, now - row[1]) * rate)
                        )
                        if row is None:
                            # Reclaim only fully refilled entries, never outstanding debt.
                            self._cleanup_buckets(now)
                            size = self.db.execute(
                                "SELECT count(*) FROM buckets"
                            ).fetchone()[0]
                            if (
                                size + new_bucket_count
                                >= self.config.max_tracking_entries
                            ):
                                denied = AdmissionDenied(
                                    "tracking_capacity", kind, scope
                                )
                                break
                        if row is None:
                            new_bucket_count += 1
                        if tokens < 1:
                            denied = AdmissionDenied(
                                "rate", kind, scope, (1 - tokens) / rate
                            )
                            break
                        buckets.append((bucket, tokens - 1, now, rate, burst))
                    if denied is None:
                        self.db.executemany(
                            "INSERT INTO buckets VALUES(?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET tokens=excluded.tokens,updated=excluded.updated,rate=excluded.rate,burst=excluded.burst",
                            buckets,
                        )
                # Rate tokens remain charged when active-cap admission fails.
                if denied is None:
                    for scope, key in scopes:
                        prefix = (
                            "max_active_streams"
                            if kind == "stream"
                            else "max_" + kind + "s"
                        )
                        limit = getattr(self.config, f"{prefix}_per_{scope}", None)
                        if limit is None:
                            continue
                        column = {
                            "source": "source",
                            "connection": "connection_id",
                            "session": "session_id",
                        }.get(scope)
                        sql = "SELECT count(*) FROM leases WHERE kind=?"
                        args = [kind]
                        if column:
                            sql += " AND " + column + "=?"
                            args.append(key)
                        if self.db.execute(sql, args).fetchone()[0] >= limit:
                            denied = AdmissionDenied("capacity", kind, scope)
                            break
                if denied is None:
                    self.db.execute(
                        "INSERT INTO leases VALUES(?,?,?,?,?,?)",
                        (lease_id, self.owner, kind, source, connection_id, session_id),
                    )
                    self._count(kind + ".admitted")
                else:
                    self._count(kind + ".refused." + denied.reason)
                self.db.execute("COMMIT")
            except sqlite3.Error as exc:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
                raise AdmissionDenied(
                    "coordinator_unavailable", kind, "instance"
                ) from exc
        if denied:
            raise denied
        return AdmissionLease(self, lease_id)

    def release(self, lease_id):
        if self._closed:
            return
        with self.lock:
            self.db.execute(
                "DELETE FROM leases WHERE id=? AND owner=?", (lease_id, self.owner)
            )

    def attach_session(self, lease_id, session_id):
        """Attach an already admitted child without double charging parent budgets."""
        now = self.clock()
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute(
                    "SELECT session_id FROM leases WHERE id=? AND owner=?",
                    (lease_id, self.owner),
                ).fetchone()
                if row is None:
                    raise AdmissionDenied("closed", "stream", "session")
                if row[0] == session_id:
                    self.db.execute("COMMIT")
                    return
                rate = self.config.stream_open_rate_per_session
                if rate is not None:
                    key = "stream:session:" + session_id
                    burst = self.config.stream_open_burst_per_session
                    bucket = self.db.execute(
                        "SELECT tokens,updated FROM buckets WHERE key=?", (key,)
                    ).fetchone()
                    if bucket is None:
                        self._cleanup_buckets(now)
                        size = self.db.execute(
                            "SELECT count(*) FROM buckets"
                        ).fetchone()[0]
                        if size >= self.config.max_tracking_entries:
                            raise AdmissionDenied(
                                "tracking_capacity", "stream", "session"
                            )
                    tokens = (
                        burst
                        if bucket is None
                        else min(burst, bucket[0] + max(0, now - bucket[1]) * rate)
                    )
                    if tokens < 1:
                        self.db.execute("COMMIT")
                        raise AdmissionDenied(
                            "rate", "stream", "session", (1 - tokens) / rate
                        )
                    self.db.execute(
                        "INSERT INTO buckets VALUES(?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET tokens=excluded.tokens,updated=excluded.updated",
                        (key, tokens - 1, now, rate, burst),
                    )
                cap = self.config.max_active_streams_per_session
                count = self.db.execute(
                    "SELECT count(*) FROM leases WHERE kind='stream' AND session_id=?",
                    (session_id,),
                ).fetchone()[0]
                if cap is not None and count >= cap:
                    self.db.execute("COMMIT")
                    raise AdmissionDenied("capacity", "stream", "session")
                self.db.execute(
                    "UPDATE leases SET session_id=? WHERE id=?", (session_id, lease_id)
                )
                self.db.execute("COMMIT")
            except Exception:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
                raise

    def release_connection(self, connection_id):
        if self._closed:
            return
        with self.lock:
            self.db.execute(
                "DELETE FROM leases WHERE connection_id=? AND owner=?",
                (connection_id, self.owner),
            )

    def reclaim_owner(self, owner):
        with self.lock:
            self.db.execute("DELETE FROM leases WHERE owner=?", (owner,))

    def reclaim_pid(self, pid):
        """Supervisor-only: call after the OS confirms the old worker has exited."""
        with self.lock:
            self.db.execute("DELETE FROM leases WHERE owner LIKE ?", (str(pid) + ":%",))

    def snapshot(self):
        with self.lock:
            active = dict(
                self.db.execute("SELECT kind,count(*) FROM leases GROUP BY kind")
            )
            counters = dict(self.db.execute("SELECT key,value FROM counters"))
        policy = asdict(self.config)
        policy.pop("coordinator_path", None)
        policy.pop("owner_generation", None)
        return {
            "scope": "instance",
            "owner": "tigrcorn",
            "policy": policy,
            "active": active,
            "counters": counters,
        }

    def close(self):
        if self._closed:
            return
        with self.lock:
            self.db.execute("DELETE FROM leases WHERE owner=?", (self.owner,))
            self.db.close()
            self._closed = True
            if self._owns_path:
                try:
                    os.unlink(self.path)
                except OSError:
                    pass
