import math

import rlbot.flat
from numba import jit

from backend.gamestate.common_values import CAR_MAX_SPEED, CAR_MAX_THROTTLE_SPEED, BOOST_ACCELERATION, TICK_TIME, \
    BALL_RADIUS
from backend.gamestate.player import Player
from backend.rlbot_conversion import convert_vec3
from utils import my_min


def rough_eta(player: Player, pred: rlbot.flat.BallPrediction) -> float:
    time = rough_eta.cache.setdefault(player.index, 0)
    for _ in range(2):
        tick = my_min(int(time * 120), 600 - 1)
        ball = pred.slices[tick]
        car_to_ball = convert_vec3(ball.physics.location) - player.pos
        dist = car_to_ball.length()
        car_to_ball_dir = car_to_ball / dist
        init_vel = player.vel.dot(car_to_ball_dir)
        time = linear_eta(init_vel, dist - 1.5 * BALL_RADIUS, player.boost / 33.3)
    rough_eta.cache[player.index] = time
    return time
rough_eta.cache = {}


@jit
def _solve_exp_segment(v0: float, x0: float, v_inf: float) -> float:
    """Solve for t in x(t) = x0 when v(t) = v_inf - (v_inf - v0) * exp(-t)"""
    A = v_inf - v0

    # Cheap initial guess
    t = x0 / max(v0, 1.0)

    # One iteration of Newton's method
    E = math.exp(-t)
    x_rem = v_inf * t + (v0 - v_inf) * (1 - E) - x0
    v_rem = v_inf - A * E
    t = t - x_rem / v_rem

    # Second iteration
    E = math.exp(-t)
    x_rem = v_inf * t + (v0 - v_inf) * (1 - E) - x0
    v_rem = v_inf - A * E
    t = t - x_rem / v_rem

    return t


@jit
def _solve_quad_segment(v0: float, x0: float, a: float) -> float:
    """Solve for t in x(t) = v0 * t + 0.5 * a * t^2 = x0"""
    # Cheap initial guess
    t = x0 / max(v0, 1.0)

    # One iteration of Newton's method
    x_rem = v0 * t + 0.5 * a * t * t - x0
    v_rem = v0 + a * t
    return t - x_rem / v_rem


@jit
def linear_eta(v0: float, x0: float, boost_dur: float) -> float:
    """Calculate linear ETA based on initial velocity, distance, and boost duration"""
    D = 1556.0
    THR_MAX = CAR_MAX_THROTTLE_SPEED
    B = BOOST_ACCELERATION
    v_inf = D + B

    t_sum = 0.0

    # CASE E: v0 >= max_speed
    if v0 >= CAR_MAX_SPEED:
        return x0 / CAR_MAX_SPEED

    # CASE A: v0 < THR_MAX and boost_dur > 0 (throttle and boost)
    if v0 < THR_MAX and boost_dur > 0:
        # Check if target hit during exponential phase
        t_dest = _solve_exp_segment(v0, x0, v_inf)
        if t_dest >= 0.0 and t_dest <= boost_dur:
            return t_dest

        t_to_max_throttle = math.log((v_inf - v0) / (v_inf - THR_MAX))
        T = min(t_to_max_throttle, boost_dur)

        # Compute state at end of case A
        exp_T = math.exp(-T)
        vT = v_inf - (v_inf - v0) * exp_T
        xT = v_inf * T + (v0 - v_inf) * (1 - exp_T)

        x0 -= xT
        v0 = vT
        boost_dur -= T
        t_sum += T

    # CASE B: v0 < THR_MAX and boost_dur == 0 (throttle)
    if v0 < THR_MAX and boost_dur <= 0:
        t_dest = _solve_exp_segment(v0, x0, D)
        t_to_max_throttle = math.log((D - v0) / (D - THR_MAX))

        # Do we reach destination before THR_MAX?
        if t_dest >= 0.0 and t_dest < t_to_max_throttle:
            return t_dest

        # Compute state at end of case B
        exp_T = math.exp(-t_to_max_throttle)
        vT = D - (D - v0) * exp_T
        xT = D * t_to_max_throttle + (v0 - D) * (1 - exp_T)

        x0 -= xT
        v0 = vT
        t_sum += t_to_max_throttle

    # CASE C: v0 >= THR_MAX and boost_dur > 0 (boost)
    if v0 >= THR_MAX and boost_dur > 0:
        # Do we reach destination before out of boost?
        t_dest = _solve_quad_segment(v0, x0, B)
        if t_dest >= 0.0 and t_dest <= boost_dur:
            return t_dest

        # Do we hit max speed during boost?
        t_to_max_speed = (CAR_MAX_SPEED - v0) / B
        if t_to_max_speed <= boost_dur:
            x0 -= v0 * t_to_max_speed + 0.5 * B * t_to_max_speed * t_to_max_speed
            return t_sum + t_to_max_speed + x0 / CAR_MAX_SPEED

        # We run out of boost first
        x0 -= v0 * boost_dur + 0.5 * B * boost_dur * boost_dur
        v0 = v0 + B * boost_dur
        boost_dur = 0
        t_sum += boost_dur

    # CASE D: THR_MAX <= v0 < vmax and boost_dur == 0 (no accel)
    return t_sum + x0 / v0