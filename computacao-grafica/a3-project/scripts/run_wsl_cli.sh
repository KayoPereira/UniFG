#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WINDOWS_LOCALAPPDATA="$(powershell.exe -NoProfile -Command '$env:LOCALAPPDATA' | tr -d '\r')"
WSL_LOCALAPPDATA="$(wslpath "$WINDOWS_LOCALAPPDATA")"

export DATA_DIR="$WSL_LOCALAPPDATA/a3-project-data"
export FACES_DIR="$DATA_DIR/faces"
export DATABASE_PATH="$DATA_DIR/attendance.db"

mkdir -p "$FACES_DIR"

cd "$PROJECT_ROOT"
python3 -m app.cli "$@"
