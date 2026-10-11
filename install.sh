#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Keep package downloads on disk; /tmp may be a small tmpfs.
export TMPDIR="$PWD/.install-tmp"
mkdir -p "$TMPDIR"

python3 -m venv backend_venv
backend_venv/bin/python -m pip install --upgrade pip
backend_venv/bin/pip install -r backend/requirements.txt

if command -v npm >/dev/null 2>&1; then
  npm install
fi

chmod +x start-bot.sh
printf '\nInstall complete. Run ./start-bot.sh for first-run Telegram setup.\n'
