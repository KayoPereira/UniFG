#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PS_SCRIPT_WIN="$(wslpath -w "$SCRIPT_DIR/run_windows_cli.ps1")"

powershell.exe -ExecutionPolicy Bypass -File "$PS_SCRIPT_WIN" "$@"
