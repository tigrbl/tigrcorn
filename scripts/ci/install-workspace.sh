#!/usr/bin/env bash
set -euo pipefail

workspace_args=()
for project in pkgs/*/pyproject.toml; do
  workspace_args+=(-e "${project%/pyproject.toml}")
done

python -m pip install "${workspace_args[@]}" -e '.[certification,dev]'
