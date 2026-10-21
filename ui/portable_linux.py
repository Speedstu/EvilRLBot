"""Portable launch commands for native RLBot v5 agents on Linux.

The v5 engine already supports launching Windows-only binaries under Wine.
Do not prevent that behaviour by inserting our own Linux shell wrapper.

For Python bot packs, replace a Windows Python executable with the
ABI-compatible Linux interpreter chosen by Evil RLBot.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path, PureWindowsPath

_PYTHON = re.compile(r"(?i)^(?:python(?:w|3(?:\.\d+)?)?|py)(?:\.exe)?$")
_OPTIONS = {"-u", "-B", "-E", "-s", "-S", "-O", "-OO"}


def _windows_args(command: str) -> list[str]:
    tokens = shlex.split(command, posix=False)
    return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] == '"' else t
            for t in tokens]


def _root_dir(config: Path, value: object) -> Path:
    base = config.parent.resolve()
    raw = str(value or "").strip()
    if not raw or raw == ".":
        return base
    if PureWindowsPath(raw).is_absolute():
        return base
    return (base / raw.replace("\\", "/")).resolve()


def classify(command: str) -> str:
    """python, windows-binary, or native-shell."""
    try:
        args = _windows_args(command)
    except ValueError:
        raise ValueError("Malformed bot run_command quotation") from None
    if not args:
        raise ValueError("Bot has no run command")
    program = PureWindowsPath(args[0]).name.lower()
    if _PYTHON.fullmatch(program):
        return "python"
    if program.endswith((".exe", ".bat", ".cmd")):
        return "windows-binary"
    return "native-shell"


def python_command(command: str, interpreter: Path, config: Path, root: Path) -> str:
    if classify(command) != "python":
        raise ValueError("Not a Python launch command")
    args = _windows_args(command)
    pos = 1
    if PureWindowsPath(args[0]).name.lower() in {"py", "py.exe"}:
        if pos < len(args) and re.fullmatch(r"-3(?:\.\d+)?", args[pos]):
            pos += 1
    flags = []
    while pos < len(args) and args[pos] in _OPTIONS:
        flags.append(args[pos])
        pos += 1
    if pos >= len(args):
        raise ValueError(f"No Python entrypoint in {config.name} run_command")
    if args[pos] == "-m":
        if len(args) <= pos + 1:
            raise ValueError("Python -m requires a module name")
        return shlex.join([str(interpreter), *flags, "-m", *args[pos + 1:]])
    script = args[pos].replace("\\", "/")
    candidate = (root / script).resolve()
    if not candidate.is_file():
        source = Path(script)
        matches = list(config.parent.rglob(source.name))[:3]
        matches = [p for p in matches if p.is_file() and "site-packages" not in p.parts]
        if len(matches) == 1:
            candidate = matches[0].resolve()
    if not candidate.is_file() or not candidate.is_relative_to(config.parent.resolve()):
        raise ValueError(
            f"Python entrypoint {args[pos]!r} is not present in the imported "
            f"bot. Ask its author for Linux-compatible bot files."
        )
    return shlex.join([str(interpreter), *flags, str(candidate), *args[pos + 1:]])


def select_command(settings: dict, config: Path, interpreter: Path):
    """Return command, working directory and whether Linux wrapper is required."""
    root = _root_dir(config, settings.get("root_dir"))
    linux = str(settings.get("run_command_linux") or "").strip()
    raw = str(settings.get("run_command") or settings.get("run_command_windows") or "").strip()
    if linux:
        return linux, root, True
    mode = classify(raw)
    if mode == "windows-binary":
        return raw, root, False
    if mode == "python":
        return python_command(raw, interpreter, config, root), root, True
    return raw, root, True

def configure_wine_for_match(match_config: Path) -> bool:
    """Expose Heroic's existing Wine binary to RLBotServer when needed.

    RLBot v5 supports Wine fallback for a run_command without
    run_command_linux. Fedora users often only have Wine under Heroic's
    Proton tools, outside their shell PATH. Do not alter the user's machine
    environment, create a prefix, or download Wine.
    """
    import os
    import shutil
    import tomllib

    try:
        with Path(match_config).open("rb") as handle:
            match = tomllib.load(handle)
    except (FileNotFoundError, ValueError, OSError):
        return False
    needs_wine = False
    for car in match.get("cars", []):
        config_file = car.get("config_file")
        if not config_file:
            continue
        botfile = Path(config_file)
        if not botfile.is_absolute():
            botfile = Path(match_config).parent / botfile
        if botfile.suffix.lower() != ".toml" or not botfile.is_file():
            continue
        try:
            with botfile.open("rb") as handle:
                settings = tomllib.load(handle).get("settings") or {}
            cmd = str(settings.get("run_command") or "")
            if not settings.get("run_command_linux") and classify(cmd) == "windows-binary":
                needs_wine = True
                break
        except (ValueError, OSError, TypeError):
            continue
    if not needs_wine:
        return False
    from ui.offline_launcher import installation
    config = installation()
    wine = config["wine"]
    if wine.is_file():
        wine_directory = str(wine.parent)
        existing = os.environ.get("PATH", "")
        if wine_directory not in existing.split(os.pathsep):
            os.environ["PATH"] = wine_directory + os.pathsep + existing
    elif shutil.which("wine") is None:
        raise RuntimeError(
            "This Windows-only bot requires Wine/Proton on Linux. "
            "Install a compatible Wine runner in Heroic or provide "
            "run_command_linux in its bot.toml."
        )
    prefix = config["prefix"]
    if prefix.is_dir():
        os.environ.setdefault("WINEPREFIX", str(prefix))
    return True
