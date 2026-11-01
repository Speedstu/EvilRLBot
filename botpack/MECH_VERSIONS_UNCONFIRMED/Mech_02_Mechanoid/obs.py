import numpy as np

from util.physics_object import PhysicsObject
from util.game_state import GameState
from util.player_data import PlayerData
from util import common_values

class AdvancedObsPadded:
    # Coeffs from CppOBS/AdvancedObs.h
    POS_COEF = 1.0 / 5000.0
    VEL_COEF = 1.0 / 2300.0
    ANG_VEL_COEF = 1.0 / 3.0

    MAX_TEAMMATES = 2
    MAX_OPPONENTS = 3
    PLAYER_FEAT_SIZE = 29

    def __init__(self):
        pass

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

        # Teammates padded to MAX_TEAMMATES (2*29 = 58 dims)
        teammates = [p for p in state.players if p.team_num == player.team_num and p.car_id != player.car_id]
        for i in range(self.MAX_TEAMMATES):
            if i < len(teammates):
                self._add_player_to_obs(obs, teammates[i], inverted, ball)
            else:
                obs.extend([0.0] * self.PLAYER_FEAT_SIZE)

        # Opponents padded to MAX_OPPONENTS (3*29 = 87 dims)
        opponents = [p for p in state.players if p.team_num != player.team_num]
        for i in range(self.MAX_OPPONENTS):
            if i < len(opponents):
                self._add_player_to_obs(obs, opponents[i], inverted, ball)
            else:
                obs.extend([0.0] * self.PLAYER_FEAT_SIZE)

        # Total: Ball (9) + Action (8) + Pads (34) + Self (29) + Teammates (58) + Opponents (87) = 225
        return np.asarray(obs, dtype=np.float32)
