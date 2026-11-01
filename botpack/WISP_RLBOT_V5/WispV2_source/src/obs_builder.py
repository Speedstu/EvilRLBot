import random

import rlbot.flat

from backend.gamestate.phys_obj import PhysObj
from backend.gamestate import common_values
from backend.gamestate.gamestate import GameState
from backend.gamestate.player import Player
from backend.gamestate.team import Team
from backend.obs_buffer import ObsBuffer
from backend.rlbot_conversion import convert_phys
from eta import rough_eta
from utils import dist_to_back_wall, dist_to_side_wall, dist_to_corner_wall, normal_at_landing, clip, turn_radius, \
    dodge_relative_rot_mat, is_goal_post_between, dist_to_closest_wall


class CustomObs:
    POS_COEF = 1.0 / 5000.0
    VEL_COEF = 1.0 / 2300.0
    ANG_VEL_COEF = 1.0 / 3.0
    MAX_PLAYERS = 3  # Always 3 players per team slot

    CLOSE_BOOST_CAR_OFFSET = 420.0
    CLOSE_BOOST_PADS_COUNT = 5

    TOTAL_BALL_PRED_TICKS = 600
    BALL_PRED_INIT_STEP = 22
    BALL_PRED_OBS_MAX = 600
    BALL_PRED_STEP_INCREASE_MULT = 3

    def add_player_to_obs(self, obs: ObsBuffer, player: Player, inv: bool, mirror_x: bool, ball: PhysObj, ball_pred: rlbot.flat.BallPrediction):
        phys = player.invert_y(inv).mirror_x(mirror_x)
        dodge_rot_mat = dodge_relative_rot_mat(phys.rot_mat, mirror_x)
        my_goal = common_values.BLUE_GOAL_CENTER
        opp_goal = common_values.ORANGE_GOAL_CENTER

        obs += phys.pos * self.POS_COEF
        obs += phys.rot_mat.forward
        obs += phys.rot_mat.up
        obs += phys.vel * self.VEL_COEF
        obs += phys.ang_vel * self.ANG_VEL_COEF
        obs += phys.rot_mat.dot(phys.ang_vel) * self.ANG_VEL_COEF
        obs += phys.rot_mat.forward.dot(phys.vel) * self.VEL_COEF

        # Local ball pos and vel
        obs += phys.rot_mat.dot(ball.pos - phys.pos) * self.POS_COEF
        obs += phys.rot_mat.dot(ball.vel - phys.vel) * self.VEL_COEF
        dodge_rel_ball_pos = dodge_rot_mat.dot(ball.pos - phys.pos) * self.POS_COEF
        obs += dodge_rel_ball_pos.x
        obs += dodge_rel_ball_pos.y
        dodge_rel_ball_vel = dodge_rot_mat.dot(ball.vel - phys.vel) * self.VEL_COEF
        obs += dodge_rel_ball_vel.x
        obs += dodge_rel_ball_vel.y

        # Local shot direction
        obs += phys.rot_mat.dot((my_goal - ball.pos).normalized()) * self.POS_COEF
        obs += phys.rot_mat.dot((opp_goal - ball.pos).normalized()) * self.POS_COEF
        dodge_rel_shot_own_goal = dodge_rot_mat.dot((my_goal - ball.pos).normalized()).to_2d() * self.POS_COEF
        obs += dodge_rel_shot_own_goal.x
        obs += dodge_rel_shot_own_goal.y
        dodge_rel_shot_opp_goal = dodge_rot_mat.dot((opp_goal - ball.pos).normalized()).to_2d() * self.POS_COEF
        obs += dodge_rel_shot_opp_goal.x
        obs += dodge_rel_shot_opp_goal.y

        obs += player.boost / 100.0
        obs += player.is_on_ground
        obs += player.has_flip_or_jump()
        obs += player.is_demoed
        obs += player.is_jumping
        obs += player.has_flip_reset()

        obs += abs(player.pos.y) > common_values.BACK_WALL_Y - 10
        obs += is_goal_post_between(player.pos, ball.pos)
        obs += dist_to_closest_wall(player.pos.x, player.pos.y) * self.POS_COEF

        obs += 10 if player.is_demoed else rough_eta(player, ball_pred)

        if player.is_demoed:
            # We zero everything above if we are demoed
            obs.fill_zero()
        obs += player.is_demoed
        obs += player.demo_respawn_timer / common_values.DEMO_RESPAWN_TIME


    def build_obs(self, player: Player, state: GameState, ball_pred: rlbot.flat.BallPrediction, score_diff: int) -> ObsBuffer:
        obs = ObsBuffer()
        inv = player.team == Team.ORANGE
        mirror_x = inv != (player.pos.x < 0)
        phys = player.invert_y(inv).mirror_x(mirror_x)

        ball = state.ball.invert_y(inv).mirror_x(mirror_x)
        pads = state.get_boost_pads(inv, mirror_x)
        pad_timers = state.get_boost_pad_timers(inv, mirror_x)

        my_goal = common_values.ORANGE_GOAL_CENTER if inv else common_values.BLUE_GOAL_CENTER
        opp_goal = common_values.BLUE_GOAL_CENTER if inv else common_values.ORANGE_GOAL_CENTER

        # ===== BALL =====
        obs += ball.pos * self.POS_COEF
        obs += ball.vel * self.VEL_COEF
        obs += ball.ang_vel * self.ANG_VEL_COEF

        obs += (my_goal - ball.pos) * self.POS_COEF
        obs += (opp_goal - ball.pos) * self.POS_COEF

        obs += ball.pos.to_2d().is_zero()   # Is kickoff

        # Predictions
        i = self.BALL_PRED_INIT_STEP
        while i < self.BALL_PRED_OBS_MAX:
            slice = ball_pred.slices[i]
            pred = convert_phys(slice.physics).invert_y(inv).mirror_x(mirror_x)
            obs += pred.pos * self.POS_COEF
            obs += pred.vel * self.VEL_COEF
            obs += phys.rot_mat.dot(pred.pos - phys.pos) * self.POS_COEF
            obs += phys.rot_mat.dot(pred.vel - phys.vel) * self.VEL_COEF
            i *= self.BALL_PRED_STEP_INCREASE_MULT

        # ===== BOOST PADS =====
        soon_pos = player.pos + player.rot_mat.forward * self.CLOSE_BOOST_CAR_OFFSET

        for i in range(common_values.BOOST_LOCATIONS_AMOUNT):
            if pads[i]:
                obs += 1.0   # Available
            else:
                t = float(pad_timers[i]) if i < len(pad_timers) else 0.0
                obs += 1.0 / (1.0 + t)

        close_pads = sorted(common_values.BOOST_LOCATIONS, key=lambda pos: pos.dist_sq(soon_pos))
        for pad in close_pads[:self.CLOSE_BOOST_PADS_COUNT]:
            rel_pad_pos = player.rot_mat.dot(pad - player.pos) * self.POS_COEF
            obs += rel_pad_pos.x
            obs += -rel_pad_pos.y if mirror_x else rel_pad_pos.y   # Relative left-right is mirrored

        # ===== ACTIONS =====
        obs += (player.prev_action.mirror_x() if mirror_x else player.prev_action).get_np()

        # ===== ARENA/WALLS =====
        obs += dist_to_back_wall(player.pos.x, player.pos.y) * self.POS_COEF
        obs += dist_to_side_wall(player.pos.x, player.pos.y) * self.POS_COEF
        obs += dist_to_corner_wall(player.pos.x, player.pos.y) * self.POS_COEF
        obs += phys.rot_mat.dot(normal_at_landing(player))

        # ===== SCOREBOARD =====
        obs += clip(score_diff, -1, 1)

        # ===== CARS =====
        fw_vel = player.vel.dot(phys.rot_mat.forward)
        obs += turn_radius(min(abs(fw_vel), common_values.CAR_MAX_SPEED)) / 1300.0
        obs += player.ball_touched_step
        obs += player.handbrake_val

        self_obs = ObsBuffer()
        self.add_player_to_obs(self_obs, player, inv, mirror_x, ball, ball_pred)
        player_obs_size = len(self_obs)
        obs += self_obs

        teammates: list[ObsBuffer] = []
        opponents: list[ObsBuffer] = []

        for other in state.players:
            if other.index == player.index:
                continue

            player_obs = ObsBuffer()
            self.add_player_to_obs(player_obs, other, inv, mirror_x, ball, ball_pred)

            if other.team == player.team:
                teammates.append(player_obs)
            else:
                opponents.append(player_obs)

        # Pad to always have 3 teammates and 3 opponents
        while len(teammates) < self.MAX_PLAYERS - 1:
            teammates.append(ObsBuffer(player_obs_size))
        while len(opponents) < self.MAX_PLAYERS:
            opponents.append(ObsBuffer(player_obs_size))

        # Shuffle before adding (also handles team sizes of 4+)
        random.shuffle(teammates)
        random.shuffle(opponents)

        for t in teammates:
            obs += t
        for o in opponents:
            obs += o

        return obs
