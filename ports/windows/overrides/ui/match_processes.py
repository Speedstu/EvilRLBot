"""Restrict match cleanup to processes started by this Evil RLBot installation.

Never terminate RocketLeague.exe. Its process is frequently parented to an
older RLBotServer instance, and killing a whole process tree would close it.
"""
from __future__ import annotations

from pathlib import Path
import os
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT).casefold().replace("/", "\\")
GENERATED = str(Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
                / "EvilRLBot" / "generated" / "ui").casefold().replace("/", "\\")


def _norm(s: str) -> str:
    return str(s or "").strip('"').casefold().replace("/", "\\")


def _ours(proc: psutil.Process) -> bool:
    """Match full paths, not process names or unrelated Python sessions."""
    try:
        name = proc.name().casefold()
        args = [_norm(a) for a in proc.cmdline()]
        exe = _norm(proc.exe())
        # Only our server binary, not other RLBot installations.
        if name == "rlbotserver.exe":
            return exe == APP + "\\rlbotserver.exe"
        if name in ("python.exe", "pythonw.exe"):
            return any(a in {
                APP + "\\run.py", APP + "\\src\\v5_bridge.py",
                APP + "\\v4_runtime\\worker.py",
            } for a in args[1:])
        if name == "cmd.exe":
            # Match only generated wrapper scripts or the exact server binary.
            return any(GENERATED + "\\" in a and "\\run_v5.cmd" in a
                       or GENERATED + "\\" in a and "\\run.cmd" in a
                       or APP + "\\rlbotserver.exe" in a
                       for a in args[1:])
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess, OSError):
        return False
    return False


def owned_processes() -> list[psutil.Process]:
    return [p for p in psutil.process_iter()
            if p.pid != os.getpid() and _ours(p)]


def stop_owned_processes(timeout: float = 4.0) -> dict:
    """Stop only app-owned runtimes, bridges, worker processes and cmd wrappers.

    Never use Windows taskkill /T here. Rocket League can be a child of
    RLBotServer and must remain open when restarting matches.
    """
    candidates = owned_processes()
    if not candidates:
        return {"stopped": 0, "survivors": []}
    # Stop bot workers/bridges before the server; game process is untouched.
    def priority(p):
        try:
            args = " ".join(p.cmdline()).casefold()
            name = p.name().casefold()
            if "worker.py" in args or "v5_bridge.py" in args: return 0
            if name == "cmd.exe": return 1
            if name == "rlbotserver.exe": return 2
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
        return 3
    candidates.sort(key=priority)
    for p in candidates:
        try: p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    _, alive = psutil.wait_procs(candidates, timeout=timeout)
    for p in alive:
        try: p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    _, alive = psutil.wait_procs(alive, timeout=1.5)
    return {"stopped": len(candidates) - len(alive),
            "survivors": [p.pid for p in alive if p.is_running()]}
