import math

from backend.gamestate import common_values
from backend.gamestate.rot_mat import RotMat
from backend.gamestate.vec import Vec

ROUNDNESS = 280.0
INV_SQRT_2 = 1 / math.sqrt(2)
ONES = Vec(1, 1, 1)
ROT_45_MAT = RotMat([
    Vec(INV_SQRT_2, INV_SQRT_2, 0),
    Vec(-INV_SQRT_2, INV_SQRT_2, 0),
    Vec(0, 0, 1)
])
SEMI_SIZE = Vec(
    common_values.SIDE_WALL_X,
    common_values.BACK_WALL_Y,
    common_values.CEILING_Z / 2,
)
CORNER_SEMI_SIZE = Vec(
    INV_SQRT_2 * common_values.CORNER_WALL_AX_INTERSECT,
    INV_SQRT_2 * common_values.CORNER_WALL_AX_INTERSECT,
    common_values.CEILING_Z / 2,
)
GOALS_SEMI_SIZE = Vec(
    common_values.GOAL_WIDTH_FROM_CENTER,
    common_values.BACK_NET_Y,
    common_values.GOAL_HEIGHT / 2,
)
CENTER = Vec(0, 0, common_values.CEILING_Z / 2)
GOAL_CENTER = Vec(0, 0, common_values.GOAL_HEIGHT / 2)

def sdf_wall_dist(point: Vec) -> float:
    """
    Returns the distance to the nearest wall of using an SDF approximation.
    The result is negative if the point is outside the arena.
    """

    # SDF box https://www.youtube.com/watch?v=62-pRVZuS5c
    # SDF rounded corners https://www.youtube.com/watch?v=s5NGeUV2EyU

    # Base cube
    base_q = abs(point - CENTER) - SEMI_SIZE + ONES * ROUNDNESS
    base_dist_outside = base_q.max(Vec()).length()
    base_dist_inside = min(base_q.max_comp(), 0)
    base_dist = base_dist_outside + base_dist_inside

    # Corners cube
    corner_q = abs((ROT_45_MAT.dot(point)) - CENTER) - CORNER_SEMI_SIZE + ONES * ROUNDNESS
    corner_dist_outside = corner_q.max(Vec()).length()
    corner_dist_inside = min(corner_q.max_comp(), 0)
    corner_dist = corner_dist_outside + corner_dist_inside

    # Intersection of base and corners
    base_corner_dist = max(base_dist, corner_dist) - ROUNDNESS

    # Goals cube
    goals_q = abs(point - GOAL_CENTER) - GOALS_SEMI_SIZE + ONES * ROUNDNESS
    goals_dist_outside = goals_q.max(Vec()).length()
    goals_dist_inside = min(goals_q.max_comp(), 0)
    goals_dist = goals_dist_outside + goals_dist_inside

    # Union with goals and invert result
    return -min(base_corner_dist, goals_dist)


def sdf_normal(point: Vec) -> Vec:
    """
    Returns the normalized gradient at the given point. At wall distance 0 this is the arena's surface normal.
    """
    # SDF normals https://www.iquilezles.org/www/articles/normalsSDF/normalsSDF.htm
    d = 0.0004
    return Vec(
        sdf_wall_dist(point + Vec(d, 0, 0)) - sdf_wall_dist(point - Vec(d, 0, 0)),
        sdf_wall_dist(point + Vec(0, d, 0)) - sdf_wall_dist(point - Vec(0, d, 0)),
        sdf_wall_dist(point + Vec(0, 0, d)) - sdf_wall_dist(point - Vec(0, 0, d)),
    ).normalized()


def sdf_contains(point: Vec) -> bool:
    return sdf_wall_dist(point) > 0
