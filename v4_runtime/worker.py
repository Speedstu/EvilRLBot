#!/usr/bin/env python3
"""Exact RLBot v4 bot runtime for EvilRLBot.

This process intentionally runs inside .venv-v4 where rlbot==1.68.0 is
installed as the real `rlbot` package. It never imports the RLBot v5 Python
package. A separate v5 bridge process translates packets and actions.
"""
from __future__ import annotations

import importlib
import os
import sys
import traceback
from multiprocessing.connection import Client
from pathlib import Path
from typing import Any
from queue import Queue, Empty
from urllib.parse import urlparse
from types import SimpleNamespace

# Host Python may need the small framework package from the bundled runtime,
# while keeping its own ABI-compatible torch, numpy and other native wheels.
_framework_site = os.environ.get("EVILRLBOT_V4_FRAMEWORK_SITE")
if _framework_site and Path(_framework_site).is_dir() and _framework_site not in sys.path:
    sys.path.insert(0, _framework_site)

from rlbot.agents.base_agent import BaseAgent, SimpleControllerState
from rlbot.utils.game_state_util import GameState
from rlbot.utils.rendering.rendering_manager import Color
from rlbot.matchconfig.match_config import MatchConfig
from rlbot.messages.flat.MatchSettings import MatchSettings
from rlbot.parsing import match_settings_config_parser as v4types
from rlbot.parsing.bot_config_bundle import get_bot_config_bundle
from rlbot.utils.class_importer import import_agent

# Per-bot dependencies are appended only after the real RLBot 1.68 API has
# been imported. Isolate packages by config path, not by global pip installs.
_bot_deps = os.environ.get("EVILRLBOT_V4_DEPS")
if _bot_deps and Path(_bot_deps).is_dir() and _bot_deps not in sys.path:
    sys.path.insert(1, _bot_deps)
# Python -I intentionally ignores PYTHONPATH. Add only the persistent
# PyTorch installation corresponding to this bot's selected backend.
import hashlib
_cfg = os.environ.get("EVILRLBOT_V4_SOURCE") or os.environ.get("EVILRLBOT_V4_CONFIG", "")
_choice_root = Path.home() / ".local/share/evilrlbot/dependencies/.torch-choice"
_backend = "cpu"
if _cfg:
    _choice_file = _choice_root / hashlib.sha256(
        str(Path(_cfg).resolve()).encode()
    ).hexdigest()[:18]
    if _choice_file.is_file():
        _preferred = _choice_file.read_text().strip()
        if _preferred in {"cpu", "cuda"}:
            _backend = _preferred
_torch_dir = (Path.home() / ".local/share/evilrlbot/dependencies/.torch-runtime"
              / f"py312-{_backend}")
if (_torch_dir / ".evilrlbot-torch-complete").is_file():
    sys.path.insert(2, str(_torch_dir))
from rlbot.utils.structures.ball_prediction_struct import BallPrediction
from rlbot.utils.structures.game_data_struct import FieldInfoPacket, GameTickPacket


AUTHKEY = b"evilrlbot-v4-v5"


def _assign_vec(dst, value):
    if not value:
        return
    dst.x = float(value[0])
    dst.y = float(value[1])
    dst.z = float(value[2])


def _assign_rot(dst, value):
    if not value:
        return
    dst.pitch = float(value[0])
    dst.yaw = float(value[1])
    dst.roll = float(value[2])


def _assign_physics(dst, value):
    if not value:
        return
    _assign_vec(dst.location, value.get("location"))
    _assign_rot(dst.rotation, value.get("rotation"))
    _assign_vec(dst.velocity, value.get("velocity"))
    _assign_vec(dst.angular_velocity, value.get("angular_velocity"))



def _pick(values, index, fallback=None):
    try:
        return values[int(index)]
    except (TypeError, ValueError, IndexError):
        return fallback


def _make_match_config(data: dict) -> MatchConfig:
    mc = MatchConfig()
    mc.game_mode = _pick(v4types.game_mode_types, data.get("game_mode"), "Soccer")
    mc.game_map = data.get("game_map") or "Stadium_P"
    mc.skip_replays = bool(data.get("skip_replays", False))
    mc.instant_start = bool(data.get("instant_start", False))
    mc.existing_match_behavior = _pick(
        v4types.existing_match_behavior_types, data.get("existing_match_behavior"), "Restart If Different"
    )
    mc.enable_rendering = bool(data.get("enable_rendering", True))
    mc.enable_state_setting = bool(data.get("enable_state_setting", True))
    mc.auto_save_replay = bool(data.get("auto_save_replay", False))

    mut = data.get("mutators") or {}
    mapping = {
        "match_length": v4types.match_length_types,
        "max_score": v4types.max_score_types,
        "overtime": v4types.overtime_mutator_types,
        "series_length": v4types.series_length_mutator_types,
        "game_speed": v4types.game_speed_mutator_types,
        "ball_max_speed": v4types.ball_max_speed_mutator_types,
        "ball_type": v4types.ball_type_mutator_types,
        "ball_weight": v4types.ball_weight_mutator_types,
        "ball_size": v4types.ball_size_mutator_types,
        "ball_bounciness": v4types.ball_bounciness_mutator_types,
        "boost_amount": v4types.boost_amount_mutator_types,
        "rumble": v4types.rumble_mutator_types,
        "boost_strength": v4types.boost_strength_mutator_types,
        "gravity": v4types.gravity_mutator_types,
        "demolish": v4types.demolish_mutator_types,
        "respawn_time": v4types.respawn_time_mutator_types,
    }
    for key, values in mapping.items():
        picked = _pick(values, mut.get(key), None)
        if picked is not None:
            setattr(mc.mutators, key, picked)
    return mc


def _match_settings_flat(mc: MatchConfig):
    builder = mc.create_flatbuffer()
    raw = bytes(builder.Output())
    return MatchSettings.GetRootAsMatchSettings(raw, 0)


def _ns(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _ns(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_ns(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_ns(v) for v in value)
    return value


def _make_packet(data: dict, profile=None) -> GameTickPacket:
    out = GameTickPacket()

    cars = data.get("cars", ())
    out.num_cars = min(len(cars), len(out.game_cars))
    for i in range(out.num_cars):
        src = cars[i]
        car = out.game_cars[i]
        _assign_physics(car.physics, src.get("physics"))
        score = src.get("score_info") or {}
        car.score_info.score = int(score.get("score", 0))
        car.score_info.goals = int(score.get("goals", 0))
        car.score_info.own_goals = int(score.get("own_goals", 0))
        car.score_info.assists = int(score.get("assists", 0))
        car.score_info.saves = int(score.get("saves", 0))
        car.score_info.shots = int(score.get("shots", 0))
        car.score_info.demolitions = int(score.get("demolitions", 0))
        car.is_demolished = bool(src.get("is_demolished", False))
        car.has_wheel_contact = bool(src.get("has_wheel_contact", False))
        car.is_super_sonic = bool(src.get("is_super_sonic", False))
        car.is_bot = bool(src.get("is_bot", False))
        car.jumped = bool(src.get("jumped", False))
        car.double_jumped = bool(src.get("double_jumped", False))
        car.name = str(src.get("name", ""))[:31]
        car.team = int(src.get("team", 0))
        car.boost = int(round(float(src.get("boost", 0))))
        hitbox = src.get("hitbox") or (0, 0, 0)
        car.hitbox.length = float(hitbox[0])
        car.hitbox.width = float(hitbox[1])
        car.hitbox.height = float(hitbox[2])
        _assign_vec(car.hitbox_offset, src.get("hitbox_offset"))
        car.spawn_id = int(src.get("spawn_id", 0))

    boosts = data.get("boosts", ())
    out.num_boost = min(len(boosts), len(out.game_boosts))
    for i in range(out.num_boost):
        out.game_boosts[i].is_active = bool(boosts[i][0])
        out.game_boosts[i].timer = float(boosts[i][1])

    ball = data.get("ball") or {}
    _assign_physics(out.game_ball.physics, ball.get("physics"))
    touch = ball.get("latest_touch") or {}
    out.game_ball.latest_touch.player_name = str(touch.get("player_name", ""))[:31]
    out.game_ball.latest_touch.time_seconds = float(touch.get("time_seconds", 0))
    _assign_vec(out.game_ball.latest_touch.hit_location, touch.get("hit_location"))
    _assign_vec(out.game_ball.latest_touch.hit_normal, touch.get("hit_normal"))
    out.game_ball.latest_touch.team = int(touch.get("team", 0))
    out.game_ball.latest_touch.player_index = int(touch.get("player_index", -1))
    dropshot = ball.get("drop_shot_info") or {}
    out.game_ball.drop_shot_info.absorbed_force = float(dropshot.get("absorbed_force", 0))
    out.game_ball.drop_shot_info.damage_index = int(dropshot.get("damage_index", 0))
    out.game_ball.drop_shot_info.force_accum_recent = float(dropshot.get("force_accum_recent", 0))
    shape = ball.get("collision_shape") or {}
    out.game_ball.collision_shape.type = int(shape.get("type", 1))
    out.game_ball.collision_shape.box.length = float(shape.get("length", 0))
    out.game_ball.collision_shape.box.width = float(shape.get("width", 0))
    out.game_ball.collision_shape.box.height = float(shape.get("height", 0))
    out.game_ball.collision_shape.sphere.diameter = float(shape.get("diameter", 0))
    out.game_ball.collision_shape.cylinder.diameter = float(shape.get("diameter", 0))
    out.game_ball.collision_shape.cylinder.height = float(shape.get("height", 0))

    info = data.get("game_info") or {}
    gi = out.game_info
    gi.seconds_elapsed = float(info.get("seconds_elapsed", 0))
    gi.game_time_remaining = float(info.get("game_time_remaining", 0))
    gi.is_overtime = bool(info.get("is_overtime", False))
    gi.is_unlimited_time = bool(info.get("is_unlimited_time", False))
    gi.is_round_active = bool(info.get("is_round_active", False))
    gi.is_kickoff_pause = bool(info.get("is_kickoff_pause", False))
    gi.is_match_ended = bool(info.get("is_match_ended", False))
    gi.world_gravity_z = float(info.get("world_gravity_z", -650))
    gi.game_speed = float(info.get("game_speed", 1))
    gi.frame_num = int(info.get("frame_num", 0))

    teams = data.get("teams", ())
    out.num_teams = min(len(teams), len(out.teams))
    for i in range(out.num_teams):
        out.teams[i].team_index = int(teams[i][0])
        out.teams[i].score = int(teams[i][1])

    tiles = data.get("tiles", ())
    out.num_tiles = min(len(tiles), len(out.dropshot_tiles))
    for i in range(out.num_tiles):
        out.dropshot_tiles[i].tile_state = int(tiles[i])

    # Hybrid surface: keep the exact v4 ctypes packet, then add v5-style
    # top-level names and fields which ctypes v4 never had. Existing v4 code
    # still reads game_cars/game_ball/game_info, while hybrid code can read
    # players/balls/match_info/boost_pads from the same packet object.
    v5 = data.get("v5") or {}
    hybrid_players = []
    for i, src in enumerate(v5.get("players") or []):
        hp = _ns(src)
        if i < out.num_cars:
            legacy = out.game_cars[i]
            hp.physics = legacy.physics
            hp.score_info = legacy.score_info
            hp.hitbox = legacy.hitbox
            hp.hitbox_offset = legacy.hitbox_offset
        hybrid_players.append(hp)
    out.players = hybrid_players
    out.num_players = len(hybrid_players)
    out.boost_pads = [out.game_boosts[i] for i in range(out.num_boost)]

    hybrid_balls = []
    for i, src in enumerate(v5.get("balls") or []):
        hb = _ns(src)
        if i == 0:
            hb.physics = out.game_ball.physics
        hybrid_balls.append(hb)
    out.balls = hybrid_balls
    out.num_balls = len(hybrid_balls)
    out.match_info = _ns(v5.get("match_info") or {})
    out.tiles = _ns(v5.get("tiles") or [])
    out.v5_teams = _ns(v5.get("teams") or [])
    out.ball = hybrid_balls[0] if hybrid_balls else None
    out.num_boosts = out.num_boost
    out.v5 = SimpleNamespace(
        players=out.players, boost_pads=out.boost_pads, balls=out.balls,
        match_info=out.match_info, teams=out.v5_teams, tiles=out.tiles,
    )
    out.evilrlbot = _ns({
        "packet_source": "RLBot v5",
        "frontend": "RLBot v4 exact + v5 extensions",
        "profile": profile or {},
        "has_v4_fields": True,
        "has_v5_fields": True,
    })

    return out


def _make_field_info(data: dict) -> FieldInfoPacket:
    out = FieldInfoPacket()
    boosts = data.get("boost_pads", ())
    out.num_boosts = min(len(boosts), len(out.boost_pads))
    for i in range(out.num_boosts):
        _assign_vec(out.boost_pads[i].location, boosts[i][0])
        out.boost_pads[i].is_full_boost = bool(boosts[i][1])

    goals = data.get("goals", ())
    out.num_goals = min(len(goals), len(out.goals))
    for i in range(out.num_goals):
        g = goals[i]
        out.goals[i].team_num = int(g.get("team_num", 0))
        _assign_vec(out.goals[i].location, g.get("location"))
        _assign_vec(out.goals[i].direction, g.get("direction"))
        out.goals[i].width = float(g.get("width", 0))
        out.goals[i].height = float(g.get("height", 0))
    return out


def _make_prediction(data: dict) -> BallPrediction:
    out = BallPrediction()
    slices = data.get("slices", ())
    out.num_slices = min(len(slices), len(out.slices))
    for i in range(out.num_slices):
        item = slices[i]
        out.slices[i].game_seconds = float(item.get("game_seconds", 0))
        _assign_physics(out.slices[i].physics, item.get("physics"))
    return out


def _color_tuple(color: Color):
    return (int(color.r), int(color.g), int(color.b), int(color.a))


def _vec_tuple(value):
    if hasattr(value, "x"):
        return (float(value.x), float(value.y), float(value.z))
    return (float(value[0]), float(value[1]), float(value[2]))


class RemoteRenderer:
    """v4 RenderingManager API, with commands replayed by the v5 bridge."""

    def __init__(self, bot_index: int, bot_team: int):
        self.bot_index = bot_index
        self.bot_team = bot_team
        self.group_id = None
        self.render_state = False
        self.touched_group_ids = set()
        self.commands = []

    def drain(self):
        commands, self.commands = self.commands, []
        return commands

    def set_bot_index_and_team(self, bot_index=0, bot_team=0):
        self.bot_index = bot_index
        self.bot_team = bot_team

    def begin_rendering(self, group_id="default"):
        self.group_id = str(group_id)
        self.touched_group_ids.add(self.group_id)
        self.render_state = True
        self.commands.append(("begin", self.group_id))
        return self

    def end_rendering(self):
        if self.render_state:
            self.commands.append(("end",))
        self.render_state = False
        self.group_id = None
        return self

    def clear_screen(self, group_id="default"):
        self.commands.append(("clear", str(group_id)))
        return self

    def clear_all_touched_render_groups(self):
        for group_id in tuple(self.touched_group_ids):
            self.clear_screen(group_id)
        return self

    def is_rendering(self):
        return self.render_state

    def draw_line_2d(self, x1, y1, x2, y2, color):
        # v4 itself logs this as unsupported.
        return self

    def draw_polyline_2d(self, vectors, color):
        return self

    def draw_line_2d_3d(self, x, y, vec, color):
        return self

    def draw_line_3d(self, vec1, vec2, color):
        self.commands.append(("line3d", _vec_tuple(vec1), _vec_tuple(vec2), _color_tuple(color)))
        return self

    def draw_polyline_3d(self, vectors, color):
        self.commands.append(("polyline3d", [_vec_tuple(v) for v in vectors], _color_tuple(color)))
        return self

    def draw_rect_2d(self, x, y, width, height, filled, color):
        self.commands.append(("rect2d", float(x), float(y), float(width), float(height), bool(filled), _color_tuple(color)))
        return self

    def draw_rect_3d(self, vec, width, height, filled, color, centered=False):
        self.commands.append(("rect3d", _vec_tuple(vec), float(width), float(height), bool(filled), _color_tuple(color), bool(centered)))
        return self

    def draw_string_2d(self, x, y, scale_x, scale_y, text, color):
        self.commands.append(("string2d", float(x), float(y), float(scale_x), float(scale_y), str(text), _color_tuple(color)))
        return self

    def draw_string_3d(self, vec, scale_x, scale_y, text, color):
        self.commands.append(("string3d", _vec_tuple(vec), float(scale_x), float(scale_y), str(text), _color_tuple(color)))
        return self

    def create_color(self, alpha, red, green, blue):
        return Color(int(red), int(green), int(blue), int(alpha))

    def black(self): return self.create_color(255, 0, 0, 0)
    def white(self): return self.create_color(255, 255, 255, 255)
    def gray(self): return self.create_color(255, 128, 128, 128)
    def grey(self): return self.gray()
    def blue(self): return self.create_color(255, 0, 0, 255)
    def red(self): return self.create_color(255, 255, 0, 0)
    def green(self): return self.create_color(255, 0, 128, 0)
    def lime(self): return self.create_color(255, 0, 255, 0)
    def yellow(self): return self.create_color(255, 255, 255, 0)
    def orange(self): return self.create_color(255, 225, 128, 0)
    def cyan(self): return self.create_color(255, 0, 255, 255)
    def pink(self): return self.create_color(255, 255, 0, 255)
    def purple(self): return self.create_color(255, 128, 0, 128)
    def teal(self): return self.create_color(255, 0, 128, 128)

    def team_color(self, team=None, alt_color=False):
        team = self.bot_team if team is None else team
        if team == 0:
            return self.cyan() if alt_color else self.blue()
        if team == 1:
            return self.red() if alt_color else self.orange()
        return self.gray() if alt_color else self.white()



def _serialize_loadout(loadout):
    if loadout is None:
        return None
    paint = loadout.paint_config
    return {
        "team_color_id": int(loadout.team_color_id),
        "custom_color_id": int(loadout.custom_color_id),
        "car_id": int(loadout.car_id),
        "decal_id": int(loadout.decal_id),
        "wheels_id": int(loadout.wheels_id),
        "boost_id": int(loadout.boost_id),
        "antenna_id": int(loadout.antenna_id),
        "hat_id": int(loadout.hat_id),
        "paint_finish_id": int(loadout.paint_finish_id),
        "custom_finish_id": int(loadout.custom_finish_id),
        "engine_audio_id": int(loadout.engine_audio_id),
        "trails_id": int(loadout.trails_id),
        "goal_explosion_id": int(loadout.goal_explosion_id),
        "paint": {
            "car_paint_id": int(paint.car_paint_id),
            "decal_paint_id": int(paint.decal_paint_id),
            "wheels_paint_id": int(paint.wheels_paint_id),
            "boost_paint_id": int(paint.boost_paint_id),
            "antenna_paint_id": int(paint.antenna_paint_id),
            "hat_paint_id": int(paint.hat_paint_id),
            "trails_paint_id": int(paint.trails_paint_id),
            "goal_explosion_paint_id": int(paint.goal_explosion_paint_id),
        },
        "primary_color_lookup": getattr(loadout, "primary_color_lookup", None),
        "secondary_color_lookup": getattr(loadout, "secondary_color_lookup", None),
    }


def _serialize_vector_obj(v):
    if v is None:
        return None
    return (v.x, v.y, v.z)


def _serialize_rotator_obj(r):
    if r is None:
        return None
    return (r.pitch, r.yaw, r.roll)


def _serialize_physics_obj(p):
    if p is None:
        return None
    return {
        "location": _serialize_vector_obj(p.location),
        "rotation": _serialize_rotator_obj(p.rotation),
        "velocity": _serialize_vector_obj(p.velocity),
        "angular_velocity": _serialize_vector_obj(p.angular_velocity),
    }


def _serialize_game_state(state: GameState):
    if state is None:
        return None
    out = {
        "ball": None,
        "cars": {},
        "boosts": {},
        "game_info": None,
        "console_commands": list(state.console_commands or []),
    }
    if state.ball is not None:
        out["ball"] = {"physics": _serialize_physics_obj(state.ball.physics)}
    for idx, car in (state.cars or {}).items():
        out["cars"][int(idx)] = {
            "physics": _serialize_physics_obj(car.physics),
            "boost_amount": car.boost_amount,
            "jumped": car.jumped,
            "double_jumped": car.double_jumped,
        }
    for idx, boost in (state.boosts or {}).items():
        out["boosts"][int(idx)] = {"respawn_time": boost.respawn_time}
    if state.game_info is not None:
        out["game_info"] = {
            "world_gravity_z": state.game_info.world_gravity_z,
            "game_speed": state.game_info.game_speed,
            "paused": state.game_info.paused,
            "end_match": state.game_info.end_match,
        }
    return out


class LocalMatchcomms:
    """Queue-compatible v4 matchcomms client transported through the v5 bridge."""
    def __init__(self):
        self.incoming_broadcast = Queue()
        self.outgoing_broadcast = Queue()

    def close(self):
        pass


class Runtime:
    def __init__(self, conn, init: dict):
        self.conn = conn
        self.init = init
        self.profile = init.get("profile") or {}
        self.actions = []
        self.field_info = _make_field_info(init.get("field_info") or {})
        self.prediction = BallPrediction()
        self._prediction_current = True
        self._prediction_fetches = 0
        self.match_config = _make_match_config(init.get("match") or {})
        self.match_settings = _match_settings_flat(self.match_config)
        self.renderer = RemoteRenderer(int(init["index"]), int(init["team"]))
        self.tick_counter = 0
        self.agent_class_wrapper = None
        self.agent_class_file = None
        self.last_module_mtime = 0.0
        self.agent = self._load_agent()
        self._wire_agent()
        self.loadout = self._serialize_loadout()

    def _load_agent(self):
        self.bundle = None
        self.agent_config = None
        bot_config = self.init.get("bot_config")
        if bot_config:
            self.bundle = get_bot_config_bundle(bot_config)
            # Mirror SetupManager.run_agent from RLBot v4.
            os.chdir(Path(self.bundle.config_directory).parent)
            wrapper = import_agent(self.bundle.python_file)
            self.agent_class_wrapper = wrapper
            self.agent_class_file = Path(self.bundle.python_file)
            self.last_module_mtime = self._tree_mtime(self.agent_class_file.parent)
            cls = wrapper.get_loaded_class()
            self.agent_config = cls.base_create_agent_configurations()
            self.agent_config.parse_file(self.bundle.config_obj, config_directory=self.bundle.config_directory)
            return cls(str(self.init["name"]), int(self.init["team"]), int(self.init["index"]))

        root = Path(self.init["project_root"])
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        module = importlib.import_module(self.init["module"])
        class_name = self.init.get("class")
        if class_name:
            cls = getattr(module, class_name)
        else:
            candidates = [
                value for value in vars(module).values()
                if isinstance(value, type) and issubclass(value, BaseAgent) and value is not BaseAgent
            ]
            if len(candidates) != 1:
                raise RuntimeError(
                    f"Expected exactly one RLBot v4 BaseAgent subclass in {module.__name__}, "
                    f"found {[c.__name__ for c in candidates]}"
                )
            cls = candidates[0]
        return cls(str(self.init["name"]), int(self.init["team"]), int(self.init["index"]))

    @staticmethod
    def _tree_mtime(directory: Path) -> float:
        newest = 0.0
        try:
            for path in directory.rglob("*.py"):
                try:
                    newest = max(newest, path.stat().st_mtime)
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            pass
        return newest

    def _maybe_hot_reload(self):
        if self.agent_class_wrapper is None or self.agent_class_file is None:
            return
        if self.tick_counter % 20 != 1 or not self.agent.is_hot_reload_enabled():
            return
        newest = self._tree_mtime(self.agent_class_file.parent)
        if newest == self.last_module_mtime:
            return
        self.last_module_mtime = newest
        old_agent = self.agent
        try:
            self.renderer.clear_all_touched_render_groups()
            # Avoid stale timestamp+size based .pyc reuse during very fast edits.
            for pyc in self.agent_class_file.parent.rglob("*.pyc"):
                try:
                    pyc.unlink()
                except OSError:
                    pass
            importlib.invalidate_caches()
            self.agent_class_wrapper.reload()
            cls = self.agent_class_wrapper.get_loaded_class()
            self.agent_config = cls.base_create_agent_configurations()
            self.agent_config.parse_file(
                self.bundle.config_obj, config_directory=self.bundle.config_directory
            )
            self.agent = cls(
                str(self.init["name"]), int(self.init["team"]), int(self.init["index"])
            )
            self._wire_agent()
            try:
                old_agent.retire()
            except Exception:
                traceback.print_exc()
        except Exception:
            self.agent = old_agent
            traceback.print_exc()

    def _serialize_loadout(self):
        if self.bundle is None or self.bundle.looks_path is None:
            return None
        loadout = self.bundle.generate_loadout_config(int(self.init["index"]), int(self.init["team"]))
        paint = loadout.paint_config
        return {
            "team_color_id": loadout.team_color_id,
            "custom_color_id": loadout.custom_color_id,
            "car_id": loadout.car_id,
            "decal_id": loadout.decal_id,
            "wheels_id": loadout.wheels_id,
            "boost_id": loadout.boost_id,
            "antenna_id": loadout.antenna_id,
            "hat_id": loadout.hat_id,
            "paint_finish_id": loadout.paint_finish_id,
            "custom_finish_id": loadout.custom_finish_id,
            "engine_audio_id": loadout.engine_audio_id,
            "trails_id": loadout.trails_id,
            "goal_explosion_id": loadout.goal_explosion_id,
            "paint": {
                "car_paint_id": paint.car_paint_id,
                "decal_paint_id": paint.decal_paint_id,
                "wheels_paint_id": paint.wheels_paint_id,
                "boost_paint_id": paint.boost_paint_id,
                "antenna_paint_id": paint.antenna_paint_id,
                "hat_paint_id": paint.hat_paint_id,
                "trails_paint_id": paint.trails_paint_id,
                "goal_explosion_paint_id": paint.goal_explosion_paint_id,
            },
        }

    def _wire_agent(self):
        self.agent.init_match_config(self.match_config)
        if self.agent_config is not None:
            self.agent.load_config(self.agent_config.get_header("Bot Parameters"))
        self.agent._register_quick_chat(self._quick_chat)
        self.agent._register_field_info(lambda: self.field_info)
        self.agent._register_set_game_state(self._set_game_state)
        self.agent._register_ball_prediction_struct(self._get_prediction)
        self.agent._register_ball_prediction(self._get_prediction)
        self.agent._register_match_settings_func(lambda: self.match_settings)
        self.agent._register_get_rigid_body_tick(lambda: None)
        self.agent.matchcomms_root = urlparse("ws://127.0.0.1/evilrlbot")
        self.agent._matchcomms = LocalMatchcomms()
        self.agent._set_renderer(self.renderer)
        self.agent._set_spawn_id(int(self.init.get("spawn_id", 0)))
        self.agent.evilrlbot = _ns({
            "profile": self.profile,
            "frontend": "v4-exact",
            "engine": "v5",
            "hybrid_packet": True,
        })
        self.agent.initialize_agent()

    def _get_prediction(self):
        # Called only by V4's public prediction API. The IPC parent
        # calculates the exact live prediction on request, not every frame.
        if not self._prediction_current:
            self.conn.send({"type": "prediction_request"})
            response = self.conn.recv()
            if response.get("type") != "prediction_result":
                raise RuntimeError(f"Bad prediction IPC response: {response.get('type')}")
            self.prediction = _make_prediction(response.get("prediction") or {})
            self._prediction_current = True
            self._prediction_fetches += 1
        return self.prediction

    def _quick_chat(self, team_only, quick_chat):
        self.actions.append(("quick_chat", bool(team_only), int(quick_chat)))

    def _set_game_state(self, state):
        self.actions.append(("game_state", _serialize_game_state(state)))

    def step(self, message):
        self.actions = []
        self.renderer.commands = []
        self.tick_counter += 1
        self._maybe_hot_reload()
        prediction = message.get("prediction")
        self._prediction_current = prediction is not None
        if prediction is not None:
            self.prediction = _make_prediction(prediction)
        for item in message.get("matchcomms") or []:
            self.agent._matchcomms.incoming_broadcast.put(item)
        for item in message.get("quick_chats") or []:
            self.agent.handle_quick_chat(int(item[0]), int(item[1]), int(item[2]))
        packet = _make_packet(message["packet"], self.profile)
        controller = self.agent.get_output(packet)
        while True:
            try:
                item = self.agent._matchcomms.outgoing_broadcast.get_nowait()
            except Empty:
                break
            self.actions.append(("matchcomm", item))
        if controller is None:
            controller = SimpleControllerState()
        if isinstance(controller, (list, tuple)):
            values = list(controller) + [False] * 9
            controller = SimpleControllerState(
                throttle=values[0], steer=values[1], pitch=values[2], yaw=values[3],
                roll=values[4], jump=values[5], boost=values[6], handbrake=values[7],
                use_item=values[8],
            )
        return {
            "controller": (
                float(controller.throttle), float(controller.steer), float(controller.pitch),
                float(controller.yaw), float(controller.roll), bool(controller.jump),
                bool(controller.boost), bool(controller.handbrake), bool(getattr(controller, "use_item", False)),
            ),
            "actions": self.actions,
            "renders": self.renderer.drain(),
        }

    def retire(self):
        try:
            self.agent.retire()
        except Exception:
            traceback.print_exc()
        try:
            self.agent._matchcomms.close()
        except Exception:
            pass


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: worker.py <unix-socket-path>")
    conn = Client(sys.argv[1], family="AF_UNIX", authkey=AUTHKEY)
    try:
        init = conn.recv()
        try:
            runtime = Runtime(conn, init)
        except Exception:
            # Preserve the original error instead of sending EOF to the V5
            # bridge. This is what produces the otherwise opaque spectator
            # lobby when a V4 bot dies during initialize_agent().
            problem = traceback.format_exc()
            traceback.print_exc()
            try:
                conn.send({"type": "init_error", "traceback": problem})
            except (EOFError, BrokenPipeError, OSError):
                pass
            return
        conn.send({
            "type": "ready",
            "rlbot_v4": "1.68.0",
            "loadout": runtime.loadout,
            "python_file": runtime.bundle.python_file if runtime.bundle is not None else None,
        })
        while True:
            message = conn.recv()
            kind = message.get("type")
            if kind == "tick":
                try:
                    conn.send({"type": "tick_result", **runtime.step(message)})
                except Exception:
                    conn.send({"type": "error", "traceback": traceback.format_exc()})
            elif kind == "retire":
                runtime.retire()
                conn.send({"type": "retired"})
                break
    except EOFError:
        pass
    finally:
        conn.close()


if __name__ == "__main__":
    main()
