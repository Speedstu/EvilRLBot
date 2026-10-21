#!/usr/bin/env python3
"""Create a Linux AppImage from the current source and tested runtime bundle.

A previous public AppImage supplies its existing Python interpreter,
RLBotServer and installed wheels. We extract it, update the tracked source
and AppRun version, then repack it with appimagetool on GitHub's Ubuntu runner.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def build(baseline: Path, appimagetool: Path, version: str) -> None:
    work = ROOT / "build/appimage-repack"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    subprocess.run([str(baseline), "--appimage-extract"], cwd=work, check=True)
    appdir = work / "squashfs-root"
    runtime = appdir / "usr/share/evilrlbot/runtime"
    bootstrap = appdir / "AppRun"
    for required in (runtime / ".venv/bin/python",
                     runtime / ".venv-v4/bin/python",
                     runtime / "RLBotServer", bootstrap):
        if not required.exists() and not required.is_symlink():
            raise RuntimeError(f"Previous AppImage is missing {required}")

    # Do not overwrite bundled interpreters, wheels, framework shims, or
    # downstream bot models. Only refresh reviewed source files.
    safe_roots = ("ui", "src", "common", "v4_runtime", "legacy_bot", "tools")
    text_exts = {".py", ".cfg", ".toml", ".json", ".html", ".css", ".js",
                 ".png", ".svg", ".ico", ".sh", ".cjs", ".csv", ".jpg", ".md"}
    for root_name in safe_roots:
        root = ROOT / root_name
        for source in root.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(ROOT)
            if any(p in {"__pycache__", "frameworks", ".venv", ".venv-v4"}
                   for p in relative.parts):
                continue
            if source.suffix.lower() not in text_exts:
                continue
            target = runtime / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for file_name in ("run.py", "LICENSE", "README.md"):
        source = ROOT / file_name
        if source.exists():
            shutil.copy2(source, runtime / file_name)

    # Keep the app's actual Qt window icon, AppImage's .DirIcon and the
    # desktop/theme icon in sync with the current GUI shield logo.
    # The previous AppImage bundled the legacy green E icon at the root;
    # copying Python/UI sources alone never replaced those system icons.
    logo = ROOT / "ui/assets/logo.png"             # 512x512 RGBA
    small = ROOT / "packaging/icons/evil-rlbot-128.png"
    if not logo.is_file() or not small.is_file():
        raise RuntimeError("Missing official Evil RLBot shield icons")
    icon_files = (
        (small, appdir / "usr/share/icons/hicolor/128x128/apps/evil-rlbot.png"),
        (logo, appdir / "usr/share/icons/hicolor/512x512/apps/evil-rlbot.png"),
    )
    for source, destination in icon_files:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            destination.unlink()
        shutil.copy2(source, destination)
    desktop = ROOT / "packaging/evil-rlbot.desktop"
    metadata = desktop.read_text(encoding="utf-8")
    for field in ("Icon=evil-rlbot", "StartupWMClass=evil-rlbot"):
        if field not in metadata:
            raise RuntimeError(f"Desktop icon metadata missing {field}")
    for dest in (appdir / "evil-rlbot.desktop",
                 appdir / "usr/share/applications/evil-rlbot.desktop"):
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink():
            dest.unlink()
        shutil.copy2(desktop, dest)
    app_icon = appdir / "evil-rlbot.png"
    if app_icon.exists() or app_icon.is_symlink():
        app_icon.unlink()
    app_icon.symlink_to("usr/share/icons/hicolor/512x512/apps/evil-rlbot.png")
    dir_icon = appdir / ".DirIcon"
    if dir_icon.exists() or dir_icon.is_symlink():
        dir_icon.unlink()
    dir_icon.symlink_to("evil-rlbot.png")
    # Check both resolution variants and icon entrypoints before packaging.
    import hashlib
    digest = lambda p: hashlib.sha256(p.read_bytes()).digest()
    assert digest(app_icon) == digest(logo)
    assert digest(appdir / "usr/share/icons/hicolor/128x128/apps/evil-rlbot.png") == digest(small)
    assert digest(dir_icon) == digest(logo)

    apprun_text = bootstrap.read_text(encoding="utf-8")
    match = re.search(r'^VERSION="(\d{4}\.\d{1,2}\.\d{1,2}\.\d+)"$', apprun_text, re.M)
    if not match:
        raise RuntimeError("Could not locate a versioned AppRun bootstrap")
    apprun_text = (apprun_text[:match.start(1)] + version
                   + apprun_text[match.end(1):])
    bootstrap.write_text(apprun_text, encoding="utf-8")
    bootstrap.chmod(bootstrap.stat().st_mode | 0o111)

    out = ROOT / "dist" / f"EvilRLBot-{version}-x86_64.AppImage"
    out.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "ARCH": "x86_64", "VERSION": version,
           "APPIMAGE_EXTRACT_AND_RUN": "1"}
    subprocess.run([str(appimagetool), str(appdir), str(out)], check=True, env=env)
    out.chmod(out.stat().st_mode | 0o111)
    print(f"LINUX_APPIMAGE={out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--appimagetool", type=Path, required=True)
    p.add_argument("--version", required=True)
    a = p.parse_args()
    build(a.baseline.resolve(), a.appimagetool.resolve(), a.version)
