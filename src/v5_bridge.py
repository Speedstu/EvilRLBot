#!/usr/bin/env python3
"""RLBot v5 engine bridge for an exact RLBot v4 bot runtime."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from multiprocessing.connection import Listener
from pathlib import Path

from rlbot import flat
from rlbot.managers import Bot

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.detection import detect_bot

AUTHKEY = b"evilrlbot-v4-v5"


def _vec(v):
    if v is None:
        return (0.0, 0.0, 0.0)
    return (float(v.x), float(v.y), float(v.z))


def _rot(r):
    if r is None:
        return (0.0, 0.0, 0.0)
    return (float(r.pitch), float(r.yaw), float(r.roll))


def _physics(p):
    if p is None:
        return {
            "location": (0.0, 0.0, 0.0),
            "rotation": (0.0, 0.0, 0.0),
            "velocity": (0.0, 0.0, 0.0),
            "angular_velocity": (0.0, 0.0, 0.0),
        }
    return {
        "location": _vec(p.location),
        "rotation": _rot(p.rotation),
        "velocity": _vec(p.velocity),
        "angular_velocity": _vec(p.angular_velocity),
    }


def _enum_name(value):
    text = str(value)
    return text.rsplit(".", 1)[-1]


def _score(score):
    if score is None:
        return {}
    return {
        "score": int(score.score),
        "goals": int(score.goals),
        "own_goals": int(score.own_goals),
        "assists": int(score.assists),
        "saves": int(score.saves),
        "shots": int(score.shots),
        "demolitions": int(score.demolitions),
    }


def _shape(shape):
    if isinstance(shape, flat.BoxShape):
        return {
            "type": 0,
            "length": float(shape.length),
            "width": float(shape.width),
            "height": float(shape.height),
            "diameter": 0.0,
        }
    if isinstance(shape, flat.SphereShape):
        return {
            "type": 1,
            "length": 0.0,
            "width": 0.0,
            "height": 0.0,
            "diameter": float(shape.diameter),
        }
    if isinstance(shape, flat.CylinderShape):
        return {
            "type": 2,
            "length": 0.0,
            "width": 0.0,
            "height": float(shape.height),
            "diameter": float(shape.diameter),
        }
    return {"type": 1, "length": 0.0, "width": 0.0, "height": 0.0, "diameter": 0.0}


def _latest_touch(packet, ball_index=0):
    best = None
    best_index = -1
    for i, player in enumerate(packet.players):
        touch = player.latest_touch
        if touch is None or int(touch.ball_index) != ball_index:
            continue
        if best is None or touch.game_seconds > best.game_seconds:
            best = touch
            best_index = i
    if best is None:
        return {
            "player_name": "",
            "time_seconds": 0.0,
            "hit_location": (0.0, 0.0, 0.0),
            "hit_normal": (0.0, 0.0, 0.0),
            "team": 0,
            "player_index": -1,
        }
    player = packet.players[best_index]
    return {
        "player_name": player.name or "",
        "time_seconds": float(best.game_seconds),
        "hit_location": _vec(best.location),
        "hit_normal": _vec(best.normal),
        "team": int(player.team),
        "player_index": best_index,
    }


def _controller_data(c):
    if c is None:
        return {"throttle": 0.0, "steer": 0.0, "pitch": 0.0, "yaw": 0.0, "roll": 0.0,
                "jump": False, "boost": False, "handbrake": False, "use_item": False}
    return {"throttle": float(c.throttle), "steer": float(c.steer), "pitch": float(c.pitch),
            "yaw": float(c.yaw), "roll": float(c.roll), "jump": bool(c.jump),
            "boost": bool(c.boost), "handbrake": bool(c.handbrake), "use_item": bool(c.use_item)}


def _touch_data(touch):
    if touch is None:
        return None
    return {"ball_index": int(touch.ball_index), "game_seconds": float(touch.game_seconds),
            "location": _vec(touch.location), "normal": _vec(touch.normal)}


def _safe_enum_value(value):
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return str(value)


def _packet_to_v4_data(packet):
    cars = []
    v5_players = []
    for player in packet.players:
        hb = player.hitbox
        base = {
            "physics": _physics(player.physics), "score_info": _score(player.score_info),
            "is_demolished": float(player.demolished_timeout) > 0.0,
            "has_wheel_contact": player.air_state == flat.AirState.OnGround,
            "is_super_sonic": bool(player.is_supersonic), "is_bot": bool(player.is_bot),
            "jumped": bool(player.has_jumped), "double_jumped": bool(player.has_double_jumped),
            "name": player.name or "", "team": int(player.team), "boost": float(player.boost),
            "hitbox": (float(getattr(hb, "length", 0.0)), float(getattr(hb, "width", 0.0)), float(getattr(hb, "height", 0.0))),
            "hitbox_offset": _vec(player.hitbox_offset), "spawn_id": int(player.player_id),
        }
        cars.append(base)
        v5_players.append({
            **base, "player_id": int(player.player_id),
            "demolished_timeout": float(player.demolished_timeout),
            "air_state": _safe_enum_value(player.air_state), "is_supersonic": bool(player.is_supersonic),
            "has_jumped": bool(player.has_jumped), "has_double_jumped": bool(player.has_double_jumped),
            "has_dodged": bool(player.has_dodged), "dodge_elapsed": float(player.dodge_elapsed),
            "dodge_timeout": float(player.dodge_timeout),
            "dodge_dir": (float(player.dodge_dir.x), float(player.dodge_dir.y)) if player.dodge_dir is not None else (0.0, 0.0),
            "last_input": _controller_data(player.last_input), "latest_touch": _touch_data(player.latest_touch),
            "accolades": [str(x) for x in (player.accolades or [])],
            "rumble_item": _safe_enum_value(player.rumble_item),
            "time_until_next_item": float(player.time_until_next_item),
            "max_time_until_next_item": float(player.max_time_until_next_item),
        })

    boosts = [(bool(b.is_active), float(b.timer)) for b in packet.boost_pads]
    v5_balls = [{"physics": _physics(b.physics), "shape": _shape(b.shape),
                 "charge_level": float(b.charge_level), "target_speed": float(b.target_speed)} for b in packet.balls]

    if packet.balls:
        b = packet.balls[0]
        ball = {"physics": _physics(b.physics), "latest_touch": _latest_touch(packet, 0),
                "drop_shot_info": {"absorbed_force": 0.0, "damage_index": 0, "force_accum_recent": 0.0},
                "collision_shape": _shape(b.shape), "charge_level": float(b.charge_level),
                "target_speed": float(b.target_speed)}
    else:
        ball = {"physics": _physics(None), "latest_touch": _latest_touch(packet, 0), "drop_shot_info": {},
                "collision_shape": _shape(None), "charge_level": 0.0, "target_speed": 0.0}

    mi = packet.match_info
    phase = mi.match_phase
    game_info = {"seconds_elapsed": float(mi.seconds_elapsed), "game_time_remaining": float(mi.game_time_remaining),
                 "is_overtime": bool(mi.is_overtime), "is_unlimited_time": bool(mi.is_unlimited_time),
                 "is_round_active": phase in (flat.MatchPhase.Kickoff, flat.MatchPhase.Active, flat.MatchPhase.Paused),
                 "is_kickoff_pause": phase == flat.MatchPhase.Kickoff, "is_match_ended": phase == flat.MatchPhase.Ended,
                 "world_gravity_z": float(mi.world_gravity_z), "game_speed": float(mi.game_speed), "frame_num": int(mi.frame_num)}
    v5_match_info = {**game_info, "match_phase": _safe_enum_value(mi.match_phase), "last_spectated": int(mi.last_spectated)}
    teams = [(int(t.team_index), int(t.score)) for t in packet.teams]
    tiles = [0 for _ in packet.tiles]
    v5_tiles = [{"location": _vec(t.location), "team": int(t.team)} for t in packet.tiles]

    return {"cars": cars, "boosts": boosts, "ball": ball, "game_info": game_info,
            "teams": teams, "tiles": tiles,
            "v5": {"players": v5_players,
                   "boost_pads": [{"is_active": bool(b.is_active), "timer": float(b.timer)} for b in packet.boost_pads],
                   "balls": v5_balls, "match_info": v5_match_info,
                   "teams": [{"team_index": int(t.team_index), "score": int(t.score)} for t in packet.teams],
                   "tiles": v5_tiles}}

def _field_to_v4_data(field):
    return {
        "boost_pads": [(_vec(p.location), bool(p.is_full_boost)) for p in field.boost_pads],
        "goals": [
            {
                "team_num": int(g.team_num),
                "location": _vec(g.location),
                "direction": _vec(g.direction),
                "width": float(g.width),
                "height": float(g.height),
            }
            for g in field.goals
        ],
    }


def _prediction_to_v4_data(prediction):
    return {
        "slices": [
            {"game_seconds": float(s.game_seconds), "physics": _physics(s.physics)}
            for s in prediction.slices
        ]
    }


def _match_to_v4_data(match):
    mode = int(match.game_mode)
    mut = match.mutators

    fields = (
        "match_length", "max_score", "overtime", "series_length", "game_speed",
        "ball_max_speed", "ball_type", "ball_weight", "ball_size", "ball_bounciness",
        "boost_amount", "rumble", "boost_strength", "gravity", "demolish", "respawn_time",
    )
    mutators = {}
    for field in fields:
        value = getattr(mut, field, None) if mut is not None else None
        mutators[field] = int(value) if value is not None else None

    players = []
    for p in match.player_configurations:
        name = ""
        variety = p.variety
        if hasattr(variety, "name"):
            name = variety.name or ""
        players.append({"name": name, "team": int(p.team), "spawn_id": int(p.player_id)})

    return {
        "game_mode": mode,
        "game_map": match.game_map_upk or "Stadium_P",
        "skip_replays": bool(match.skip_replays),
        "instant_start": bool(match.instant_start),
        "existing_match_behavior": int(match.existing_match_behavior),
        "enable_rendering": _enum_name(match.enable_rendering) != "AlwaysOff",
        "enable_state_setting": bool(match.enable_state_setting),
        "auto_save_replay": bool(match.auto_save_replay),
        "mutators": mutators,
        "players": players,
    }


def _color(c):
    return flat.Color(int(c[0]), int(c[1]), int(c[2]), int(c[3]))


def _v3(v):
    return flat.Vector3(float(v[0]), float(v[1]), float(v[2]))


def _partial_vec(v):
    if v is None:
        return None
    return flat.Vector3Partial(v[0], v[1], v[2])


def _partial_rot(v):
    if v is None:
        return None
    return flat.RotatorPartial(v[0], v[1], v[2])


def _desired_physics(data):
    if data is None:
        return None
    return flat.DesiredPhysics(
        _partial_vec(data.get("location")),
        _partial_rot(data.get("rotation")),
        _partial_vec(data.get("velocity")),
        _partial_vec(data.get("angular_velocity")),
    )



def _loadout_from_v4(data):
    if not data:
        return None
    paint = data.get("paint") or {}
    return flat.PlayerLoadout(
        team_color_id=data.get("team_color_id", 0),
        custom_color_id=data.get("custom_color_id", 0),
        car_id=data.get("car_id", 0),
        decal_id=data.get("decal_id", 0),
        wheels_id=data.get("wheels_id", 0),
        boost_id=data.get("boost_id", 0),
        antenna_id=data.get("antenna_id", 0),
        hat_id=data.get("hat_id", 0),
        paint_finish_id=data.get("paint_finish_id", 0),
        custom_finish_id=data.get("custom_finish_id", 0),
        engine_audio_id=data.get("engine_audio_id", 0),
        trails_id=data.get("trails_id", 0),
        goal_explosion_id=data.get("goal_explosion_id", 0),
        loadout_paint=flat.LoadoutPaint(
            car_paint_id=paint.get("car_paint_id", 0),
            decal_paint_id=paint.get("decal_paint_id", 0),
            wheels_paint_id=paint.get("wheels_paint_id", 0),
            boost_paint_id=paint.get("boost_paint_id", 0),
            antenna_paint_id=paint.get("antenna_paint_id", 0),
            hat_paint_id=paint.get("hat_paint_id", 0),
            trails_paint_id=paint.get("trails_paint_id", 0),
            goal_explosion_paint_id=paint.get("goal_explosion_paint_id", 0),
        ),
        primary_color_lookup=data.get("primary_color_lookup"),
        secondary_color_lookup=data.get("secondary_color_lookup"),
    )


QUICK_CHAT_TEXT = {
    0: "I got it!", 1: "Need boost!", 2: "Take the shot!", 3: "Defending...", 4: "Go for it!",
    5: "Centering!", 6: "All yours.", 7: "In position.", 8: "Incoming!", 9: "Nice shot!",
    10: "Great pass!", 11: "Thanks!", 12: "What a save!", 13: "Nice one!", 14: "What a play!",
    15: "Great clear!", 16: "Nice block!", 17: "OMG!", 18: "Noooo!", 19: "Wow!",
    20: "Close one!", 21: "No way!", 22: "Holy cow!", 23: "Whew.", 24: "Siiiick!",
    25: "Calculated.", 26: "Savage!", 27: "Okay.", 28: "@#$%!", 29: "No problem.",
    30: "Whoops...", 31: "Sorry!", 32: "My bad...", 33: "Oops!", 34: "My fault.",
    35: "gg", 36: "Well played.", 37: "That was fun!", 38: "Rematch!", 39: "One. More. Game.",
    40: "What a game!", 41: "Nice moves.", 42: "Everybody dance!",
}


class EvilV4Bridge(Bot):
    def __init__(self, default_agent_id=None):
        super().__init__(default_agent_id or "evilrlbot/evil_v4_exact")
        self._listener = None
        self._conn = None
        self._worker = None
        self._worker_log = None
        self._ipc_path = None
        self._last_controller = flat.ControllerState()
        self._incoming_matchcomms = []
        self._incoming_quick_chats = []
        self._timings = []
        self._prediction_requests = 0

    def _worker_failure(self, context, log_path):
        code = self._worker.poll() if self._worker is not None else None
        tail = "(worker log missing)"
        try:
            with Path(log_path).open("rb") as log:
                log.seek(max(0, log.seek(0, os.SEEK_END) - 13000))
                tail = log.read().decode("utf-8", "replace")[-3500:]
        except OSError:
            pass
        return f"{context}; worker exit code={code}.\nV4 worker log: {log_path}\n{tail}"

    def initialize(self):
        logs = ROOT / "logs"
        logs.mkdir(exist_ok=True)
        self._ipc_path = f"/tmp/evilrlbot-{os.getpid()}-{self.player_id}.sock"
        try:
            os.unlink(self._ipc_path)
        except FileNotFoundError:
            pass

        self._listener = Listener(self._ipc_path, family="AF_UNIX", authkey=AUTHKEY)
        try:
            self._listener._listener._socket.settimeout(12.0)
        except Exception:
            pass

        module = os.environ.get("EVILRLBOT_V4_MODULE", "legacy_bot.bot")
        class_name = os.environ.get("EVILRLBOT_V4_CLASS") or None
        bot_config = os.environ.get("EVILRLBOT_V4_CONFIG") or str(ROOT / "legacy_bot" / "bot.cfg")
        if not Path(bot_config).is_file():
            bot_config = None
        detection_target = Path(bot_config) if bot_config else ROOT / "legacy_bot"
        self._profile = detect_bot(detection_target)
        self.logger.info(
            "EvilRLBot detection: framework=%s obs=%s action=%s tick_skip=%s model=%s",
            self._profile.get("framework"),
            self._profile.get("observation"),
            self._profile.get("action_parser"),
            self._profile.get("tick_skip"),
            self._profile.get("model_runtime"),
        )
        log_path = logs / f"v4-worker-{self.index}.log"
        self._worker_log = open(log_path, "ab", buffering=0)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        # Prefer a working host Python with ABI-compatible native packages.
        from ui.host_python import select_python, bundled_python
        from ui.bot_importer import discover, dependency_path, usable_torch_path
        from ui.preflight import _required_modules, _requirement_specs
        source = Path(env.get("EVILRLBOT_V4_SOURCE") or bot_config or
                      str(ROOT / "legacy_bot/bot.cfg")).resolve()
        candidates = discover(source)
        candidate = next((c for c in candidates if c.path.resolve() == source),
                         candidates[0] if candidates else None)
        modules = tuple(_required_modules(source, candidate)) if candidate else ()
        specs = tuple(_requirement_specs(candidate.requirements)) if candidate else ()
        dep = dependency_path(source)
        torch_layer = usable_torch_path(source)
        selected = select_python("rlbot-v4", modules, specs,
                                 str(dep) if dep.is_dir() else "",
                                 str(torch_layer) if torch_layer else "")
        if not selected.okay:
            raise RuntimeError(f"No compatible Python for V4 bot: {selected.error}")
        if selected.framework_site:
            env["EVILRLBOT_V4_FRAMEWORK_SITE"] = str(selected.framework_site)
        else:
            env.pop("EVILRLBOT_V4_FRAMEWORK_SITE", None)
        self.logger.info("V4 worker using Python: %s", selected.python)
        self._worker = subprocess.Popen(
            [
                str(selected.python),
                *(["-I"] if selected.python.resolve() == bundled_python("rlbot-v4").resolve() else []),
                str(ROOT / "v4_runtime" / "worker.py"),
                self._ipc_path,
            ],
            cwd=ROOT,
            env=env,
            stdout=self._worker_log,
            stderr=subprocess.STDOUT,
        )

        try:
            self._conn = self._listener.accept()
        except Exception:
            if self._worker.poll() is not None:
                raise RuntimeError(self._worker_failure("V4 worker exited before opening IPC socket", log_path))
            raise

        self._conn.send({
            "type": "init",
            "project_root": str(ROOT),
            "module": module,
            "class": class_name,
            "bot_config": bot_config,
            "v4_config": os.environ.get("EVILRLBOT_V4_CONFIG") or None,
            "python_file": os.environ.get("EVILRLBOT_V4_PYTHON_FILE") or None,
            "name": self.name,
            "team": self.team,
            "index": self.index,
            "spawn_id": self.player_id,
            "profile": self._profile,
            "field_info": _field_to_v4_data(self.field_info),
            "match": _match_to_v4_data(self.match_config),
        })

        if not self._conn.poll(25.0):
            raise RuntimeError(self._worker_failure("RLBot v4 worker initialization timed out", log_path))
        try:
            answer = self._conn.recv()
        except EOFError as exc:
            raise RuntimeError(self._worker_failure("V4 worker disconnected during initialization", log_path)) from exc
        if answer.get("type") == "init_error":
            cause = str(answer.get("traceback", "unknown"))[-4000:]
            raise RuntimeError(f"RLBot V4 bot initialization failed:\n{cause}\nWorker log: {log_path}")
        if answer.get("type") != "ready":
            raise RuntimeError(f"Bad v4 worker initialization response: {answer}; log: {log_path}")
        v4_loadout = _loadout_from_v4(answer.get("loadout"))
        if v4_loadout is not None:
            self.set_loadout(v4_loadout)
        self.logger.info("EvilRLBot exact v4 frontend ready on RLBot v5 engine (%s)", answer.get("rlbot_v4"))

    def _apply_game_state(self, state):
        if not state:
            return
        balls = {}
        ball = state.get("ball")
        if ball is not None:
            balls[0] = flat.DesiredBallState(_desired_physics(ball.get("physics")))

        cars = {}
        for idx, car in (state.get("cars") or {}).items():
            cars[int(idx)] = flat.DesiredCarState(
                _desired_physics(car.get("physics")),
                car.get("boost_amount"),
            )

        info = state.get("game_info")
        match_info = None
        if info is not None:
            match_info = flat.DesiredMatchInfo(
                info.get("world_gravity_z"),
                info.get("game_speed"),
            )

        self.set_game_state(
            balls=balls,
            cars=cars,
            match_info=match_info,
            commands=list(state.get("console_commands") or []),
        )

    def _apply_actions(self, actions):
        for action in actions:
            kind = action[0]
            if kind == "quick_chat":
                _, team_only, quick_chat = action
                quick_chat = int(quick_chat)
                self.send_match_comm(
                    str(quick_chat).encode("utf-8"),
                    display=QUICK_CHAT_TEXT.get(quick_chat),
                    team_only=bool(team_only),
                )
            elif kind == "game_state":
                self._apply_game_state(action[1])
            elif kind == "matchcomm":
                # v4 matchcomms accepts arbitrary JSON-compatible objects.
                import json
                payload = json.dumps(action[1], separators=(",", ":")).encode("utf-8")
                self.send_match_comm(payload)

    def _apply_renders(self, commands):
        active = False
        for cmd in commands:
            kind = cmd[0]
            if kind == "begin":
                if active:
                    self.renderer.end_rendering()
                self.renderer.begin_rendering(cmd[1])
                active = True
            elif kind == "end":
                if active:
                    self.renderer.end_rendering()
                    active = False
            elif kind == "clear":
                if active:
                    self.renderer.end_rendering()
                    active = False
                self.renderer.clear_render_group(cmd[1])
            elif kind == "line3d":
                self.renderer.draw_line_3d(_v3(cmd[1]), _v3(cmd[2]), _color(cmd[3]))
            elif kind == "polyline3d":
                self.renderer.draw_polyline_3d([_v3(v) for v in cmd[1]], _color(cmd[2]))
            elif kind == "rect2d":
                self.renderer.draw_rect_2d(cmd[1], cmd[2], cmd[3], cmd[4], _color(cmd[6]))
            elif kind == "rect3d":
                self.renderer.draw_rect_3d(_v3(cmd[1]), cmd[2], cmd[3], _color(cmd[5]))
            elif kind == "string2d":
                # v4 has independent X/Y scales; v5 has one scale. Y is closest to old font sizing.
                self.renderer.draw_string_2d(cmd[5], cmd[1], cmd[2], cmd[4], _color(cmd[6]))
            elif kind == "string3d":
                self.renderer.draw_string_3d(cmd[4], _v3(cmd[1]), cmd[3], _color(cmd[5]))
        if active:
            self.renderer.end_rendering()

    def get_output(self, packet):
        # Keep the V4 API exact, but avoid pushing 720 predicted ball slices
        # across IPC on every tick. The worker requests them only when a bot
        # actually calls get_ball_prediction_struct().
        if self._conn is None:
            return self._last_controller
        if self._worker is not None and self._worker.poll() is not None:
            self.logger.error("RLBot v4 worker exited with code %s", self._worker.returncode)
            return self._last_controller

        t0 = time.perf_counter()
        try:
            incoming, self._incoming_matchcomms = self._incoming_matchcomms, []
            quick_chats, self._incoming_quick_chats = self._incoming_quick_chats, []
            tick = {
                "type": "tick",
                "packet": _packet_to_v4_data(packet),
                "matchcomms": incoming,
                "quick_chats": quick_chats,
            }
            # Escape hatch for user bots that depend on private pre-refactor
            # behavior; on-demand is otherwise lossless for registered APIs.
            if os.environ.get("EVILRLBOT_V4_EAGER_PREDICTION") == "1":
                tick["prediction"] = _prediction_to_v4_data(self.ball_prediction)
            t1 = time.perf_counter()
            self._conn.send(tick)
            deadline = time.perf_counter() + 0.20
            while True:
                remaining = deadline - time.perf_counter()
                if remaining <= 0 or not self._conn.poll(remaining):
                    self.logger.warning("RLBot v4 worker missed 200ms response deadline")
                    return self._last_controller
                result = self._conn.recv()
                if result.get("type") == "prediction_request":
                    # Only compute the exact V5 prediction when the actual
                    # V4 bot needs it; cache occurs within worker this tick.
                    self._prediction_requests += 1
                    self._conn.send({
                        "type": "prediction_result",
                        "prediction": _prediction_to_v4_data(self.ball_prediction)
                    })
                    continue
                break
            t2 = time.perf_counter()
        except (EOFError, BrokenPipeError, OSError) as exc:
            self.logger.error("Lost RLBot v4 worker: %s", exc)
            return self._last_controller

        if result.get("type") == "error":
            self.logger.error("RLBot v4 bot exception:\n%s", result.get("traceback"))
            return self._last_controller
        if result.get("type") != "tick_result":
            return self._last_controller

        self._apply_actions(result.get("actions") or [])
        self._apply_renders(result.get("renders") or [])

        c = result["controller"]
        self._last_controller = flat.ControllerState(
            throttle=float(c[0]),
            steer=float(c[1]),
            pitch=float(c[2]),
            yaw=float(c[3]),
            roll=float(c[4]),
            jump=bool(c[5]),
            boost=bool(c[6]),
            handbrake=bool(c[7]),
            use_item=bool(c[8]),
        )
        elapsed = time.perf_counter() - t0
        self._timings.append(((t1 - t0)*1000, (t2 - t1)*1000, elapsed*1000))
        if len(self._timings) >= 240:
            data = sorted(self._timings, key=lambda x:x[2])
            idx = int(len(data)*0.95)
            self.logger.info(
                "V4 bridge metrics n=%d p50=%.3fms p95=%.3fms "
                "encode_avg=%.3fms worker_rtt_avg=%.3fms prediction_requests=%d",
                len(data), data[len(data)//2][2], data[idx][2],
                sum(t[0] for t in data)/len(data),
                sum(t[1] for t in data)/len(data),
                self._prediction_requests,
            )
            self._timings.clear()
            self._prediction_requests = 0
        return self._last_controller

    def handle_match_comm(self, index, team, content, display, team_only):
        import json
        raw = content.decode("utf-8", "replace") if content else ""
        if display is not None:
            try:
                quick_chat = int(raw)
            except ValueError:
                quick_chat = None
            if quick_chat is not None:
                self._incoming_quick_chats.append((index, team, quick_chat))
                return
        try:
            value = json.loads(raw) if raw else {"display": display}
        except Exception:
            value = {
                "index": index, "team": team, "content": raw,
                "display": display, "team_only": team_only,
            }
        self._incoming_matchcomms.append(value)

    def retire(self):
        if self._conn is not None:
            try:
                self._conn.send({"type": "retire"})
                if self._conn.poll(1.0):
                    self._conn.recv()
            except Exception:
                pass
            try:
                self._conn.close()
            except Exception:
                pass
        if self._worker is not None and self._worker.poll() is None:
            self._worker.terminate()
            try:
                self._worker.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._worker.kill()
        if self._listener is not None:
            try:
                self._listener.close()
            except Exception:
                pass
        if self._worker_log is not None:
            self._worker_log.close()
        if self._ipc_path:
            try:
                os.unlink(self._ipc_path)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    EvilV4Bridge("evilrlbot/evil_v4_exact").run()
