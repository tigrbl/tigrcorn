from __future__ import annotations

from .imports import *

@dataclass(slots=True)
class InteropProcessSpec:
    name: str
    adapter: str
    role: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    ready_pattern: str | None = None
    ready_timeout: float = DEFAULT_READY_TIMEOUT
    run_timeout: float = DEFAULT_RUN_TIMEOUT
    version_command: list[str] | None = None
    image: str | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance_kind: str = 'unspecified'
    implementation_source: str | None = None
    implementation_identity: str | None = None
    implementation_version: str | None = None


@dataclass(slots=True)
class InteropScenario:
    id: str
    protocol: str
    role: str
    feature: str
    peer: str
    sut: InteropProcessSpec
    peer_process: InteropProcessSpec
    assertions: list[dict[str, Any]] = field(default_factory=list)
    transport: str | None = None
    ip_family: str = 'ipv4'
    cipher_group: str | None = None
    retry: bool = False
    resumption: bool = False
    zero_rtt: bool = False
    key_update: bool = False
    migration: bool = False
    goaway: bool = False
    qpack_blocking: bool = False
    capture: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence_tier: str = 'mixed'
    enabled: bool = True

    @property
    def dimensions(self) -> dict[str, Any]:
        return {
            'protocol': self.protocol,
            'role': self.role,
            'feature': self.feature,
            'peer': self.peer,
            'cipher_group': self.cipher_group,
            'ip_family': self.ip_family,
            'retry': self.retry,
            'resumption': self.resumption,
            'zero_rtt': self.zero_rtt,
            'key_update': self.key_update,
            'migration': self.migration,
            'goaway': self.goaway,
            'qpack_blocking': self.qpack_blocking,
            'evidence_tier': self.evidence_tier,
        }


@dataclass(slots=True)
class InteropMatrix:
    name: str
    scenarios: list[InteropScenario]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def enabled_scenarios(self) -> list[InteropScenario]:
        return [scenario for scenario in self.scenarios if scenario.enabled and scenario.sut.enabled and scenario.peer_process.enabled]


@dataclass(slots=True)
class InteropProcessResult:
    name: str
    adapter: str
    role: str
    exit_code: int | None
    stdout_path: str
    stderr_path: str
    stdout_text: str = ''
    stderr_text: str = ''
    version: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    timed_out: bool = False
    error: str | None = None

    def to_observed(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'adapter': self.adapter,
            'role': self.role,
            'exit_code': self.exit_code,
            'stdout_path': self.stdout_path,
            'stderr_path': self.stderr_path,
            'stdout_text': self.stdout_text,
            'stderr_text': self.stderr_text,
            'version': self.version,
            'provenance': self.provenance,
            'timed_out': self.timed_out,
            'error': self.error,
        }


@dataclass(slots=True)
class InteropScenarioResult:
    scenario_id: str
    passed: bool
    commit_hash: str
    artifact_dir: str
    assertions_failed: list[str] = field(default_factory=list)
    error: str | None = None
    sut: dict[str, Any] = field(default_factory=dict)
    peer: dict[str, Any] = field(default_factory=dict)
    transcript: dict[str, Any] = field(default_factory=dict)
    negotiation: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InteropRunSummary:
    matrix_name: str
    commit_hash: str
    artifact_root: str
    total: int
    passed: int
    failed: int
    skipped: int
    scenarios: list[InteropScenarioResult]


class InteropRunnerError(RuntimeError):
    pass

__all__ = [name for name in globals() if not name.startswith('__')]
