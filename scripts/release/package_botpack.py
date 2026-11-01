#!/usr/bin/env python3
"""Package the tracked optional community botpack, excluding all Wolvot files.

This does not alter the Windows installer or Linux AppImage and never runs
third-party executables or unpickles third-party weights.
"""
from __future__ import annotations

import argparse
import stat
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]
BOTPACK = ROOT / "botpack"
SUBFOLDERS = (
    "BOT_RLBOT_V4",
    "MECH_VERSIONS_UNCONFIRMED",
    "WISP_RLBOT_V5",
    "LICENCES",
)
MAX_FILE_BYTES = 100_000_000
REQUIRED = {
    "BOT_RLBOT_V4/Element/bot.cfg",
    "BOT_RLBOT_V4/Necto/bot.cfg",
    "BOT_RLBOT_V4/Nexto/bot.cfg",
    "MECH_VERSIONS_UNCONFIRMED/Mech_01/bot.cfg",
    "MECH_VERSIONS_UNCONFIRMED/Mech_02_Mechanoid/bot.cfg",
    "MECH_VERSIONS_UNCONFIRMED/Mech_03_VelocityRL/bot.cfg",
    "WISP_RLBOT_V5/WispV2_binary/wisp.bot.toml",
    "WISP_RLBOT_V5/WispV2_source/src/wisp.bot.toml",
    "WISP_RLBOT_V5/WispV2_binary/x86_64-pc-windows-msvc/bot.exe",
    "README.md",
    "README.txt",
    "LICENCES/Necto_LICENSE.txt",
}


def source_files() -> list[Path]:
    if not BOTPACK.is_dir():
        raise RuntimeError("The community botpack directory is missing")
    files = sorted(p for p in BOTPACK.rglob("*") if p.is_file())
    relative = {p.relative_to(BOTPACK).as_posix() for p in files}
    if missing := REQUIRED - relative:
        raise RuntimeError(f"Missing required botpack files: {sorted(missing)}")
    if len(files) < 140:
        raise RuntimeError("The community botpack looks incomplete")
    for p in files:
        if p.is_symlink():
            raise RuntimeError(f"Symlinks are not permitted: {p}")
        rel = p.relative_to(BOTPACK)
        if "wolvot" in rel.as_posix().lower():
            raise RuntimeError(f"Wolvot was accidentally included: {rel}")
        if rel.parts[0] not in (*SUBFOLDERS, "README.md", "README.txt"):
            raise RuntimeError(f"Unexpected botpack root: {rel}")
        if p.stat().st_size >= MAX_FILE_BYTES:
            raise RuntimeError(f"File too large for ordinary GitHub storage: {rel}")
    return files


def package(version: str) -> Path:
    files = source_files()
    output = ROOT / "dist" / f"EvilRLBot-Community-Botpack-No-Wolvot-{version}.zip"
    output.parent.mkdir(exist_ok=True, parents=True)
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for file in files:
            archive.write(file, "BOTPACK/" + file.relative_to(BOTPACK).as_posix())
    with ZipFile(output) as archive:
        archive_members = archive.namelist()
        if len(archive_members) != len(files):
            raise RuntimeError("Botpack package is incomplete")
        if any("wolvot" in p.lower() for p in archive_members):
            raise RuntimeError("Wolvot slipped into packaged ZIP")
        if set(archive_members) != {
            "BOTPACK/" + p.relative_to(BOTPACK).as_posix() for p in files
        }:
            raise RuntimeError("Botpack manifest verification failed")
    print(f"BOTPACK_PACKAGE={output}")
    print(f"BOTPACK_FILES={len(files)}")
    print(f"BOTPACK_SIZE={output.stat().st_size}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    arguments = parser.parse_args()
    package(arguments.version)
