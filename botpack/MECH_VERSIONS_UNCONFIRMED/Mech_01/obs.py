import numpy as np

from .util.physics_object import PhysicsObject
from .util.game_state import GameState
from .util.player_data import PlayerData
from .util import common_values

class AdvancedObs:
    # Coeffs from CppOBS/AdvancedObs.h
    POS_COEF = 1.0 / 5000.0
    VEL_COEF = 1.0 / 2300.0
    ANG_VEL_COEF = 1.0 / 3.0

    def __init__(self, max_players=6):
        self.max_players = max_players

    def _add_player_to_obs(self, obs_list: list, player: PlayerData, inverted: bool, ball_phys: PhysicsObject):
        phys = player.inverted_car_data if inverted else player.car_data

        # Player Physics
        obs_list.extend(list(phys.position * self.POS_COEF)) # 3
        
        rot = phys.rotation_mtx()
        forward = rot[:, 0]
        up = rot[:, 2]
        obs_list.extend(list(forward)) # 3
        obs_list.extend(list(up))      # 3
        
        obs_list.extend(list(phys.linear_velocity * self.VEL_COEF))     # 3
        obs_list.extend(list(phys.angular_velocity * self.ANG_VEL_COEF)) # 3
        
        # Local ang vel ?? C++ line 12: obs += phys.rotMat.Dot(phys.angVel) * ANG_VEL_COEF;
        # phys.rotMat is 3x3, angVel is 3. Dot product is 3 elements.
        local_ang_vel = rot.T @ phys.angular_velocity
        obs_list.extend(list(local_ang_vel * self.ANG_VEL_COEF)) # 3

        # Local ball pos and vel
        rel_pos = ball_phys.position - phys.position
        rel_vel = ball_phys.linear_velocity - phys.linear_velocity
        local_rel_pos = rot.T @ rel_pos
        local_rel_vel = rot.T @ rel_vel
        obs_list.extend(list(local_rel_pos * self.POS_COEF)) # 3
        obs_list.extend(list(local_rel_vel * self.VEL_COEF)) # 3

        # Player state
        obs_list.append(player.boost_amount) # 1
        obs_list.append(1.0 if player.on_ground else 0.0) # 1
        obs_list.append(1.0 if player.has_flip else 0.0)  # 1 (HasFlipOrJump)
        obs_list.append(1.0 if player.is_demoed else 0.0) # 1
        obs_list.append(1.0 if getattr(player, 'has_jumped', False) else 0.0) # 1 (hasJumped)

        # Total per player: 3+3+3+3+3+3+3+3 + 1+1+1+1+1 = 29 dims

    def build_obs(self, player: PlayerData, state: GameState, prev_action: np.ndarray) -> np.ndarray:
        obs = []
        inverted = player.team_num == 1

        ball = state.inverted_ball if inverted else state.ball
        pads = state.get_boost_pads(inverted)
        pad_timers = state.get_boost_pad_timers(inverted)
        
        # Ball Physics (9 dims)
        obs.extend(list(ball.position * self.POS_COEF))
        obs.extend(list(ball.linear_velocity * self.VEL_COEF))
        obs.extend(list(ball.angular_velocity * self.ANG_VEL_COEF))

        # Previous Action (8 dims)
        if prev_action is None:
            prev_action = np.zeros(8, dtype=np.float32)
        obs.extend(list(prev_action))

        # Boost Pads (34 dims) - with "clever trick"
        amount = common_values.BOOST_LOCATIONS_AMOUNT
        for i in range(amount):
             if pads[i] >= 0.5: # Is active
                 obs.append(1.0)
             else:
                 # 1.0 / (1.0 + timer)
                 timer = float(pad_timers[i]) if i < len(pad_timers) else 0.0
                 obs.append(1.0 / (1.0 + timer))

        # Self (29 dims)
        self._add_player_to_obs(obs, player, inverted, ball)

        # Teammates (0 dims for 1v1, but strict implementation loop would add them)
        # We must FORCE 1v1 structure to match the 109 input size.
        # This means NO teammates and EXACTLY ONE opponent.
        
        # Opponents (29 dims)
        
        # Find opponent
        opponents = [p for p in state.players if p.team_num != player.team_num]
        
        if len(opponents) > 0:
            opp = opponents[0]
            self._add_player_to_obs(obs, opp, inverted, ball)
        else:
            # Dummy opponent (Zeros for 29 dims)
            obs.extend([0.0] * 29)

        # Recalculate Total:
        # Ball (9) + Action (8) + Pads (34) + Self (29) + Opp (29) = 109.
        
        return np.asarray(obs, dtype=np.float32)
