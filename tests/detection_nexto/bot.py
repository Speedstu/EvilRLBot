from rlbot.agents.base_agent import BaseAgent, SimpleControllerState
from rlgym_compat import GameState
from nexto_obs import NextoObsBuilder
import torch

class Bot(BaseAgent):
    def __init__(self, name, team, index):
        super().__init__(name, team, index)
        self.obs_builder = NextoObsBuilder()
        self.tick_skip = 8
        self.model = torch.jit.load('nexto-model.pt')
