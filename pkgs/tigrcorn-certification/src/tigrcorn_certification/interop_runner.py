from __future__ import annotations

import json
import os
import platform
import re
import selectors
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from tigrcorn.config.observability_surface import QLOG_EXPERIMENTAL_SCHEMA_VERSION
from tigrcorn.transports.quic.packets import (
    QuicLongHeaderPacket,
    QuicRetryPacket,
    QuicShortHeaderPacket,
    QuicVersionNegotiationPacket,
    decode_packet,
    split_coalesced_packets,
)
from tigrcorn.version import __version__

DEFAULT_READY_TIMEOUT = 10.0
DEFAULT_RUN_TIMEOUT = 30.0
VALID_PROVENANCE_KINDS = {
    'unspecified',
    'same_stack_fixture',
    'third_party_library',
    'third_party_binary',
    'package_owned',
}
VALID_EVIDENCE_TIERS = {'local_conformance', 'same_stack_replay', 'independent_certification', 'mixed'}
INTEROP_ARTIFACT_SCHEMA_VERSION = 1
QLOG_VERSION = '0.3'
INTEROP_BUNDLE_REQUIRED_FILES = (
    'manifest.json',
    'summary.json',
    'index.json',
)
INTEROP_SCENARIO_REQUIRED_FILES = (
    'summary.json',
    'index.json',
    'result.json',
    'scenario.json',
    'command.json',
    'env.json',
    'versions.json',
    'wire_capture.json',
)


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


class _ManagedProcess:
    def __init__(self, process: subprocess.Popen[Any], stdout_path: Path, stderr_path: Path) -> None:
        self.process = process
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path

    def stop(self, *, timeout: float = 5.0) -> int | None:
        if self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                except Exception:
                    pass
                try:
                    self.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    return None
        return self.process.returncode


class BasePeerAdapter:
    def inspect_version(self, spec: InteropProcessSpec, *, env: Mapping[str, str], cwd: Path | None) -> dict[str, Any]:
        raise NotImplementedError

    def run_oneshot(
        self,
        spec: InteropProcessSpec,
        *,
        env: Mapping[str, str],
        cwd: Path | None,
        stdout_path: Path,
        stderr_path: Path,
    ) -> InteropProcessResult:
        raise NotImplementedError

    def start_persistent(
        self,
        spec: InteropProcessSpec,
        *,
        env: Mapping[str, str],
        cwd: Path | None,
        stdout_path: Path,
        stderr_path: Path,
    ) -> tuple[_ManagedProcess, InteropProcessResult]:
        raise NotImplementedError


class SubprocessPeerAdapter(BasePeerAdapter):
    def inspect_version(self, spec: InteropProcessSpec, *, env: Mapping[str, str], cwd: Path | None) -> dict[str, Any]:
        executable = shutil.which(spec.command[0]) if spec.command else None
        payload: dict[str, Any] = {
            'command': list(spec.command),
            'executable': executable,
        }
        if executable is not None:
            try:
                payload['executable_sha256'] = _sha256_path(Path(executable))
            except Exception:
                pass
        if spec.version_command is not None:
            try:
                completed = subprocess.run(
                    spec.version_command,
                    cwd=str(cwd) if cwd is not None else None,
                    env=dict(env),
                    capture_output=True,
                    text=True,
                    timeout=min(spec.run_timeout, 15.0),
                )
                payload['version_command'] = list(spec.version_command)
                payload['version_exit_code'] = completed.returncode
                payload['version_stdout'] = completed.stdout.strip()
                payload['version_stderr'] = completed.stderr.strip()
            except Exception as exc:
                payload['version_error'] = str(exc)
        return payload

    def run_oneshot(
        self,
        spec: InteropProcessSpec,
        *,
        env: Mapping[str, str],
        cwd: Path | None,
        stdout_path: Path,
        stderr_path: Path,
    ) -> InteropProcessResult:
        with stdout_path.open('w', encoding='utf-8', errors='replace') as stdout_handle, stderr_path.open('w', encoding='utf-8', errors='replace') as stderr_handle:
            try:
                completed = subprocess.run(
                    spec.command,
                    cwd=str(cwd) if cwd is not None else None,
                    env=dict(env),
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    text=True,
                    timeout=spec.run_timeout,
                )
                return InteropProcessResult(
                    name=spec.name,
                    adapter=spec.adapter,
                    role=spec.role,
                    exit_code=completed.returncode,
                    stdout_path=str(stdout_path),
                    stderr_path=str(stderr_path),
                    stdout_text=stdout_path.read_text(encoding='utf-8', errors='replace') if stdout_path.exists() else '',
                    stderr_text=stderr_path.read_text(encoding='utf-8', errors='replace') if stderr_path.exists() else '',
                )
            except subprocess.TimeoutExpired:
                return InteropProcessResult(
                    name=spec.name,
                    adapter=spec.adapter,
                    role=spec.role,
                    exit_code=None,
                    stdout_path=str(stdout_path),
                    stderr_path=str(stderr_path),
                    stdout_text=stdout_path.read_text(encoding='utf-8', errors='replace') if stdout_path.exists() else '',
                    stderr_text=stderr_path.read_text(encoding='utf-8', errors='replace') if stderr_path.exists() else '',
                    timed_out=True,
                    error=f'{spec.name} timed out after {spec.run_timeout:.3f}s',
                )
            except Exception as exc:
                return InteropProcessResult(
                    name=spec.name,
                    adapter=spec.adapter,
                    role=spec.role,
                    exit_code=None,
                    stdout_path=str(stdout_path),
                    stderr_path=str(stderr_path),
                    stdout_text=stdout_path.read_text(encoding='utf-8', errors='replace') if stdout_path.exists() else '',
                    stderr_text=stderr_path.read_text(encoding='utf-8', errors='replace') if stderr_path.exists() else '',
                    error=str(exc),
                )

    def start_persistent(
        self,
        spec: InteropProcessSpec,
        *,
        env: Mapping[str, str],
        cwd: Path | None,
        stdout_path: Path,
        stderr_path: Path,
    ) -> tuple[_ManagedProcess, InteropProcessResult]:
        stdout_handle = stdout_path.open('w', encoding='utf-8', errors='replace')
        stderr_handle = stderr_path.open('w', encoding='utf-8', errors='replace')
        try:
            process = subprocess.Popen(
                spec.command,
                cwd=str(cwd) if cwd is not None else None,
                env=dict(env),
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
            )
        finally:
            stdout_handle.close()
            stderr_handle.close()
        managed = _ManagedProcess(process, stdout_path, stderr_path)
        error = _wait_for_server_ready(
            spec=spec,
            process=process,
            env=env,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        result = InteropProcessResult(
            name=spec.name,
            adapter=spec.adapter,
            role=spec.role,
            exit_code=process.returncode,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            stdout_text=stdout_path.read_text(encoding='utf-8', errors='replace') if stdout_path.exists() else '',
            stderr_text=stderr_path.read_text(encoding='utf-8', errors='replace') if stderr_path.exists() else '',
            error=error,
        )
        if error is not None:
            managed.stop(timeout=1.0)
            result.exit_code = process.returncode
            result.stdout_text = stdout_path.read_text(encoding='utf-8', errors='replace') if stdout_path.exists() else ''
            result.stderr_text = stderr_path.read_text(encoding='utf-8', errors='replace') if stderr_path.exists() else ''
        return managed, result


class DockerPeerAdapter(SubprocessPeerAdapter):
    def inspect_version(self, spec: InteropProcessSpec, *, env: Mapping[str, str], cwd: Path | None) -> dict[str, Any]:
        payload = super().inspect_version(spec, env=env, cwd=cwd)
        if spec.image is not None:
            payload['image'] = spec.image
            try:
                completed = subprocess.run(
                    ['docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}', spec.image],
                    capture_output=True,
                    text=True,
                    timeout=15.0,
                )
                payload['image_inspect_exit_code'] = completed.returncode
                payload['image_repo_digests'] = completed.stdout.strip()
                payload['docker_stderr'] = completed.stderr.strip()
            except Exception as exc:
                payload['image_inspect_error'] = str(exc)
        return payload

    def _docker_command(self, spec: InteropProcessSpec) -> list[str]:
        if spec.image is None:
            raise InteropRunnerError('docker adapter requires an image')
        command = ['docker', 'run', '--rm']
        for key, value in spec.env.items():
            command.extend(['-e', f'{key}={value}'])
        command.append(spec.image)
        command.extend(spec.command)
        return command

    def run_oneshot(
        self,
        spec: InteropProcessSpec,
        *,
        env: Mapping[str, str],
        cwd: Path | None,
        stdout_path: Path,
        stderr_path: Path,
    ) -> InteropProcessResult:
        docker_spec = InteropProcessSpec(
            name=spec.name,
            adapter=spec.adapter,
            role=spec.role,
            command=self._docker_command(spec),
            env={},
            cwd=spec.cwd,
            ready_pattern=spec.ready_pattern,
            ready_timeout=spec.ready_timeout,
            run_timeout=spec.run_timeout,
            version_command=spec.version_command,
            image=spec.image,
            enabled=spec.enabled,
            metadata=dict(spec.metadata),
        )
        return super().run_oneshot(docker_spec, env=env, cwd=cwd, stdout_path=stdout_path, stderr_path=stderr_path)

    def start_persistent(
        self,
        spec: InteropProcessSpec,
        *,
        env: Mapping[str, str],
        cwd: Path | None,
        stdout_path: Path,
        stderr_path: Path,
    ) -> tuple[_ManagedProcess, InteropProcessResult]:
        docker_spec = InteropProcessSpec(
            name=spec.name,
            adapter=spec.adapter,
            role=spec.role,
            command=self._docker_command(spec),
            env={},
            cwd=spec.cwd,
            ready_pattern=spec.ready_pattern,
            ready_timeout=spec.ready_timeout,
            run_timeout=spec.run_timeout,
            version_command=spec.version_command,
            image=spec.image,
            enabled=spec.enabled,
            metadata=dict(spec.metadata),
        )
        return super().start_persistent(docker_spec, env=env, cwd=cwd, stdout_path=stdout_path, stderr_path=stderr_path)


_ADAPTERS: dict[str, type[BasePeerAdapter]] = {
    'subprocess': SubprocessPeerAdapter,
    'docker': DockerPeerAdapter,
}


class _PacketTraceWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._handle = path.open('w', encoding='utf-8')

    def write(self, *, direction: str, transport: str, local: tuple[str, int], remote: tuple[str, int], payload: bytes) -> None:
        record = {
            'timestamp': time.time(),
            'direction': direction,
            'transport': transport,
            'local': {'host': local[0], 'port': local[1]},
            'remote': {'host': remote[0], 'port': remote[1]},
            'length': len(payload),
            'payload_hex': payload.hex(),
        }
        with self._lock:
            self._handle.write(json.dumps(record, sort_keys=True) + '\n')
            self._handle.flush()

    def close(self) -> None:
        try:
            self._handle.close()
        except Exception:
            pass


class _TCPRelay(threading.Thread):
    def __init__(self, source: socket.socket, sink: socket.socket, writer: _PacketTraceWriter, *, direction: str, local: tuple[str, int], remote: tuple[str, int]) -> None:
        super().__init__(daemon=True)
        self.source = source
        self.sink = sink
        self.writer = writer
        self.direction = direction
        self.local = local
        self.remote = remote

    def run(self) -> None:
        try:
            while True:
                chunk = self.source.recv(65535)
                if not chunk:
                    break
                self.writer.write(direction=self.direction, transport='tcp', local=self.local, remote=self.remote, payload=chunk)
                self.sink.sendall(chunk)
        except OSError:
            pass
        finally:
            try:
                self.sink.shutdown(socket.SHUT_WR)
            except OSError:
                pass


class TCPRecordProxy:
    def __init__(self, *, listen_host: str, listen_port: int, target_host: str, target_port: int, packet_trace_path: Path, ip_family: str = 'ipv4') -> None:
        family = socket.AF_INET6 if ip_family == 'ipv6' else socket.AF_INET
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self._server = socket.socket(family, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if family == socket.AF_INET6:
            self._server.bind((listen_host, listen_port, 0, 0))
        else:
            self._server.bind((listen_host, listen_port))
        self._server.listen(5)
        self._server.settimeout(0.2)
        self._writer = _PacketTraceWriter(packet_trace_path)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._connections: list[tuple[socket.socket, socket.socket]] = []

    def start(self) -> None:
        self._thread.start()

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                client_sock, _client_addr = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                server_sock = socket.create_connection((self.target_host, self.target_port), timeout=5.0)
            except OSError:
                client_sock.close()
                continue
            self._connections.append((client_sock, server_sock))
            local_client = _normalize_sockaddr(client_sock.getsockname())
            remote_server = _normalize_sockaddr(server_sock.getpeername())
            local_server = _normalize_sockaddr(server_sock.getsockname())
            remote_client = _normalize_sockaddr(client_sock.getpeername())
            c2s = _TCPRelay(client_sock, server_sock, self._writer, direction='client_to_server', local=local_client, remote=remote_server)
            s2c = _TCPRelay(server_sock, client_sock, self._writer, direction='server_to_client', local=local_server, remote=remote_client)
            c2s.start()
            s2c.start()

    def close(self) -> None:
        self._stop.set()
        try:
            self._server.close()
        except OSError:
            pass
        self._thread.join(timeout=1.0)
        for left, right in self._connections:
            try:
                left.close()
            except OSError:
                pass
            try:
                right.close()
            except OSError:
                pass
        self._writer.close()


class UDPRecordProxy:
    def __init__(self, *, listen_host: str, listen_port: int, target_host: str, target_port: int, packet_trace_path: Path, ip_family: str = 'ipv4') -> None:
        family = socket.AF_INET6 if ip_family == 'ipv6' else socket.AF_INET
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self._downstream = socket.socket(family, socket.SOCK_DGRAM)
        self._upstream = socket.socket(family, socket.SOCK_DGRAM)
        if family == socket.AF_INET6:
            self._downstream.bind((listen_host, listen_port, 0, 0))
            self._upstream.bind((listen_host, 0, 0, 0))
        else:
            self._downstream.bind((listen_host, listen_port))
            self._upstream.bind((listen_host, 0))
        self._downstream.setblocking(False)
        self._upstream.setblocking(False)
        self._writer = _PacketTraceWriter(packet_trace_path)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._last_client: tuple[str, int] | None = None

    def start(self) -> None:
        self._thread.start()

    def _loop(self) -> None:
        selector = selectors.DefaultSelector()
        selector.register(self._downstream, selectors.EVENT_READ)
        selector.register(self._upstream, selectors.EVENT_READ)
        target = (self.target_host, self.target_port)
        try:
            while not self._stop.is_set():
                events = selector.select(timeout=0.2)
                for key, _mask in events:
                    if key.fileobj is self._downstream:
                        try:
                            payload, addr = self._downstream.recvfrom(65535)
                        except OSError:
                            continue
                        self._last_client = _normalize_sockaddr(addr)
                        self._writer.write(
                            direction='client_to_server',
                            transport='udp',
                            local=_normalize_sockaddr(self._downstream.getsockname()),
                            remote=(self.target_host, self.target_port),
                            payload=payload,
                        )
                        try:
                            self._upstream.sendto(payload, target)
                        except OSError:
                            continue
                    elif key.fileobj is self._upstream:
                        try:
                            payload, _addr = self._upstream.recvfrom(65535)
                        except OSError:
                            continue
                        if self._last_client is None:
                            continue
                        self._writer.write(
                            direction='server_to_client',
                            transport='udp',
                            local=_normalize_sockaddr(self._upstream.getsockname()),
                            remote=self._last_client,
                            payload=payload,
                        )
                        try:
                            self._downstream.sendto(payload, self._last_client)
                        except OSError:
                            continue
        finally:
            selector.close()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        try:
            self._downstream.close()
        except OSError:
            pass
        try:
            self._upstream.close()
        except OSError:
            pass
        self._writer.close()


class ExternalInteropRunner:
    def __init__(self, *, matrix: InteropMatrix, artifact_root: str | Path, source_root: str | Path | None = None) -> None:
        for scenario in matrix.scenarios:
            _validate_scenario_provenance(scenario)
        self.matrix = matrix
        self.artifact_root = Path(artifact_root)
        self.source_root = Path(source_root) if source_root is not None else Path.cwd()
        self.commit_hash = detect_source_revision(self.source_root)
        self.environment_manifest = build_environment_manifest(self.source_root, commit_hash=self.commit_hash)

    def run(self, *, scenario_ids: Iterable[str] | None = None, strict: bool = False) -> InteropRunSummary:
        selected = set(scenario_ids or ())
        scenarios = self.matrix.enabled_scenarios
        if selected:
            scenarios = [scenario for scenario in scenarios if scenario.id in selected]
        run_root = self.artifact_root / self.commit_hash / self.matrix.name
        run_root.mkdir(parents=True, exist_ok=True)
        bundle_kind = str(self.matrix.metadata.get('bundle_kind', self.matrix.metadata.get('evidence_tier', 'mixed')) or 'mixed')
        wrapper_families = dict(self.matrix.metadata.get('phase9b_wrapper_families', {}))
        _write_json(
            run_root / 'manifest.json',
            {
                'matrix_name': self.matrix.name,
                'bundle_kind': bundle_kind,
                'artifact_schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
                'required_bundle_files': list(INTEROP_BUNDLE_REQUIRED_FILES),
                'required_scenario_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
                'commit_hash': self.commit_hash,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'dimensions': summarize_matrix_dimensions(self.matrix),
                'environment': self.environment_manifest,
                'matrix_sha256': _sha256_bytes(json.dumps(_matrix_to_json(self.matrix), sort_keys=True).encode('utf-8')),
                'wrapper_families': wrapper_families,
            },
        )
        results: list[InteropScenarioResult] = []
        passed = 0
        failed = 0
        skipped = len([scenario for scenario in self.matrix.scenarios if scenario not in scenarios])
        for scenario in scenarios:
            result = self._run_scenario(scenario, run_root)
            results.append(result)
            if result.passed:
                passed += 1
            else:
                failed += 1
                if strict:
                    break
        summary = InteropRunSummary(
            matrix_name=self.matrix.name,
            commit_hash=self.commit_hash,
            artifact_root=str(run_root),
            total=len(results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            scenarios=results,
        )
        root_index_payload = {
            'schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
            'bundle_kind': bundle_kind,
            'required_bundle_files': list(INTEROP_BUNDLE_REQUIRED_FILES),
            'required_scenario_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
            'matrix_name': summary.matrix_name,
            'commit_hash': summary.commit_hash,
            'artifact_root': summary.artifact_root,
            'total': summary.total,
            'passed': summary.passed,
            'failed': summary.failed,
            'skipped': summary.skipped,
            'wrapper_families': wrapper_families,
            'scenarios': [
                {
                    'id': item.scenario_id,
                    'passed': item.passed,
                    'artifact_dir': item.artifact_dir,
                    'assertions_failed': item.assertions_failed,
                    'error': item.error,
                    'summary_path': str(Path(item.artifact_dir) / 'summary.json'),
                    'index_path': str(Path(item.artifact_dir) / 'index.json'),
                    'result_path': str(Path(item.artifact_dir) / 'result.json'),
                }
                for item in summary.scenarios
            ],
        }
        _write_json(run_root / 'index.json', root_index_payload)
        _write_json(
            run_root / 'summary.json',
            {
                'schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
                'bundle_kind': bundle_kind,
                'matrix_name': summary.matrix_name,
                'commit_hash': summary.commit_hash,
                'artifact_root': summary.artifact_root,
                'total': summary.total,
                'passed': summary.passed,
                'failed': summary.failed,
                'skipped': summary.skipped,
                'scenario_ids': [item.scenario_id for item in summary.scenarios],
                'required_bundle_files': list(INTEROP_BUNDLE_REQUIRED_FILES),
                'required_scenario_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
                'wrapper_families': wrapper_families,
            },
        )
        return summary

    def _run_scenario(self, scenario: InteropScenario, run_root: Path) -> InteropScenarioResult:
        scenario_root = run_root / _safe_name(scenario.id)
        if scenario_root.exists():
            shutil.rmtree(scenario_root)
        scenario_root.mkdir(parents=True, exist_ok=True)
        transport = scenario.transport or _default_transport_for_protocol(scenario.protocol)
        socket_type = socket.SOCK_DGRAM if transport == 'udp' else socket.SOCK_STREAM
        bind_host = '::1' if scenario.ip_family == 'ipv6' else '127.0.0.1'
        bind_port = _reserve_port(bind_host, socket_type)
        proxy_port = _reserve_distinct_port(bind_host, socket_type, {bind_port})
        packet_trace_path = scenario_root / 'packet_trace.jsonl'
        qlog_path = scenario_root / 'qlog.json'
        sut_stdout_path = scenario_root / 'sut_stdout.log'
        sut_stderr_path = scenario_root / 'sut_stderr.log'
        peer_stdout_path = scenario_root / 'peer_stdout.log'
        peer_stderr_path = scenario_root / 'peer_stderr.log'
        sut_transcript_path = scenario_root / 'sut_transcript.json'
        peer_transcript_path = scenario_root / 'peer_transcript.json'
        sut_negotiation_path = scenario_root / 'sut_negotiation.json'
        peer_negotiation_path = scenario_root / 'peer_negotiation.json'
        connect_host = bind_host
        connect_port = bind_port
        proxy: TCPRecordProxy | UDPRecordProxy | None = None
        if scenario.capture.get('proxy', True):
            if transport == 'udp':
                proxy = UDPRecordProxy(
                    listen_host=bind_host,
                    listen_port=proxy_port,
                    target_host=bind_host,
                    target_port=bind_port,
                    packet_trace_path=packet_trace_path,
                    ip_family=scenario.ip_family,
                )
            else:
                proxy = TCPRecordProxy(
                    listen_host=bind_host,
                    listen_port=proxy_port,
                    target_host=bind_host,
                    target_port=bind_port,
                    packet_trace_path=packet_trace_path,
                    ip_family=scenario.ip_family,
                )
            proxy.start()
            connect_port = proxy_port
        else:
            packet_trace_path.touch()
        context = {
            'bind_host': bind_host,
            'bind_port': str(bind_port),
            'target_host': connect_host,
            'target_port': str(connect_port),
            'artifact_dir': str(scenario_root),
            'packet_trace_path': str(packet_trace_path),
            'qlog_path': str(qlog_path),
            'scenario_id': scenario.id,
            'matrix_name': self.matrix.name,
            'commit_hash': self.commit_hash,
            'protocol': scenario.protocol,
            'feature': scenario.feature,
            'role': scenario.role,
            'ip_family': scenario.ip_family,
            'cipher_group': scenario.cipher_group or '',
            'retry': scenario.retry,
            'resumption': scenario.resumption,
            'zero_rtt': scenario.zero_rtt,
            'key_update': scenario.key_update,
            'migration': scenario.migration,
            'goaway': scenario.goaway,
            'qpack_blocking': scenario.qpack_blocking,
        }
        sut_spec = _materialize_process_spec(scenario.sut, context)
        peer_spec = _materialize_process_spec(scenario.peer_process, context)
        sut_env = _build_process_env(self.source_root, sut_spec, sut_transcript_path, sut_negotiation_path, context)
        peer_env = _build_process_env(self.source_root, peer_spec, peer_transcript_path, peer_negotiation_path, context)
        sut_cwd = Path(sut_spec.cwd) if sut_spec.cwd is not None else self.source_root
        peer_cwd = Path(peer_spec.cwd) if peer_spec.cwd is not None else self.source_root
        sut_adapter = _instantiate_adapter(sut_spec.adapter)
        peer_adapter = _instantiate_adapter(peer_spec.adapter)
        sut_version = sut_adapter.inspect_version(sut_spec, env=sut_env, cwd=sut_cwd)
        peer_version = peer_adapter.inspect_version(peer_spec, env=peer_env, cwd=peer_cwd)
        sut_result: InteropProcessResult | None = None
        peer_result: InteropProcessResult | None = None
        server_handle: _ManagedProcess | None = None
        error: str | None = None
        try:
            if sut_spec.role == 'server' and peer_spec.role == 'client':
                server_handle, sut_result = sut_adapter.start_persistent(
                    sut_spec,
                    env=sut_env,
                    cwd=sut_cwd,
                    stdout_path=sut_stdout_path,
                    stderr_path=sut_stderr_path,
                )
                sut_result.version = sut_version
                sut_result.provenance = _build_provenance_payload(sut_spec, sut_version)
                if sut_result.error is None:
                    peer_result = peer_adapter.run_oneshot(
                        peer_spec,
                        env=peer_env,
                        cwd=peer_cwd,
                        stdout_path=peer_stdout_path,
                        stderr_path=peer_stderr_path,
                    )
                    peer_result.version = peer_version
                    peer_result.provenance = _build_provenance_payload(peer_spec, peer_version)
                else:
                    error = sut_result.error
            elif sut_spec.role == 'client' and peer_spec.role == 'server':
                server_handle, peer_result = peer_adapter.start_persistent(
                    peer_spec,
                    env=peer_env,
                    cwd=peer_cwd,
                    stdout_path=peer_stdout_path,
                    stderr_path=peer_stderr_path,
                )
                peer_result.version = peer_version
                peer_result.provenance = _build_provenance_payload(peer_spec, peer_version)
                if peer_result.error is None:
                    sut_result = sut_adapter.run_oneshot(
                        sut_spec,
                        env=sut_env,
                        cwd=sut_cwd,
                        stdout_path=sut_stdout_path,
                        stderr_path=sut_stderr_path,
                    )
                    sut_result.version = sut_version
                    sut_result.provenance = _build_provenance_payload(sut_spec, sut_version)
                else:
                    error = peer_result.error
            else:
                raise InteropRunnerError('exactly one side must be server and the other must be client')
        except Exception as exc:
            error = str(exc)
        finally:
            time.sleep(0.1)
            if server_handle is not None:
                exit_code = server_handle.stop(timeout=2.0)
                if sut_result is not None and sut_spec.role == 'server':
                    sut_result.exit_code = exit_code
                    sut_result.stdout_text = sut_stdout_path.read_text(encoding='utf-8', errors='replace') if sut_stdout_path.exists() else ''
                    sut_result.stderr_text = sut_stderr_path.read_text(encoding='utf-8', errors='replace') if sut_stderr_path.exists() else ''
                if peer_result is not None and peer_spec.role == 'server':
                    peer_result.exit_code = exit_code
                    peer_result.stdout_text = peer_stdout_path.read_text(encoding='utf-8', errors='replace') if peer_stdout_path.exists() else ''
                    peer_result.stderr_text = peer_stderr_path.read_text(encoding='utf-8', errors='replace') if peer_stderr_path.exists() else ''
            if proxy is not None:
                proxy.close()
        if sut_result is None:
            sut_result = InteropProcessResult(
                name=sut_spec.name,
                adapter=sut_spec.adapter,
                role=sut_spec.role,
                exit_code=None,
                stdout_path=str(sut_stdout_path),
                stderr_path=str(sut_stderr_path),
                error='sut did not run',
                version=sut_version,
                provenance=_build_provenance_payload(sut_spec, sut_version),
            )
        if peer_result is None:
            peer_result = InteropProcessResult(
                name=peer_spec.name,
                adapter=peer_spec.adapter,
                role=peer_spec.role,
                exit_code=None,
                stdout_path=str(peer_stdout_path),
                stderr_path=str(peer_stderr_path),
                error='peer did not run',
                version=peer_version,
                provenance=_build_provenance_payload(peer_spec, peer_version),
            )
        if error is None:
            error = sut_result.error or peer_result.error
        sut_transcript = _load_json_if_present(sut_transcript_path)
        peer_transcript = _load_json_if_present(peer_transcript_path)
        sut_negotiation = _load_json_if_present(sut_negotiation_path)
        peer_negotiation = _load_json_if_present(peer_negotiation_path)
        if sut_transcript is None and sut_spec.role == 'server':
            sut_transcript = _synthesize_sut_transcript(
                scenario=scenario,
                sut_spec=sut_spec,
                sut_result=sut_result,
                peer_transcript=peer_transcript,
            )
            _write_json(sut_transcript_path, sut_transcript)
        if sut_negotiation is None and sut_spec.role == 'server':
            sut_negotiation = _synthesize_sut_negotiation(
                scenario=scenario,
                sut_spec=sut_spec,
                sut_result=sut_result,
                peer_negotiation=peer_negotiation,
                peer_transcript=peer_transcript,
                source_root=self.source_root,
            )
            _write_json(sut_negotiation_path, sut_negotiation)
        if transport == 'udp' and scenario.protocol in {'quic', 'quic-tls', 'http3'}:
            generate_observer_qlog(
                packet_trace_path=packet_trace_path,
                qlog_path=qlog_path,
                title=scenario.id,
                protocol=scenario.protocol,
                ip_family=scenario.ip_family,
                negotiation=(sut_negotiation if isinstance(sut_negotiation, dict) else None) or (peer_negotiation if isinstance(peer_negotiation, dict) else None),
                error=error,
            )
        artifacts = {
            'packet_trace': _artifact_metadata(packet_trace_path),
            'qlog': _artifact_metadata(qlog_path),
            'sut_transcript': _artifact_metadata(sut_transcript_path),
            'peer_transcript': _artifact_metadata(peer_transcript_path),
            'sut_negotiation': _artifact_metadata(sut_negotiation_path),
            'peer_negotiation': _artifact_metadata(peer_negotiation_path),
        }
        observed = {
            'scenario': {'id': scenario.id, **scenario.dimensions, 'metadata': scenario.metadata},
            'sut': sut_result.to_observed(),
            'peer': peer_result.to_observed(),
            'transcript': {'sut': sut_transcript, 'peer': peer_transcript},
            'negotiation': {'sut': sut_negotiation, 'peer': peer_negotiation},
            'artifacts': artifacts,
        }
        failed_assertions = evaluate_assertions(scenario.assertions, observed)
        passed = error is None and not failed_assertions
        result = InteropScenarioResult(
            scenario_id=scenario.id,
            passed=passed,
            commit_hash=self.commit_hash,
            artifact_dir=str(scenario_root),
            assertions_failed=failed_assertions,
            error=error,
            sut=sut_result.to_observed(),
            peer=peer_result.to_observed(),
            transcript={'sut': sut_transcript, 'peer': peer_transcript},
            negotiation={'sut': sut_negotiation, 'peer': peer_negotiation},
            artifacts=artifacts,
        )
        _write_json(
            scenario_root / 'result.json',
            {
                'scenario_id': result.scenario_id,
                'passed': result.passed,
                'commit_hash': result.commit_hash,
                'artifact_dir': result.artifact_dir,
                'assertions_failed': result.assertions_failed,
                'error': result.error,
                'sut': result.sut,
                'peer': result.peer,
                'transcript': result.transcript,
                'negotiation': result.negotiation,
                'artifacts': result.artifacts,
            },
        )
        _write_json(
            scenario_root / 'scenario.json',
            {
                'id': scenario.id,
                'dimensions': scenario.dimensions,
                'assertions': scenario.assertions,
                'capture': scenario.capture,
                'metadata': scenario.metadata,
                'sut': _spec_to_json(scenario.sut),
                'peer_process': _spec_to_json(scenario.peer_process),
            },
        )
        _write_json(
            scenario_root / 'command.json',
            {
                'scenario_id': scenario.id,
                'sut': {
                    'adapter': sut_spec.adapter,
                    'command': sut_spec.command,
                    'version_command': sut_spec.version_command,
                    'cwd': str(sut_cwd),
                },
                'peer': {
                    'adapter': peer_spec.adapter,
                    'command': peer_spec.command,
                    'version_command': peer_spec.version_command,
                    'cwd': str(peer_cwd),
                },
            },
        )
        _write_json(
            scenario_root / 'env.json',
            {
                'scenario_id': scenario.id,
                'shared_context': context,
                'sut': {
                    'cwd': str(sut_cwd),
                    'env': _snapshot_interop_env(sut_env, sut_spec),
                },
                'peer': {
                    'cwd': str(peer_cwd),
                    'env': _snapshot_interop_env(peer_env, peer_spec),
                },
            },
        )
        _write_json(
            scenario_root / 'versions.json',
            {
                'scenario_id': scenario.id,
                'sut': sut_version,
                'peer': peer_version,
                'sut_provenance': sut_result.provenance,
                'peer_provenance': peer_result.provenance,
            },
        )
        _write_json(
            scenario_root / 'wire_capture.json',
            {
                'scenario_id': scenario.id,
                'transport': transport,
                'capture': scenario.capture,
                'packet_trace': artifacts['packet_trace'],
                'qlog': artifacts['qlog'],
                'logs': {
                    'sut_stdout': _artifact_metadata(sut_stdout_path),
                    'sut_stderr': _artifact_metadata(sut_stderr_path),
                    'peer_stdout': _artifact_metadata(peer_stdout_path),
                    'peer_stderr': _artifact_metadata(peer_stderr_path),
                },
                'transcripts': {
                    'sut_transcript': artifacts['sut_transcript'],
                    'peer_transcript': artifacts['peer_transcript'],
                },
                'negotiation': {
                    'sut_negotiation': artifacts['sut_negotiation'],
                    'peer_negotiation': artifacts['peer_negotiation'],
                },
            },
        )
        _write_json(
            scenario_root / 'summary.json',
            {
                'schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
                'scenario_id': scenario.id,
                'protocol': scenario.protocol,
                'feature': scenario.feature,
                'peer': scenario.peer,
                'role': scenario.role,
                'evidence_tier': scenario.evidence_tier,
                'passed': result.passed,
                'error': result.error,
                'assertions_failed': result.assertions_failed,
                'required_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
            },
        )
        _write_json(
            scenario_root / 'index.json',
            {
                'schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
                'scenario_id': scenario.id,
                'artifact_dir': str(scenario_root),
                'passed': result.passed,
                'error': result.error,
                'required_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
                'artifact_files': {},
                'result_path': str(scenario_root / 'result.json'),
                'summary_path': str(scenario_root / 'summary.json'),
            },
        )
        artifact_inventory = {
            name: _artifact_metadata(scenario_root / name)
            for name in INTEROP_SCENARIO_REQUIRED_FILES
        }
        artifact_inventory.update(
            {
                'packet_trace.jsonl': _artifact_metadata(packet_trace_path),
                'qlog.json': _artifact_metadata(qlog_path),
                'sut_stdout.log': _artifact_metadata(sut_stdout_path),
                'sut_stderr.log': _artifact_metadata(sut_stderr_path),
                'peer_stdout.log': _artifact_metadata(peer_stdout_path),
                'peer_stderr.log': _artifact_metadata(peer_stderr_path),
                'sut_transcript.json': _artifact_metadata(sut_transcript_path),
                'peer_transcript.json': _artifact_metadata(peer_transcript_path),
                'sut_negotiation.json': _artifact_metadata(sut_negotiation_path),
                'peer_negotiation.json': _artifact_metadata(peer_negotiation_path),
            }
        )
        _write_json(
            scenario_root / 'summary.json',
            {
                'schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
                'scenario_id': scenario.id,
                'protocol': scenario.protocol,
                'feature': scenario.feature,
                'peer': scenario.peer,
                'role': scenario.role,
                'evidence_tier': scenario.evidence_tier,
                'passed': result.passed,
                'error': result.error,
                'assertions_failed': result.assertions_failed,
                'required_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
                'artifact_files': artifact_inventory,
            },
        )
        _write_json(
            scenario_root / 'index.json',
            {
                'schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
                'scenario_id': scenario.id,
                'artifact_dir': str(scenario_root),
                'passed': result.passed,
                'error': result.error,
                'required_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
                'artifact_files': artifact_inventory,
                'result_path': str(scenario_root / 'result.json'),
                'summary_path': str(scenario_root / 'summary.json'),
            },
        )
        return result


# ----- Public helpers ----------------------------------------------------

def load_external_matrix(path: str | Path) -> InteropMatrix:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    matrix_payload = payload.get('matrix', payload)
    metadata = dict(matrix_payload.get('metadata', {}))
    default_evidence_tier = str(metadata.get('evidence_tier', 'mixed'))
    scenarios = [_load_scenario(entry, default_evidence_tier=default_evidence_tier) for entry in matrix_payload.get('scenarios', [])]
    return InteropMatrix(
        name=matrix_payload['name'],
        scenarios=scenarios,
        metadata=metadata,
    )



def summarize_matrix_dimensions(matrix: InteropMatrix) -> dict[str, list[Any]]:
    keys = [
        'protocol', 'role', 'feature', 'peer', 'cipher_group', 'ip_family', 'retry', 'resumption', 'zero_rtt', 'key_update', 'migration', 'goaway', 'qpack_blocking', 'evidence_tier'
    ]
    dimensions: dict[str, set[Any]] = {key: set() for key in keys}
    for scenario in matrix.scenarios:
        for key, value in scenario.dimensions.items():
            dimensions[key].add(value)
    return {key: sorted(values) for key, values in dimensions.items()}



def detect_source_revision(source_root: str | Path) -> str:
    env_commit = os.environ.get('TIGRCORN_COMMIT_HASH') or os.environ.get('GIT_COMMIT')
    if env_commit:
        return env_commit
    try:
        completed = subprocess.run(
            ['git', '-C', str(Path(source_root)), 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout.strip()
    except Exception:
        pass
    return f'tree-{hash_source_tree(source_root)[:16]}'



def build_environment_manifest(source_root: str | Path, *, commit_hash: str | None = None) -> dict[str, Any]:
    source_root = Path(source_root)
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'python': {
            'version': platform.python_version(),
            'implementation': platform.python_implementation(),
            'executable': os.sys.executable,
        },
        'platform': {
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'platform': platform.platform(),
        },
        'tigrcorn': {
            'version': __version__,
            'commit_hash': commit_hash or detect_source_revision(source_root),
            'source_tree_sha256': hash_source_tree(source_root),
        },
        'tools': {
            'git': _probe_command(['git', '--version']),
            'docker': _probe_command(['docker', '--version']),
            'curl': _probe_command(['curl', '--version']),
            'openssl': _probe_command(['openssl', 'version']),
        },
    }



def hash_source_tree(source_root: str | Path) -> str:
    source_root = Path(source_root)
    entries: list[tuple[str, str]] = []
    skipped_prefixes = (
        ('docs', 'review', 'conformance', 'releases'),
        ('.artifacts',),
        ('.tmp',),
        ('dist',),
    )
    for root, _dirs, filenames in os.walk(source_root):
        root_path = Path(root)
        if '.git' in root_path.parts or '__pycache__' in root_path.parts:
            continue
        relative_parts = root_path.relative_to(source_root).parts if root_path != source_root else ()
        if any(part.startswith('tmp') for part in relative_parts):
            continue
        if any(relative_parts[:len(prefix)] == prefix for prefix in skipped_prefixes):
            continue
        for filename in sorted(filenames):
            path = root_path / filename
            if path.suffix in {'.pyc', '.pyo'} or not path.is_file():
                continue
            entries.append((str(path.relative_to(source_root)), _sha256_path(path)))
    return _sha256_bytes(json.dumps(entries, separators=(',', ':')).encode('utf-8'))



def evaluate_assertions(assertions: list[dict[str, Any]], observed: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for index, assertion in enumerate(assertions):
        path = assertion.get('path')
        if not isinstance(path, str):
            failures.append(f'assertion[{index}] missing path')
            continue
        try:
            actual = _resolve_path(observed, path)
        except KeyError:
            failures.append(f'assertion[{index}] path not found: {path}')
            continue
        if 'equals' in assertion and actual != assertion['equals']:
            failures.append(f'assertion[{index}] {path} expected {assertion["equals"]!r}, got {actual!r}')
        if 'not_equals' in assertion and actual == assertion['not_equals']:
            failures.append(f'assertion[{index}] {path} unexpectedly equals {assertion["not_equals"]!r}')
        if 'contains' in assertion:
            expected = assertion['contains']
            if isinstance(actual, (str, bytes)):
                if expected not in actual:
                    failures.append(f'assertion[{index}] {path} does not contain {expected!r}')
            elif isinstance(actual, Mapping):
                if expected not in actual:
                    failures.append(f'assertion[{index}] {path} missing key {expected!r}')
            elif isinstance(actual, Iterable):
                if expected not in actual:
                    failures.append(f'assertion[{index}] {path} does not contain item {expected!r}')
            else:
                failures.append(f'assertion[{index}] {path} is not containable')
        if 'regex' in assertion and not re.search(str(assertion['regex']), str(actual)):
            failures.append(f'assertion[{index}] {path} does not match /{assertion["regex"]}/')
        if 'greater_or_equal' in assertion and actual < assertion['greater_or_equal']:
            failures.append(f'assertion[{index}] {path} expected >= {assertion["greater_or_equal"]!r}, got {actual!r}')
        if 'less_or_equal' in assertion and actual > assertion['less_or_equal']:
            failures.append(f'assertion[{index}] {path} expected <= {assertion["less_or_equal"]!r}, got {actual!r}')
        if 'in' in assertion and actual not in assertion['in']:
            failures.append(f'assertion[{index}] {path} expected one of {assertion["in"]!r}, got {actual!r}')
    return failures



def generate_observer_qlog(
    *,
    packet_trace_path: str | Path,
    qlog_path: str | Path,
    title: str,
    protocol: str,
    ip_family: str,
    negotiation: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    trace_path = Path(packet_trace_path)
    records: list[dict[str, Any]] = []
    if trace_path.exists():
        for line in trace_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    if not records:
        _write_json(
            Path(qlog_path),
            {
                'qlog_version': QLOG_VERSION,
                'schema_version': QLOG_EXPERIMENTAL_SCHEMA_VERSION,
                'traces': [],
            },
        )
        return
    base_time = float(records[0]['timestamp'])
    events: list[list[Any]] = [
        [
            0.0,
            'connectivity',
            'connection_started',
            {
                'ip_version': 'ipv6' if ip_family == 'ipv6' else 'ipv4',
                'protocol': protocol,
                'server': {'host': 'redacted', 'port': 'redacted'},
            },
        ]
    ]
    if negotiation:
        events.append([0.0, 'transport', 'parameters_set', dict(negotiation)])
    for record in records:
        payload = bytes.fromhex(record['payload_hex'])
        packets = [_describe_quic_packet(chunk) for chunk in _split_observed_packets(payload)]
        packets = [item for item in packets if item is not None]
        if not packets:
            packets = [{'packet_type': 'unknown', 'length': len(payload)}]
        else:
            packets = [_redact_qlog_packet(item) for item in packets]
        events.append([
            round((float(record['timestamp']) - base_time) * 1000.0, 3),
            'transport',
            'packet_received' if record['direction'] == 'client_to_server' else 'packet_sent',
            {
                'direction': record['direction'],
                'length': record['length'],
                'packets': packets,
            },
        ])
    if error:
        events.append([round((float(records[-1]['timestamp']) - base_time) * 1000.0, 3), 'transport', 'connection_closed', {'error': error}])
    _write_json(
        Path(qlog_path),
        {
            'qlog_version': QLOG_VERSION,
            'schema_version': QLOG_EXPERIMENTAL_SCHEMA_VERSION,
            'traces': [
                {
                    'vantage_point': {'type': 'network', 'name': 'tigrcorn-interop-runner'},
                    'title': title,
                    'common_fields': {
                        'protocol_type': 'QUIC',
                        'tigrcorn_qlog': {
                            'experimental': True,
                            'schema_version': QLOG_EXPERIMENTAL_SCHEMA_VERSION,
                            'redaction': {
                                'network_endpoints': 'redacted',
                                'connection_ids': 'redacted',
                                'payload_bytes': 'omitted',
                            },
                        },
                    },
                    'events': events,
                }
            ],
        },
    )



def run_external_matrix(
    matrix_path: str | Path,
    *,
    artifact_root: str | Path,
    source_root: str | Path | None = None,
    scenario_ids: Iterable[str] | None = None,
    strict: bool = False,
) -> InteropRunSummary:
    matrix = load_external_matrix(matrix_path)
    runner = ExternalInteropRunner(matrix=matrix, artifact_root=artifact_root, source_root=source_root)
    return runner.run(scenario_ids=scenario_ids, strict=strict)


# ----- Internal helpers --------------------------------------------------

def _load_scenario(entry: dict[str, Any], *, default_evidence_tier: str = 'mixed') -> InteropScenario:
    evidence_tier = str(entry.get('evidence_tier', default_evidence_tier))
    if evidence_tier not in VALID_EVIDENCE_TIERS:
        raise InteropRunnerError(f'invalid evidence_tier: {evidence_tier!r}')
    scenario = InteropScenario(
        id=entry['id'],
        protocol=entry['protocol'],
        role=entry['role'],
        feature=entry['feature'],
        peer=entry['peer'],
        sut=_load_process_spec(entry['sut']),
        peer_process=_load_process_spec(entry['peer_process']),
        assertions=[dict(item) for item in entry.get('assertions', [])],
        transport=entry.get('transport'),
        ip_family=entry.get('ip_family', 'ipv4'),
        cipher_group=entry.get('cipher_group'),
        retry=bool(entry.get('retry', False)),
        resumption=bool(entry.get('resumption', False)),
        zero_rtt=bool(entry.get('zero_rtt', False)),
        key_update=bool(entry.get('key_update', False)),
        migration=bool(entry.get('migration', False)),
        goaway=bool(entry.get('goaway', False)),
        qpack_blocking=bool(entry.get('qpack_blocking', False)),
        capture=dict(entry.get('capture', {})),
        metadata=dict(entry.get('metadata', {})),
        evidence_tier=evidence_tier,
        enabled=bool(entry.get('enabled', True)),
    )
    _validate_scenario_provenance(scenario)
    return scenario



def _load_process_spec(entry: dict[str, Any]) -> InteropProcessSpec:
    command = entry.get('command')
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        raise InteropRunnerError('process command must be a list of strings')
    version_command = entry.get('version_command')
    if version_command is not None and (not isinstance(version_command, list) or not all(isinstance(item, str) for item in version_command)):
        raise InteropRunnerError('version_command must be a list of strings when provided')
    spec = InteropProcessSpec(
        name=entry['name'],
        adapter=entry.get('adapter', 'subprocess'),
        role=entry['role'],
        command=list(command),
        env={str(key): str(value) for key, value in dict(entry.get('env', {})).items()},
        cwd=entry.get('cwd'),
        ready_pattern=entry.get('ready_pattern'),
        ready_timeout=float(entry.get('ready_timeout', DEFAULT_READY_TIMEOUT)),
        run_timeout=float(entry.get('run_timeout', DEFAULT_RUN_TIMEOUT)),
        version_command=list(version_command) if version_command is not None else None,
        image=entry.get('image'),
        enabled=bool(entry.get('enabled', True)),
        metadata=dict(entry.get('metadata', {})),
        provenance_kind=str(entry.get('provenance_kind', 'unspecified')),
        implementation_source=entry.get('implementation_source'),
        implementation_identity=entry.get('implementation_identity'),
        implementation_version=entry.get('implementation_version'),
    )
    _validate_process_provenance(spec)
    return spec



def _validate_process_provenance(spec: InteropProcessSpec) -> None:
    if spec.provenance_kind not in VALID_PROVENANCE_KINDS:
        raise InteropRunnerError(f'invalid provenance_kind for {spec.name}: {spec.provenance_kind!r}')
    if spec.provenance_kind != 'unspecified' and not spec.implementation_identity:
        raise InteropRunnerError(f'implementation_identity is required for {spec.name} when provenance_kind is {spec.provenance_kind!r}')
    if spec.provenance_kind in {'third_party_library', 'third_party_binary'} and not spec.implementation_source:
        raise InteropRunnerError(f'implementation_source is required for third-party peer {spec.name}')



def _validate_scenario_provenance(scenario: InteropScenario) -> None:
    if scenario.evidence_tier not in VALID_EVIDENCE_TIERS:
        raise InteropRunnerError(f'invalid evidence_tier for {scenario.id}: {scenario.evidence_tier!r}')
    if scenario.evidence_tier == 'independent_certification':
        peer_kind = scenario.peer_process.provenance_kind
        if peer_kind not in {'third_party_library', 'third_party_binary'}:
            raise InteropRunnerError(
                f'independent_certification scenario {scenario.id} requires a third-party peer, not {peer_kind!r}'
            )
        if not scenario.peer_process.implementation_identity or not scenario.peer_process.implementation_source:
            raise InteropRunnerError(
                f'independent_certification scenario {scenario.id} requires peer implementation_identity and implementation_source'
            )



def _build_provenance_payload(spec: InteropProcessSpec, version: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'kind': spec.provenance_kind,
        'implementation_source': spec.implementation_source,
        'implementation_identity': spec.implementation_identity,
        'implementation_version': spec.implementation_version,
    }
    if version:
        observed = version.get('version_stdout') or version.get('stdout')
        if observed:
            payload['observed_version_output'] = observed
    return payload


def _instantiate_adapter(name: str) -> BasePeerAdapter:
    try:
        return _ADAPTERS[name]()
    except KeyError as exc:
        raise InteropRunnerError(f'unknown interop adapter: {name}') from exc



def _resolve_process_command(command: Sequence[str]) -> list[str]:
    resolved = list(command)
    if not resolved:
        return resolved
    executable = resolved[0]
    if executable == '/opt/pyvenv/bin/python':
        resolved[0] = os.environ.get('TIGRCORN_INTEROP_PYTHON', os.sys.executable)
    return resolved



def _materialize_process_spec(spec: InteropProcessSpec, context: Mapping[str, str]) -> InteropProcessSpec:
    return InteropProcessSpec(
        name=_apply_template(spec.name, context),
        adapter=spec.adapter,
        role=spec.role,
        command=_resolve_process_command([_apply_template(item, context) for item in spec.command]),
        env={key: _apply_template(value, context) for key, value in spec.env.items()},
        cwd=_apply_template(spec.cwd, context) if spec.cwd is not None else None,
        ready_pattern=_apply_template(spec.ready_pattern, context) if spec.ready_pattern is not None else None,
        ready_timeout=spec.ready_timeout,
        run_timeout=spec.run_timeout,
        version_command=_resolve_process_command([_apply_template(item, context) for item in spec.version_command]) if spec.version_command is not None else None,
        image=_apply_template(spec.image, context) if spec.image is not None else None,
        enabled=spec.enabled,
        metadata=dict(spec.metadata),
        provenance_kind=spec.provenance_kind,
        implementation_source=_apply_template(spec.implementation_source, context) if spec.implementation_source is not None else None,
        implementation_identity=_apply_template(spec.implementation_identity, context) if spec.implementation_identity is not None else None,
        implementation_version=_apply_template(spec.implementation_version, context) if spec.implementation_version is not None else None,
    )



def _build_process_env(source_root: Path, spec: InteropProcessSpec, transcript_path: Path, negotiation_path: Path, context: Mapping[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(spec.env)
    pythonpath_parts = [str(source_root / 'src'), str(source_root)]
    if env.get('PYTHONPATH'):
        pythonpath_parts.append(env['PYTHONPATH'])
    env['PYTHONPATH'] = os.pathsep.join(pythonpath_parts)
    env['PYTHONUNBUFFERED'] = '1'
    env['INTEROP_BIND_HOST'] = context['bind_host']
    env['INTEROP_BIND_PORT'] = context['bind_port']
    env['INTEROP_TARGET_HOST'] = context['target_host']
    env['INTEROP_TARGET_PORT'] = context['target_port']
    env['INTEROP_ARTIFACT_DIR'] = context['artifact_dir']
    env['INTEROP_PACKET_TRACE_PATH'] = context['packet_trace_path']
    env['INTEROP_QLOG_PATH'] = context['qlog_path']
    env['INTEROP_TRANSCRIPT_PATH'] = str(transcript_path)
    env['INTEROP_NEGOTIATION_PATH'] = str(negotiation_path)
    env['INTEROP_SCENARIO_ID'] = context['scenario_id']
    env['INTEROP_MATRIX_NAME'] = context['matrix_name']
    env['INTEROP_COMMIT_HASH'] = context['commit_hash']
    env['INTEROP_PROTOCOL'] = context['protocol']
    env['INTEROP_FEATURE'] = context['feature']
    env['INTEROP_ROLE'] = spec.role
    env['INTEROP_IP_FAMILY'] = context['ip_family']
    if context.get('retry'):
        env['INTEROP_ENABLE_RETRY'] = '1'
    if context.get('resumption'):
        env['INTEROP_ENABLE_RESUMPTION'] = '1'
    if context.get('zero_rtt'):
        env['INTEROP_ENABLE_ZERO_RTT'] = '1'
    if context.get('key_update'):
        env['INTEROP_ENABLE_KEY_UPDATE'] = '1'
    if context.get('migration'):
        env['INTEROP_ENABLE_MIGRATION'] = '1'
    if context.get('goaway'):
        env['INTEROP_ENABLE_GOAWAY'] = '1'
    if context.get('qpack_blocking'):
        env['INTEROP_ENABLE_QPACK_BLOCKING'] = '1'
    if context.get('cipher_group'):
        env['INTEROP_CIPHER_GROUP'] = context['cipher_group']
    return env



def _snapshot_interop_env(env: Mapping[str, str], spec: InteropProcessSpec) -> dict[str, str]:
    explicit_keys = set(spec.env)
    return {
        key: str(value)
        for key, value in sorted(env.items())
        if key.startswith('INTEROP_') or key in explicit_keys
    }


def _wait_for_server_ready(*, spec: InteropProcessSpec, process: subprocess.Popen[Any], env: Mapping[str, str], stdout_path: Path, stderr_path: Path) -> str | None:
    bind_host = env.get('INTEROP_BIND_HOST')
    bind_port = int(env['INTEROP_BIND_PORT']) if env.get('INTEROP_BIND_PORT') and env['INTEROP_BIND_PORT'].isdigit() else None
    transport = 'udp' if env.get('INTEROP_PROTOCOL') in {'quic', 'quic-tls', 'http3'} else 'tcp'
    ready_regex = re.compile(spec.ready_pattern) if spec.ready_pattern is not None else None
    deadline = time.monotonic() + spec.ready_timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return f'{spec.name} exited before becoming ready'
        if ready_regex is not None:
            stdout_text = stdout_path.read_text(encoding='utf-8', errors='replace') if stdout_path.exists() else ''
            stderr_text = stderr_path.read_text(encoding='utf-8', errors='replace') if stderr_path.exists() else ''
            if ready_regex.search(stdout_text) or ready_regex.search(stderr_text):
                return None
        if bind_host is not None and bind_port is not None and _probe_server_port(bind_host, bind_port, transport):
            return None
        if transport == 'udp' and ready_regex is None and time.monotonic() + 0.0 >= deadline - spec.ready_timeout + 0.2:
            return None
        time.sleep(0.05)
    return f'{spec.name} did not become ready within {spec.ready_timeout:.3f}s'



def _probe_server_port(host: str, port: int, transport: str) -> bool:
    if transport != 'tcp':
        return False
    family = socket.AF_INET6 if ':' in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.1)
            probe.connect((host, port))
        return True
    except OSError:
        return False



def _resolve_path(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split('.'):
        if isinstance(current, Mapping):
            if part not in current:
                raise KeyError(path)
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            try:
                current = current[index]
            except IndexError as exc:
                raise KeyError(path) from exc
        else:
            raise KeyError(path)
    return current



def _default_transport_for_protocol(protocol: str) -> str:
    return 'udp' if protocol in {'quic', 'quic-tls', 'http3'} else 'tcp'



def _reserve_port(host: str, socktype: int) -> int:
    family = socket.AF_INET6 if ':' in host else socket.AF_INET
    with socket.socket(family, socktype) as sock:
        if family == socket.AF_INET6:
            sock.bind((host, 0, 0, 0))
        else:
            sock.bind((host, 0))
        return int(sock.getsockname()[1])



def _reserve_distinct_port(host: str, socktype: int, forbidden: set[int]) -> int:
    for _ in range(128):
        port = _reserve_port(host, socktype)
        if port not in forbidden:
            return port
    raise InteropRunnerError('unable to reserve a distinct port for the interop runner')



def _normalize_sockaddr(addr: Any) -> tuple[str, int]:
    if isinstance(addr, tuple) and len(addr) >= 2:
        return str(addr[0]), int(addr[1])
    raise InteropRunnerError(f'unsupported socket address: {addr!r}')



def _apply_template(value: str, context: Mapping[str, str]) -> str:
    try:
        return value.format_map(context)
    except KeyError:
        return value



def _artifact_metadata(path: Path) -> dict[str, Any]:
    return {
        'path': str(path),
        'exists': path.exists(),
        'size': path.stat().st_size if path.exists() else 0,
        'sha256': _sha256_path(path) if path.exists() else None,
    }



def _probe_command(command: list[str]) -> dict[str, Any]:
    executable = shutil.which(command[0])
    payload: dict[str, Any] = {'command': command, 'executable': executable, 'available': executable is not None}
    if executable is None:
        return payload
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=5.0)
        payload['exit_code'] = completed.returncode
        payload['stdout'] = completed.stdout.strip()
        payload['stderr'] = completed.stderr.strip()
    except Exception as exc:
        payload['error'] = str(exc)
    return payload



def _load_json_if_present(path: Path) -> Any:
    if not path.exists():
        return None
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        return None
    return json.loads(text)



def _extract_cli_option(command: Sequence[str], flag: str) -> str | None:
    for index, item in enumerate(command):
        if item == flag and index + 1 < len(command):
            return command[index + 1]
    return None



def _resolve_cli_path(value: str | None, source_root: Path) -> str | None:
    if value in (None, ''):
        return None
    root = source_root.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = (root / path).resolve()
    if path.exists() and (path == root or root in path.parents):
        return str(path.relative_to(root))
    return str(path)



def _synthesize_sut_transcript(
    *,
    scenario: InteropScenario,
    sut_spec: InteropProcessSpec,
    sut_result: InteropProcessResult,
    peer_transcript: Any,
) -> dict[str, Any]:
    peer_request = peer_transcript.get('request') if isinstance(peer_transcript, dict) else None
    peer_response = peer_transcript.get('response') if isinstance(peer_transcript, dict) else None
    return {
        'observation_model': 'interop_runner_synthesized_from_peer_observation',
        'scenario_id': scenario.id,
        'protocol': scenario.protocol,
        'feature': scenario.feature,
        'role': 'server',
        'request': peer_request,
        'response': peer_response,
        'server_process': {
            'name': sut_spec.name,
            'adapter': sut_spec.adapter,
            'role': sut_spec.role,
            'implementation_source': sut_result.provenance.get('implementation_source'),
            'implementation_identity': sut_result.provenance.get('implementation_identity'),
            'implementation_version': sut_result.provenance.get('implementation_version'),
            'exit_code': sut_result.exit_code,
            'stdout_path': sut_result.stdout_path,
            'stderr_path': sut_result.stderr_path,
        },
        'derived_from_peer_transcript': isinstance(peer_transcript, dict),
    }



def _synthesize_sut_negotiation(
    *,
    scenario: InteropScenario,
    sut_spec: InteropProcessSpec,
    sut_result: InteropProcessResult,
    peer_negotiation: Any,
    peer_transcript: Any,
    source_root: Path,
) -> dict[str, Any]:
    peer_map = peer_negotiation if isinstance(peer_negotiation, dict) else {}
    peer_response = peer_transcript.get('response') if isinstance(peer_transcript, dict) else {}
    response_extension_header = peer_map.get('response_extension_header')
    if response_extension_header in (None, '') and isinstance(peer_response, dict):
        response_extension_header = peer_response.get('extension_header')
    negotiated_extensions = list(peer_map.get('negotiated_extensions') or [])
    if not negotiated_extensions and isinstance(response_extension_header, str) and response_extension_header.lower().startswith('permessage-deflate'):
        negotiated_extensions = ['PerMessageDeflate']
    ssl_certfile = _resolve_cli_path(_extract_cli_option(sut_spec.command, '--ssl-certfile'), source_root)
    ssl_keyfile = _resolve_cli_path(_extract_cli_option(sut_spec.command, '--ssl-keyfile'), source_root)
    return {
        'observation_model': 'interop_runner_synthesized_from_peer_observation',
        'scenario_id': scenario.id,
        'protocol': peer_map.get('protocol') or scenario.protocol,
        'feature': scenario.feature,
        'role': 'server',
        'implementation': sut_result.provenance.get('implementation_source') or sut_spec.implementation_source or sut_spec.name,
        'implementation_source': sut_result.provenance.get('implementation_source'),
        'implementation_identity': sut_result.provenance.get('implementation_identity'),
        'implementation_version': sut_result.provenance.get('implementation_version'),
        'handshake_complete': peer_map.get('handshake_complete'),
        'compression_requested': peer_map.get('compression_requested'),
        'response_extension_header': response_extension_header,
        'negotiated_extensions': negotiated_extensions,
        'connect_protocol_enabled': peer_map.get('connect_protocol_enabled'),
        'settings_enable_connect_protocol': peer_map.get('settings_enable_connect_protocol'),
        'certificate_inputs': {
            'server_certfile': {
                'path': ssl_certfile,
                'exists': bool(ssl_certfile),
            },
            'server_keyfile': {
                'path': ssl_keyfile,
                'exists': bool(ssl_keyfile),
            },
        },
        'derived_from_peer_negotiation': isinstance(peer_negotiation, dict),
    }



def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')



def _safe_name(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]+', '-', value).strip('-') or 'scenario'



def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()



def _sha256_path(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()



def _split_observed_packets(payload: bytes) -> list[bytes]:
    try:
        return split_coalesced_packets(payload, destination_connection_id_length=8)
    except Exception:
        return [payload]



def _describe_quic_packet(payload: bytes) -> dict[str, Any] | None:
    try:
        packet = decode_packet(payload, destination_connection_id_length=8)
    except Exception:
        return None
    description: dict[str, Any] = {'length': len(payload)}
    if isinstance(packet, QuicLongHeaderPacket):
        description['packet_type'] = packet.packet_type.name.lower()
        description['version'] = packet.version
        description['dcid'] = packet.destination_connection_id.hex()
        description['scid'] = packet.source_connection_id.hex()
        description['packet_number'] = int.from_bytes(packet.packet_number, 'big')
    elif isinstance(packet, QuicRetryPacket):
        description['packet_type'] = 'retry'
        description['version'] = packet.version
        description['dcid'] = packet.destination_connection_id.hex()
        description['scid'] = packet.source_connection_id.hex()
    elif isinstance(packet, QuicVersionNegotiationPacket):
        description['packet_type'] = 'version_negotiation'
        description['versions'] = list(packet.supported_versions)
        description['dcid'] = packet.destination_connection_id.hex()
        description['scid'] = packet.source_connection_id.hex()
    elif isinstance(packet, QuicShortHeaderPacket):
        description['packet_type'] = '1rtt'
        description['dcid'] = packet.destination_connection_id.hex()
        description['packet_number'] = int.from_bytes(packet.packet_number, 'big')
        description['key_phase'] = packet.key_phase
    else:
        return None
    return description


def _redact_qlog_packet(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload)
    for key in ('dcid', 'scid'):
        if key in redacted:
            redacted[key] = 'redacted'
    return redacted



def _matrix_to_json(matrix: InteropMatrix) -> dict[str, Any]:
    return {
        'name': matrix.name,
        'metadata': matrix.metadata,
        'scenarios': [
            {
                'id': scenario.id,
                'protocol': scenario.protocol,
                'role': scenario.role,
                'feature': scenario.feature,
                'peer': scenario.peer,
                'transport': scenario.transport,
                'ip_family': scenario.ip_family,
                'cipher_group': scenario.cipher_group,
                'retry': scenario.retry,
                'resumption': scenario.resumption,
                'zero_rtt': scenario.zero_rtt,
                'key_update': scenario.key_update,
                'migration': scenario.migration,
                'goaway': scenario.goaway,
                'qpack_blocking': scenario.qpack_blocking,
                'capture': scenario.capture,
                'metadata': scenario.metadata,
                'evidence_tier': scenario.evidence_tier,
                'assertions': scenario.assertions,
                'sut': _spec_to_json(scenario.sut),
                'peer_process': _spec_to_json(scenario.peer_process),
                'enabled': scenario.enabled,
            }
            for scenario in matrix.scenarios
        ],
    }



def _spec_to_json(spec: InteropProcessSpec) -> dict[str, Any]:
    return {
        'name': spec.name,
        'adapter': spec.adapter,
        'role': spec.role,
        'command': spec.command,
        'env': spec.env,
        'cwd': spec.cwd,
        'ready_pattern': spec.ready_pattern,
        'ready_timeout': spec.ready_timeout,
        'run_timeout': spec.run_timeout,
        'version_command': spec.version_command,
        'image': spec.image,
        'enabled': spec.enabled,
        'metadata': spec.metadata,
        'provenance_kind': spec.provenance_kind,
        'implementation_source': spec.implementation_source,
        'implementation_identity': spec.implementation_identity,
        'implementation_version': spec.implementation_version,
    }
