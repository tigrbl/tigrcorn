from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Iterable

from tigrcorn_static.static import (
    StaticSecurityCertificationError,
    build_static_certification_evidence,
    certify_static_delivery_security,
    static_delivery_certification_artifact,
)

from ..artifacts import canonical_json


class StaticCertificationCommandError(ValueError):
    """Raised when static certification cannot be completed."""


def build_static_certification_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tigrcorn certify static")
    parser.add_argument("--mount", required=True, help="Static mount directory to certify")
    parser.add_argument("--profile", default="default", help="Blessed deployment profile")
    parser.add_argument("--output", required=True, help="Directory where certification artifacts are written")
    return parser


def certify_static(
    *,
    mount: str | Path,
    profile: str = "default",
    output: str | Path,
    require_supported: Callable[[Iterable[str]], None] | None = None,
) -> dict[str, object]:
    mount_path = Path(mount)
    if not mount_path.exists() or not mount_path.is_dir():
        raise StaticCertificationCommandError(f"static mount does not exist or is not a directory: {mount_path}")

    if require_supported is not None:
        require_supported(["delivery.static"])

    evidence = build_static_certification_evidence(mount_path, profile=profile)
    certification = certify_static_delivery_security(evidence)
    static_artifact = {
        "artifact": static_delivery_certification_artifact(),
        "certification": certification,
        "evidence": evidence,
        "mount_name": mount_path.name,
        "profile": profile,
        "schema_version": 1,
    }
    manifest = {
        "artifacts": [
            {
                "digest": _digest(static_artifact),
                "name": "static.json",
            }
        ],
        "certification": "static",
        "digest_algorithm": "sha256",
        "manifest_version": 1,
        "profile": profile,
    }
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    static_path = output_path / "static.json"
    manifest_path = output_path / "manifest.json"
    static_path.write_text(canonical_json(static_artifact), encoding="utf-8", newline="\n")
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8", newline="\n")
    return {
        "artifact_paths": [str(static_path), str(manifest_path)],
        "mount": str(mount_path),
        "output": str(output_path),
        "passed": True,
        "profile": profile,
    }


def certify_static_main(
    argv: list[str] | None = None,
    *,
    require_supported: Callable[[Iterable[str]], None] | None = None,
) -> int:
    parser = build_static_certification_parser()
    ns = parser.parse_args(list(argv or ()))

    capability_gate = None
    if require_supported is not None:
        capability_gate = lambda ids: require_supported(ids, profile=ns.profile)  # noqa: E731
    try:
        result = certify_static(
            mount=ns.mount,
            profile=ns.profile,
            output=ns.output,
            require_supported=capability_gate,
        )
    except (StaticCertificationCommandError, StaticSecurityCertificationError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _digest(payload: dict[str, object]) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


__all__ = [
    "StaticCertificationCommandError",
    "build_static_certification_parser",
    "certify_static",
    "certify_static_main",
]
