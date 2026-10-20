#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export EVILRLBOT_V4_CONFIG="${EVILRLBOT_V4_CONFIG:-$(cd "$(dirname "$0")/.." && pwd -P)/legacy_bot/bot.cfg}"
exec ../.venv/bin/python v5_bridge.py
