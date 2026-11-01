import torch
from backend.gamestate.action import Action
from backend.gamestate.gamestate import GameState
from backend.gamestate.player import Player
from backend.gamestate.team import Team


# DefaultAction
class DefaultAction:
    def __init__(self):
        # Build lookup table

        R_B = [0, 1]
        R_F = [-1, 0, 1]

        self.actions = []

        # Ground
        for throttle in R_F:
            for steer in R_F:
                for boost in R_B:
                    for handbrake in R_B:
                        # Prevent useless throttle when boosting
                        if boost == 1 and throttle != 1:
                            continue

                        self.actions.append(
                            Action([throttle, steer, 0, steer, 0, 0, boost, handbrake])
                        )

        num_ground_actions = len(self.actions)

        # Aerial
        for pitch in R_F:
            for yaw in R_F:
                for roll in R_F:
                    for jump in R_B:
                        for boost in R_B:
                            # Only need roll for sideflip
                            if jump == 1 and yaw != 0:
                                continue

                            # Duplicate with ground
                            if pitch == roll and roll == jump and jump == 0:
                                continue

                            # Enable handbrake for potential wavedashes
                            handbrake = (
                                1
                                if (jump == 1) and (pitch != 0 or yaw != 0 or roll != 0)
                                else 0
                            )

                            self.actions.append(
                                Action(
                                    [
                                        boost,
                                        yaw,
                                        pitch,
                                        yaw,
                                        roll,
                                        jump,
                                        boost,
                                        handbrake,
                                    ]
                                )
                            )

        ### BUILD MASKS ###

        n = len(self.actions)
        self.jump_mask = torch.zeros(n, dtype=torch.bool)
        self.boost_mask = torch.zeros(n, dtype=torch.bool)
        self.ground_mask = torch.zeros(n, dtype=torch.bool)
        self.air_mask = torch.zeros(n, dtype=torch.bool)

        # Process actions and set masks
        for i in range(len(self.actions)):
            action = self.actions[i]

            if action.jump:
                self.jump_mask[i] = True
            if action.boost:
                self.boost_mask[i] = True

            if i < num_ground_actions:
                self.ground_mask[i] = True
            if i > num_ground_actions and not action.jump:
                self.air_mask[i] = True

            # Add additional yaw-only actions to air mask
            # These actions were skipped during air action generation to prevent duplicates
            if i < num_ground_actions:
                if action.throttle == action.boost and (action.yaw != 0) == bool(
                    action.handbrake
                ):
                    self.air_mask[i] = True

    @staticmethod
    def _apply_mask(mask: torch.Tensor, result: torch.Tensor, add: bool):
        if add:
            result |= mask
        else:
            result &= ~mask

    def get_action_mask(self, player: Player, state: GameState) -> torch.Tensor:
        result = torch.zeros(len(self.actions), dtype=torch.bool)

        if player.is_on_ground:
            DefaultAction._apply_mask(self.ground_mask, result, True)
        else:
            DefaultAction._apply_mask(self.air_mask, result, True)

        if player.boost == 0:
            DefaultAction._apply_mask(self.boost_mask, result, False)

        if player.has_flip_or_jump() or player.is_probably_turtled():
            DefaultAction._apply_mask(self.jump_mask, result, True)

        return result

    def get_action(self, index: int, player: Player, state: GameState) -> Action:
        return self.actions[index]


class XMirroredActionParser(DefaultAction):
    def get_action(self, index: int, player: Player, state: GameState) -> Action:
        mirror_x = (player.team == Team.ORANGE) != (player.pos.x < 0)
        return self.actions[index].mirror_x() if mirror_x else self.actions[index]