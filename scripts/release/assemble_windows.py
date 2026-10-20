#!/usr/bin/env python3
"""Reassemble Windows distribution from the last tested runtime and current source.

The ZIP intentionally reuses the Windows native launcher, Python runtimes and
RLBotServer from our last published Windows portable distribution. Python
source and packaging metadata always come from the current Git commit.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]

def build(baseline: Path, version: str) -> None:
    dist = ROOT / "dist"
    staged = ROOT / "release/EvilRLBot"
    if staged.exists():
        shutil.rmtree(staged)
    dist.mkdir(parents=True, exist_ok=True)
    with ZipFile(baseline) as archive:
        safe = [name for name in archive.namelist()
                if name.startswith("EvilRLBot/") and ".." not in Path(name).parts]
        if not safe or len(safe) != len(archive.namelist()):
            raise ValueError("Invalid Windows baseline ZIP structure")
        archive.extractall(ROOT / "release")

    for required in ("EvilRLBot.exe", "RLBotServer.exe", "runtime/v4/python.exe",
                     "runtime/v5/python.exe"):
        if not (staged / required).is_file():
            raise RuntimeError(f"Windows baseline missing {required}")

    # Use the Windows-specific code overlays, leaving the tested embedded
    # Python site-packages and the native server unchanged.
    from sys import path
    path.insert(0, str(ROOT / "scripts"))
    from prepare_windows_source import assemble

    workspace = ROOT / "build/windows-source"
    assemble(workspace)
    extensions = {".py", ".json", ".cfg", ".toml", ".html", ".css", ".js",
                  ".png", ".svg", ".ico", ".sh", ".cmd", ".cjs", ".txt", ".csv", ".jpg", ".md"}
    for src in workspace.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in extensions:
            continue
        rel = src.relative_to(workspace)
        if "__pycache__" in rel.parts or rel.parts[0] in {"runtime", "build", "dist"}:
            continue
        target = staged / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)

    # The Windows archive always contains a user-facing release version.
    readme = staged / "README-WINDOWS.txt"
    readme.write_text(
        f"Evil RLBot {version} - Windows x64\n\n"
        "Extract the entire ZIP and launch EvilRLBot.exe.\n"
        "Requires Rocket League installed through Epic or Steam.\n"
        "Bot imports and user Python packages are stored in LOCALAPPDATA,\n"
        "outside the application directory and survive updates.\n\n"
        "Runtime libraries and RLBotServer are carried forward from a known-good\n"
        "previous Windows release. See GitHub for source and build details.\n",
        encoding="utf-8",
    )

    package(version)

def package(version: str) -> None:
    dist = ROOT / "dist"
    staged = ROOT / "release/EvilRLBot"
    archive_path = dist / f"EvilRLBot-Windows-{version}-Portable.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for f in sorted(staged.rglob("*")):
            if f.is_file():
                archive.write(f, f.relative_to(ROOT / "release").as_posix())
    print(f"WINDOWS_PORTABLE={archive_path} ({archive_path.stat().st_size} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--package-only", action="store_true")
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if args.package_only:
        package(args.version)
    else:
        if args.baseline is None:
            parser.error("--baseline required unless --package-only")
        build(args.baseline.resolve(), args.version)
