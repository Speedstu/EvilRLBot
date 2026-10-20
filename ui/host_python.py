"""Find an already-working Python runtime for a bot without installing packages.

Framework V4/V5 must be selected independently: an installed V4 rlbot cannot
run a V5 agent. Python native wheels (e.g. torch) cannot cross ABI versions.
We probe the exact interpreter and dependency paths before choosing it.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Choice:
    python: Path
    framework_site: Path | None
    okay: bool
    error: str = ""


def bundled_python(framework: str) -> Path:
    if os.name == "nt":
        return ROOT / "runtime" / ("v4" if framework == "rlbot-v4" else "v5") / "python.exe"
    return ROOT / (".venv-v4" if framework == "rlbot-v4" else ".venv") / "bin" / "python"


def bundled_site(framework: str) -> Path | None:
    # Only the RLBot framework and its pure-Python support modules.
    # NEVER inject all of an embedded interpreter's site-packages into a
    # different Python: that can shadow typing, dataclasses, NumPy or DLLs.
    shim = ROOT / "common" / "frameworks" / ("v4" if framework == "rlbot-v4" else "v5")
    if (shim / "rlbot").is_dir():
        return shim
    base = bundled_python(framework)
    if os.name == "nt":
        site = base.parent / "Lib" / "site-packages"
        return site if site.is_dir() else None
    sites = sorted((base.parents[1] / "lib").glob("python*/site-packages"))
    return next((x for x in sites if x.is_dir()), None)


@lru_cache(maxsize=1)
def host_pythons() -> tuple[Path, ...]:
    """No global package modifications, shell activation or full disk scans."""
    paths: list[Path] = []
    def add(candidate):
        if candidate:
            p = Path(str(candidate).strip('"'))
            if p.is_file() and p not in paths:
                paths.append(p)
    for key in ("EVILRLBOT_HOST_PYTHON", "EVILRLBOT_PYTHON_V4", "EVILRLBOT_PYTHON_V5"):
        add(os.environ.get(key))
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        for p in sorted((local / "Programs" / "Python").glob("Python*/python.exe")):
            add(p)
        try:
            out = subprocess.run(["py", "-0p"], capture_output=True, text=True, timeout=4)
            for line in (out.stdout + out.stderr).splitlines():
                match = re.search(r"([A-Za-z]:\\[^\r\n]*?python(?:w)?\.exe)", line, re.I)
                if match: add(match.group(1).strip())
        except (OSError, subprocess.TimeoutExpired):
            pass
        for exe in ("python.exe",):
            add(shutil.which(exe))
    else:
        for name in ("python3.12", "python3.11", "python3.13", "python3", "python"):
            add(shutil.which(name))
        home = Path.home()
        # Only likely venv locations, bounded depth. Reuse existing PyTorch
        # from projects instead of creating a new multi-GB installation.
        for pattern in ("Projects/*/.venv*/bin/python",
                        "Projects/*/*/.venv*/bin/python",
                        ".virtualenvs/*/bin/python", ".local/share/virtualenvs/*/bin/python",
                        ".venvs/*/bin/python"):
            for p in sorted(home.glob(pattern))[:35]:
                add(p)
    # Preserve virtualenv symlinks: their site-packages are independent.
    embedded = {str(bundled_python(f).absolute()) for f in ("rlbot-v4", "rlbot-v5")}
    return tuple(p for p in paths if str(p.absolute()) not in embedded)


def _probe(python: Path, framework: str, modules: tuple[str, ...],
           specs: tuple[str, ...], dependency_path: Path | None,
           torch_layer: Path | None, site: Path | None) -> tuple[bool, str]:
    if not python.is_file():
        return False, f"Python not found: {python}"
    # Build the import path in the child process: -I on embedded Python
    # protects its RLBot framework from unintended user PYTHONPATH.
    script = """
import sys,importlib
from importlib.metadata import version
from packaging.requirements import Requirement
if APPROOT not in sys.path: sys.path.insert(0, APPROOT)
# V5 framework overlay has priority over the host's V4 rlbot distribution.
for loc in reversed(P):
    if loc and loc not in sys.path: sys.path.insert(0,loc)
import rlbot
if F == 'rlbot-v4':
    from rlbot.agents.base_agent import BaseAgent
    # The real worker has more imports than BaseAgent alone; catch missing
    # transitive packages before announcing the bot as launch-ready.
    importlib.import_module('v4_runtime.worker')
else:
    from rlbot.managers import Bot
for module in M: importlib.import_module(module)
for item in R:
    req=Requirement(item)
    actual=version(req.name)
    if req.specifier and actual not in req.specifier:
        raise RuntimeError(f'{req.name} {actual} does not satisfy {req.specifier}')
"""
    paths = [str(x) for x in (site, dependency_path, torch_layer) if x and x.is_dir()]
    # Leave the chosen framework path ahead of bot-specific packages.
    args = [str(python)]
    if python.resolve() == bundled_python(framework).resolve():
        args.append("-I")
    data = ("F=" + repr(framework) + "\nAPPROOT=" + repr(str(ROOT)) + "\nP=" + repr(paths) +
            "\nM=" + repr(modules) + "\nR=" + repr(specs) + "\n" + script)
    try:
        res = subprocess.run(args + ["-c", data], capture_output=True,
                             text=True, timeout=21,
                             env={**os.environ, "PYTHONPATH": ""})
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, str(err)
    if res.returncode:
        return False, (res.stderr or res.stdout).strip()[-370:] or f"exit {res.returncode}"
    return True, ""


@lru_cache(maxsize=256)
def select_python(framework: str, modules: tuple[str, ...] = (),
                  specs: tuple[str, ...] = (), deps: str = "",
                  torch_dir: str = "") -> Choice:
    """Prioritize a working host interpreter, fall back to bundled Python.

    A framework-only overlay is allowed when host Python already has the
    numeric/ML wheels, but its installed rlbot is of the other major version.
    """
    if framework not in ("rlbot-v4", "rlbot-v5"):
        raise ValueError(framework)
    dep = Path(deps) if deps else None
    torch = Path(torch_dir) if torch_dir else None
    site = bundled_site(framework)
    best_error = ""
    for host in host_pythons():
        for framework_path in (None, site):
            if framework_path and not framework_path.is_dir():
                continue
            ok, reason = _probe(host, framework, modules, specs, dep, torch, framework_path)
            if ok:
                return Choice(host, framework_path, True)
            best_error = reason or best_error
    embedded = bundled_python(framework)
    ok, reason = _probe(embedded, framework, modules, specs, dep, torch, None)
    return Choice(embedded, None, ok, reason or best_error)
