"""Official Legendary offline RLBot launch, portable across Linux user accounts.

Rocket League game files and Epic authentication are NOT part of the AppImage.
Auto-discover Heroic's existing installation or choose paths via Game Setup.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

HOME = Path.home()
PROJECT = Path(__file__).resolve().parents[1]
SETTINGS = HOME / ".config/evilrlbot/rocketleague.json"
PRIVATE_LOG = HOME / ".local/state/evilrlbot/offline-legendary-private.log"
LEGENDARY = "/app/bin/heroic/resources/app.asar.unpacked/build/bin/x64/linux/legendary"


def _heroic_roots() -> list[Path]:
    return [
        HOME / ".var/app/com.heroicgameslauncher.hgl/config/heroic",
        HOME / ".config/heroic",
    ]


def _load_preferences() -> dict:
    if SETTINGS.is_file():
        try:
            data = json.loads(SETTINGS.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if k in ("game", "prefix", "wine") and isinstance(v, str)}
        except (OSError, ValueError):
            pass
    return {}


def save_preferences(game: str, prefix: str, wine: str) -> None:
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    data = {"game": game.strip(), "prefix": prefix.strip(), "wine": wine.strip()}
    temp = SETTINGS.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(SETTINGS)


def _legendary_config() -> Path:
    for root in _heroic_roots():
        path = root / "legendaryConfig/legendary"
        if (path / "user.json").is_file():
            return path
    candidate = HOME / ".config/legendary"
    if (candidate / "user.json").is_file():
        return candidate
    return _heroic_roots()[0] / "legendaryConfig/legendary"


def _game_path() -> Path:
    prefs = _load_preferences()
    if prefs.get("game"):
        return Path(prefs["game"]).expanduser()
    for config in [_legendary_config(), *[p / "legendaryConfig/legendary" for p in _heroic_roots()]]:
        installed = config / "installed.json"
        if installed.is_file():
            try:
                data = json.loads(installed.read_text(encoding="utf-8"))
                info = data.get("Sugar", {})
                game = Path(info.get("install_path") or "") if isinstance(info, dict) else Path()
                if str(game) not in ("", ".") and (game / "Binaries/Win64/RocketLeague.exe").is_file():
                    return game
            except (OSError, ValueError, TypeError):
                continue
    return HOME / "Games/RocketLeagueOffline"


def _prefix_path() -> Path:
    prefs = _load_preferences()
    if prefs.get("prefix"):
        return Path(prefs["prefix"]).expanduser()
    existing = HOME / "Games/RocketLeaguePrefixGE/pfx"
    if (existing / "system.reg").is_file():
        return existing
    # First-time Wine prefix can be initialized by Heroic/Legendary.
    return HOME / ".local/share/evilrlbot/rocketleague-prefix/pfx"


def _wine_path() -> Path:
    prefs = _load_preferences()
    if prefs.get("wine"):
        return Path(prefs["wine"]).expanduser()
    for root in _heroic_roots():
        candidates = sorted(root.glob("tools/proton/*/files/bin/wine"), reverse=True)
        candidates += sorted(root.glob("tools/wine/*/bin/wine"), reverse=True)
        for path in candidates:
            if path.is_file():
                return path
    return Path("/usr/bin/wine")


def installation() -> dict:
    return {"game": _game_path(), "prefix": _prefix_path(), "wine": _wine_path(),
            "legendary_config": _legendary_config()}


def running_game_pids() -> list[int]:
    game = str(_game_path())
    result: list[int] = []
    for p in Path("/proc").iterdir():
        if not p.name.isdecimal():
            continue
        try:
            if not (p / "comm").read_text().strip().startswith("RocketLeague.ex"):
                continue
            command = (p / "cmdline").read_bytes().decode("utf-8", "replace")
            # Wine game paths use Z:\home\... or Unix paths in the process list.
            # Keep this strict so Stop never terminates another Rocket League.
            if "RocketLeague.exe" in command and (
                game in command or game.replace("/", "\\") in command
            ):
                result.append(int(p.name))
        except (OSError, UnicodeError):
            continue
    return result


def command() -> list[str]:
    if shutil.which("flatpak") is None:
        raise RuntimeError("Heroic Flatpak is required for Legendary Offline. Install Heroic or select Steam.")
    info = installation()
    game, prefix, wine, config = (info[k] for k in ("game", "prefix", "wine", "legendary_config"))
    if not (game / "Binaries/Win64/RocketLeague.exe").is_file():
        raise RuntimeError("Rocket League not found. Open Menu → Configure Rocket League, or import it into Heroic.")
    if not wine.is_file():
        raise RuntimeError("No compatible Wine runner found. Install one in Heroic, then Configure Rocket League.")
    if not (config / "user.json").is_file():
        raise RuntimeError("Sign in to your own Epic Games account in Heroic first. No account is included.")
    prefix.mkdir(parents=True, exist_ok=True)
    command = [
        "flatpak", "run",
        f"--env=LEGENDARY_CONFIG_PATH={config}",
    ]
    dxvk = game / "Binaries/Win64/dxvk.conf"
    if dxvk.is_file():
        command.append(f"--env=DXVK_CONFIG_FILE={dxvk}")
    command.extend([
        f"--command={LEGENDARY}",
        "com.heroicgameslauncher.hgl", "launch", "Sugar",
        "--offline", "--skip-version-check",
        "--wine", str(wine), "--wine-prefix", str(prefix),
        "-rlbot", "RLBot_ControllerURL=127.0.0.1:23233", "RLBot_PacketSendRate=240",
        "-nomovie", "-windowed", "-ResX=1280", "-ResY=720",
    ])
    return command


def environment() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    env.setdefault("DISPLAY", ":0")
    if Path(f"{env['XDG_RUNTIME_DIR']}/wayland-1").exists():
        env.setdefault("WAYLAND_DISPLAY", "wayland-1")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={env['XDG_RUNTIME_DIR']}/bus")
    return env
