#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export PANEL_HOST="${PANEL_HOST:-0.0.0.0}"
export PANEL_PORT="${PANEL_PORT:-8781}"

exec .venv/bin/python -m src.panel_server
