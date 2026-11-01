import numpy as np
import os
import sys
from rlbot.agents.base_agent import BaseAgent, SimpleControllerState
from rlbot.utils.structures.game_data_struct import GameTickPacket
import math

BOT_DIR = os.path.dirname(os.path.realpath(__file__))
if BOT_DIR not in sys.path:
    sys.path.insert(0, BOT_DIR)

from util import common_values
from util.game_state import GameState
from util.player_data import PlayerData
from agent import Agent as Agent_Base
from obs import AdvancedObsPadded


class RLGymPPOBot(BaseAgent):
    def __init__(self, name, team, index):
        super().__init__(name, team, index)
        self.base_agent = Agent_Base()
        self.base_obs_builder = AdvancedObsPadded()
        self.tick_skip = 8
        self.game_state: GameState = None
        self.controls = SimpleControllerState()
        self.action = None
        self.update_action = True
        self.ticks = 0
        self.prev_time = 0


    def is_hot_reload_enabled(self):
        return True

    def initialize_agent(self):
        self.game_state = GameState(self.get_field_info())
        self.update_action = True
        self.ticks = self.tick_skip
        self.controls = SimpleControllerState()
        self.action = np.zeros(8)

    def get_output(self, packet: GameTickPacket) -> SimpleControllerState:
        cur_time = packet.game_info.seconds_elapsed
        delta = cur_time - self.prev_time
        self.prev_time = cur_time
        ticks_elapsed = round(delta * 120)
        self.ticks += ticks_elapsed
        self.game_state.decode(packet, ticks_elapsed)

        if self.update_action:
            self.update_action = False
            player = self.game_state.players[self.index]
            active_obs_builder = self.base_obs_builder
            active_agent = self.base_agent
            obs = active_obs_builder.build_obs(player, self.game_state, self.action)
            self.action = active_agent.act(obs)

        if self.ticks >= self.tick_skip - 1:
            self.update_controls(self.action)

        if self.ticks >= self.tick_skip:
            self.ticks = 0
            self.update_action = True

        return self.controls

    def update_controls(self, action):
        self.controls.throttle = action[0]
        self.controls.steer = action[1]
        self.controls.pitch = action[2]
        self.controls.yaw = action[3]
        self.controls.roll = action[4]
        self.controls.jump = action[5] > 0
        self.controls.boost = action[6] > 0
        self.controls.handbrake = action[7] > 0
