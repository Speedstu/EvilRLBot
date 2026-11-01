from typing import Iterable, Optional

import numpy as np


class Action:  # Lawsuit
    def __init__(self, vals: Optional[Iterable[float]] | np.ndarray = None):
        # Accept lists, tuples or numpy arrays. Default to zero vector of length 8.
        if vals is None:
            vals = np.zeros(8, dtype=np.float32)
        self.vals = np.array(vals, dtype=np.float32)

    @property
    def throttle(self):
        return self.vals[0]

    @throttle.setter
    def throttle(self, val: float):
        self.vals[0] = val

    @property
    def steer(self):
        return self.vals[1]

    @steer.setter
    def steer(self, val: float):
        self.vals[1] = val

    @property
    def pitch(self):
        return self.vals[2]

    @pitch.setter
    def pitch(self, val: float):
        self.vals[2] = val

    @property
    def yaw(self):
        return self.vals[3]

    @yaw.setter
    def yaw(self, val: float):
        self.vals[3] = val

    @property
    def roll(self):
        return self.vals[4]

    @roll.setter
    def roll(self, val: float):
        self.vals[4] = val

    @property
    def jump(self):
        return self.vals[5]

    @jump.setter
    def jump(self, val: float):
        self.vals[5] = val

    @property
    def boost(self):
        return self.vals[6]

    @boost.setter
    def boost(self, val: float):
        self.vals[6] = val

    @property
    def handbrake(self):
        return self.vals[7]

    @handbrake.setter
    def handbrake(self, val: float):
        self.vals[7] = val

    def mirror_x(self) -> 'Action':
        return Action([self.throttle, -self.steer, self.pitch, -self.yaw, -self.roll, self.jump, self.boost, self.handbrake])

    def get_dict(self):
        return {
            "throttle": self.throttle,
            "steer": self.steer,
            "pitch": self.pitch,
            "yaw": self.yaw,
            "roll": self.roll,
            "jump": self.jump,
            "boost": self.boost,
            "handbrake": self.handbrake,
        }

    def __getitem__(self, i):
        return self.vals[i]

    def __setitem__(self, i, value):
        self.vals[i] = value

    def __str__(self):
        return str(self.get_dict())

    def get_np(self) -> np.ndarray:
        return self.vals
