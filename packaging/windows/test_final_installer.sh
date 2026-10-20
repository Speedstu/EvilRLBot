#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
WINE="$HOME/.var/app/com.heroicgameslauncher.hgl/config/heroic/tools/proton/Proton-CachyOS-latest/files/bin/wine"
export WINEPREFIX="$PWD/build/wine-sandbox" WINEDEBUG=-all
LOCAL="$WINEPREFIX/drive_c/users/steamuser/AppData/Local"
INST="$LOCAL/Programs/EvilRLBot"
KEEP="$LOCAL/EvilRLBot/bots/evilrlbot-keep-data.txt"
mkdir -p "$(dirname "$KEEP")" "$INST/runtime/v4/Lib/site-packages/pip"
printf 'User bot data persists\n' > "$KEEP"
printf 'old-pip-marker\n' > "$INST/runtime/v4/Lib/site-packages/pip/old-pip-marker.txt"
echo PRETEST_PREVIOUS_RUNTIME_SIMULATED
timeout 125s "$WINE" dist/EvilRLBot-Windows-x64-Setup.exe /S
test -f "$INST/runtime/v4/python.exe"
test -f "$INST/runtime/v5/python.exe"
test -f "$INST/Uninstall.exe"
test -f "$KEEP"
test ! -f "$INST/runtime/v4/Lib/site-packages/pip/old-pip-marker.txt"
echo OLD_PIP_REMOVED_USER_DATA_PRESERVED
timeout 20s "$WINE" "$INST/runtime/v4/python.exe" -m pip --version
timeout 20s "$WINE" "$INST/runtime/v5/python.exe" -m pip --version
timeout 28s "$WINE" "$INST/runtime/v4/python.exe" -c 'import numpy;from rlbot.agents.base_agent import BaseAgent;print("INSTALLED V4 READY",numpy.__version__)'
timeout 28s "$WINE" "$INST/runtime/v5/python.exe" -c 'from PySide6.QtWidgets import QApplication;from rlbot.managers import MatchManager;print("INSTALLED V5 GUI READY")'
echo 'FINAL_INSTALLER_UPGRADE_VALIDATED'
