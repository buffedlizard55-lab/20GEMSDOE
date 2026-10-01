#!/usr/bin/env bash
# Idempotent SHA-256-verified restoration from immutable GitHub bridge commits.
# No DrivenData scraping, default-branch clones, unused H16 contexts or partial final files.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-${ROOT}/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then PYTHON_BIN="python3"; fi
exec "$PYTHON_BIN" "${ROOT}/scripts/restore_data.py" "$@"
