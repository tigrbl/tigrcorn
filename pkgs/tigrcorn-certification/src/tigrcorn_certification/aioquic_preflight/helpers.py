from __future__ import annotations

from .imports import *

class AioquicAdapterPreflightError(RuntimeError):
    """Raised when the aioquic adapter preflight fails and strict pass mode is enabled."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _module_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _command_option(command: Sequence[str], option: str) -> str | None:
    try:
        index = list(command).index(option)
    except ValueError:
        return None
    next_index = index + 1
    if next_index >= len(command):
        return None
    return str(command[next_index])


def _module_name(command: Sequence[str]) -> str | None:
    try:
        index = list(command).index('-m')
    except ValueError:
        return None
    next_index = index + 1
    if next_index >= len(command):
        return None
    return str(command[next_index])


def _path_ready(entry: Mapping[str, Any] | None) -> bool:
    if not isinstance(entry, Mapping):
        return False
    return bool(entry.get('exists')) and bool(entry.get('is_file'))


def _default_certificate_inputs(repo_root: Path, peer_command: Sequence[str]) -> dict[str, Any]:
    def _entry(option: str) -> dict[str, Any]:
        value = _command_option(peer_command, option)
        if value is None:
            return {'path': None, 'exists': False, 'is_file': False}
        candidate = repo_root / value
        return {
            'path': value,
            'exists': candidate.exists(),
            'is_file': candidate.is_file(),
        }

    ca = _entry('--cacert')
    cert = _entry('--client-cert')
    key = _entry('--client-key')
    client_material_requested = bool(cert['path'] or key['path'])
    client_material_ready = (not client_material_requested) or (bool(cert['exists']) and bool(key['exists']))
    return {
        'ca_cert': ca,
        'client_cert': cert,
        'client_key': key,
        'client_material_requested': client_material_requested,
        'client_material_ready': client_material_ready,
        'ready': bool(ca['exists']) and client_material_ready,
    }


def _scenario_kind(scenario_id: str) -> str:
    if 'websocket' in scenario_id:
        return 'http3_websocket_adapter'
    return 'http3_client_adapter'
