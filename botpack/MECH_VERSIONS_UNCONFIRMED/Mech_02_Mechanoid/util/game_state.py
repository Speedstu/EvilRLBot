import numpy as np
from typing import List

from rlbot.utils.structures.game_data_struct import GameTickPacket, FieldInfoPacket, PlayerInfo

from .physics_object import PhysicsObject
from .player_data import PlayerData


class GameState:
    def __init__(self, game_info: FieldInfoPacket):
        self.blue_score = 0
        self.orange_score = 0
        self.players: List[PlayerData] = []
        self._on_ground_ticks = np.zeros(64)

        self.ball: PhysicsObject = PhysicsObject()
        self.inverted_ball: PhysicsObject = PhysicsObject()

        # List of "booleans" (1 or 0)
        self.boost_pads: np.ndarray = np.zeros(game_info.num_boosts, dtype=np.float32)
        self.inverted_boost_pads: np.ndarray = np.zeros_like(self.boost_pads, dtype=np.float32)

        # Boost pad timers (seconds until pad becomes available). Mirrors C++ GetBoostPadTimers.
        self.boost_pad_timers: np.ndarray = np.zeros(game_info.num_boosts, dtype=np.float32)
        self.inverted_boost_pad_timers: np.ndarray = np.zeros_like(self.boost_pad_timers, dtype=np.float32)

    def decode(self, packet: GameTickPacket, ticks_elapsed=1):
        self.blue_score = packet.teams[0].score
        self.orange_score = packet.teams[1].score

        for i in range(packet.num_boost):
            self.boost_pads[i] = packet.game_boosts[i].is_active
            # RLBot exposes a timer field (seconds until pad respawns). Fallback to 0 if missing.
            self.boost_pad_timers[i] = getattr(packet.game_boosts[i], 'timer', 0.0)
        self.inverted_boost_pads[:] = self.boost_pads[::-1]
        self.inverted_boost_pad_timers[:] = self.boost_pad_timers[::-1]

        self.ball.decode_ball_data(packet.game_ball.physics)
        self.inverted_ball.invert(self.ball)

        self.players = []
        for i in range(packet.num_cars):
            player = self._decode_player(packet.game_cars[i], i, ticks_elapsed)
            self.players.append(player)

            if player.ball_touched:
                self.last_touch = player.car_id

    def _decode_player(self, player_info: PlayerInfo, index: int, ticks_elapsed: int) -> PlayerData:
        player_data = PlayerData()

        player_data.car_data.decode_car_data(player_info.physics)
        player_data.inverted_car_data.invert(player_data.car_data)

        if player_info.has_wheel_contact:
            self._on_ground_ticks[index] = 0
        else:
            self._on_ground_ticks[index] += ticks_elapsed

        player_data.car_id = index
        player_data.team_num = player_info.team
        player_data.is_demoed = player_info.is_demolished
        player_data.on_ground = player_info.has_wheel_contact or self._on_ground_ticks[index] <= 6
        player_data.ball_touched = False
        player_data.has_flip = not player_info.double_jumped  # Rough match to C++ HasFlip
        # Track jump status; C++ obs uses HasFlipOrJump() and hasJumped
        player_data.has_jump = not getattr(player_info, 'jumped', False)
        player_data.has_jumped = getattr(player_info, 'jumped', False)
        player_data.boost_amount = player_info.boost / 100

        return player_data

    # Helpers to mirror C++ state.GetBoostPads(inv) / GetBoostPadTimers(inv)
    def get_boost_pads(self, inverted: bool) -> np.ndarray:
        return self.inverted_boost_pads if inverted else self.boost_pads

    def get_boost_pad_timers(self, inverted: bool) -> np.ndarray:
        return self.inverted_boost_pad_timers if inverted else self.boost_pad_timers
