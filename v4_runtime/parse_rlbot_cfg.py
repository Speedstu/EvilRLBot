#!/usr/bin/env python3
"""Parse an RLBot v4 rlbot.cfg using the real RLBot 1.68.0 parser and emit JSON."""
from __future__ import annotations

import configparser
import json
import sys
from pathlib import Path

from rlbot.matchconfig.conversions import read_match_config_from_file
from rlbot.parsing.match_settings_config_parser import game_map_dict


def load(path: Path):
    match = read_match_config_from_file(path)

    raw = configparser.RawConfigParser()
    raw.read(path, encoding="utf-8")
    launcher_pref = None
    if raw.has_section("RLBot Configuration"):
        launcher_pref = raw.get("RLBot Configuration", "launcher_preference", fallback=None)
        if launcher_pref in ("", "None", "none"):
            launcher_pref = None

    players = []
    for p in match.player_configs:
        if p.rlbot_controlled and p.bot:
            kind = "rlbot"
        elif p.rlbot_controlled and not p.bot:
            kind = "party_member_bot"
        elif p.bot:
            kind = "psyonix"
        else:
            kind = "human"
        players.append({
            "name": p.name,
            "team": int(p.team),
            "kind": kind,
            "bot_skill": float(p.bot_skill or 0.0),
            "config_path": str(Path(p.config_path).resolve()) if p.config_path else None,
            "spawn_id": int(p.spawn_id),
        })

    mut = match.mutators
    mutators = {
        "match_length": mut.match_length,
        "max_score": mut.max_score,
        "overtime": mut.overtime,
        "series_length": mut.series_length,
        "game_speed": mut.game_speed,
        "ball_max_speed": mut.ball_max_speed,
        "ball_type": mut.ball_type,
        "ball_weight": mut.ball_weight,
        "ball_size": mut.ball_size,
        "ball_bounciness": mut.ball_bounciness,
        "boost_amount": mut.boost_amount,
        "rumble": mut.rumble,
        "boost_strength": mut.boost_strength,
        "gravity": mut.gravity,
        "demolish": mut.demolish,
        "respawn_time": mut.respawn_time,
    }

    game_map = match.game_map
    return {
        "source": str(path.resolve()),
        "launcher_preference": launcher_pref,
        "game_mode": match.game_mode,
        "game_map": game_map,
        "game_map_upk": game_map_dict.get(game_map, game_map),
        "skip_replays": bool(match.skip_replays),
        "start_without_countdown": bool(match.instant_start),
        "existing_match_behavior": match.existing_match_behavior,
        "enable_rendering": bool(match.enable_rendering),
        "enable_state_setting": bool(match.enable_state_setting),
        "auto_save_replay": bool(match.auto_save_replay),
        "enable_lockstep": bool(match.enable_lockstep),
        "networking_role": match.networking_role,
        "network_address": match.network_address,
        "mutators": mutators,
        "players": players,
        "scripts": [str(Path(s.config_path).resolve()) for s in match.script_configs],
        "extension": (
            str(Path(match.extension_config.python_file_path).resolve())
            if match.extension_config and match.extension_config.python_file_path else None
        ),
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: parse_rlbot_cfg.py <rlbot.cfg>")
    print(json.dumps(load(Path(sys.argv[1])), separators=(",", ":")))


if __name__ == "__main__":
    main()
