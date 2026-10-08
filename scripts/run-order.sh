#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export SCANTO_FORMS_ENV_FILE="${SCANTO_FORMS_ENV_FILE:-$root/.env.worker}"
exec "${SCANFORMS_PYTHON:-$root/.venv/bin/python}" "$root/backend/manage.py" operate_order "$@"
