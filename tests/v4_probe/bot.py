from rlbot.agents.base_agent import BaseAgent, SimpleControllerState
from rlbot.utils.game_state_util import GameState, CarState
from rlbot.utils.structures.quick_chats import QuickChats

class ProbeBot(BaseAgent):
    @staticmethod
    def create_agent_configurations(config):
        config.get_header('Bot Parameters').add_value('probe_value', int, default=0)

    def init_match_config(self, match_config):
        self.seen_mode = match_config.game_mode

    def load_config(self, header):
        self.probe_value = header.getint('probe_value')

    def initialize_agent(self):
        assert self.probe_value == 1337
        assert self.seen_mode == 'Soccer'
        assert self.get_field_info().num_boosts == 1
        assert self.get_match_settings().GameMode() == 0
        self.got_quick_chat = False

    def handle_quick_chat(self, index, team, quick_chat):
        self.got_quick_chat = (index == 9 and team == 1 and quick_chat == QuickChats.Compliments_NiceShot)

    def get_output(self, packet):
        assert self.got_quick_chat
        assert self.matchcomms.incoming_broadcast.get_nowait() == {'incoming': 'ok'}
        # EvilRLBot hybrid packet: exact v4 names and v5 names at once.
        assert packet.game_cars[0].spawn_id == 123
        assert packet.players[0].player_id == 123
        assert packet.players[0].physics.location.x == packet.game_cars[0].physics.location.x
        assert packet.balls[0].physics.location.x == packet.game_ball.physics.location.x
        assert packet.ball is packet.balls[0]
        assert packet.match_info.frame_num == packet.game_info.frame_num
        assert packet.num_players == packet.num_cars
        assert packet.num_balls == 1
        assert packet.evilrlbot.has_v4_fields and packet.evilrlbot.has_v5_fields
        assert self.evilrlbot.engine == 'v5'
        assert packet.num_cars == 1
        assert packet.game_info.is_round_active
        assert self.get_ball_prediction_struct().num_slices == 1
        self.renderer.begin_rendering('probe')
        self.renderer.draw_line_3d(packet.game_cars[self.index].physics.location, packet.game_ball.physics.location, self.renderer.purple())
        self.renderer.draw_string_3d(packet.game_ball.physics.location, 1, 1, 'v4 real', self.renderer.white())
        self.renderer.end_rendering()
        self.send_quick_chat(False, QuickChats.Information_IGotIt)
        self.matchcomms.outgoing_broadcast.put({'probe': 'matchcomms-ok'})
        self.set_game_state(GameState(cars={self.index: CarState(boost_amount=42)}))
        return SimpleControllerState(throttle=0.75, steer=-0.25, boost=True)
