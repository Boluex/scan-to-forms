#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${SCANFORMS_PYTHON:-$root/.venv/bin/python}" "$root/backend/scripts/local_workflow.py" digitize "$@"
