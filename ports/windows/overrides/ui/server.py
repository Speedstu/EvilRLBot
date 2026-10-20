#!/usr/bin/env python3
"""Local-only Evil RLBot GUI: classic team setup on the native v5 engine."""
from __future__ import annotations

import configparser
import json
import os
import signal
import subprocess
import sys
import threading
import time
import tomllib
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.detection import detect_bot
from ui.match_config import build_match, validate_setup
from ui import offline_launcher
from ui.winpaths import DATA, CONFIG_DIR, LOG_DIR, V5_PY

HOST = "127.0.0.1"
DEFAULT_PORT = 17850
LIBRARY_FILE = CONFIG_DIR / "library.json"
SETUP_FILE = CONFIG_DIR / "match-setup.json"
RUNNER = ROOT / "run.py"
HTML = ROOT / "ui" / "index.html"
LOG = LOG_DIR / "ui-match.log"

_process_lock = threading.RLock()
_match_process = None
_match_log_handle = None
_last_match_file = None
_game_process = None
_game_log_handle = None
_owned_game = False


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def _load_library():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if LIBRARY_FILE.is_file():
        try:
            data = json.loads(LIBRARY_FILE.read_text())
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict) and "path" in x and "id" in x]
        except (ValueError, OSError):
            pass
    data = [{
        "id": uuid.uuid4().hex,
        "path": str(ROOT / "legacy_bot" / "bot.cfg"),
        "favorite": True,
        "category": "Standard",
    }]
    _save_json(LIBRARY_FILE, data)
    return data


def _bot_paths():
    return {str(x["id"]): str(x["path"]) for x in _load_library()}


def _load_setup():
    if SETUP_FILE.is_file():
        try:
            setup = json.loads(SETUP_FILE.read_text())
            return validate_setup(setup, _bot_paths())
        except (OSError, ValueError, TypeError):
            pass
    lib = _load_library()
    players = [{"kind": "human", "team": 0}]
    if lib:
        players.append({"kind": "bot", "id": str(lib[0]["id"]), "team": 1})
    return {"players": players, "map": "Stadium_P", "mode": "Soccar", "launcher": "Epic"}


def _name_for(path: Path) -> str:
    try:
        if path.suffix.lower() == ".cfg":
            cp = configparser.RawConfigParser()
            cp.read(path, encoding="utf-8")
            if cp.has_section("Locations"):
                return cp.get("Locations", "name", fallback=path.stem)
        if path.suffix.lower() == ".toml":
            with open(path, "rb") as f:
                data = tomllib.load(f)
            return str(data.get("settings", {}).get("name") or path.stem)
    except Exception:
        pass
    return path.name if path.is_dir() else path.stem


def _bot_payload(item):
    path = Path(item["path"]).expanduser().resolve()
    report = detect_bot(path)
    category = item.get("category") or ("ML" if report.get("observation") != "unknown" else "Standard")
    return {
        **item,
        "path": str(path),
        "name": item.get("display_name") or _name_for(path),
        "exists": path.exists(),
        "category": category,
        "diagnostics": report,
    }


def _status():
    with _process_lock:
        running = _match_process is not None and _match_process.poll() is None
        code = None if running or _match_process is None else _match_process.returncode
        pid = _match_process.pid if running else None
    return {"running": running, "pid": pid, "exit_code": code, "match_file": str(_last_match_file) if _last_match_file else None}


def _terminate_group(proc, *, timeout=3):
    """Terminate only process trees created by Evil RLBot, not other games."""
    if proc is None or proc.poll() is not None:
        return
    try:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=timeout + 3, check=False,
        )
        proc.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        try:
            proc.kill()
            proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _stop_match():
    global _match_process, _match_log_handle, _game_process, _game_log_handle, _owned_game
    with _process_lock:
        if _owned_game:
            # Only close game processes we explicitly launched from the copied
            # RocketLeagueOffline directory, never an unrelated user's game.
            for pid in offline_launcher.running_game_pids():
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        _terminate_group(_game_process)
        _terminate_group(_match_process)
        _game_process = None
        _match_process = None
        _owned_game = False
        if _game_log_handle is not None:
            _game_log_handle.close()
            _game_log_handle = None
        if _match_log_handle is not None:
            _match_log_handle.close()
            _match_log_handle = None


def _start_match(setup: dict):
    global _match_process, _match_log_handle, _last_match_file
    global _game_process, _game_log_handle, _owned_game
    # Validate bot dependencies *before* generating configs or launching a
    # game. Errors must never create an empty spectator-only match.
    from ui.preflight import check_bots
    problems = check_bots(setup, _bot_paths())
    if problems:
        raise ValueError(
            "Bots cannot start: required Python packages or runtime failed checks.\n\n"
            + "\n\n".join(problems[:8])
        )
    match_file = build_match(setup, _bot_paths())
    from rlbot.config import load_match_config
    load_match_config(match_file)
    # On Windows the RLBot V5 launcher handles Epic/Steam itself.
    # No game binaries, credentials or launcher modifications are bundled.
    offline = False
    with _process_lock:
        _stop_match()
        LOG.parent.mkdir(exist_ok=True)
        handle = open(LOG, "wb", buffering=0)
        try:
            proc = subprocess.Popen(
                [str(V5_PY), str(RUNNER), str(match_file)],
                cwd=ROOT,
                stdout=handle, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except BaseException:
            handle.close()
            raise
        _match_process = proc
        _match_log_handle = handle
        _last_match_file = match_file
        if offline:
            # Protect all Legendary output; it may include temporary Epic auth
            # tokens or game login arguments. Never expose it via UI logs.
            try:
                offline_launcher.PRIVATE_LOG.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                offline_launcher.PRIVATE_LOG.parent.chmod(0o700)
                fd = os.open(offline_launcher.PRIVATE_LOG,
                             os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                private_handle = os.fdopen(fd, "wb", buffering=0)
                _game_log_handle = private_handle
                _game_process = subprocess.Popen(
                    game_cmd, cwd=ROOT, stdout=private_handle,
                    stderr=subprocess.STDOUT, start_new_session=True,
                    env=offline_launcher.environment(),
                )
                _owned_game = True
            except BaseException:
                _stop_match()
                raise
        return {"pid": proc.pid, "log": str(LOG), "match_file": str(match_file),
                "launcher": setup.get("launcher")}


class Handler(BaseHTTPRequestHandler):
    server_version = "EvilRLBotUI/2.0"

    def log_message(self, fmt, *args):
        return

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 64 * 1024:
                raise ValueError("Request too large")
            raw = self.rfile.read(length) if length else b"{}"
            result = json.loads(raw or b"{}")
            return result if isinstance(result, dict) else {}
        except (ValueError, OSError):
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/bots":
            self._json([_bot_payload(x) for x in _load_library()])
            return
        if parsed.path == "/api/setup":
            self._json(_load_setup())
            return
        if parsed.path == "/api/status":
            self._json(_status())
            return
        if parsed.path == "/api/diagnostics":
            bot_id = parse_qs(parsed.query).get("id", [""])[0]
            item = next((x for x in _load_library() if x.get("id") == bot_id), None)
            if not item:
                self._json({"error": "Bot not found"}, 404)
            else:
                self._json(_bot_payload(item))
            return
        if parsed.path == "/api/log":
            log_text = LOG.read_text(errors="replace")[-50000:] if LOG.exists() else ""
            self._json({"text": log_text})
            return
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        # Browser same-origin JSON calls only. A different website cannot drive
        # local bot launches via a blind HTML form or cross-origin JSON fetch.
        origin = self.headers.get("Origin")
        allowed = {f"http://{HOST}:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if origin and origin not in allowed:
            self._json({"error": "Cross-origin request denied"}, 403)
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._json({"error": "JSON requests only"}, 415)
            return
        data = self._read_json()

        if parsed.path == "/api/add":
            raw = str(data.get("path", "")).strip()
            if not raw:
                self._json({"error": "Enter a bot path"}, 400)
                return
            path = Path(raw).expanduser().resolve()
            if not path.exists():
                self._json({"error": f"Path not found: {path}"}, 400)
                return
            report = detect_bot(path)
            if report.get("framework") == "unknown":
                self._json({"error": "No RLBot v4/v5 implementation detected", "diagnostics": report}, 400)
                return
            items = _load_library()
            existing = next((x for x in items if Path(x["path"]).expanduser().resolve() == path), None)
            if existing:
                self._json(_bot_payload(existing))
                return
            item = {
                "id": uuid.uuid4().hex, "path": str(path), "favorite": False,
                "category": "ML" if report.get("observation") != "unknown" else "Standard",
            }
            items.append(item)
            _save_json(LIBRARY_FILE, items)
            self._json(_bot_payload(item), 201)
            return

        if parsed.path == "/api/remove":
            bot_id = str(data.get("id", ""))
            items = _load_library()
            new_items = [x for x in items if x.get("id") != bot_id]
            _save_json(LIBRARY_FILE, new_items)
            self._json({"ok": len(new_items) != len(items)})
            return

        if parsed.path == "/api/favorite":
            bot_id = str(data.get("id", ""))
            items = _load_library()
            item = next((x for x in items if x.get("id") == bot_id), None)
            if not item:
                self._json({"error": "Bot not found"}, 404)
                return
            item["favorite"] = not bool(item.get("favorite"))
            _save_json(LIBRARY_FILE, items)
            self._json({"favorite": item["favorite"]})
            return

        if parsed.path == "/api/setup":
            try:
                setup = validate_setup(data, _bot_paths())
                _save_json(SETUP_FILE, setup)
                self._json({"ok": True, "setup": setup})
            except (ValueError, TypeError) as exc:
                self._json({"error": str(exc)}, 400)
            return

        if parsed.path == "/api/start":
            try:
                # Compatible with the previous single-bot UI request format.
                if "players" not in data:
                    bot_id = str(data.get("id", ""))
                    team = int(data.get("team", 1))
                    data["players"] = [
                        {"kind": "human", "team": 1 - team},
                        {"kind": "bot", "id": bot_id, "team": team},
                    ]
                setup = validate_setup(data, _bot_paths())
                result = _start_match(setup)
                _save_json(SETUP_FILE, setup)
                self._json({"ok": True, **result})
            except (ValueError, TypeError) as exc:
                self._json({"error": str(exc)}, 400)
            except Exception as exc:
                self._json({"error": f"Unable to start match: {exc}"}, 500)
            return

        if parsed.path == "/api/stop":
            _stop_match()
            self._json({"ok": True})
            return

        if parsed.path == "/api/pick":
            try:
                kind = data.get("kind", "file")
                cmd = ["zenity", "--file-selection", "--title=Import RLBot bot"]
                if kind == "folder":
                    cmd.append("--directory")
                cp = subprocess.run(cmd, text=True, capture_output=True, timeout=90, check=False)
                self._json({"path": cp.stdout.strip() if cp.returncode == 0 else ""})
            except (OSError, subprocess.TimeoutExpired):
                self._json({"path": "", "error": "Native file chooser unavailable"})
            return

        self.send_error(404)


def open_browser(url: str):
    time.sleep(0.35)
    try:
        subprocess.Popen(["cmd", "/c", "start", "", url], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def main():
    port = DEFAULT_PORT
    no_browser = "--no-browser" in sys.argv
    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            port = int(arg.split("=", 1)[1])
    url = f"http://{HOST}:{port}/"
    try:
        server = ThreadingHTTPServer((HOST, port), Handler)
    except OSError:
        if not no_browser:
            open_browser(url)
        print(url)
        return
    print(f"Evil RLBot UI: {url}", flush=True)
    if not no_browser:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _stop_match()
        server.server_close()


if __name__ == "__main__":
    main()
