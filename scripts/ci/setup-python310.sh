#!/usr/bin/env bash
set -euo pipefail

if ! dpkg-query -W -f='${db:Status-Status}' python3.10-venv 2>/dev/null | grep -qx installed; then
  sudo apt-get update
  sudo apt-get install -y python3.10-venv
fi

venv_dir="$RUNNER_TEMP/tigrcorn-python310"
/usr/bin/python3.10 -m venv "$venv_dir"
echo "$venv_dir/bin" >> "$GITHUB_PATH"
