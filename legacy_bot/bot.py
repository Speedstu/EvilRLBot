# This file intentionally looks like a classic RLBot v4 bot.
# Existing v4 bot logic can be pasted here with minimal/no API changes.
from math import atan2

from rlbot.agents.base_agent import BaseAgent, SimpleControllerState


class EvilBot(BaseAgent):
    def initialize_agent(self):
        self.tick_count = 0

    def get_output(self, packet):
        self.tick_count += 1
        controls = SimpleControllerState()
        if packet.num_cars <= self.index:
            return controls

        car = packet.game_cars[self.index]
        ball = packet.game_ball
        dx = ball.physics.location.x - car.physics.location.x
        dy = ball.physics.location.y - car.physics.location.y
        target_yaw = atan2(dy, dx)
        current_yaw = car.physics.rotation.yaw

        # shortest signed angle, then a simple proportional steering command
        error = (target_yaw - current_yaw + 3.14159265) % (2 * 3.14159265) - 3.14159265
        controls.throttle = 1.0
        controls.steer = max(-1.0, min(1.0, error * 2.5))
        controls.boost = abs(error) < 0.15 and car.boost > 10
        return controls
