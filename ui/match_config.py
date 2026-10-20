"""Build a RLBot v5 match from a classic RLBot-style team lineup.

V4 bots are hosted by the real v4 runtime via a v5 bridge. Native v5 bots run
directly on v5. Every car gets its own generated agent config to prevent
overwriting a teammate's bridge configuration.
"""
from __future__ import annotations

import json
import sys
import tomllib
import uuid
import shlex
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from common.detection import detect_bot
from tools.auto_bot import resolve

GENERATED = ROOT / ".generated" / "ui"
MAPS = {
    "Stadium_P", "HoopsStadium_P", "Labs_Utopia_P", "EuroStadium_P",
    "TrainStation_P", "UtopiaStadium_P", "Park_P", "Underpass_P",
}
MODES = {"Soccar", "Hoops", "Dropshot", "Snowday", "Rumble", "Heatseeker"}
SKILLS = {"Beginner", "Rookie", "Pro", "Allstar"}
LAUNCHERS = {"Steam", "Heroic", "Legendary", "NoLaunch", "OfflineLegendary"}
MUTATORS = {
    "match_length": {"FiveMinutes", "TenMinutes", "TwentyMinutes", "Unlimited"},
    "max_score": {"Unlimited", "OneGoal", "ThreeGoals", "FiveGoals"},
    "boost_amount": {"NormalBoost", "UnlimitedBoost", "SlowRecharge", "RapidRecharge", "NoBoost"},
    "ball_size": {"Default", "Small", "Large", "Gigantic"},
    "gravity": {"Default", "Low", "High", "SuperHigh"},
    "game_speed": {"Default", "SloMo", "TimeWarp"},
    "overtime": {"Unlimited", "FiveMaxFirstScore", "FiveMaxRandomTeam"},
    "series_length": {"Unlimited", "ThreeGames", "FiveGames", "SevenGames"},
    "ball_max_speed": {"Default", "Slow", "Fast", "SuperFast"},
    "ball_type": {"Default", "Cube", "Puck", "Basketball"},
    "ball_weight": {"Default", "Light", "Heavy", "SuperLight"},
    "ball_bounciness": {"Default", "Low", "High", "SuperHigh"},
    "rumble": {"Off", "DefaultRumble", "Slow", "Civilized", "DestructionDerby", "SpringLoaded", "SpikesOnly", "SpikeRush"},
    "boost_strength": {"One", "OneAndAHalf", "Two", "Ten"},
    "demolish": {"Default", "Disabled", "FriendlyFire", "OnContact", "OnContactFf"},
    "respawn_time": {"ThreeSeconds", "TwoSeconds", "OneSecond", "DisableGoalReset"},
}
OPTIONS = {"skip_replays", "instant_start", "enable_rendering", "enable_state_setting", "auto_save_replay"}
DEFAULT_OPTIONS = {
    "skip_replays": True, "instant_start": False,
    "enable_rendering": True, "enable_state_setting": True, "auto_save_replay": False,
}
def _v5_with_deps(original: Path, agent: Path, per_player: Path) -> Path:
    """Use pre-existing Python/torch when it can run the V5 agent."""
    from ui.bot_importer import dependency_path, usable_torch_path, discover
    from ui.preflight import _required_modules, _requirement_specs
    from ui.host_python import select_python
    import tomli_w

    with agent.open("rb") as f:
        cfg = tomllib.load(f)
    settings = cfg.get("settings")
    if not isinstance(settings, dict):
        raise ValueError(f"Invalid V5 agent settings: {agent}")
    cmd = settings.get("run_command_linux") or settings.get("run_command")
    if not cmd:
        raise ValueError(f"Bot has no Linux run command: {agent}")
    original_root = (agent.parent / (settings.get("root_dir") or ".")).resolve()
    bridge = original.suffix.lower() == ".cfg"
    paths = []
    python = ROOT / ".venv/bin/python"
    if not bridge:
        candidates = discover(original)
        candidate = next((c for c in candidates if c.path == original),
                         candidates[0] if candidates else None)
        deps = dependency_path(original)
        shared = usable_torch_path(original)
        modules = tuple(_required_modules(original, candidate)) if candidate else ()
        specs = tuple(_requirement_specs(candidate.requirements)) if candidate else ()
        selected = select_python("rlbot-v5", modules, specs,
                                 str(deps) if deps.is_dir() else "",
                                 str(shared) if shared else "")
        if not selected.okay:
            raise RuntimeError(f"No compatible V5 Python: {selected.error}")
        python = selected.python
        paths = [str(p) for p in (selected.framework_site, deps, shared)
                 if p is not None and p.is_dir()]
    wrapper = per_player / "run_v5.sh"
    extra = (f"export PYTHONPATH={shlex.quote(':'.join(paths))}:$PYTHONPATH\n"
             if paths else "")
    wrapper.write_text(
        "#!/usr/bin/env bash\nset -e\n"
        + f"cd {shlex.quote(str(original_root))}\n"
        + f"export PATH={shlex.quote(str(python.parent))}:${{PATH}}\n"
        + extra
        + f"exec bash -c {shlex.quote(str(cmd))}\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    settings["root_dir"] = str(original_root)
    settings["run_command_linux"] = str(wrapper)
    settings["run_command"] = str(wrapper)
    if settings.get("loadout_file"):
        settings["loadout_file"] = str((agent.parent / settings["loadout_file"]).resolve())
    settings["agent_id"] = str(settings.get("agent_id", "evilrlbot/agent")) + "/" + hashlib.sha256(str(per_player).encode()).hexdigest()[:10]
    generated = per_player / "agent_v5.toml"
    generated.write_text(tomli_w.dumps(cfg), encoding="utf-8")
    return generated

DEFAULT_MUTATORS = {
    "match_length": "FiveMinutes", "max_score": "Unlimited", "boost_amount": "NormalBoost",
    "ball_size": "Default", "gravity": "Default", "game_speed": "Default",
    "overtime": "Unlimited", "series_length": "Unlimited", "ball_max_speed": "Default",
    "ball_type": "Default", "ball_weight": "Default", "ball_bounciness": "Default",
    "rumble": "Off", "boost_strength": "One", "demolish": "Default",
    "respawn_time": "ThreeSeconds",
}


def validate_setup(setup: dict, bot_paths: dict[str, str]) -> dict:
    if not isinstance(setup, dict):
        raise ValueError("Invalid match setup")
    supplied = setup.get("players")
    if not isinstance(supplied, list) or not 1 <= len(supplied) <= 10:
        raise ValueError("Add between 1 and 10 players (including bots)")
    players = []
    num_humans = 0
    for entry in supplied:
        if not isinstance(entry, dict):
            raise ValueError("Invalid player entry")
        team = entry.get("team")
        if type(team) is not int or team not in (0, 1):
            raise ValueError("Each player needs a Blue or Orange team")
        kind = entry.get("kind")
        if kind == "human":
            num_humans += 1
            players.append({"kind": kind, "team": team})
        elif kind == "psyonix":
            skill = entry.get("skill", "Pro")
            if skill not in SKILLS:
                raise ValueError("Invalid Psyonix AI difficulty")
            players.append({"kind": kind, "team": team, "skill": skill})
        elif kind == "bot":
            bot_id = entry.get("id")
            if not isinstance(bot_id, str) or bot_id not in bot_paths:
                raise ValueError("One of the selected bots is no longer in the library")
            path = Path(bot_paths[bot_id]).expanduser().resolve()
            if not path.exists():
                raise ValueError(f"Bot missing: {path}")
            players.append({"kind": kind, "team": team, "id": bot_id})
        else:
            raise ValueError("Unsupported player type")
    if num_humans > 1:
        raise ValueError("Only one local human is supported by this launcher")
    mode = setup.get("mode", "Soccar")
    game_map = setup.get("map", "Stadium_P")
    if mode not in MODES or game_map not in MAPS:
        raise ValueError("Unsupported arena or game mode")
    launcher = setup.get("launcher", "Steam")
    if launcher not in LAUNCHERS:
        raise ValueError("Unsupported Rocket League launcher")
    raw_mut = setup.get("mutators") or {}
    raw_opt = setup.get("options") or {}
    if not isinstance(raw_mut, dict) or not isinstance(raw_opt, dict):
        raise ValueError("Invalid match settings")
    mut = dict(DEFAULT_MUTATORS)
    for key, val in raw_mut.items():
        if key not in MUTATORS or val not in MUTATORS[key]:
            raise ValueError(f"Unsupported mutator: {key}={val}")
        mut[key] = val
    opts = dict(DEFAULT_OPTIONS)
    for key, val in raw_opt.items():
        if key not in OPTIONS or type(val) is not bool:
            raise ValueError(f"Unsupported match option: {key}")
        opts[key] = val
    return {"players": players, "mode": mode, "map": game_map, "mutators": mut, "options": opts, "launcher": launcher}


def build_match(setup: dict, bot_paths: dict[str, str]) -> Path:
    setup = validate_setup(setup, bot_paths)
    match_root = GENERATED / uuid.uuid4().hex
    match_root.mkdir(parents=True)
    lines = [
        "#:schema https://rlbot.org/schemas/match.json",
        "[rlbot]",
        f'launcher = {json.dumps("NoLaunch" if setup["launcher"] == "OfflineLegendary" else ("Custom" if setup["launcher"] in {"Heroic", "Legendary"} else setup["launcher"]))}',
        *([f'launcher_arg = {json.dumps(setup["launcher"].lower())}'] if setup["launcher"] in {"Heroic", "Legendary"} else []),
        "auto_start_agents = true", "wait_for_agents = true", "",
        "[match]", f'game_mode = {json.dumps(setup["mode"])}',
        f'game_map_upk = {json.dumps(setup["map"])}',
        'existing_match_behavior = "Restart"', 'freeplay = false',
    ]
    for key, val in setup["options"].items():
        lines.append(f"{key} = {str(val).lower()}")
    lines += ["", "[mutators]"]
    for key, val in setup["mutators"].items():
        lines.append(f"{key} = {json.dumps(val)}")

    for idx, player in enumerate(setup["players"]):
        lines += ["", "[[cars]]", f'team = {player["team"]}']
        if player["kind"] == "human":
            lines.append('type = "Human"')
        elif player["kind"] == "psyonix":
            lines += ['type = "Psyonix"', f'skill = {json.dumps(player["skill"])}']
        else:
            source = Path(bot_paths[player["id"]]).expanduser().resolve()
            # An rlbot.cfg or match.toml describes a *whole match*, not a player.
            # Those should be launched through the dedicated match-import command.
            if source.is_file():
                lowered = source.name.lower()
                if lowered == "rlbot.cfg":
                    raise ValueError("A complete rlbot.cfg is not a single bot. Import its bot.cfg, or run evilrlbot-v4cfg.")
                if source.suffix == ".toml" and "[[cars]]" in source.read_text(errors="replace"):
                    raise ValueError("A match.toml is a complete match. Import a bot.toml instead.")
            part_root = match_root / f"player_{idx}"
            part_root.mkdir()
            resolved_match = resolve(source, detect_bot(source), part_root, player["team"], setup["map"], setup["mode"])
            with resolved_match.open("rb") as f:
                generated = tomllib.load(f)
            configs = [p.get("config_file") for p in generated.get("cars", []) if p.get("config_file")]
            if len(configs) != 1:
                raise ValueError(f"Expected one bot config for {source}, got {len(configs)}")
            agent_file = _v5_with_deps(source, Path(configs[0]).resolve(), part_root)
            lines += ['type = "RLBot"', f'config_file = {json.dumps(str(agent_file))}', "auto_start = true"]
    match_file = match_root / "match.toml"
    match_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return match_file
