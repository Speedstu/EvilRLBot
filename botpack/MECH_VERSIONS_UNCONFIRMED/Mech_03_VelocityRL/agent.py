# In agent.py

import os
import numpy as np
import torch
from .discrete_policy import DiscreteFF
from .your_act import LookupAction


OBS_SIZE = 109
SHARED_LAYER_SIZES = [512, 512, 512, 512]
POLICY_LAYER_SIZES = [1024, 512, 512, 512, 512]

class Agent:
    def __init__(self):
        self.action_parser = LookupAction()
        self.num_actions = len(self.action_parser._lookup_table)
        cur_dir = os.path.dirname(os.path.realpath(__file__))
        
        device = torch.device("cpu")
        
        self.policy = DiscreteFF(OBS_SIZE, self.num_actions, SHARED_LAYER_SIZES, POLICY_LAYER_SIZES, device)
        
        shared_head_path = os.path.join(cur_dir, "SHARED_HEAD.LT")
        policy_path = os.path.join(cur_dir, "POLICY.LT")

        # Add `weights_only=False` to both torch.load calls
        self.policy.shared_head.load_state_dict(torch.load(shared_head_path, map_location=device, weights_only=False).state_dict())
        self.policy.policy.load_state_dict(torch.load(policy_path, map_location=device, weights_only=False).state_dict())

        torch.set_num_threads(1)

    def act(self, state):
        with torch.no_grad():
            action_idx, probs = self.policy.get_action(state, True)

        action = np.array(self.action_parser.parse_actions([action_idx]))
        if len(action.shape) == 2:
            if action.shape[0] == 1:
                action = action[0]
        
        if len(action.shape) != 1:
            raise Exception("Invalid action:", action)
        
        return action