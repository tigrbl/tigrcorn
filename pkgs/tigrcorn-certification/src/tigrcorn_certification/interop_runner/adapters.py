from __future__ import annotations

from .imports import *
from .models import *
from .process import *
from .helpers import *
from .ports import _wait_for_server_ready

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

__all__ = [name for name in globals() if not name.startswith('__')]
