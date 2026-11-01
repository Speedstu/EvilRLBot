import numpy as np

from .vec import Vec

class RotMat:
    def __init__(self, vals = None):
        if vals is None:
            self.vals = np.eye(3, dtype=np.float32)
        elif isinstance(vals, np.ndarray):
            assert vals.shape == (3, 3)
            self.vals = vals.astype(np.float32)
        elif isinstance(vals, list):
            if len(vals) == 3 and all(type(row) == Vec for row in vals):
                self.vals = np.array([row.vals.copy() for row in vals], dtype=np.float32)
            elif len(vals) == 3 and all(len(row) == 3 for row in vals):
                self.vals = np.array(vals, dtype=np.float32)
            elif len(vals) == 9:
                self.vals = np.array(vals, dtype=np.float32).reshape((3, 3))
            else:
                assert False, "Bad list format for RotMat"
        elif isinstance(vals, RotMat):
            self.vals = vals.vals.copy()
        else:
            assert False, "Bad type for constructing RotMat"

    ### DIRECTION GETTERS ###

    @property
    def forward(self):
        return Vec(self.vals[0])
    @forward.setter
    def forward(self, vals):
        self.vals[0] = Vec(vals).vals

    @property
    def right(self):
        return Vec(self.vals[1])
    @right.setter
    def right(self, vals):
        self.vals[1] = Vec(vals).vals

    @property
    def up(self):
        return Vec(self.vals[2])
    @up.setter
    def up(self, vals):
        self.vals[2] = Vec(vals).vals

    ### OPERATORS ###

    def __mul__(self, scale):
        return RotMat(self.vals * scale)
    def __rmul__(self, scale):
        return self.__mul__(scale)

    def __truediv__(self, scale):
        return RotMat(self.vals / scale)
    def __rtruediv__(self, scale):
        return self.__truediv__(scale)

    def __neg__(self):
        return RotMat(-self.vals)

    def __getitem__(self, i):
        return Vec.make_data_ref(self.vals[i])
    def __setitem__(self, i, value):
        self.vals[i] = Vec(value).vals

    def __eq__(self):
        return self.vals == other.vals
    def __ne__(self):
        return not (self == other)

    def __str__(self):
        return "RotMat" + self.vals.tolist().__str__()

    ### UTILITIES ###

    def dot(self, other):
        # CREDIT: From redd
        if isinstance(other, RotMat):
            return RotMat(np.dot(self.vals, other.vals))
        elif isinstance(other, Vec):
            return Vec(
                other.dot(self.forward),
                other.dot(self.right),
                other.dot(self.up)
            )
        else:
            return NotImplemented

    def transpose(self):
        return RotMat(self.vals.transpose())

    def np(self) -> np.ndarray:
        return self.vals.copy()