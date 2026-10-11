#!/bin/bash
# Start Telegram bot for Cheat Clip Pro
# Usage: ./start-bot.sh

cd "$(dirname "$0")"

# First-run setup collects Telegram/API settings locally.
if [ ! -f backend/.env ]; then
    python3 setup.py
fi

# Activate virtual environment
source backend_venv/bin/activate

# Load secrets/config from backend/.env without printing values
if [ -f backend/.env ]; then
    set -a
    . backend/.env
    set +a
fi
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ "$TELEGRAM_BOT_TOKEN" = "your_bot_token_here" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN missing in backend/.env or environment"
    exit 1
fi

# Start bot as module so `backend` imports resolve
PYTHONPATH="$PWD" python -m backend.bot
