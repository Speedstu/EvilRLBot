"""Read-only readiness checks for the user-owned Rocket League installation.

These checks don't bypass the game launcher. An offline/local match can still
require the launcher to initialize Epic Online Services before the menu opens.
"""
from __future__ import annotations

import os
from pathlib import Path
from ui.offline_launcher import installation

HOME = Path.home()
GAME = HOME / "Games" / "RocketLeagueOffline"
GAME_EXE = GAME / "Binaries" / "Win64" / "RocketLeague.exe"
PROTON = HOME / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic" / "tools" / "proton" / "Proton-CachyOS-latest" / "proton"
LOG = HOME / "Games" / "RocketLeaguePrefixGE" / "pfx" / "drive_c" / "users" / "steamuser" / "Documents" / "My Games" / "Rocket League" / "TAGame" / "Logs" / "Launch.log"


def inspect_game() -> dict:
    """Report the local copy and the most recent actual game startup failure."""
    info = installation()
    status = {
        "game_path": str(GAME),
        "copied_executable": (info["game"] / "Binaries/Win64/RocketLeague.exe").is_file(),
        "game_data": (info["game"] / "TAGame" / "CookedPCConsole").is_dir(),
        "proton_available": info["wine"].is_file(),
        "eos_launcher_error": False,
        "gameplay_verified": False,
    }
    if LOG.is_file():
        try:
            # Bounded read, never report account IDs, login tokens or private logs.
            with LOG.open("rb") as f:
                f.seek(max(0, LOG.stat().st_size - 65536))
                tail = f.read().decode("utf-8", "replace")
            status["eos_launcher_error"] = (
                "Failed to init online subsytem" in tail
                or "Failed to init online subsystem" in tail
                or "failed to init LauncherCheck" in tail
            )
        except OSError:
            pass
    return status


def explain_game_status() -> str:
    info = inspect_game()
    if not info["copied_executable"] or not info["game_data"]:
        return "Rocket League is not fully installed on the Omen."
    if not info["proton_available"]:
        return "Rocket League files found; install/select Proton to launch."
    if info["eos_launcher_error"]:
        return "Game + Proton ready. Use Legendary Offline / RLBot for local matches; online Epic launch previously failed EOS."
    return "Game files and Proton found. Real in-game match has not been verified yet."
