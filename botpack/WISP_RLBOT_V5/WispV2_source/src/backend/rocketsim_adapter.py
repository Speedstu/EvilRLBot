from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Sequence

import numpy as np
import rlbot.flat
import RocketSim

from .gamestate import common_values
from .gamestate.action import Action
from .gamestate.gamestate import GameState
from .gamestate.phys_obj import PhysObj
from .gamestate.player import Player
from .gamestate.rot_mat import RotMat
from .gamestate.team import Team
from .gamestate.vec import Vec


@dataclass
class _PlayerTemporalState:
    air_time: float = 0.0
    air_time_since_jump: float = 0.0
    supersonic_time: float = 0.0
    time_spent_boosting: float = 0.0
    handbrake_val: float = 0.0
    last_touch_seconds: float = -1.0
    last_touch_tick: int = 0


class _FlatPacketView:
    """Convenience wrapper providing safe access to RLBot flatbuffer fields."""

    def __init__(self, packet: rlbot.flat.GamePacket) -> None:
        self.players = packet.players
        self.boost_pads = packet.boost_pads
        self.balls = packet.balls
        self.match_info = packet.match_info

    @property
    def player_count(self) -> int:
        return len(self.players) if self.players is not None else 0

    @property
    def boost_pad_count(self) -> int:
        return len(self.boost_pads) if self.boost_pads is not None else 0

    @property
    def seconds_elapsed(self) -> float | None:
        if self.match_info is None:
            return None
        return float(self.match_info.seconds_elapsed)


_ROCKETSIM_INITIALIZED = False


def _ensure_rocketsim_initialized(mesh_directory: Path | None) -> None:
    global _ROCKETSIM_INITIALIZED
    if _ROCKETSIM_INITIALIZED:
        return

    if mesh_directory is not None:
        RocketSim.init(str(mesh_directory))
    else:
        RocketSim.init()

    _ROCKETSIM_INITIALIZED = True


def _vec_from_flat(vec3: rlbot.flat.Vector3) -> RocketSim.Vec:
    return RocketSim.Vec(float(vec3.x), float(vec3.y), float(vec3.z))


def _angle_from_rot(rotator: rlbot.flat.Rotator | None) -> RocketSim.Angle:
    if rotator is None:
        return RocketSim.Angle()
    return RocketSim.Angle(
        float(rotator.yaw), float(rotator.pitch), float(rotator.roll)
    )


def _vec_from_rs(vec: RocketSim.Vec) -> Vec:
    return Vec(float(vec.x), float(vec.y), float(vec.z))


def _rotmat_from_rs(rot_mat: RocketSim.RotMat) -> RotMat:
    return RotMat(
        [
            [
                float(rot_mat.forward.x),
                float(rot_mat.forward.y),
                float(rot_mat.forward.z),
            ],
            [float(rot_mat.right.x), float(rot_mat.right.y), float(rot_mat.right.z)],
            [float(rot_mat.up.x), float(rot_mat.up.y), float(rot_mat.up.z)],
        ]
    )


def _copy_action(action: Action | None) -> Action:
    if action is None:
        return Action()
    return Action(action.get_np().copy())


class RocketSimStateAdapter:
    """Builds RocketSim-backed GameState snapshots mirroring the C++ adapter."""

    _TICK_RATE = 120.0
    _TICK_TIME = 1.0 / _TICK_RATE
    _BOOST_MAP_EPS = 10.0  # Squared 2D distance threshold used in C++ adapter

    def __init__(self, collision_mesh_dir: Path | str | None = None) -> None:
        mesh_dir_path: Path | None
        if collision_mesh_dir is None:
            mesh_dir_path = None
        else:
            mesh_dir_path = Path(collision_mesh_dir).expanduser().resolve()

        _ensure_rocketsim_initialized(mesh_dir_path)

        self._arena_config = RocketSim.ArenaConfig()
        self._arena: RocketSim.Arena | None = None
        self._car_cache: list[RocketSim.Car] = []
        self._temporal_state: list[_PlayerTemporalState] = []
        self._boost_pad_index_map: list[int] = []
        self._last_tick_count: int = 0
        self._arena_dirty = True

    def reset(self) -> None:
        self._arena = None
        self._car_cache.clear()
        self._temporal_state.clear()
        self._boost_pad_index_map.clear()
        self._last_tick_count = 0
        self._arena_dirty = True

    def build(
        self, packet: rlbot.flat.GamePacket, prev_actions: Sequence[Action]
    ) -> GameState:
        view = _FlatPacketView(packet)
        player_count = view.player_count
        if player_count == 0:
            self._last_tick_count = 0
            return GameState()

        self._ensure_arena_setup(view)

        seconds_elapsed = view.seconds_elapsed
        if seconds_elapsed is None:
            tick_count = self._last_tick_count
        else:
            tick_count = max(0, int(round(seconds_elapsed * self._TICK_RATE)))

        if tick_count < self._last_tick_count:
            # Match restarted or timer reset
            self.reset()
            self._ensure_arena_setup(view)
            self._last_tick_count = tick_count

        tick_delta = max(0, tick_count - self._last_tick_count)
        delta_time = tick_delta * self._TICK_TIME
        self._last_tick_count = tick_count

        self._sync_ball(view)
        self._sync_cars(view, tick_count, delta_time)
        self._sync_boost_pads(view)

        return self._build_state(view, prev_actions, tick_count, tick_delta)

    def _ensure_arena_setup(self, packet_view: _FlatPacketView) -> None:
        player_count = packet_view.player_count
        needs_rebuild = (
            self._arena is None
            or self._arena_dirty
            or len(self._car_cache) != player_count
        )

        if not needs_rebuild:
            return

        arena = RocketSim.Arena(
            RocketSim.GameMode.SOCCAR,
            tick_rate=self._TICK_RATE,
            config=self._arena_config,
        )
        self._arena = arena
        self._car_cache = []
        self._temporal_state = []

        for idx in range(player_count):
            player_info = packet_view.players[idx]
            team = (
                RocketSim.Team.BLUE if player_info.team == 0 else RocketSim.Team.ORANGE
            )
            car = arena.add_car(team)
            self._car_cache.append(car)
            self._temporal_state.append(_PlayerTemporalState())

        self._boost_pad_index_map = self._build_boost_pad_index_map()
        self._arena_dirty = False

    def _build_boost_pad_index_map(self) -> list[int]:
        assert self._arena is not None
        pads = self._arena.get_boost_pads()
        expected = len(common_values.BOOST_LOCATIONS)
        if len(pads) != expected:
            raise RuntimeError(
                f"Arena boost pad count {len(pads)} does not match expected {expected}"
            )

        mapping: list[int] = []
        used = [False] * len(pads)
        for expected_idx, expected_pos in enumerate(common_values.BOOST_LOCATIONS):
            match_index = -1
            best_dist = float("inf")
            for pad_idx, pad in enumerate(pads):
                if used[pad_idx]:
                    continue
                pad_pos = pad.get_pos()
                dx = float(pad_pos.x) - expected_pos.x
                dy = float(pad_pos.y) - expected_pos.y
                dist_sq = dx * dx + dy * dy
                if dist_sq < self._BOOST_MAP_EPS and dist_sq < best_dist:
                    best_dist = dist_sq
                    match_index = pad_idx

            if match_index == -1:
                raise RuntimeError(
                    f"Failed to map RocketSim boost pad for expected index {expected_idx}"
                )

            used[match_index] = True
            mapping.append(match_index)

        return mapping

    def _sync_ball(self, packet_view: _FlatPacketView) -> None:
        assert self._arena is not None
        if packet_view.balls is None or len(packet_view.balls) == 0:
            return

        ball = packet_view.balls[0]
        physics = ball.physics
        if physics is None:
            return

        ball_state = RocketSim.BallState()
        ball_state.pos = _vec_from_flat(physics.location)
        ball_state.vel = _vec_from_flat(physics.velocity)
        ball_state.ang_vel = _vec_from_flat(physics.angular_velocity)
        ball_state.rot_mat = _angle_from_rot(physics.rotation).as_rot_mat()

        self._arena.ball.set_state(ball_state)

    def _sync_cars(
        self, packet_view: _FlatPacketView, tick_count: int, delta_time: float
    ) -> None:
        assert self._arena is not None
        player_count = packet_view.player_count

        if len(self._temporal_state) < player_count:
            self._temporal_state.extend(
                _PlayerTemporalState()
                for _ in range(player_count - len(self._temporal_state))
            )

        for idx, car in enumerate(self._car_cache):
            if idx >= player_count:
                continue

            player_info: Any = packet_view.players[idx]
            physics = getattr(player_info, "physics", None)
            state = RocketSim.CarState()

            if physics is not None:
                state.pos = _vec_from_flat(physics.location)
                state.vel = _vec_from_flat(physics.velocity)
                state.ang_vel = _vec_from_flat(physics.angular_velocity)
                state.rot_mat = _angle_from_rot(physics.rotation).as_rot_mat()

            temporal = self._temporal_state[idx]
            if tick_count == 0:
                temporal = _PlayerTemporalState()
                self._temporal_state[idx] = temporal

            air_state = getattr(player_info, "air_state", rlbot.flat.AirState.OnGround)
            is_on_ground = air_state == rlbot.flat.AirState.OnGround
            state.is_on_ground = is_on_ground
            state.is_jumping = air_state == rlbot.flat.AirState
            state.is_flipping = air_state == rlbot.flat.AirState.Dodging
            state.has_jumped = bool(getattr(player_info, "has_jumped", False))
            state.has_double_jumped = bool(
                getattr(player_info, "has_double_jumped", False)
            )
            state.has_flipped = bool(getattr(player_info, "has_dodged", False))

            demolish_timeout = float(getattr(player_info, "demolished_timeout", 0.0))
            state.boost = float(getattr(player_info, "boost", 0.0))
            state.is_demoed = demolish_timeout > 0.0
            state.demo_respawn_timer = max(0.0, demolish_timeout)
            state.is_supersonic = bool(getattr(player_info, "is_supersonic", False))

            controls = self._to_car_controls(getattr(player_info, "last_input", None))
            car.set_controls(controls)
            state.last_controls = controls

            if not is_on_ground:
                temporal.air_time += delta_time
            else:
                temporal.air_time = 0.0
            state.air_time = temporal.air_time

            if not is_on_ground:
                if player_info.has_jumped and air_state != rlbot.flat.AirState.Jumping:
                    temporal.air_time_since_jump += delta_time
                else:
                    temporal.air_time_since_jump = 0.0
            state.air_time_since_jump = temporal.air_time_since_jump

            if state.is_supersonic:
                temporal.supersonic_time += delta_time
            else:
                temporal.supersonic_time = 0.0
            state.supersonic_time = temporal.supersonic_time

            boosting = controls.boost and state.boost > 0.0
            if boosting:
                temporal.time_spent_boosting += delta_time
            elif temporal.time_spent_boosting > 0.0:
                temporal.time_spent_boosting = 0.0
            state.time_spent_boosting = temporal.time_spent_boosting

            if controls.handbrake:
                temporal.handbrake_val = min(
                    1.0, temporal.handbrake_val + delta_time * 5.0
                )
            else:
                temporal.handbrake_val = max(
                    0.0, temporal.handbrake_val - delta_time * 5.0
                )
            state.handbrake_val = temporal.handbrake_val

            latest_touch = getattr(player_info, "latest_touch", None)
            if latest_touch is not None and getattr(latest_touch, "ball_index", 0) == 0:
                temporal.last_touch_seconds = float(
                    getattr(latest_touch, "game_seconds", 0.0)
                )
                temporal.last_touch_tick = int(
                    round(temporal.last_touch_seconds * self._TICK_RATE)
                )

            car.set_state(state)

    def _sync_boost_pads(self, packet_view: _FlatPacketView) -> None:
        assert self._arena is not None
        if (
            packet_view.boost_pads is None
            or packet_view.boost_pad_count == 0
            or not self._boost_pad_index_map
        ):
            return

        pads = self._arena.get_boost_pads()
        for rl_index, pad_index in enumerate(self._boost_pad_index_map):
            if rl_index >= packet_view.boost_pad_count:
                break
            pad = pads[pad_index]
            pad_state = pad.get_state()
            rl_pad = packet_view.boost_pads[rl_index]
            pad_state.is_active = bool(getattr(rl_pad, "is_active", False))
            pad_state.cooldown = float(getattr(rl_pad, "timer", 0.0))
            pad.set_state(pad_state)

    def _build_state(
        self,
        packet_view: _FlatPacketView,
        prev_actions: Sequence[Action],
        tick_count: int,
        tick_delta: int,
    ) -> GameState:
        assert self._arena is not None

        state = GameState()

        ball_state = self._arena.ball.get_state()
        state.ball = PhysObj(
            pos=_vec_from_rs(ball_state.pos),
            rot_mat=_rotmat_from_rs(ball_state.rot_mat),
            vel=_vec_from_rs(ball_state.vel),
            ang_vel=_vec_from_rs(ball_state.ang_vel),
        )

        player_count = packet_view.player_count
        prev_actions_list: List[Action] = list(prev_actions)
        if len(prev_actions_list) < player_count:
            prev_actions_list.extend(
                Action() for _ in range(player_count - len(prev_actions_list))
            )

        window = max(1, tick_delta)
        for idx, car in enumerate(self._car_cache):
            if idx >= player_count:
                break

            car_state = car.get_state()
            player_info: Any = packet_view.players[idx]

            player = Player(
                Team.BLUE if getattr(player_info, "team", 0) == 0 else Team.ORANGE
            )
            player.set_phys(
                PhysObj(
                    pos=_vec_from_rs(car_state.pos),
                    rot_mat=_rotmat_from_rs(car_state.rot_mat),
                    vel=_vec_from_rs(car_state.vel),
                    ang_vel=_vec_from_rs(car_state.ang_vel),
                )
            )

            player.index = idx
            player.is_on_ground = bool(car_state.is_on_ground)
            player.is_jumping = bool(car_state.is_jumping)
            player.has_jumped = bool(car_state.has_jumped)
            player.is_flipping = bool(car_state.is_flipping)
            player.has_flipped = bool(car_state.has_flipped)
            player.has_double_jumped = bool(car_state.has_double_jumped)
            player.boost = float(car_state.boost)
            player.is_demoed = bool(car_state.is_demoed)

            player.prev_action = _copy_action(prev_actions_list[idx])

            temporal = self._temporal_state[idx]
            player.ball_touched_tick = (
                tick_count > 0 and temporal.last_touch_tick == tick_count - 1
            )
            player.ball_touched_step = (
                temporal.last_touch_tick != 0
                and temporal.last_touch_tick + window >= tick_count
                and temporal.last_touch_tick <= tick_count
            )
            player.handbrake_val = temporal.handbrake_val
            # Provide air_time_since_jump for HasFlipOrJump parity
            player.air_time_since_jump = float(temporal.air_time_since_jump)

            state.players.append(player)

        pad_count = len(self._boost_pad_index_map)
        pads = self._arena.get_boost_pads()
        boost_pads = np.zeros(pad_count, dtype=np.bool_)
        boost_pad_timers = np.zeros(pad_count, dtype=np.float32)
        for rl_index, pad_index in enumerate(self._boost_pad_index_map):
            pad_state = pads[pad_index].get_state()
            boost_pads[rl_index] = pad_state.is_active
            boost_pad_timers[rl_index] = pad_state.cooldown

        if pad_count > 0:
            state.boost_pads = boost_pads
            state.boost_pad_timers = boost_pad_timers
            state.boost_pads_inv = boost_pads[::-1].copy()
            state.boost_pad_timers_inv = boost_pad_timers[::-1].copy()

        return state

    @staticmethod
    def _to_car_controls(
        last_input: rlbot.flat.ControllerState | None,
    ) -> RocketSim.CarControls:
        controls = RocketSim.CarControls()
        if last_input is None:
            return controls

        controls.throttle = float(last_input.throttle)
        controls.steer = float(last_input.steer)
        controls.pitch = float(last_input.pitch)
        controls.yaw = float(last_input.yaw)
        controls.roll = float(last_input.roll)
        controls.jump = bool(last_input.jump)
        controls.boost = bool(last_input.boost)
        controls.handbrake = bool(last_input.handbrake)
        return controls
