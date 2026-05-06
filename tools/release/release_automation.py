from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_VERSION_RE = re.compile(r'(?m)^(version\s*=\s*)"([^"]+)"')
PYPROJECT_NAME_RE = re.compile(r'(?m)^name\s*=\s*"([^"]+)"')
PYPROJECT_DEP_RE = re.compile(r'(tigrcorn-[A-Za-z0-9-]+)==[0-9][A-Za-z0-9.!+_-]*')
PY_VERSION_RE = re.compile(r'(?m)^(__version__\s*=\s*)"([^"]+)"')
PACKAGE_SPLIT_RE = re.compile(r"[\s,]+")
PYTHON_VERSION_FILE = ROOT / "pkgs" / "tigrcorn-core" / "src" / "tigrcorn_core" / "version.py"
RELEASE_NOTES_DIR = ROOT / "docs" / "release-notes"
RELEASE_NOTES_NAME_LIMIT = 24


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    dev: int | None = None
    npm: bool = False

    @classmethod
    def parse(cls, value: str, *, npm: bool = False) -> "Version":
        if npm:
            match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-dev\.(\d+))?", value)
        else:
            match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:\.dev(\d+))?", value)
        if not match:
            raise ValueError(f"unsupported version {value!r}")
        major, minor, patch, dev = match.groups()
        return cls(
            int(major),
            int(minor),
            int(patch),
            int(dev) if dev is not None else None,
            npm=npm,
        )

    def bump(self, semver: str) -> "Version":
        segment = semver.lower()
        if segment in {"w", "major"}:
            raise ValueError("w/major bumps are disallowed in the release workflow")
        if segment in {"x", "minor"}:
            segment = "minor"
        elif segment in {"y", "patch"}:
            segment = "patch"
        elif segment in {"z", "dev"}:
            segment = "dev"

        if segment == "finalize":
            if self.dev is None:
                return self
            return Version(self.major, self.minor, self.patch, npm=self.npm)
        if segment == "minor":
            return Version(self.major, self.minor + 1, 0, 1, self.npm)
        if segment in {"patch", "dev"}:
            if self.dev is None:
                return Version(self.major, self.minor, self.patch + 1, 1, self.npm)
            return Version(self.major, self.minor, self.patch, self.dev + 1, self.npm)
        raise ValueError(f"unsupported semver bump action {semver!r}")

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.dev is None:
            return base
        if self.npm:
            return f"{base}-dev.{self.dev}"
        return f"{base}.dev{self.dev}"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_if_changed(path: Path, text: str) -> bool:
    old = read(path)
    if old == text:
        return False
    path.write_text(text, encoding="utf-8", newline="")
    return True


def write_json_if_changed(path: Path, payload: Any) -> bool:
    text = json.dumps(payload, indent=2) + "\n"
    return write_if_changed(path, text)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def python_projects() -> list[dict[str, str]]:
    paths = [ROOT / "pyproject.toml"]
    paths.extend(sorted(ROOT.glob("pkgs/*/pyproject.toml")))
    projects: list[dict[str, str]] = []
    for pyproject in paths:
        text = read(pyproject)
        name_match = PYPROJECT_NAME_RE.search(text)
        version_match = PYPROJECT_VERSION_RE.search(text)
        if not name_match or not version_match:
            continue
        projects.append(
            {
                "kind": "pypi",
                "name": name_match.group(1),
                "version": version_match.group(2),
                "path": relative(pyproject),
            }
        )
    return projects


def npm_projects() -> list[dict[str, str]]:
    projects: list[dict[str, str]] = []
    for manifest in sorted(ROOT.glob("packages/*/package.json")):
        payload = json.loads(read(manifest))
        if payload.get("private") is True:
            continue
        name = str(payload["name"])
        projects.append(
            {
                "kind": "npm",
                "name": name,
                "version": str(payload["version"]),
                "path": relative(manifest),
            }
        )
    return projects


def parse_package_selection(value: str | None) -> str:
    return (value or "all").strip() or "all"


def selected_projects(selection: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    py_projects = python_projects()
    npm = npm_projects()
    py_by_name = {project["name"]: project for project in py_projects}
    npm_by_name = {project["name"]: project for project in npm}
    npm_by_short = {project["name"].split("/")[-1]: project for project in npm}

    if selection == "all":
        return py_projects, npm
    if selection == "tigrcorn core packages":
        return py_projects, []
    if selection in {"probes", "wt-peer-probes"}:
        return [], [npm_by_short["wt-peer-probes"]]
    if selection in py_by_name:
        return [py_by_name[selection]], []
    if selection in npm_by_name:
        return [], [npm_by_name[selection]]
    if selection in npm_by_short:
        return [], [npm_by_short[selection]]

    names = sorted({*py_by_name, *npm_by_name, *npm_by_short, "all", "tigrcorn core packages", "probes"})
    raise ValueError(f"unknown package selection {selection!r}. Known selections: {', '.join(names)}")


def replace_python_version(path: Path, new_version: str) -> bool:
    text = read(path)
    updated, count = PYPROJECT_VERSION_RE.subn(rf'\g<1>"{new_version}"', text, count=1)
    if count != 1:
        raise RuntimeError(f"project version not found in {path}")
    return write_if_changed(path, updated)


def replace_internal_python_deps(path: Path, selected_names: set[str], new_versions: dict[str, str]) -> bool:
    text = read(path)

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in selected_names:
            return match.group(0)
        return f"{name}=={new_versions[name]}"

    updated = PYPROJECT_DEP_RE.sub(repl, text)
    return write_if_changed(path, updated)


def replace_python_dunder_version(new_version: str) -> bool:
    text = read(PYTHON_VERSION_FILE)
    updated, count = PY_VERSION_RE.subn(rf'\g<1>"{new_version}"', text, count=1)
    if count != 1:
        raise RuntimeError(f"__version__ not found in {PYTHON_VERSION_FILE}")
    return write_if_changed(PYTHON_VERSION_FILE, updated)


def update_npm_manifest(path: Path, new_version: str) -> bool:
    payload = json.loads(read(path))
    payload["version"] = new_version
    return write_json_if_changed(path, payload)


def update_npm_lock(manifest: Path, new_version: str) -> list[str]:
    lock_path = manifest.with_name("package-lock.json")
    if not lock_path.exists():
        return []
    payload = json.loads(read(lock_path))
    payload["version"] = new_version
    root_package = payload.get("packages", {}).get("")
    if isinstance(root_package, dict):
        root_package["version"] = new_version
    if write_json_if_changed(lock_path, payload):
        return [relative(lock_path)]
    return []


def release_notes_filename(version: str) -> str:
    name = f"RELEASE_NOTES_{version}.md"
    if len(name) <= RELEASE_NOTES_NAME_LIMIT:
        return name
    return f"REL_{version}.md"


def ensure_release_notes(version: str, plan_releases: list[dict[str, str]]) -> list[str]:
    path = RELEASE_NOTES_DIR / release_notes_filename(version)
    if path.exists():
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Release notes - tigrcorn {version}",
        "",
        "This release was prepared by the publish-all-packages workflow.",
        "",
        "## Package versions",
        "",
    ]
    for release in plan_releases:
        lines.append(f"- `{release['name']}`: `{release['old_version']}` -> `{release['version']}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="")
    return [relative(path)]


def build_plan(semver: str, *, write_changes: bool, packages: str | None = None) -> dict[str, Any]:
    selection = parse_package_selection(packages)
    py_selected, npm_selected = selected_projects(selection)
    changed: list[str] = []

    py_releases: list[dict[str, str]] = []
    py_versions: dict[str, str] = {}
    for project in py_selected:
        new_version = str(Version.parse(project["version"]).bump(semver))
        release = {**project, "old_version": project["version"], "version": new_version}
        py_releases.append(release)
        py_versions[project["name"]] = new_version
        if write_changes and replace_python_version(ROOT / project["path"], new_version):
            changed.append(project["path"])

    if write_changes and py_releases:
        selected_names = {release["name"] for release in py_releases}
        for release in py_releases:
            path = ROOT / release["path"]
            if replace_internal_python_deps(path, selected_names, py_versions):
                changed.append(release["path"])
        if "tigrcorn-core" in selected_names:
            core_version = py_versions["tigrcorn-core"]
            if replace_python_dunder_version(core_version):
                changed.append(relative(PYTHON_VERSION_FILE))

    npm_releases: list[dict[str, str]] = []
    for project in npm_selected:
        new_version = str(Version.parse(project["version"], npm=True).bump(semver))
        release = {**project, "old_version": project["version"], "version": new_version}
        npm_releases.append(release)
        if write_changes and update_npm_manifest(ROOT / project["path"], new_version):
            changed.append(project["path"])
        if write_changes:
            changed.extend(update_npm_lock(ROOT / project["path"], new_version))

    if write_changes:
        root_release = next((release for release in py_releases if release["name"] == "tigrcorn"), None)
        if root_release is not None:
            changed.extend(ensure_release_notes(root_release["version"], [*py_releases, *npm_releases]))

    github_releases = [
        {"tag": f'{release["name"]}=={release["version"]}', **release}
        for release in [*py_releases, *npm_releases]
    ]
    prerelease = any(Version.parse(release["version"], npm=release["kind"] == "npm").dev is not None for release in github_releases)

    return {
        "semver": semver,
        "prerelease": prerelease,
        "package_selection": selection,
        "python": py_releases,
        "npm": npm_releases,
        "github_releases": github_releases,
        "changed_files": sorted(set(changed)),
    }


def current_version_summary() -> dict[str, Any]:
    py_projects = python_projects()
    npm = npm_projects()
    releases = [
        {"tag": f'{project["name"]}=={project["version"]}', **project}
        for project in [*py_projects, *npm]
    ]
    prerelease = any(Version.parse(release["version"], npm=release["kind"] == "npm").dev is not None for release in releases)
    return {
        "semver": "current",
        "prerelease": prerelease,
        "package_selection": "event",
        "python": py_projects,
        "npm": npm,
        "github_releases": releases,
        "changed_files": [],
    }


def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args), flush=True)
    return subprocess.run(args, cwd=ROOT, check=True, text=True, **kwargs)


def git_output(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def normalize_python_project(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def url_exists(url: str) -> bool:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30):
            return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise RuntimeError(f"{url} lookup failed with HTTP {exc.code}") from exc


def validate_release_targets(plan_path: Path, *, github: bool, pypi: bool, npmjs: bool) -> None:
    plan = json.loads(read(plan_path))
    failures: list[str] = []

    if github:
        for release in plan["github_releases"]:
            tag = release["tag"]
            tag_exists = subprocess.run(
                ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
                cwd=ROOT,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if tag_exists.returncode == 0:
                failures.append(f"Git tag already exists: {tag}")
                continue
            release_exists = subprocess.run(
                ["gh", "release", "view", tag],
                cwd=ROOT,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if release_exists.returncode == 0:
                failures.append(f"GitHub release already exists: {tag}")

    if pypi:
        for release in plan["python"]:
            project = normalize_python_project(release["name"])
            version = release["version"]
            url = f"https://pypi.org/pypi/{project}/{version}/json"
            if url_exists(url):
                failures.append(f"PyPI version already exists: {project} {version}")

    if npmjs:
        for release in plan["npm"]:
            encoded = urllib.parse.quote(release["name"], safe="")
            version = release["version"]
            url = f"https://registry.npmjs.org/{encoded}/{version}"
            if url_exists(url):
                failures.append(f"npmjs version already exists: {release['name']} {version}")

    if failures:
        print("Release target validation failed:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    selected = []
    if github:
        selected.append("GitHub releases")
    if pypi:
        selected.append("PyPI")
    if npmjs:
        selected.append("npmjs")
    print(f"Release target validation passed for: {', '.join(selected) or 'none'}")


def create_github_tags(plan_path: Path) -> None:
    plan = json.loads(read(plan_path))
    created_tags: list[str] = []
    for release in plan["github_releases"]:
        tag = release["tag"]
        existing = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if existing.returncode == 0:
            raise RuntimeError(f"tag {tag} already exists")
        run(["git", "tag", "-a", tag, "-m", tag])
        created_tags.append(tag)
    if created_tags:
        run(["git", "push", "origin", *created_tags])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    bump = subparsers.add_parser("bump")
    bump.add_argument("--semver", choices=["minor", "patch", "dev", "x", "y", "z", "finalize"], required=True)
    bump.add_argument("--summary", type=Path, required=True)
    bump.add_argument("--packages", default="all")
    bump.add_argument("--write", action="store_true")

    current = subparsers.add_parser("current")
    current.add_argument("--summary", type=Path, required=True)

    validate_targets = subparsers.add_parser("validate-release-targets")
    validate_targets.add_argument("--summary", type=Path, required=True)
    validate_targets.add_argument("--github", action="store_true")
    validate_targets.add_argument("--pypi", action="store_true")
    validate_targets.add_argument("--npmjs", action="store_true")

    gh = subparsers.add_parser("create-github-tags")
    gh.add_argument("--summary", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.command == "bump":
        plan = build_plan(args.semver, write_changes=args.write, packages=args.packages)
        args.summary.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(plan, indent=2))
        return 0
    if args.command == "current":
        plan = current_version_summary()
        args.summary.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(plan, indent=2))
        return 0
    if args.command == "validate-release-targets":
        if args.github and not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
            raise RuntimeError("GH_TOKEN or GITHUB_TOKEN is required")
        validate_release_targets(
            args.summary,
            github=args.github,
            pypi=args.pypi,
            npmjs=args.npmjs,
        )
        return 0
    if args.command == "create-github-tags":
        create_github_tags(args.summary)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    sys.exit(main())
