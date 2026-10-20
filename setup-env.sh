#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3.12 -m venv .venv
./.venv/bin/python -m pip install -U pip wheel setuptools
./.venv/bin/pip install -r requirements.txt
./.venv/bin/pip install -r requirements-ui.txt

python3.12 -m venv .venv-v4
./.venv-v4/bin/python -m pip install -U pip wheel
# Two-step install is intentional: rlbot 1.68.0 pins flatbuffers 1.12, which is broken on Python 3.12.
./.venv-v4/bin/pip install rlbot==1.68.0
./.venv-v4/bin/pip install -U flatbuffers==25.12.19 'setuptools<81'

curl -fL https://github.com/RLBot/core/releases/download/v5.0.0-rc17/RLBotServer -o RLBotServer
chmod +x RLBotServer evilrlbot-run evilrlbot-selftest evilrlbot-v4cfg evilrlbot-auto evilrlbot-detect evilrlbot-ui evilrlbot-ui-web src/start_bridge.sh

./evilrlbot-selftest
./.venv/bin/python -m unittest discover -s tests -p "test_*.py"
if command -v node >/dev/null 2>&1; then node tests/test_ui_js.cjs; fi

mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
ln -sfn "$PWD/evilrlbot-run" "$HOME/.local/bin/evil-rlbot"
ln -sfn "$PWD/evilrlbot-v4cfg" "$HOME/.local/bin/evil-rlbot-v4cfg"
ln -sfn "$PWD/evilrlbot-auto" "$HOME/.local/bin/evil-rlbot-auto"
ln -sfn "$PWD/evilrlbot-detect" "$HOME/.local/bin/evil-rlbot-detect"
ln -sfn "$PWD/evilrlbot-ui" "$HOME/.local/bin/evil-rlbot-ui"
ln -sfn "$PWD/evilrlbot-ui-web" "$HOME/.local/bin/evil-rlbot-ui-web"

# Keep the existing desktop shortcut consistent with the browser-based match UI.
cat > "$HOME/.local/share/applications/evil-rlbot.desktop" <<EOF_DESKTOP
[Desktop Entry]
Type=Application
Name=Evil RLBot
Comment=Native Qt desktop GUI for RLBot V4/V5 with V5 engine
Exec=$PWD/evilrlbot-ui
Icon=$PWD/ui/evilrlbot-icon.png
Terminal=false
Categories=Game;
StartupNotify=true
EOF_DESKTOP
