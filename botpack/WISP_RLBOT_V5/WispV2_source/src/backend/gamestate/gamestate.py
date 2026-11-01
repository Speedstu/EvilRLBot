from typing import List
import numpy as np

from .phys_obj import PhysObj
from .player import Player
from . import common_values

class GameState:
    def __init__(self):
        self.ball = PhysObj()
        self.players: List[Player] = []

        self.boost_pads: np.ndarray = np.array([False] * common_values.BOOST_LOCATIONS_AMOUNT)
        self.boost_pads_inv: np.ndarray = self.boost_pads.copy()

        self.boost_pad_timers: np.ndarray = np.array([0.0] * common_values.BOOST_LOCATIONS_AMOUNT)
        self.boost_pad_timers_inv: np.ndarray = self.boost_pad_timers.copy()

    def get_ball_phys(self, inv: bool):
        return self.ball.invert_y(inv)

    def get_boost_pads(self, inv: bool, mirror_x: bool):
        pads = self.boost_pads_inv if inv else self.boost_pads
        if mirror_x:
            return [pads[common_values.MIRRORED_PAD_MAPPING[i]] for i in range(common_values.BOOST_LOCATIONS_AMOUNT)]
        return pads

    def get_boost_pad_timers(self, inv: bool, mirror_x: bool):
        pads = self.boost_pad_timers_inv if inv else self.boost_pad_timers
        if mirror_x:
            return [pads[common_values.MIRRORED_PAD_MAPPING[i]] for i in range(common_values.BOOST_LOCATIONS_AMOUNT)]
        return pads
