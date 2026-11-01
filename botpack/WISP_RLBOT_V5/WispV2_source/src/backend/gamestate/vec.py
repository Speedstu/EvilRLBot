from __future__ import annotations

from typing import Iterable, cast

import numpy as np  # pyright: ignore[reportMissingImports]
from rlbot.flat import Vector3


class Vec:
    _SCALE_2D = np.array([1, 1, 0])

    # Can use individual xyz, or numpy arrays, or other lists
    def __init__(
        self,
        x: float | np.ndarray | Iterable[float] | "Vec" = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        if isinstance(x, np.ndarray):
            arr_nd = cast(np.ndarray, x)
            if arr_nd.shape != (3,):
                raise AssertionError("Array must have shape (3,)")
            self.vals = arr_nd.astype(np.float32)
        elif isinstance(x, Vec):
            self.vals = x.vals.copy()
        elif isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            arr = np.array(list(x), dtype=np.float32)
            if arr.shape != (3,):
                raise AssertionError("Input must have 3 elements")
            self.vals = arr
        else:
            # Individual xyz
            self.vals = np.array([float(x), float(y), float(z)], dtype=np.float32)

    @staticmethod
    def make_data_ref(data: np.ndarray):
        result = Vec()
        result.vals = data
        return result

    ### ELEMENT ACCESS ###

    @property
    def x(self):
        return self.vals[0]

    @x.setter
    def x(self, val: float):
        self.vals[0] = val

    @property
    def y(self):
        return self.vals[1]

    @y.setter
    def y(self, val: float):
        self.vals[1] = val

    @property
    def z(self):
        return self.vals[2]

    @z.setter
    def z(self, val: float):
        self.vals[2] = val

    ### CONVERSION ###

    def numpy(self):
        return self.vals

    def rlbot(self):
        return Vector3(self.x, self.y, self.z)

    ### OPERATIONS ###

    def __add__(self, other):
        if isinstance(other, Vec):
            return Vec(self.vals + other.vals)
        else:  # scalar
            return Vec(self.vals + other)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, Vec):
            return Vec(self.vals - other.vals)
        else:
            return Vec(self.vals - other)

    def __rsub__(self, other):
        if isinstance(other, Vec):
            return Vec(other.vals - self.vals)
        else:
            return Vec(other - self.vals)

    def __mul__(self, other):
        if isinstance(other, Vec):
            return Vec(self.vals * other.vals)
        else:
            return Vec(self.vals * other)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, Vec):
            return Vec(self.vals / other.vals)
        else:
            return Vec(self.vals / other)

    def __rtruediv__(self, other):
        return self.__truediv__(other)

    def __neg__(self):
        return Vec(-self.vals)

    def __getitem__(self, i):
        return self.vals[i]

    def __setitem__(self, i, value):
        self.vals[i] = value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vec):
            return NotImplemented
        return bool(np.array_equal(self.vals, other.vals))

    def __ne__(self, other: object) -> bool:
        eq_result = self.__eq__(other)
        if eq_result is NotImplemented:
            return NotImplemented
        return not eq_result

    def __abs__(self):
        return Vec(np.abs(self.vals))

    def __str__(self):
        return "Vec" + self.vals.tolist().__str__()

    ### UTILITIES ###

    def is_zero(self):
        return not self.vals.any()

    def to_2d(self):
        return self * Vec._SCALE_2D

    def length(self):
        return np.linalg.norm(self.vals)

    def length_sq(self):
        return float(np.dot(self.vals, self.vals))

    def dist(self, other):
        return (self - other).length()

    def dist_2d(self, other):
        return ((self - other) * Vec._SCALE_2D).length()

    def dist_sq(self, other):
        return (self - other).length_sq()

    def dist_sq_2d(self, other):
        return ((self - other) * Vec._SCALE_2D).length_sq()

    def normalized(self):
        # The lazy way lol
        return self / max(self.length(), 1e-7)

    def dot(self, other):
        return np.dot(self.vals, other.vals)

    def cross(self, other):
        return Vec(np.cross(self.vals, other.vals))

    def max(self, other):
        return Vec(np.maximum(self.vals, other.vals))

    def max_comp(self):
        return np.max(self.vals)
