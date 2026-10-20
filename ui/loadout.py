"""Read and write a bot's in-game appearance (v4 looks.cfg / v5 loadout.toml).

Both formats hold the same fields; only the section names differ. Saving
rewrites individual `key = value` lines so comments and unrelated settings in
the bot's files survive untouched.
"""
from __future__ import annotations

import configparser
import csv
import json
import random
import re
import tomllib
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
TEAMS = ("blue", "orange")

# (field, item category in items.csv, paint field or None, label)
ITEM_FIELDS = [
    ("car_id", "Body", "car_paint_id", "Car"),
    ("decal_id", "Skin", "decal_paint_id", "Decal"),
    ("wheels_id", "Wheels", "wheels_paint_id", "Wheels"),
    ("boost_id", "Boost", "boost_paint_id", "Boost"),
    ("antenna_id", "Antenna", "antenna_paint_id", "Antenna"),
    ("hat_id", "Hat", "hat_paint_id", "Topper"),
    ("trails_id", "SupersonicTrail", "trails_paint_id", "Trail"),
    ("goal_explosion_id", "GoalExplosion", "goal_explosion_paint_id", "Goal explosion"),
    ("paint_finish_id", "PaintFinish", None, "Primary finish"),
    ("custom_finish_id", "PaintFinish", None, "Accent finish"),
    ("engine_audio_id", "EngineAudio", None, "Engine audio"),
]
COLOR_FIELDS = ("team_color_id", "custom_color_id")
LOADOUT_KEYS = COLOR_FIELDS + tuple(f for f, *_ in ITEM_FIELDS)
PAINT_KEYS = tuple(p for _, _, p, _ in ITEM_FIELDS if p)

# Rocket League paint names with their in-game colours.
PAINTS = [
    (0, "No paint", None), (1, "Crimson", "#c4161c"), (2, "Lime", "#7fd321"),
    (3, "Black", "#141414"), (4, "Sky Blue", "#38b6e8"), (5, "Cobalt", "#3a4fc4"),
    (6, "Burnt Sienna", "#8a3a1d"), (7, "Forest Green", "#2f7d32"),
    (8, "Purple", "#8a2be2"), (9, "Pink", "#ef6fd0"), (10, "Orange", "#f2811d"),
    (11, "Grey", "#8c8c8c"), (12, "Titanium White", "#f2f2f2"), (13, "Saffron", "#f3c623"),
]

DEFAULT = {
    "blue": {"team_color_id": 60, "custom_color_id": 0, "car_id": 23, "decal_id": 0,
             "wheels_id": 1565, "boost_id": 35, "antenna_id": 0, "hat_id": 0,
             "paint_finish_id": 1681, "custom_finish_id": 1681, "engine_audio_id": 0,
             "trails_id": 3220, "goal_explosion_id": 3018},
    "blue_paint": {"car_paint_id": 12, "decal_paint_id": 0, "wheels_paint_id": 7,
                   "boost_paint_id": 7, "antenna_paint_id": 0, "hat_paint_id": 0,
                   "trails_paint_id": 2, "goal_explosion_paint_id": 0},
}
DEFAULT["orange"] = {**DEFAULT["blue"], "team_color_id": 3}
DEFAULT["orange_paint"] = {**DEFAULT["blue_paint"], "wheels_paint_id": 14,
                           "boost_paint_id": 14, "trails_paint_id": 14}

SECTIONS = {
    "v4": {"blue": "Bot Loadout", "orange": "Bot Loadout Orange",
           "blue_paint": "Bot Paint Blue", "orange_paint": "Bot Paint Orange"},
    "v5": {"blue": "blue_loadout", "orange": "orange_loadout",
           "blue_paint": "blue_loadout.paint", "orange_paint": "orange_loadout.paint"},
}


@lru_cache(maxsize=None)
def items() -> dict[str, list[tuple[int, str]]]:
    """Item category -> [(id, name)] sorted by name."""
    result: dict[str, list[tuple[int, str]]] = {}
    with (DATA / "items.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 4 and row[0].isdigit():
                result.setdefault(row[1], []).append((int(row[0]), row[3]))
    for entries in result.values():
        entries.sort(key=lambda entry: entry[1].lower())
    return result


@lru_cache(maxsize=None)
def palettes() -> dict[str, list[list[int]]]:
    return json.loads((DATA / "colors.json").read_text(encoding="utf-8"))


def item_name(category: str, item_id: int) -> str:
    if not item_id:
        return "None"
    return next((name for i, name in items().get(category, []) if i == item_id), f"Item {item_id}")


def decals_for(car_id: int) -> list[tuple[int, str]]:
    """Decals that fit a car body ("Octane: Flames") plus universal ones."""
    car = item_name("Body", car_id)
    result = []
    for item_id, name in items().get("Skin", []):
        body, sep, decal = name.partition(":")
        if not sep:
            result.append((item_id, name))
        elif body.strip() == car:
            result.append((item_id, decal.strip()))
    return result


def _read_ini(path: Path) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser()
    parser.read(path, encoding="utf-8")
    return parser


def locate(bot_file: Path) -> tuple[str, Path, bool] | None:
    """(format, loadout path, referenced) for a bot.cfg / bot.toml, else None."""
    bot_file = Path(bot_file)
    if bot_file.suffix.lower() == ".cfg":
        parser = _read_ini(bot_file)
        name = parser.get("Locations", "looks_config", fallback="").strip()
        return "v4", bot_file.parent / (name or "looks.cfg"), bool(name)
    if bot_file.suffix.lower() == ".toml":
        try:
            settings = tomllib.loads(bot_file.read_text(encoding="utf-8")).get("settings", {})
        except (OSError, tomllib.TOMLDecodeError):
            settings = {}
        name = str(settings.get("loadout_file") or "").strip()
        return "v5", bot_file.parent / (name or "loadout.toml"), bool(name)
    return None


def load(bot_file: Path) -> dict[str, dict[str, int]]:
    """The bot's loadout, with defaults filled in for anything missing."""
    found = locate(bot_file)
    data = {key: dict(values) for key, values in DEFAULT.items()}
    if not found or not found[1].is_file():
        return data
    fmt, path, _ = found
    if fmt == "v4":
        parser = _read_ini(path)
        raw = {key: dict(parser.items(section)) if parser.has_section(section) else {}
               for key, section in SECTIONS["v4"].items()}
    else:
        try:
            toml = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            toml = {}
        raw = {}
        for team in TEAMS:
            section = toml.get(f"{team}_loadout", {})
            raw[team] = section
            raw[f"{team}_paint"] = section.get("paint", {}) if isinstance(section, dict) else {}
    for key, values in raw.items():
        for field, value in values.items():
            if field in data[key]:
                try:
                    data[key][field] = int(value)
                except (TypeError, ValueError):
                    pass
    return data


def _set_lines(text: str, section: str, values: dict[str, int]) -> str:
    """Update key = value lines inside [section], appending what is missing."""
    lines = text.splitlines()
    header = re.compile(r"^\s*\[\s*([^\]]+?)\s*\]\s*$")
    start = next((i for i, line in enumerate(lines)
                  if (m := header.match(line)) and m.group(1) == section), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"[{section}]")
        lines.extend(f"{key} = {value}" for key, value in values.items())
        return "\n".join(lines) + "\n"
    end = next((i for i in range(start + 1, len(lines)) if header.match(lines[i])), len(lines))
    pending = dict(values)
    for i in range(start + 1, end):
        m = re.match(r"^(\s*)([A-Za-z_]+)(\s*=\s*)([^#\n]*?)(\s*(#.*)?)$", lines[i])
        if m and m.group(2) in pending:
            lines[i] = f"{m.group(1)}{m.group(2)}{m.group(3)}{pending.pop(m.group(2))}{m.group(5)}"
    insert = end
    while insert > start + 1 and not lines[insert - 1].strip():
        insert -= 1
    lines[insert:insert] = [f"{key} = {value}" for key, value in pending.items()]
    return "\n".join(lines) + "\n"


def save(bot_file: Path, data: dict[str, dict[str, int]]) -> Path:
    """Write the loadout, creating and referencing a loadout file if needed."""
    found = locate(bot_file)
    if not found:
        raise ValueError("Only bots with a bot.cfg or bot.toml have an editable appearance.")
    fmt, path, referenced = found
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for key, section in SECTIONS[fmt].items():
        text = _set_lines(text, section, {k: int(v) for k, v in data[key].items()})
    path.write_text(text, encoding="utf-8")
    if not referenced:
        bot_text = Path(bot_file).read_text(encoding="utf-8")
        if fmt == "v4":
            bot_text = _set_text_value(bot_text, "Locations", "looks_config", f"./{path.name}")
        else:
            bot_text = _set_text_value(bot_text, "settings", "loadout_file", f'"{path.name}"')
        Path(bot_file).write_text(bot_text, encoding="utf-8")
    return path


def _set_text_value(text: str, section: str, key: str, value: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"^\s*\[\s*{re.escape(section)}\s*\]\s*$", line):
            lines.insert(i + 1, f"{key} = {value}")
            return "\n".join(lines) + "\n"
    return text.rstrip("\n") + f"\n\n[{section}]\n{key} = {value}\n"


def randomize(team: str, data: dict[str, dict[str, int]]) -> None:
    """Pick random items, colours and paints for one team."""
    catalogue = items()
    for field, category, paint, _ in ITEM_FIELDS:
        choices = catalogue.get(category)
        if field == "decal_id":
            choices = decals_for(data[team]["car_id"])
        if choices and field != "engine_audio_id":
            data[team][field] = random.choice(choices)[0]
        if paint:
            data[f"{team}_paint"][paint] = random.choice(PAINTS)[0]
    data[team]["team_color_id"] = random.randrange(len(palettes()[team]))
    data[team]["custom_color_id"] = random.randrange(len(palettes()["secondary"]))
