#!/usr/bin/env python3
"""Reproducible staging of Evil RLBot's Windows portable release."""
from pathlib import Path
from shutil import copytree,copy2,rmtree
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
root=Path(__file__).resolve().parents[2]
output=root/"release"/"EvilRLBot"
if output.exists():rmtree(output)
output.mkdir(parents=True)
for entry in ("ui","src","common","v4_runtime","legacy_bot","runtime"):
    copytree(root/entry, output/entry, ignore=lambda d, names: {
        n for n in names if n in ("__pycache__",".temp","tests") or n.endswith(".pyc") or n.endswith(".bak") or ".bak" in n
    })
(output/"tools").mkdir()
for name in ("auto_bot.py","v4cfg_to_v5.py","detect_bot.py"):
    copy2(root/"tools"/name,output/"tools"/name)
for name in ("EvilRLBot.exe","EvilRLBot-Debug.cmd","RLBotServer.exe","run.py","LICENSE"):
    copy2(root/name,output/name)
readme="""EVIL RLBOT — WINDOWS x64
Release 2026.10.20.4 • Portable (no browser or Python installation required)

QUICK START:
1. Extract the ENTIRE ZIP, or run EvilRLBot-Windows-Setup.exe.
2. Launch EvilRLBot.exe. Do not run the EXE inside the ZIP without extracting.
3. Have Rocket League installed through Epic Games or Steam on this PC.
4. Import a complete RLBot V4/V5 bot ZIP, 7z, RAR, folder, CFG or TOML.
5. Drag bots onto Blue/Orange team panels and press Start Match.
6. If bot dependencies are missing, install them with the prompt once.
   Existing compatible host Python / PyTorch is used first, no download.

Data such as bot imports and Python dependencies are stored in:
%LOCALAPPDATA%\\EvilRLBot\\
They are separate from the installed program and survive upgrades.

V4 and V5 frameworks are kept separate; host Python/torch is reused when
compatible, otherwise the bundled Python runtimes remain a fallback.
They communicate over an authenticated LOCALHOST port; no external network
services are exposed by this bridge.

If startup fails, launch EvilRLBot-Debug.cmd and use Menu > Export Diagnostics.
Installation does not include Rocket League files, Epic/Steam accounts, models,
or user bots.

A model-only .lt/.pt/.onnx file cannot act as a bot without its matching runner.
Third-party bots may require additional compatible Python libraries.

This is an unsigned community application. Windows may show a SmartScreen
warning, and the app may need a trust decision. Verify the source before
running third-party bot packages.

Windows 10/11 x64, recent graphics driver and Rocket League required.
"""
(output/"README-WINDOWS.txt").write_text(readme,encoding="utf8")
dist=root/"dist"
dist.mkdir(exist_ok=True)
archive=dist/"EvilRLBot-Windows-x64-Portable.zip"
with ZipFile(archive,"w",ZIP_DEFLATED,compresslevel=7,allowZip64=True) as z:
    for f in sorted(output.rglob("*")):
        if f.is_file():
            z.write(f,arcname=Path("EvilRLBot")/f.relative_to(output))
checksum=sha256(archive.read_bytes()).hexdigest()
print("PORTABLE_ZIP",archive,archive.stat().st_size,checksum)
print("RELEASE_FILES",sum(p.is_file() for p in output.rglob("*")))
print("RELEASE_ROOT",output)
