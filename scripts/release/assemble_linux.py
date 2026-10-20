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
