"""Read-only checks before launching a match; never executes third-party bot code.

A bot with missing dependencies must not lead to a spectator-only empty match.
V4 and V5 dependencies are resolved against their appropriate Python runtime
and per-bot installed package directory, including AppImage portable envs.
"""
from __future__ import annotations
import ast
import configparser
import hashlib
import json
import tomllib
import os
import subprocess
import sys
from pathlib import Path

from ui.bot_importer import dependency_path, discover, _mentions_torch

ROOT = Path(__file__).resolve().parents[1]
NAMES = {
    "pytorch": "torch", "torch": "torch", "torchvision": "torchvision",
    "torchaudio": "torchaudio", "numpy": "numpy", "onnxruntime": "onnxruntime",
    "scipy": "scipy", "rlgym": "rlgym", "pyyaml": "yaml",
}
# Names from user requirements files, not runtime package imports.
def _requirements_modules(requirements: Path) -> list[str]:
    from packaging.requirements import Requirement
    result = []
    for line in requirements.read_text(encoding="utf8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-")) or line.startswith(("git+", "http://", "https://")):
            continue
        try:
            req = Requirement(line)
            if req.marker is not None and not req.marker.evaluate():
                continue
            normalized = req.name.lower().replace("_", "-")
            module = NAMES.get(normalized, normalized.replace("-", "_"))
            # Only safe-to-resolve import names; custom distributions may map
            # to completely different Python import names.
            if normalized in NAMES and module not in result:
                result.append(module)
        except Exception:
            continue
    return result


def _bot_python_sources(config: Path, framework: str) -> list[Path]:
    """Find local source code without executing arbitrary third-party bots."""
    paths = []
    directory = config.parent.resolve()
    if config.suffix.lower() == ".py":
        paths.append(config)
    elif framework == "rlbot-v4" and config.suffix.lower() == ".cfg":
        cfg = configparser.RawConfigParser()
        cfg.read(config, encoding="utf-8")
        if cfg.has_option("Locations", "python_file"):
            paths.append((directory / cfg.get("Locations", "python_file").strip().strip('"')).resolve())
    elif config.suffix.lower() == ".toml":
        try:
            with config.open("rb") as f:
                settings = tomllib.load(f).get("settings", {})
            # V5 entrypoint may be an arbitrary shell command; scanning all local
            # source files is more reliable and avoids interpreting shell text.
        except (OSError, ValueError, TypeError):
            pass
    # Scan local modules too, for models imported via "from agent import ...".
    # Bounds prevent scanning entire large codebases or virtual environments.
    for p in directory.rglob("*.py"):
        if p.is_relative_to(directory) and len(p.relative_to(directory).parts) <= 4:
            if not any(t in {".git", "venv", ".venv", ".venv-v4", "__pycache__", "site-packages", "node_modules"} for t in p.parts):
                paths.append(p.resolve())
        if len(paths) >= 85:
            break
    return list(dict.fromkeys(p for p in paths if p.is_file() and p.is_relative_to(directory)))[:85]


def _static_modules(config: Path, framework: str) -> list[str]:
    """Safely detect common mandatory runtime imports even without requirements.txt."""
    found = set()
    for python_file in _bot_python_sources(config, framework):
        try:
            if python_file.stat().st_size > 450_000:
                continue
            tree = ast.parse(python_file.read_text(encoding="utf8", errors="replace"))
        except (OSError, SyntaxError, UnicodeError, ValueError):
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [x.name.split(".", 1)[0] for x in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".", 1)[0]]
            for name in names:
                if name in NAMES.values():
                    found.add(name)
    return sorted(found)


def _required_modules(config: Path, candidate) -> list[str]:
    modules = set(_static_modules(config, candidate.framework))
    if candidate.requirements and candidate.requirements.is_file():
        modules.update(_requirements_modules(candidate.requirements))
    return sorted(modules)


def suggested_requirements(config: Path, candidate) -> Path | None:
    """Produce an explicit approval list without ever modifying a bot pack.

    If the pack forgot to declare torch (or other imported packages), append
    missing imports only for a simple requirements file. This avoids endless
    'installed dependencies but torch still missing' loops.
    """
    from ui import bot_importer
    original = candidate.requirements
    if original and original.is_file():
        original_text = original.read_text(encoding="utf8", errors="replace")
        # Complex pip -r/-e links have cwd-relative semantics. Preserve their
        # paths and don't silently rewrite them into generated manifests.
        _, _, ordinary = bot_importer._torch_specs(original)
        if not ordinary:
            return original
        declared = set(_requirements_modules(original))
    else:
        original_text = ""
        declared = set()
    modules = set(_static_modules(config, candidate.framework)) - declared
    if candidate.framework == "rlbot-v4":
        modules.discard("numpy")  # Bundled NumPy v1.26
    names = sorted({name for name, module in NAMES.items()
                    if module in modules and name == module})
    if "yaml" in modules:
        names.append("PyYAML")
    names = sorted(set(names))
    if not names:
        return original if original and original.is_file() else None
    directory = bot_importer.MANIFEST_DIR
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(str(config.resolve()).encode()).hexdigest()[:18]
    dest = directory / (key + ".txt")
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(
        "# Reviewed package source: bot requirements plus detected imports.\n"
        + original_text.rstrip() + "\n"
        + "\n".join(names) + "\n",
        encoding="utf8"
    )
    tmp.chmod(0o600)
    tmp.replace(dest)
    return dest


def _requirement_specs(path: Path | None) -> list[str]:
    if not path or not path.is_file():
        return []
    from packaging.requirements import Requirement
    result = []
    for raw in path.read_text(encoding="utf8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(("-", "http:", "https:", "git+")):
            continue
        try:
            parsed = Requirement(line)
            if parsed.url is None and not (parsed.marker and not parsed.marker.evaluate()):
                result.append(line)
        except Exception:
            continue
    return result



def _python_check(framework: str, deps: Path, modules: list[str], config_path: Path | None = None,
                  requirements: Path | None = None) -> tuple[bool, str]:
    """Probe host Python first, including its real installed torch wheels.

    RLBot V4 and V5 are validated separately. A Python 3.11 torch wheel is
    never injected into the bundled Python 3.12 interpreter.
    """
    from ui.host_python import select_python
    from ui.bot_importer import usable_torch_path
    torch = usable_torch_path(config_path)
    runtime = select_python(
        framework, tuple(sorted(modules)), tuple(_requirement_specs(requirements)),
        str(deps) if deps.is_dir() else "", str(torch) if torch else ""
    )
    return runtime.okay, runtime.error


def dependencies_ready(config: Path, candidate) -> bool:
    """A repeated import/match must never trigger downloads when imports work.

    The selected V4/V5 runtime may reuse an already-working host Python;
    no dependency download is required when imports and versions pass.
    """
    modules = _required_modules(config, candidate)
    if modules or _requirement_specs(candidate.requirements):
        return _python_check(candidate.framework, dependency_path(config),
                             modules, config, candidate.requirements)[0]
    return True


def check_bots(setup: dict, paths: dict[str, str]) -> list[str]:
    problems = []
    seen = set()
    for player in setup.get("players", []):
        if player.get("kind") != "bot":
            continue
        path = Path(paths[player["id"]]).expanduser().resolve()
        if path in seen:
            continue
        seen.add(path)
        candidates = discover(path)
        if not candidates:
            problems.append(f"{path.name}: no valid runnable V4/V5 config found.")
            continue
        candidate = next((x for x in candidates if x.path == path), candidates[0])
        if candidate.warning:
            problems.append(f"{candidate.name}: {candidate.warning}")
            continue
        # Frozen Windows bots are standalone executables. They don't require
        # Linux Python packages; RLBotServer can start them using Wine.
        if candidate.framework == "rlbot-v5" and path.suffix.lower() == ".toml":
            try:
                from ui.portable_linux import classify
                with path.open("rb") as handle:
                    cfg = tomllib.load(handle).get("settings") or {}
                if not cfg.get("run_command_linux") and classify(
                        str(cfg.get("run_command") or cfg.get("run_command_windows") or "")) == "windows-binary":
                    continue
            except (OSError, ValueError, TypeError):
                pass
        modules = _required_modules(path, candidate)
        if not modules and not _requirement_specs(candidate.requirements):
            continue
        deps = dependency_path(path)
        ok, cause = _python_check(candidate.framework, deps, modules, path, candidate.requirements)
        if not ok:
            source = candidate.requirements or "static imports (no requirements.txt)"
            problems.append(
                f"{candidate.name} ({candidate.framework}): {cause}\n"
                f"Dependency source: {source}\n"
                "Use Menu → Install bot dependencies… and retry Start Match."
            )
    return problems
