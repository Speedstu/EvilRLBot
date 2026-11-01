import copy

from .vec import Vec
from .rot_mat import RotMat

class PhysObj:
    def __init__(self, pos=Vec(), rot_mat=RotMat(), vel=Vec(), ang_vel=Vec()):
        self.pos = pos
        self.rot_mat = rot_mat
        self.vel = vel
        self.ang_vel = ang_vel

    _INVERT_SCALE = Vec(-1, -1, 1)
    def invert_y(self, should_invert = True):
        result = copy.deepcopy(self)
        if should_invert:
            result.pos *= self._INVERT_SCALE
            for i in range(3):
                result.rot_mat[i] *= self._INVERT_SCALE
            result.vel *= self._INVERT_SCALE
            result.ang_vel *= self._INVERT_SCALE
        return result

    def mirror_x(self, should_mirror = True):
        result = copy.deepcopy(self)
        if should_mirror:
            result.pos.x *= -1

            result.rot_mat.forward *= Vec(-1, 1, 1)
            result.rot_mat.right *= Vec(1, -1, -1)
            result.rot_mat.up *= Vec(-1, 1, 1)

            result.vel.x *= -1
            result.ang_vel *= Vec(1, -1, -1)
        return result

    def get_dict(self):
        return {
            "pos": self.pos,
            "rot_mat": self.rot_mat,
            "vel": self.vel,
            "ang_vel": self.ang_vel
        }

    def __str__(self):
        d = self.get_dict()
        str_d = {}
        for (k, v) in d.items():
            str_d[k] = str(v)
        return str(str_d)

