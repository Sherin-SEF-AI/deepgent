#!/usr/bin/env bash
# One-command install: put deepgent (with the GUI) on your PATH via uv's tool
# system, so `deepgent`, `dg`, and `deepgent-gui` work from anywhere.
#
#   ./install.sh
#
# Requires uv (https://docs.astral.sh/uv/). Re-run any time to update.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

echo "installing deepgent from ${repo} ..."
uv tool install --force --editable "${repo}[gui]"

echo
if command -v deepgent >/dev/null 2>&1; then
  echo "installed: $(command -v deepgent)  ($(deepgent --version))"
  echo "try:  deepgent doctor   |   deepgent gui   |   deepgent mcp"
else
  echo "deepgent installed, but its bin dir is not on PATH."
  echo "add uv's tool bin to PATH:  uv tool update-shell   (then restart the shell)"
fi
