#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Use the existing checkout. No separate worktree is needed.
exec .venv/bin/gunicorn config.wsgi:application --bind "${BIND:-127.0.0.1:8000}" --workers 1 --threads 4 --timeout 60 --access-logfile - --error-logfile -
