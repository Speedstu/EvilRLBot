import math

from arena_sdf import sdf_contains, sdf_normal
from backend.gamestate import common_values
from backend.gamestate.common_values import GRAVITY
from backend.gamestate.phys_obj import PhysObj
from backend.gamestate.rot_mat import RotMat
from backend.gamestate.vec import Vec


SQRT_2 = math.sqrt(2)
INV_SQRT_2 = 1 / SQRT_2


def clip(v, mn = 0.0, mx = 1.0):
    if v < mn:
        return mn
    if v > mx:
        return mx
    return v


def my_min(v1: float, v2: float):
    return v1 if v1 < v2 else v2


def my_max(v1: float, v2: float):
    return v1 if v1 > v2 else v2


def my_abs(v: float):
    return v if v >= 0 else -v


def is_goal_post_between(fst: Vec, snd: Vec) -> bool:
    """
    Returns true if the line segment from fst to snd goes through a goal post or cross bar
    """
    fst_not_goal = my_abs(fst.y) < common_values.BACK_WALL_Y
    if fst_not_goal and my_abs(snd.y) < common_values.BACK_WALL_Y:
        return False

    in_goal = snd if fst_not_goal else fst
    other = fst if fst_not_goal else snd

    # Flip to positive y (flipping x is unnecessary as we have to check both posts anyway)
    if in_goal.y < 0:
        in_goal = Vec(in_goal.x, -in_goal.y, in_goal.z)
        other = Vec(other.x, -other.y, other.z)

    # Left post
    gx = in_goal.x + common_values.GOAL_WIDTH_FROM_CENTER
    gy = in_goal.y - common_values.BACK_WALL_Y
    bx = other.x + common_values.GOAL_WIDTH_FROM_CENTER
    by = other.y - common_values.BACK_WALL_Y
    if bx < 0 and gy / gx >= by / bx:
        return True

    # Right post
    gx = in_goal.x - common_values.GOAL_WIDTH_FROM_CENTER
    gy = in_goal.y - common_values.BACK_WALL_Y
    bx = other.x - common_values.GOAL_WIDTH_FROM_CENTER
    by = other.y - common_values.BACK_WALL_Y
    if bx > 0 and gy / gx <= by / bx:
        return True

    # Cross bar
    gy = in_goal.y - common_values.BACK_WALL_Y
    gz = in_goal.z - common_values.GOAL_HEIGHT
    by = other.y - common_values.BACK_WALL_Y
    bz = other.z - common_values.GOAL_HEIGHT
    if bz > 0 and gz / gy >= bz / by:
        return True

    return False


def dist_to_side_wall(x: float, y: float) -> float:
    return common_values.SIDE_WALL_X - my_abs(x)


def dist_to_back_wall(x: float, y: float) -> float:
    return common_values.BACK_WALL_Y - my_abs(y)


def dist_to_corner_wall(x: float, y: float) -> float:
    x1 = common_values.SIDE_WALL_X - 1152
    y1 = common_values.BACK_WALL_Y
    x2 = common_values.SIDE_WALL_X
    y2 = common_values.BACK_WALL_Y - 1152
    
    A = my_abs(x) - x1
    B = my_abs(y) - y1
    C = x2 - x1
    D = y2 - y1
    
    dot = A * C + B * D
    len_squared = C * C + D * D
    param = -1
    
    if not (len_squared == 0):
        param = dot / len_squared
        
    if param < 0:
        xx = x1
        yy = y1
    elif param > 1:
        xx = x2
        yy = y2
    else:
        xx = x1 + param * C
        yy = y1 + param * D
        
    dx = my_abs(x) - xx
    dy = my_abs(y) - yy
    
    return math.sqrt(dx * dx + dy * dy)


def dist_to_closest_wall(x: float, y: float) -> float:
    return my_min(my_min(dist_to_side_wall(x, y), dist_to_back_wall(x, y)), dist_to_corner_wall(x, y))


def normal_at_landing(phys: PhysObj) -> Vec:
    TIME_STEP = 0.25
    pos = phys.pos
    vel = phys.vel
    max = 10.0
    while sdf_contains(pos) and max > 0:
        vel = vel + GRAVITY * TIME_STEP
        pos = pos + vel * TIME_STEP
        max -= TIME_STEP
    pos = pos - 0.5 * vel * TIME_STEP  # Undo half a step
    return sdf_normal(pos)


def turn_radius(v: float) -> float:
    if v == 0:
        return 0
    return 1.0 / curvature(v)


def curvature(v: float) -> float:
    if 0.0 <= v < 500.0:
        return 0.006900 - 5.84e-6 * v
    if 500.0 <= v < 1000.0:
        return 0.005610 - 3.26e-6 * v
    if 1000.0 <= v < 1500.0:
        return 0.004300 - 1.95e-6 * v
    if 1500.0 <= v < 1750.0:
        return 0.003025 - 1.1e-6 * v
    if 1750.0 <= v < 2500.0:
        return 0.001800 - 4e-7 * v

    return 0.0


def dodge_relative_rot_mat(original: RotMat, mirror_x: bool) -> RotMat:
    rel_mat = RotMat()
    fw = original.forward.to_2d().normalized()
    rel_mat.forward = fw
    rel_mat.right.x = fw.y if mirror_x else -fw.y
    rel_mat.right.y = -fw.x if mirror_x else fw.x
    rel_mat.up.z = 1.0
    return rel_mat
