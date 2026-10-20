#!/usr/bin/env python3
"""Assemble the Windows source tree from the shared code and Windows overlays.

This produces source only. Vendored Python runtimes and the RLBotServer binary
are deliberately not stored in Git. They are supplied by the release build.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import shutil

ROOT = Path(__file__).resolve().parents[1]

def ignored(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in {
        ".git", "__pycache__", "frameworks", "build", "dist", "runtime",
        ".venv", ".venv-v4", ".generated", "logs", ".references"
    } or name.endswith((".pyc", ".pyo", ".bak")) or ".bak" in name}

def assemble(target: Path) -> None:
    if target.resolve() == ROOT.resolve() or ROOT.resolve() in target.resolve().parents:
        # Build output inside the tree is fine, but never replace its root.
        if target.resolve() == ROOT.resolve():
            raise ValueError("refusing to overwrite repository root")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for folder in ("ui", "src", "common", "v4_runtime", "legacy_bot", "tools"):
        shutil.copytree(ROOT / folder, target / folder, ignore=ignored)
    shutil.copytree(ROOT / "packaging/windows", target / "packaging/windows", ignore=ignored)
    for name in ("run.py", "rlbot.toml", "requirements.txt", "requirements-ui.txt",
                 "requirements-v4.txt", "LICENSE"):
        shutil.copy2(ROOT / name, target / name)
    overlay = ROOT / "ports/windows/overrides"
    for source in sorted(overlay.rglob("*")):
        if source.is_file():
            dest = target / source.relative_to(overlay)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    print(f"Windows sources: {target}")
    print("Runtime, launcher executable and RLBotServer: not included")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/windows-source")
    args = parser.parse_args()
    assemble(args.output)
