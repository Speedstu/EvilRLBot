#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
VERSION="2026.10.20.4"
OUTDIR="${1:-$ROOT/dist}"
APPDIR="$ROOT/build/EvilRLBot.AppDir"
mkdir -p "$OUTDIR"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/share/evilrlbot/runtime" "$APPDIR/usr/share/icons/hicolor/128x128/apps"
RUNTIME="$APPDIR/usr/share/evilrlbot/runtime"
# Selective packaging: never include .git, secrets, games, user bot weights,
# checkpoints, captured logs, cached source archives, or private browser data.
for item in LICENSE README.md requirements.txt requirements-v4.txt requirements-ui.txt  RLBotServer run.py evilrlbot-ui evilrlbot-auto evilrlbot-detect evilrlbot-v4cfg  legacy_bot ui src common tools v4_runtime; do
  if [[ -e "$ROOT/$item" ]]; then
    if [[ "$item" == "tools" ]]; then
      mkdir -p "$RUNTIME/tools"
      for file in auto_bot.py detect_bot.py v4cfg_to_v5.py selftest_exact.py; do
        [[ ! -f "$ROOT/tools/$file" ]] || cp -a "$ROOT/tools/$file" "$RUNTIME/tools/"
      done
    elif [[ "$item" == "ui" ]]; then
      mkdir -p "$RUNTIME/ui"
      cp -a "$ROOT/ui/"*.py "$RUNTIME/ui/"
      cp -a "$ROOT/ui/"*.png "$RUNTIME/ui/" 2>/dev/null || :
      [[ ! -d "$ROOT/ui/assets" ]] || cp -a "$ROOT/ui/assets" "$RUNTIME/ui/"
    else
      cp -a "$ROOT/$item" "$RUNTIME/"
    fi
  fi
done
mkdir -p "$RUNTIME/python"
tar -xzf "$ROOT/build/tools/python-3.12-linux-install-only.tar.gz" -C "$RUNTIME"
# Use wheel/site packages from tested venvs, and rebase their interpreter paths
# in AppRun after first extraction. Original system Python is NOT bundled.
for envname in .venv .venv-v4; do
  cp -a "$ROOT/$envname" "$RUNTIME/$envname"
  find "$RUNTIME/$envname" -type d -name __pycache__ -prune -exec rm -rf {} + || true
  find "$RUNTIME/$envname" -type f -name '*.pyc' -delete || true
done
# Playwright and web testing aren't needed by the native Qt UI.
rm -rf "$RUNTIME/.venv/lib/python3.12/site-packages/playwright"        "$RUNTIME/.venv/lib/python3.12/site-packages/playwright-"*.dist-info        "$RUNTIME/.venv/lib/python3.12/site-packages/playwright-"*.data
cp -a "$ROOT/packaging/AppRun" "$APPDIR/AppRun"
cp -a "$ROOT/packaging/evil-rlbot.desktop" "$APPDIR/evil-rlbot.desktop"
cp -a "$ROOT/ui/evilrlbot-icon.png" "$APPDIR/usr/share/icons/hicolor/128x128/apps/evil-rlbot.png"
ln -s usr/share/icons/hicolor/128x128/apps/evil-rlbot.png "$APPDIR/evil-rlbot.png"
ln -s evil-rlbot.png "$APPDIR/.DirIcon"
chmod +x "$RUNTIME/RLBotServer"
ARCH=x86_64 VERSION="$VERSION" "$ROOT/build/tools/appimagetool-x86_64.AppImage"  "$APPDIR" "$OUTDIR/EvilRLBot-$VERSION-x86_64.AppImage"
chmod +x "$OUTDIR/EvilRLBot-$VERSION-x86_64.AppImage"
sha256sum "$OUTDIR/EvilRLBot-$VERSION-x86_64.AppImage"
du -sh "$RUNTIME" "$OUTDIR/EvilRLBot-$VERSION-x86_64.AppImage"
