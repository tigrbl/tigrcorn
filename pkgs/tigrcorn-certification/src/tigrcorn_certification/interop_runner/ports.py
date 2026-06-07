from __future__ import annotations

from .imports import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
