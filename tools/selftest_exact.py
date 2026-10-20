#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import time
from multiprocessing.connection import Listener
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rlbot import flat
from rlbot.config import load_match_config
from src.v5_bridge import AUTHKEY, _field_to_v4_data, _packet_to_v4_data, _prediction_to_v4_data


def check_real_v4():
    code = (
        "import rlbot,ctypes;"
        "from rlbot.agents.base_agent import BaseAgent,SimpleControllerState;"
        "from rlbot.utils.structures.game_data_struct import GameTickPacket;"
        "print(rlbot.__file__);print(ctypes.sizeof(GameTickPacket))"
    )
    out = subprocess.check_output([str(ROOT / ".venv-v4/bin/python"), "-c", code], text=True)
    assert ".venv-v4" in out
    assert "17384" in out


def match_data():
    keys = [
        "match_length", "max_score", "overtime", "series_length", "game_speed",
        "ball_max_speed", "ball_type", "ball_weight", "ball_size",
        "ball_bounciness", "boost_amount", "rumble", "boost_strength",
        "gravity", "demolish", "respawn_time",
    ]
    return {
        "game_mode": 0,
        "game_map": "Stadium_P",
        "skip_replays": True,
        "instant_start": False,
        "existing_match_behavior": 2,
        "enable_rendering": True,
        "enable_state_setting": True,
        "auto_save_replay": False,
        "mutators": {key: 0 for key in keys},
    }


def check_exact_v4_worker():
    sock = f"/tmp/evilrlbot-selftest-{os.getpid()}.sock"
    try:
        os.unlink(sock)
    except FileNotFoundError:
        pass

    listener = Listener(sock, family="AF_UNIX", authkey=AUTHKEY)
    worker = subprocess.Popen(
        [str(ROOT / ".venv-v4/bin/python"), str(ROOT / "v4_runtime/worker.py"), sock],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    conn = listener.accept()

    field = flat.FieldInfo(
        boost_pads=[flat.BoostPad(flat.Vector3(0, 0, 70), True)],
        goals=[flat.GoalInfo(0, flat.Vector3(0, -5120, 321), flat.Vector3(0, 1, 0), 1786, 642)],
    )
    conn.send({
        "type": "init",
        "project_root": str(ROOT),
        "module": "unused",
        "class": None,
        "bot_config": str(ROOT / "tests/v4_probe/bot.cfg"),
        "name": "Exact V4 Probe",
        "team": 0,
        "index": 0,
        "spawn_id": 123,
        "field_info": _field_to_v4_data(field),
        "match": match_data(),
    })
    ready = conn.recv()
    assert ready["type"] == "ready"
    assert ready["rlbot_v4"] == "1.68.0"
    assert Path(ready["python_file"]).name == "bot.py"
    assert ready["loadout"]["car_id"] == 23

    packet = flat.GamePacket(
        players=[flat.PlayerInfo(
            physics=flat.Physics(flat.Vector3(0, 0, 17), flat.Rotator(), flat.Vector3(), flat.Vector3()),
            name="Exact V4 Probe",
            team=0,
            boost=100,
            player_id=123,
            air_state=flat.AirState.OnGround,
        )],
        boost_pads=[flat.BoostPadState(True, 0)],
        balls=[flat.BallInfo(
            physics=flat.Physics(flat.Vector3(1000, 100, 93), flat.Rotator(), flat.Vector3(), flat.Vector3())
        )],
        match_info=flat.MatchInfo(
            seconds_elapsed=1,
            game_time_remaining=299,
            match_phase=flat.MatchPhase.Active,
            world_gravity_z=-650,
            game_speed=1,
            frame_num=120,
        ),
        teams=[flat.TeamInfo(0, 0), flat.TeamInfo(1, 0)],
        tiles=[],
    )
    prediction = flat.BallPrediction([
        flat.PredictionSlice(
            1.5,
            flat.Physics(flat.Vector3(1200, 150, 93), flat.Rotator(), flat.Vector3(), flat.Vector3()),
        )
    ])

    conn.send({
        "type": "tick",
        "packet": _packet_to_v4_data(packet),
        "prediction": _prediction_to_v4_data(prediction),
        "matchcomms": [{"incoming": "ok"}],
        "quick_chats": [(9, 1, 9)],
    })
    result = conn.recv()
    assert result["type"] == "tick_result", result
    assert result["controller"][0] == 0.75
    assert result["controller"][1] == -0.25
    assert result["controller"][6] is True
    action_kinds = {x[0] for x in result["actions"]}
    assert {"quick_chat", "matchcomm", "game_state"} <= action_kinds
    assert [x[0] for x in result["renders"]] == ["begin", "line3d", "string3d", "end"]

    conn.send({"type": "retire"})
    assert conn.recv()["type"] == "retired"
    conn.close()
    listener.close()
    worker.wait(timeout=3)
    if worker.returncode != 0:
        raise RuntimeError(worker.stdout.read())
    try:
        os.unlink(sock)
    except FileNotFoundError:
        pass


def check_v4_rlbot_cfg_translation():
    subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "tools/v4cfg_to_v5.py"),
            str(ROOT / "legacy_bot/rlbot.cfg"),
            "--generate-only",
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    match = load_match_config(ROOT / ".generated/v4cfg/match.toml")
    assert len(match.player_configurations) == 2
    assert str(match.game_mode).endswith("Soccar")
    assert match.game_map_upk == "Stadium_P"
    assert type(match.player_configurations[0].variety).__name__ == "Human"
    assert type(match.player_configurations[1].variety).__name__ == "CustomBot"


def check_native_v5_server():
    port = 23991
    server = subprocess.Popen(
        [str(ROOT / "RLBotServer"), str(port)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        time.sleep(0.35)
        assert server.poll() is None
        env = os.environ.copy()
        env.update({
            "RLBOT_SERVER_IP": "127.0.0.1",
            "RLBOT_SERVER_PORT": str(port),
            "RLBOT_AGENT_ID": "evilrlbot/selftest",
        })
        bridge = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), str(ROOT / "src/v5_bridge.py")],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            time.sleep(0.6)
            assert bridge.poll() is None
        finally:
            bridge.terminate()
            try:
                bridge.wait(timeout=2)
            except subprocess.TimeoutExpired:
                bridge.kill()
    finally:
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()


def main():
    check_real_v4()
    check_exact_v4_worker()
    check_v4_rlbot_cfg_translation()
    check_native_v5_server()
    print("EvilRLBot exact-v4 self-test: PASS")
    print("frontend: real rlbot 1.68.0")
    print("bot config: real v4 .cfg parser + custom [Bot Parameters]")
    print("packet/controller: real v4 ctypes + SimpleControllerState")
    print("v4 APIs: field info, prediction, rendering, quick-chat, matchcomms, GameState")
    print("match config: legacy rlbot.cfg -> RLBot v5 MatchConfiguration")
    print("engine: native Linux RLBotServer v5 socket path")


if __name__ == "__main__":
    main()
