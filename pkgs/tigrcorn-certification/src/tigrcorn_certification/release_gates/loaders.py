from __future__ import annotations

from .imports import *

def load_certification_boundary(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_conformance_corpus(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))
def _load_json_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))

def _load_public_parser_flags() -> dict[str, dict[str, Any]]:
    import argparse

    from importlib import import_module

    parser = import_module('tigrcorn_' + 'runtime.cli').build_parser()
    public_flags: dict[str, dict[str, Any]] = {}
    for group in parser._action_groups:
        title = getattr(group, 'title', None)
        for action in getattr(group, '_group_actions', []):
            if isinstance(action, argparse._HelpAction):
                continue
            if action.help == argparse.SUPPRESS:
                continue
            for flag in action.option_strings:
                if not flag.startswith('--'):
                    continue
                public_flags[flag] = {
                    'dest': action.dest,
                    'group': title,
                    'choices': list(action.choices) if action.choices is not None else [],
                    'nargs': action.nargs,
                    'default': action.default,
                }
    return public_flags



def _load_performance_metric_keys(artifact_root: Path, profile_ids: list[str]) -> set[str]:
    metric_keys: set[str] = set()
    for profile_id in profile_ids:
        result_file = artifact_root / profile_id / 'result.json'
        if not result_file.exists():
            continue
        payload = json.loads(result_file.read_text(encoding='utf-8'))
        metrics = payload.get('metrics', {})
        if isinstance(metrics, Mapping):
            metric_keys.update(str(key) for key in metrics)
    return metric_keys

__all__ = [name for name in globals() if not name.startswith('__')]

