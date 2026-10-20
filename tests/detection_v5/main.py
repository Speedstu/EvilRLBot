from rlbot import flat
from rlbot.managers import Bot
from rlgym_rlbot import RLGymBot
from rlgym.rocket_league.obs_builders import DefaultObs
from rlgym.rocket_league.action_parsers import RepeatAction, LookupTableAction

class NativeV5(Bot):
    tick_skip = 4
    def get_output(self, packet: flat.GamePacket):
        return flat.ControllerState(throttle=1)
