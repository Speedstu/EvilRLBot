"""Export minimal, reviewable troubleshooting logs without bundling Epic credentials."""
from __future__ import annotations
import io
import json
import os
import platform
import re
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from ui.winpaths import LOG_DIR
SECRET_LINE = re.compile(r"(?i)(AUTH_PASSWORD|AUTH_LOGIN|AUTH_TYPE|authorization:|bearer\s|api[_-]?key|access[_-]?token|refresh[_-]?token)")
SECRET_WORD = re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*[=:]\s*([^\s,;\"']+)")
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")
URL_PASSWORD = re.compile(r"(https?://)[^\s/:@]+:[^\s@]+@", re.I)

def sanitize(text: str) -> str:
    lines = []
    for line in text.splitlines()[-2000:]:
        if SECRET_LINE.search(line):
            lines.append("[REDACTED AUTHENTICATION LINE]")
            continue
        line = URL_PASSWORD.sub(r"\1[REDACTED]@", line)
        line = SECRET_WORD.sub(r"\1=[REDACTED]", line)
        line = EMAIL.sub("[REDACTED EMAIL]", line)
        lines.append(line[:1500])
    return "\n".join(lines) + "\n"

def collect_logs() -> dict[str, str]:
    result: dict[str, str] = {}
    for log in [LOG_DIR / "ui-match.log", *sorted(LOG_DIR.glob("v4-worker-*.log"))]:
        if log.is_file():
            try:
                with log.open("rb") as f:
                    f.seek(max(0, log.stat().st_size - 220_000))
                    result["logs/"+log.name] = sanitize(f.read().decode("utf-8", "replace"))
            except OSError:
                pass
    pip_dir = LOG_DIR / "install-logs"
    if pip_dir.is_dir():
        for log in sorted(pip_dir.glob("*.log"), key=lambda p:p.stat().st_mtime, reverse=True)[:8]:
            try:
                result["pip/"+log.name] = sanitize(log.read_text(encoding="utf8",errors="replace")[-140_000:])
            except OSError:
                pass
    return result

def save_support_zip(destination: Path) -> Path:
    logs = collect_logs()
    from ui import server
    from ui.offline_launcher import installation
    details = {
        "release": "2026.10.19.2",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "log_names": list(logs),
        "match_players": [
            {"kind": p.get("kind"), "team": p.get("team"), "bot_id": p.get("id","")[:8]}
            for p in server._load_setup().get("players", [])
        ],
        "game_exe_exists": (installation()["game"] / "Binaries/Win64/RocketLeague.exe").is_file(),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "Evil RLBot support logs. Review contents before sharing. No Epic private launcher logs are included.\n")
        archive.writestr("summary.json", json.dumps(details, indent=2))
        for name, value in logs.items():
            archive.writestr(name, value)
    return destination
