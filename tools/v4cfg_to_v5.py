#!/usr/bin/env python3
"""Translate a legacy RLBot v4 rlbot.cfg into a transient RLBot v5 match config."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V4_PY = ROOT / ".venv-v4" / "bin" / "python"
V4_PARSER = ROOT / "v4_runtime" / "parse_rlbot_cfg.py"
V5_PY = ROOT / ".venv" / "bin" / "python"
V5_BRIDGE = ROOT / "src" / "v5_bridge.py"
RUNNER = ROOT / "run.py"


def q(value: str) -> str:
    return json.dumps(str(value))


MATCH_MAP = {
    "5 Minutes": "FiveMinutes",
    "10 Minutes": "TenMinutes",
    "20 Minutes": "TwentyMinutes",
    "Unlimited": "Unlimited",
}
MAX_SCORE_MAP = {
    "Unlimited": "Unlimited",
    "1 Goal": "OneGoal",
    "3 Goals": "ThreeGoals",
    "5 Goals": "FiveGoals",
}
OVERTIME_MAP = {
    "Unlimited": "Unlimited",
    "+5 Max, First Score": "FiveMaxFirstScore",
    "+5 Max, Random Team": "FiveMaxRandomTeam",
}
SERIES_MAP = {
    "Unlimited": "Unlimited",
    "3 Games": "ThreeGames",
    "5 Games": "FiveGames",
    "7 Games": "SevenGames",
}
GAME_SPEED_MAP = {"Default": "Default", "Slo-Mo": "SloMo", "Time Warp": "TimeWarp"}
BALL_MAX_MAP = {"Default": "Default", "Slow": "Slow", "Fast": "Fast", "Super Fast": "SuperFast"}
BALL_TYPE_MAP = {"Default": "Default", "Cube": "Cube", "Puck": "Puck", "Basketball": "Basketball"}
BALL_WEIGHT_MAP = {"Default": "Default", "Light": "Light", "Heavy": "Heavy", "Super Light": "SuperLight"}
BALL_SIZE_MAP = {"Default": "Default", "Small": "Small", "Large": "Large", "Gigantic": "Gigantic"}
BALL_BOUNCE_MAP = {"Default": "Default", "Low": "Low", "High": "High", "Super High": "SuperHigh"}
BOOST_AMOUNT_MAP = {
    "Default": "NormalBoost",
    "Unlimited": "UnlimitedBoost",
    "Recharge (Slow)": "SlowRecharge",
    "Recharge (Fast)": "RapidRecharge",
    "No Boost": "NoBoost",
}
RUMBLE_MAP = {
    "None": "Off",
    "Default": "DefaultRumble",
    "Slow": "Slow",
    "Civilized": "Civilized",
    "Destruction Derby": "DestructionDerby",
    "Spring Loaded": "SpringLoaded",
    "Spikes Only": "SpikesOnly",
    "Spike Rush": "SpikeRush",
}
BOOST_STRENGTH_MAP = {"1x": "One", "1.5x": "OneAndAHalf", "2x": "Two", "10x": "Ten"}
GRAVITY_MAP = {"Default": "Default", "Low": "Low", "High": "High", "Super High": "SuperHigh"}
DEMOLISH_MAP = {
    "Default": "Default",
    "Disabled": "Disabled",
    "Friendly Fire": "FriendlyFire",
    "On Contact": "OnContact",
    "On Contact (FF)": "OnContactFf",
}
RESPAWN_MAP = {
    "3 Seconds": "ThreeSeconds",
    "2 Seconds": "TwoSeconds",
    "1 Second": "OneSecond",
    "Disable Goal Reset": "DisableGoalReset",
}

MUTATOR_MAPS = {
    "match_length": MATCH_MAP,
    "max_score": MAX_SCORE_MAP,
    "overtime": OVERTIME_MAP,
    "series_length": SERIES_MAP,
    "game_speed": GAME_SPEED_MAP,
    "ball_max_speed": BALL_MAX_MAP,
    "ball_type": BALL_TYPE_MAP,
    "ball_weight": BALL_WEIGHT_MAP,
    "ball_size": BALL_SIZE_MAP,
    "ball_bounciness": BALL_BOUNCE_MAP,
    "boost_amount": BOOST_AMOUNT_MAP,
    "rumble": RUMBLE_MAP,
    "boost_strength": BOOST_STRENGTH_MAP,
    "gravity": GRAVITY_MAP,
    "demolish": DEMOLISH_MAP,
    "respawn_time": RESPAWN_MAP,
}


def parse_v4(path: Path) -> dict:
    result = subprocess.run(
        [str(V4_PY), str(V4_PARSER), str(path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("v4 parser produced no output")
    return json.loads(lines[-1])


def v5_skill(value: float) -> str:
    if value < 0.25:
        return "Rookie"
    if value < 0.75:
        return "Pro"
    return "AllStar"


def make_agent(out_dir: Path, index: int, player: dict) -> str:
    player_dir = out_dir / f"player{index}"
    player_dir.mkdir(parents=True, exist_ok=True)
    config_path = Path(player["config_path"]).resolve()

    wrapper = player_dir / "run.sh"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"export EVILRLBOT_V4_CONFIG={q(str(config_path))}\n"
        f"exec {q(str(V5_PY))} {q(str(V5_BRIDGE))}\n"
    )
    wrapper.chmod(0o755)

    agent_id = f"evilrlbot/v4cfg-{index}"
    agent = player_dir / "agent.toml"
    agent.write_text(
        "#:schema https://rlbot.org/schemas/agent.json\n"
        "[settings]\n"
        f"name = {q(player.get('name') or f'v4 bot {index}')}\n"
        'root_dir = ""\n'
        'run_command = "./run.sh"\n'
        'run_command_linux = "./run.sh"\n'
        f"agent_id = {q(agent_id)}\n"
        'logo_file = ""\n\n'
        "[details]\n"
        'description = "RLBot v4 frontend bridged to RLBot v5 by EvilRLBot"\n'
        'fun_fact = "The bot process runs RLBot 1.68.0"\n'
        'developer = "EvilRLBot bridge"\n'
        'language = "Python"\n'
        'tags = []\n'
    )
    return str(agent.relative_to(out_dir))


def build(cfg_path: Path) -> Path:
    data = parse_v4(cfg_path)
    out_dir = ROOT / ".generated" / "v4cfg"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    launcher_pref = (data.get("launcher_preference") or "steam").lower()
    launcher = "Epic" if launcher_pref == "epic" else "Steam"

    game_mode = {"Soccer": "Soccar", "Hockey": "Snowday"}.get(data["game_mode"], data["game_mode"])
    existing = {
        "Restart If Different": "RestartIfDifferent",
        "Restart": "Restart",
        "Continue And Spawn": "ContinueAndSpawn",
    }.get(data["existing_match_behavior"], "RestartIfDifferent")

    lines = [
        "# Generated by EvilRLBot from a real RLBot v4 rlbot.cfg",
        "[rlbot]",
        f"launcher = {q(launcher)}",
        "auto_start_agents = true",
        "wait_for_agents = true",
        "",
        "[match]",
        f"game_mode = {q(game_mode)}",
        f"game_map_upk = {q(data['game_map_upk'])}",
        f"skip_replays = {str(bool(data['skip_replays'])).lower()}",
        f"instant_start = {str(bool(data['start_without_countdown'])).lower()}",
        f"existing_match_behavior = {q(existing)}",
        f"enable_rendering = {str(bool(data['enable_rendering'])).lower()}",
        f"enable_state_setting = {str(bool(data['enable_state_setting'])).lower()}",
        "freeplay = false",
        "",
        "[mutators]",
    ]

    for key, mapping in MUTATOR_MAPS.items():
        old = data["mutators"].get(key)
        if old is not None:
            new = mapping.get(old)
            if new is None:
                raise ValueError(f"Cannot map v4 mutator {key}={old!r} to v5")
            lines.append(f"{key} = {q(new)}")

    for index, player in enumerate(data["players"]):
        kind = player["kind"]
        lines += ["", "[[cars]]"]
        if kind in ("rlbot", "party_member_bot"):
            rel_agent = make_agent(out_dir, index, player)
            lines.append(f"config_file = {q(rel_agent)}")
            lines.append(f"team = {int(player['team'])}")
            lines.append("auto_start = true")
            if kind == "party_member_bot":
                print(
                    f"warning: participant {index} uses v4 party_member_bot; "
                    "v5 has no identical player variety, using an RLBot-controlled car",
                    file=sys.stderr,
                )
        elif kind == "psyonix":
            lines.append('type = "Psyonix"')
            lines.append(f"team = {int(player['team'])}")
            lines.append(f"skill = {q(v5_skill(float(player['bot_skill'])))}")
            if player.get("name"):
                lines.append(f"name = {q(player['name'])}")
        elif kind == "human":
            lines.append('type = "Human"')
            lines.append(f"team = {int(player['team'])}")
        else:
            raise ValueError(f"Unsupported v4 participant type: {kind}")

    if data.get("scripts"):
        print(
            "warning: legacy [Scripts] entries are parsed but not yet launched by the v4->v5 bridge",
            file=sys.stderr,
        )
    if data.get("extension"):
        print(
            "warning: legacy RLBot v4 extension_path is parsed but v5 does not have an identical extension hook",
            file=sys.stderr,
        )
    if data.get("enable_lockstep"):
        print(
            "warning: v4 enable_lockstep has no direct RLBot v5 match-config equivalent",
            file=sys.stderr,
        )

    match_toml = out_dir / "match.toml"
    match_toml.write_text("\n".join(lines) + "\n")
    (out_dir / "source.json").write_text(json.dumps(data, indent=2))
    return match_toml


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: evilrlbot-v4cfg <rlbot.cfg> [--generate-only]")
    cfg = Path(sys.argv[1]).expanduser().resolve()
    if not cfg.is_file():
        raise SystemExit(f"not found: {cfg}")
    match = build(cfg)
    print(f"EvilRLBot generated v5 match: {match}")
    if "--generate-only" not in sys.argv[2:]:
        os.execv(str(V5_PY), [str(V5_PY), str(RUNNER), str(match)])


if __name__ == "__main__":
    main()
