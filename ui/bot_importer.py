"""Local bot import service for Evil RLBot.

Drag files, directories, or archives into the native UI. Detection is static:
importing never executes a bot. Installing dependencies and running a bot are
separate explicitly approved operations.
"""
from __future__ import annotations

import ast
import configparser
import codecs
import collections
import selectors
import signal
import time
import typing
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tomllib
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER_DIR = Path.home() / ".local/share/evilrlbot/bots"
DEPS_DIR = Path.home() / ".local/share/evilrlbot/dependencies"
MANIFEST_DIR = Path.home() / ".local/share/evilrlbot/generated-requirements"
# One persistent Torch installation shared by compatible bots, across matches,
# independently of appimage-v... upgrades. CPU/CUDA are separate.
TORCH_ROOT = DEPS_DIR / ".torch-runtime"
TORCH_NAMES = frozenset({"torch", "torchvision", "torchaudio"})
TORCH_CHOICES = DEPS_DIR / ".torch-choice"
SKIP = {".git", ".venv", ".venv-v4", "venv", "env", "node_modules", "__pycache__", "build", "dist"}
ARCHIVES = (".zip", ".7z", ".rar", ".tar.gz", ".tgz", ".tar")
MAX_FILES = 20000
MAX_ARCHIVE_TOTAL = 8 * (1024 ** 3)  # refuse oversized or zip-bomb archives
MAX_BOT_CONFIGS = 150


@dataclass(frozen=True)
class Candidate:
    path: Path
    framework: str
    name: str
    requirements: Path | None = None
    warning: str = ""


def archive_suffix(path: Path) -> bool:
    return path.name.lower().endswith(ARCHIVES)


def _is_inside(root: Path, child: Path) -> bool:
    return child.resolve().is_relative_to(root.resolve())


def _archive_output(source: Path) -> Path:
    USER_DIR.mkdir(parents=True, exist_ok=True)
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", source.name.rsplit(".", 1)[0]).strip("-")[:55] or "bot"
    # The same package dragged twice should reuse its extracted directory and
    # its existing library entry, not create duplicate bots every time.
    with source.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()[:15]
    return USER_DIR / f"{clean}-{digest}"


def _safe_members(members):
    total = count = 0
    for name, size, kind in members:
        p = Path(name.replace("\\", "/"))
        if p.is_absolute() or ".." in p.parts or "\x00" in name or not p.parts:
            raise ValueError("Archive contains unsafe paths")
        count += 1
        total += size
        if count > MAX_FILES or total > MAX_ARCHIVE_TOTAL:
            raise ValueError("Archive too large to import safely")
        if kind not in {"file", "directory"}:
            raise ValueError("Archive contains an unsupported link or special file")


def extract_archive(source: Path) -> Path:
    """Extract safely and atomically. Never overwrite an existing import."""
    source = source.expanduser().resolve()
    if not source.is_file() or not archive_suffix(source):
        raise ValueError("Choose a .zip, .7z, .rar, .tar or .tar.gz bot archive")
    dest = _archive_output(source)
    if dest.is_symlink():
        raise ValueError("Unsafe cached archive destination")
    if dest.is_dir():
        return dest
    work = dest.with_name(dest.name + ".partial-" + uuid.uuid4().hex[:8])
    work.mkdir(parents=True, exist_ok=False)
    try:
        if source.name.lower().endswith(".zip"):
            with zipfile.ZipFile(source) as z:
                entries = [(x.filename, x.file_size,
                            "directory" if x.is_dir() else
                            "link" if stat.S_IFMT((x.external_attr >> 16) & 0xffff) == stat.S_IFLNK else "file")
                           for x in z.infolist()]
                _safe_members(entries)
                for info in z.infolist():
                    output = work / info.filename
                    if not _is_inside(work, output):
                        raise ValueError("Unsafe archive entry")
                    if info.is_dir():
                        output.mkdir(parents=True, exist_ok=True)
                    else:
                        output.parent.mkdir(parents=True, exist_ok=True)
                        with z.open(info) as inp, output.open("wb") as out:
                            shutil.copyfileobj(inp, out, length=1024 * 1024)
                        if (info.external_attr >> 16) & stat.S_IXUSR:
                            output.chmod(output.stat().st_mode | stat.S_IXUSR)
        elif source.name.lower().endswith(".rar"):
            try:
                import libarchive
            except ImportError as e:
                raise ValueError("RAR support unavailable (libarchive-c required).") from e
            # RAR5 support is provided by the local libarchive library. Never
            # delegate to external commands or trust paths from the archive.
            with libarchive.file_reader(str(source)) as entries:
                total = count = 0
                for member in entries:
                    kind = "directory" if member.filetype == stat.S_IFDIR else (
                        "file" if member.filetype == stat.S_IFREG else "link")
                    _safe_members([(member.pathname, max(0, member.size), kind)])
                    count += 1
                    total += max(0, member.size)
                    if count > MAX_FILES or total > MAX_ARCHIVE_TOTAL:
                        raise ValueError("Archive too large to import safely")
                    output = work / member.pathname.replace("\\", "/")
                    if not _is_inside(work, output):
                        raise ValueError("Unsafe archive entry")
                    if kind == "directory":
                        output.mkdir(parents=True, exist_ok=True)
                    else:
                        output.parent.mkdir(parents=True, exist_ok=True)
                        with output.open("xb") as dest_file:
                            actual_size = 0
                            for block in member.get_blocks():
                                actual_size += len(block)
                                if actual_size > max(member.size, 0) or actual_size > MAX_ARCHIVE_TOTAL:
                                    raise ValueError("Decompressed file exceeds declared archive size")
                                dest_file.write(block)
                        if output.suffix.lower() in (".sh", ".bash"):
                            output.chmod(output.stat().st_mode | stat.S_IXUSR)
        elif source.name.lower().endswith(".7z"):
            try:
                import py7zr
            except ImportError as e:
                raise ValueError("7z support unavailable. Install py7zr in the Evil RLBot environment.") from e
            with py7zr.SevenZipFile(source) as z:
                entries = [(x.filename, int(getattr(x, "uncompressed", 0) or 0),
                            "directory" if getattr(x, "is_directory", False) else "file")
                           for x in z.list()]
                _safe_members(entries)
                names = z.getnames()
                for name in names:
                    if not _is_inside(work, work / name):
                        raise ValueError("Unsafe archive entry")
                z.extractall(path=work)
                # Refuse symlinks produced by any archive format.
                for p in work.rglob("*"):
                    if p.is_symlink():
                        raise ValueError("Archive contains an unsafe symbolic link")
                    if p.is_file() and p.suffix.lower() in (".sh", ".bash"):
                        p.chmod(p.stat().st_mode | stat.S_IXUSR)
        else:
            with tarfile.open(source) as t:
                _safe_members([(x.name, x.size, "directory" if x.isdir() else
                                "file" if x.isfile() else "link") for x in t.getmembers()])
                for x in t.getmembers():
                    path = work / x.name
                    if not _is_inside(work, path):
                        raise ValueError("Unsafe archive entry")
                    if x.isdir():
                        path.mkdir(parents=True, exist_ok=True)
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        f = t.extractfile(x)
                        if f is None:
                            raise ValueError("Invalid archived file")
                        with f, path.open("wb") as out:
                            shutil.copyfileobj(f, out, length=1024 * 1024)
                        if x.mode & stat.S_IXUSR:
                            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        work.rename(dest)
        return dest
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise


def _v4_cfg(path: Path) -> Candidate | None:
    try:
        cp = configparser.RawConfigParser()
        cp.read(path, encoding="utf-8")
        if not cp.has_section("Locations") or not cp.has_option("Locations", "python_file"):
            return None
        source = cp.get("Locations", "python_file").strip().strip('"')
        python_file = (path.parent / source).resolve()
        req = cp.get("Locations", "requirements_file", fallback="").strip()
        req_file = (path.parent / req).resolve() if req else path.parent / "requirements.txt"
        if not req_file.is_file():
            req_file = None
        warn = "" if python_file.is_file() else "Declared Python entrypoint not found."
        return Candidate(path, "rlbot-v4", cp.get("Locations", "name", fallback=path.stem), req_file, warn)
    except (OSError, configparser.Error, ValueError):
        return None


def _v5_toml(path: Path) -> Candidate | None:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
        settings = data.get("settings")
        if not isinstance(settings, dict) or not any(k in settings for k in ("run_command", "run_command_linux", "agent_id")):
            return None
        runnable = settings.get("run_command_linux") or settings.get("run_command") or settings.get("run_command_windows")
        req = path.parent / "requirements.txt"
        name = str(settings.get("name") or path.parent.name)
        warn = "" if runnable else "No runnable command in bot.toml"
        # RLBot v5 already supports Windows executables through Wine when
        # run_command_linux is absent. The match builder must preserve that
        # fallback rather than rejecting this bot before the engine starts.
        return Candidate(path, "rlbot-v5", name, req if req.is_file() else None, warn)
    except (OSError, ValueError, TypeError):
        return None


def discover(path: Path) -> list[Candidate]:
    """Find independently runnable bot definitions, not whole-match files."""
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_file():
        if path.suffix.lower() == ".cfg":
            c = _v4_cfg(path)
            return [c] if c else []
        if path.suffix.lower() == ".toml":
            c = _v5_toml(path)
            return [c] if c else []
        if path.suffix.lower() == ".py":
            req = path.parent / "requirements.txt"
            if _standalone_v4_agent(path):
                return [Candidate(path, "rlbot-v4", path.stem,
                                  req if req.is_file() else None)]
            from common.detection import detect_bot
            d = detect_bot(path)
            if d["framework"] == "rlbot-v5":
                return [Candidate(path, "rlbot-v5", path.stem,
                                  req if req.is_file() else None)]
        return []
    result = []
    for current, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith("."))
        root = Path(current)
        for f in sorted(files):
            if f.lower().endswith(".cfg") and f.lower() != "rlbot.cfg":
                c = _v4_cfg(root / f)
            elif f.lower().endswith(".toml"):
                c = _v5_toml(root / f)
            else:
                continue
            if c:
                result.append(c)
                if len(result) >= MAX_BOT_CONFIGS:
                    raise ValueError("Too many bot configurations in one folder")
    if not result:
        # Some V4 packages ship only a Python BaseAgent runner, without a
        # bot.cfg. Inspect the source AST, never execute it during import.
        pyfiles = []
        for current, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith("."))
            if len(Path(current).relative_to(path).parts) > 5:
                dirs.clear()
                continue
            for name in files:
                if name.lower().endswith(".py"):
                    entry = Path(current) / name
                    if _standalone_v4_agent(entry):
                        pyfiles.append(entry)
            if len(pyfiles) >= 12:
                break
        for entry in pyfiles[:12]:
            req = entry.parent / "requirements.txt"
            package = entry.parent
            if package.name.lower() in {"src", "source", "python", "code", "bot"}:
                package = package.parent
            result.append(Candidate(entry, "rlbot-v4", package.name or entry.stem,
                                    req if req.is_file() else None))
    return result


def _standalone_v4_agent(file: Path) -> bool:
    try:
        if file.stat().st_size > 300_000:
            return False
        tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"))
        import_v4 = any(
            isinstance(node, ast.ImportFrom) and
            node.module and node.module.startswith("rlbot.agents")
            for node in ast.walk(tree)
        )
        has_agent = any(
            isinstance(node, ast.ClassDef) and any(
                (isinstance(base, ast.Name) and base.id == "BaseAgent") or
                (isinstance(base, ast.Attribute) and base.attr == "BaseAgent")
                for base in node.bases
            )
            for node in ast.walk(tree)
        )
        return import_v4 and has_agent
    except (OSError, SyntaxError, UnicodeError, ValueError):
        return False


def dependency_path(config_path: Path) -> Path:
    canonical = str(config_path.expanduser().resolve())
    return DEPS_DIR / hashlib.sha256(canonical.encode()).hexdigest()[:18]


def add_to_library(candidates: list[Candidate]) -> list[dict]:
    """Store paths. All candidates are from an archive import or an existing path."""
    from ui.server import _load_library, _save_json, LIBRARY_FILE
    library = _load_library()
    imported = []
    known = {str(Path(b["path"]).resolve()): b for b in library}
    for c in candidates:
        key = str(c.path.resolve())
        if key in known:
            imported.append({"id": known[key]["id"], "path": key, "name": c.name, "framework": c.framework,
                             "requirements": str(c.requirements) if c.requirements else "", "warning": c.warning, "new": False})
            continue
        item = {"id": uuid.uuid4().hex, "path": key, "favorite": False, "category": "Standard",
                "framework": c.framework, "display_name": c.name}
        library.append(item)
        known[key] = item
        imported.append({"id": item["id"], "path": key, "name": c.name, "framework": c.framework,
                         "requirements": str(c.requirements) if c.requirements else "", "warning": c.warning, "new": True})
    _save_json(LIBRARY_FILE, library)
    return imported


def import_path(path: Path) -> list[dict]:
    path = path.expanduser().resolve()
    staged = extract_archive(path) if path.is_file() and archive_suffix(path) else path
    candidates = discover(staged)
    if not candidates:
        models = [p for p in staged.rglob("*") if p.is_file() and
                  p.suffix.lower() in {".lt", ".pt", ".pth", ".onnx", ".jit"}] if staged.is_dir() else []
        if staged.is_file() and staged.suffix.lower() in {".lt", ".pt", ".pth", ".onnx", ".jit"}:
            models = [staged]
        if models:
            raise ValueError(
                f"Found {len(models)} model file(s), but no runnable RLBot bot. "
                "A .lt/.pt/.onnx model requires its matching BaseAgent Python runner "
                "or bot.cfg/bot.toml. Import the complete bot folder, not weights alone."
            )
        raise ValueError(
            "No RLBot V4/V5 bot configuration or BaseAgent entrypoint found. "
            "Drop the complete bot folder containing bot.cfg, bot.toml, "
            "or a Python BaseAgent class."
        )
    return add_to_library(candidates)


def _mentions_torch(requirements: Path) -> bool:
    """Detect ordinary PyTorch requirements without executing the requirements."""
    try:
        data = requirements.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(re.search(r"(?mi)^\s*(?:torch|torchvision|torchaudio)(?:\s*[\[<>=~!;]|\s*$)", data))


def _safe_progress_line(text: str) -> str:
    """Do not leak credentials embedded in a private package index URL."""
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    clean = re.sub(r"(https?://)[^\s/:@]+:[^\s@]+@", r"\1***:***@", clean)
    return clean.rstrip()[:320]


def _cache_key(requirements: Path, framework: str, backend: str) -> str | None:
    """Content-keyed cache for ordinary PyPI requirements, shared across bots.

    Never share editable/git/URL/local installs; they may depend on the source
    checkout or contain untracked files outside requirements.txt.
    """
    data = requirements.read_text(encoding="utf-8", errors="replace")
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or _ignorable_requirement(line):
            continue
        if line.startswith(("-", "git+", ".", "/", "https:", "http:")):
            return None
        if " @ " in line or "file:" in line:
            return None
    payload = (framework + "\n" + backend + "\n" + "python3.12" + "\n" + data).encode()
    return hashlib.sha256(payload).hexdigest()[:25]


def _use_cached_deps(config_path: Path, cached: Path, dest: Path) -> bool:
    """Atomically link a verified cache to the selected bot."""
    if not cached.is_dir() or not (cached / ".evilrlbot-complete").exists():
        return False
    # Check importability inside the exact isolated interpreter, not host pip.
    from ui.preflight import _required_modules, _python_check
    candidates = discover(config_path)
    chosen = next((c for c in candidates if c.path == config_path), None)
    if chosen:
        modules = _required_modules(config_path, chosen)
        if modules:
            usable, _ = _python_check(chosen.framework, cached, modules, config_path)
            if not usable:
                return False
    if dest.is_symlink() and dest.resolve() == cached.resolve():
        return True
    backup = dest.with_name(dest.name + "-previous-" + uuid.uuid4().hex[:8])
    previous = dest.exists() or dest.is_symlink()
    if previous:
        dest.rename(backup)
    try:
        dest.symlink_to(cached, target_is_directory=True)
    except BaseException:
        if previous:
            backup.rename(dest)
        raise
    if previous:
        if backup.is_dir() and not backup.is_symlink():
            shutil.rmtree(backup)
        else:
            backup.unlink(missing_ok=True)
    return True


def shared_torch_path(backend: str = "cpu") -> Path:
    if backend not in {"cpu", "cuda"}:
        raise ValueError("Invalid torch backend")
    return TORCH_ROOT / f"py312-{backend}"


def usable_torch_path(config_path: Path | None = None) -> Path | None:
    # Per-bot backend selection persists outside AppImage extraction.
    candidates = [shared_torch_path("cpu"), shared_torch_path("cuda")]
    if config_path is not None:
        choice = TORCH_CHOICES / hashlib.sha256(
            str(config_path.expanduser().resolve()).encode()
        ).hexdigest()[:18]
        if choice.is_file():
            backend = choice.read_text(encoding="utf8").strip()
            if backend in {"cpu", "cuda"}:
                candidates = [shared_torch_path(backend)]
    for path in candidates:
        if path.is_dir() and (path / ".evilrlbot-torch-complete").is_file():
            return path
    return None


def remember_torch_choice(config_path: Path, backend: str) -> None:
    TORCH_CHOICES.mkdir(parents=True, exist_ok=True)
    ident = hashlib.sha256(str(config_path.resolve()).encode()).hexdigest()[:18]
    tmp = TORCH_CHOICES / (ident + ".tmp")
    tmp.write_text(backend, encoding="utf8")
    tmp.replace(TORCH_CHOICES / ident)


PIP_TOOLS = frozenset({"pip", "setuptools", "wheel"})


def _ignorable_requirement(line: str) -> bool:
    """Lines from RLBot's standard requirements.txt template that are safe to skip.

    The template points pip at PyTorch's download page and asks to upgrade pip.
    Evil RLBot picks the CPU or CUDA PyTorch source itself and ships its own
    pip, so neither changes what gets installed.
    """
    lowered = line.lower()
    if lowered.startswith(("--find-links", "-f ", "--extra-index-url", "--index-url", "-i ")):
        return "download.pytorch.org" in lowered
    return lowered.replace("_", "-") in PIP_TOOLS


def _torch_specs(requirements: Path) -> tuple[list[str], list[str], bool]:
    """Split simple requirements; leave complex pip directives on legacy path.

    Avoid installing a private second Torch copy when another bot has a
    different requirements.txt. Unsupported URL/editable deps use the legacy
    isolated installer rather than silently skipping critical packages.
    """
    from packaging.requirements import Requirement
    torch, rest = [], []
    for raw in requirements.read_text(encoding="utf8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or _ignorable_requirement(line):
            continue
        if line.startswith(("-", ".", "/", "http:", "https:", "git+")):
            return [], [], False
        try:
            spec = Requirement(line)
        except Exception:
            return [], [], False
        if spec.url or spec.extras or (spec.marker and not spec.marker.evaluate()):
            if spec.marker and not spec.marker.evaluate():
                continue
            return [], [], False
        if spec.name.lower().replace("_", "-") in TORCH_NAMES:
            torch.append(line)
        else:
            rest.append(line)
    return torch, rest, True


def _shared_torch_satisfies(path: Path, requirements: list[str]) -> tuple[bool, str]:
    if not path.is_dir() or not (path / ".evilrlbot-torch-complete").exists():
        return False, "Shared PyTorch has not been installed yet"
    from importlib.metadata import distributions
    from packaging.requirements import Requirement
    versions = {d.metadata["Name"].lower().replace("_", "-"): d.version
                for d in distributions(path=[str(path)]) if d.metadata.get("Name")}
    for line in requirements:
        req = Requirement(line)
        actual = versions.get(req.name.lower().replace("_", "-"))
        if not actual or actual not in req.specifier:
            return False, f"{req.name} requirement {req.specifier} is incompatible with shared version {actual or 'missing'}"
    return True, ""


def _run_install_command(
    command: list[str], cwd: Path, log: Path, *,
    progress: typing.Callable[[str], None] | None = None,
    stop_requested: typing.Callable[[], bool] | None = None,
    timeout_seconds: int = 2700,
    extra_env: dict[str, str] | None = None,
) -> None:
    """Stream pip diagnostics while allowing cancellation; no wheel cache bloat."""
    process = None
    history = collections.deque(maxlen=32)
    try:
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf8") as out:
            env = {**os.environ, "PIP_NO_INPUT": "1",
                   "PIP_NO_CACHE_DIR": "1", "PYTHONUNBUFFERED": "1",
                   **(extra_env or {})}
            process = subprocess.Popen(
                command, cwd=cwd, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                start_new_session=True, bufsize=0
            )
            assert process.stdout is not None
            os.set_blocking(process.stdout.fileno(), False)
            with selectors.DefaultSelector() as sel:
                sel.register(process.stdout, selectors.EVENT_READ)
                decoder = codecs.getincrementaldecoder("utf8")("replace")
                pending = ""
                last_emit = 0.0
                start = time.monotonic()
                try:
                    while True:
                        if stop_requested and stop_requested():
                            raise InterruptedError("Package installation cancelled")
                        if time.monotonic() - start > timeout_seconds:
                            raise TimeoutError(
                                f"Dependency install exceeded {timeout_seconds//60} min. Log: {log}"
                            )
                        for key, _ in sel.select(timeout=.35):
                            block = os.read(key.fileobj.fileno(), 65536)
                            if block:
                                pending += decoder.decode(block)
                                lines = pending.split("\n")
                                pending = lines.pop()
                                for line in lines:
                                    sanitized = _safe_progress_line(line)
                                    out.write(sanitized + "\n")
                                    out.flush()
                                    if sanitized:
                                        history.append(sanitized)
                                    if progress and sanitized and time.monotonic() - last_emit > 1.1:
                                        progress(sanitized)
                                        last_emit = time.monotonic()
                            else:
                                sel.unregister(key.fileobj)
                        if process.poll() is not None and not sel.get_map():
                            break
                    if pending.strip():
                        out.write(_safe_progress_line(pending) + "\n")
                finally:
                    process.stdout.close()
        if process.returncode:
            raise RuntimeError(
                f"pip exited {process.returncode}. Log: {log}\n"
                + "\n".join(list(history)[-12:])
            )
    except BaseException:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=4)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                except ProcessLookupError:
                    pass
        raise


def _ensure_shared_torch(
    python: Path, requirements: list[str], backend: str,
    cwd: Path, log_dir: Path,
    progress: typing.Callable[[str], None] | None,
    stop_requested: typing.Callable[[], bool] | None,
    timeout_seconds: int,
) -> Path:
    import fcntl
    shared = shared_torch_path(backend)
    shared.parent.mkdir(parents=True, exist_ok=True)
    lock_file = shared.parent / (backend + ".install.lock")
    with lock_file.open("a+b") as lock:
        deadline = time.monotonic() + timeout_seconds
        while True:
            if stop_requested is not None and stop_requested():
                raise InterruptedError("Shared PyTorch install cancelled")
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise TimeoutError("Timed out waiting for another PyTorch installation.")
                time.sleep(.5)
        return _ensure_shared_torch_locked(
            python, requirements, backend, cwd, log_dir,
            progress, stop_requested, timeout_seconds
        )


def _ensure_shared_torch_locked(
    python: Path, requirements: list[str], backend: str,
    cwd: Path, log_dir: Path,
    progress: typing.Callable[[str], None] | None,
    stop_requested: typing.Callable[[], bool] | None,
    timeout_seconds: int,
) -> Path:
    shared = shared_torch_path(backend)
    okay, cause = _shared_torch_satisfies(shared, requirements)
    if okay:
        if progress:
            progress(f"Reusing the existing {backend.upper()} PyTorch installation.")
        return shared
    if shared.exists():
        raise RuntimeError(
            f"A different shared {backend.upper()} PyTorch version is installed. "
            f"{cause}. For incompatible bot versions, a separate environment is "
            "needed; do not automatically download a second multi-GB copy."
        )
    shared.parent.mkdir(parents=True, exist_ok=True)
    tmp = shared.with_name(shared.name + ".partial-" + uuid.uuid4().hex[:8])
    log = log_dir / ("shared-torch-" + backend + ".log")
    if progress:
        progress(f"Installing {backend.upper()} PyTorch ONCE for all compatible bots…")
    command = [
        str(python), "-m", "pip", "install",
        "--disable-pip-version-check", "--no-input", "--prefer-binary",
        "--progress-bar", "off", "--retries", "4", "--timeout", "35",
        "--target", str(tmp)
    ]
    if backend == "cpu":
        command += ["--index-url", "https://download.pytorch.org/whl/cpu",
                    "--extra-index-url", "https://pypi.org/simple"]
    command += requirements
    try:
        _run_install_command(
            command, cwd, log, progress=progress,
            stop_requested=stop_requested, timeout_seconds=timeout_seconds
        )
        # Atomic completion marker: a crash never makes a half-installed Torch
        # look reusable on the next AppImage launch.
        (tmp / ".evilrlbot-torch-complete").write_text(backend + "\n")
        ok, cause = _shared_torch_satisfies(tmp, requirements)
        if not ok:
            raise RuntimeError(f"PyTorch package validation failed: {cause}")
        if shared.exists():
            raise RuntimeError("Another PyTorch installation completed concurrently. Retry import.")
        tmp.rename(shared)
        return shared
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def install_dependencies(
    config_path: Path,
    requirements: Path,
    framework: str,
    *,
    torch_backend: str = "cpu",
    progress: typing.Callable[[str], None] | None = None,
    stop_requested: typing.Callable[[], bool] | None = None,
    timeout_seconds: int = 2700,
) -> str:
    """Install third-party bot dependencies into an isolated, atomic target.

    By default a torch bot uses the smaller CPU wheels. A user may opt into
    larger NVIDIA CUDA wheels. Never bundle ML dependencies into the app.
    Only runs after explicit user approval, because pip may execute code.
    """
    if framework not in {"rlbot-v4", "rlbot-v5"}:
        raise ValueError(f"Unsupported RLBot framework: {framework}")
    if torch_backend not in {"cpu", "cuda"}:
        raise ValueError("Select PyTorch CPU or NVIDIA CUDA")
    deps = dependency_path(config_path)
    requirements = requirements.expanduser().resolve()
    if not requirements.is_file():
        raise FileNotFoundError(requirements)
    is_local_requirements = requirements.is_relative_to(config_path.resolve().parent)
    manifest_key = hashlib.sha256(str(config_path.resolve()).encode()).hexdigest()[:18]
    is_generated_manifest = (requirements == (MANIFEST_DIR / f"{manifest_key}.txt").resolve())
    if not (is_local_requirements or is_generated_manifest):
        raise ValueError("Requirements must belong to the bot or be an Evil RLBot generated manifest")
    python = ROOT / (".venv-v4" if framework == "rlbot-v4" else ".venv") / "bin/python"
    if not python.is_file():
        raise RuntimeError("Python runtime missing. Reinstall Evil RLBot.")

    DEPS_DIR.mkdir(parents=True, exist_ok=True)
    cache_dir = DEPS_DIR / ".shared"
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(requirements, framework, torch_backend)
    cached = cache_dir / key if key else None
    if cached is not None and _use_cached_deps(config_path, cached, deps):
        if progress:
            progress("Dependencies are already installed; reusing existing packages.")
        return f"Dependencies reused from cache: {cached}"

    # Avoid downloading existing dependencies again, including installations
    # made by earlier Evil RLBot versions before the shared cache existed.
    from ui.preflight import _required_modules, _python_check
    candidates = discover(config_path)
    chosen = next((c for c in candidates if c.path == config_path), None)
    if chosen:
        modules = _required_modules(config_path, chosen)
        if modules:
            ok, _ = _python_check(framework, deps, modules, config_path)
            if ok:
                if progress:
                    progress("All required Python imports already work; no download needed.")
                return f"Already installed for {config_path.name}"

    staging = deps.with_name(deps.name + "-partial-" + uuid.uuid4().hex[:8])
    log_dir = Path.home() / ".local/state/evilrlbot/install-logs"
    log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    log_dir.chmod(0o700)
    logfile = log_dir / (deps.name + ".log")
    torch_specs, other_specs, ordinary = _torch_specs(requirements)
    if not ordinary and _mentions_torch(requirements):
        raise ValueError("Unsupported complex requirements containing torch: refusing an additional large download; simplify the bot requirements.")
    filtered_req = staging.with_name(staging.name + "-filtered.txt")
    shared = None
    mentions_torch = bool(torch_specs) or _mentions_torch(requirements)
    try:
        if ordinary and torch_specs:
            # Reuse an ABI-compatible system/venv PyTorch before even considering
            # a multi-GB wheel download. This also handles mixed requirements
            # (e.g. torch is already installed but numpy needs a small fix).
            from ui.host_python import select_python
            hosted = select_python(framework, ("torch",), tuple(torch_specs))
            if hosted.okay:
                python = hosted.python  # install any *other* wheels for its ABI
                if progress:
                    progress(f"Reusing PyTorch from existing Python: {python}")
            else:
                shared = _ensure_shared_torch(
                    python, torch_specs, torch_backend,
                    config_path.resolve().parent, log_dir,
                    progress, stop_requested, timeout_seconds,
                )
                remember_torch_choice(config_path, torch_backend)
            if other_specs:
                filtered_req.write_text("\n".join(other_specs) + "\n", encoding="utf8")
        requirements_to_install = (
            filtered_req if ordinary and torch_specs and other_specs else
            None if ordinary and torch_specs else requirements
        )
        if requirements_to_install:
            command = [
                str(python), "-m", "pip", "install",
                "--disable-pip-version-check", "--no-input",
                "--progress-bar", "off", "--prefer-binary",
                "--retries", "5", "--timeout", "35",
                "--target", str(staging), "-r", str(requirements_to_install)
            ]
            if progress:
                progress("Installing bot-specific Python dependencies…")
            _run_install_command(
                command, config_path.resolve().parent, logfile,
                progress=progress, stop_requested=stop_requested,
                timeout_seconds=timeout_seconds,
                extra_env={"PYTHONPATH": str(shared)} if shared else None,
            )
        else:
            staging.mkdir()
            if progress:
                progress("PyTorch already shared; no additional packages required.")
        if not staging.is_dir():
            raise RuntimeError("pip exited without installing any dependencies")
        if chosen:
            modules = _required_modules(config_path, chosen)
            if modules:
                ok, reason = _python_check(framework, staging, modules, config_path)
                if not ok:
                    raise RuntimeError(
                        "Packages were downloaded but cannot be imported by Evil RLBot's "
                        f"isolated {framework} Python. {reason}\nPip log: {logfile}"
                    )
        if cached is not None:
            (staging / ".evilrlbot-complete").write_text(
                f"framework={framework}\nbackend={torch_backend}\n", encoding="utf-8"
            )
            if not cached.exists():
                staging.rename(cached)
            # If a concurrent installation won, its completeness marker is
            # verified before adopting it. Untrusted third-party packages
            # never overwrite the known-good cache.
            if _use_cached_deps(config_path, cached, deps):
                return f"Dependencies installed and cached. Log: {logfile}"
        # Non-shareable package, or cache race/failure: atomically install in
        # a bot-owned directory without deleting the previously working env.
        previous = deps.with_name(deps.name + "-previous-" + uuid.uuid4().hex[:8])
        had_previous = deps.exists() or deps.is_symlink()
        if had_previous:
            deps.rename(previous)
        try:
            staging.rename(deps)
        except BaseException:
            if had_previous:
                previous.rename(deps)
            raise
        if had_previous:
            if previous.is_dir() and not previous.is_symlink():
                shutil.rmtree(previous)
            else:
                previous.unlink(missing_ok=True)
        return f"Dependencies installed ({torch_backend if mentions_torch else 'standard'}). Log: {logfile}"
    finally:
        filtered_req.unlink(missing_ok=True)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
