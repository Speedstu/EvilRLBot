import numpy as np
import rlbot.flat

from .gamestate.vec import Vec
from .gamestate.rot_mat import RotMat
from .gamestate.phys_obj import PhysObj
from .gamestate.player import Player
from .gamestate.gamestate import GameState
from .gamestate.action import Action
from .gamestate.team import Team
from .gamestate import common_values

def convert_vec3(vec3: rlbot.flat.Vector3) -> Vec:
    return Vec(vec3.x, vec3.y, vec3.z)

def convert_rotator_to_mat(rotator: rlbot.flat.Rotator) -> RotMat:
    # Based on BulletPhysics "btMatrix3x3::setEulerZYX()"
    angles = np.array([rotator.roll, rotator.pitch, rotator.yaw])
    c = np.cos(angles)
    s = np.sin(angles)

    ci, cj, ch = c
    si, sj, sh = s
    cc, cs, sc, ss = np.outer([ci, si], [ch, sh]).flatten()

    r = RotMat([
        cj * ch, sj * sc - cs, sj * cc + ss,
        cj * sh, sj * ss + cc, sj * cs - sc,
        -sj, cj * si, cj * ci
    ]).transpose()

    # Fix transformation
    # TODO: Why is the math wrong in the first place?
    r[0][2] *= -1
    r[2][0] *= -1
    r[1][2] *= -1
    r[2][1] *= -1

    return r


def convert_phys(physics: rlbot.flat.Physics) -> PhysObj:
    return PhysObj(
        pos = convert_vec3(physics.location),
        rot_mat = convert_rotator_to_mat(physics.rotation),
        vel = convert_vec3(physics.velocity),
        ang_vel = convert_vec3(physics.angular_velocity)
    )

def convert_controller_state_to_action(controls: rlbot.flat.ControllerState) -> Action:
    result = Action()
    result.throttle = controls.throttle
    result.steer = controls.steer
    result.pitch = controls.pitch
    result.yaw = controls.yaw
    result.roll = controls.roll
    result.jump = controls.jump
    result.boost = controls.boost
    result.handbrake = controls.handbrake
    return result

def convert_action_to_controller_state(action: Action) -> rlbot.flat.ControllerState:
    return rlbot.flat.ControllerState(
        throttle=action.throttle, steer=action.steer,
        pitch=action.pitch, yaw=action.yaw, roll=action.roll,
        jump=bool(action.jump), boost=bool(action.boost), handbrake=bool(action.handbrake)
    )

def convert_player(player: rlbot.flat.PlayerInfo) -> Player:
    team = Team.BLUE if player.team == 0 else Team.ORANGE
    result = Player(team)
    result.set_phys(convert_phys(player.physics))
    result.is_on_ground = (player.air_state == rlbot.flat.AirState.OnGround)
    result.is_jumping = player.air_state == rlbot.flat.AirState.Jumping
    result.has_jumped = player.has_jumped
    result.is_flipping = player.air_state == rlbot.flat.AirState.Dodging
    result.has_flipped = player.has_dodged
    result.has_double_jumped = player.has_double_jumped

    result.boost = player.boost
    result.is_demoed = player.demolished_timeout > 0
    result.demo_respawn_timer = max(0.0, player.demolished_timeout)

    result.prev_action = convert_controller_state_to_action(player.last_input)
    return result

def convert_packet(packet: rlbot.flat.GamePacket) -> GameState:
    result = GameState()

    result.ball = convert_phys(packet.balls[0].physics)

    for rlbot_player in packet.players:
        result.players.append(convert_player(rlbot_player))

    assert len(packet.boost_pads) == len(common_values.BOOST_LOCATIONS)
    for i in range(len(common_values.BOOST_LOCATIONS)):
        rlbot_pad = packet.boost_pads[i]
        result.boost_pads[i] = rlbot_pad.is_active
        result.boost_pad_timers[i] = rlbot_pad.timer

    result.boost_pads_inv = result.boost_pads[::-1]
    result.boost_pad_timers_inv = result.boost_pad_timers[::-1]

    return result