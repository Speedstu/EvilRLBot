#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 -m compileall -q ui src tools v4_runtime run.py
python3 packaging/windows/build_release.py
WINE="$HOME/.var/app/com.heroicgameslauncher.hgl/config/heroic/tools/proton/Proton-CachyOS-latest/files/bin/wine"
export WINEPREFIX="$PWD/build/wine-sandbox" WINEDEBUG=-all
# Regression for the spectator-only empty match: RLBot launches bridges from
# each bot's working directory, not the EvilRLBot application root.
"$WINE" runtime/v5/python.exe packaging/windows/test_bridge_from_bot_cwd.py
ROOT_FOR_NSIS="$(printf '%s' "$PWD" | sed 's,^/,Z:\\,;s,/,\\,g')"
"$WINE" build/nsis/nsis-3.11/makensis.exe "/DROOT=$ROOT_FOR_NSIS" /V2 packaging/windows/installer.nsi
sha256sum dist/EvilRLBot-Windows-x64-Setup.exe dist/EvilRLBot-Windows-x64-Portable.zip
ls -lh dist/
