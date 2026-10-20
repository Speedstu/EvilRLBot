"""Regression checks for the known-working offline RLBot v5 launch path."""
from __future__ import annotations

import unittest
from ui.offline_launcher import command, running_game_pids
from ui.match_config import build_match, validate_setup
from rlbot.config import load_match_config


class OfflineLauncherTests(unittest.TestCase):
    def test_offline_command_uses_standard_rlbot_bridge(self):
        c = command()
        self.assertIn("--offline", c)
        self.assertIn("-rlbot", c)
        self.assertIn("RLBot_ControllerURL=127.0.0.1:23233", c)
        self.assertIn("RLBot_PacketSendRate=240", c)
        self.assertNotIn("--", c)  # This separator was incorrectly passed to RL.
        self.assertIn("Sugar", c)
        self.assertIn("--wine-prefix", c)

    def test_offline_launch_setting_parses_as_no_launch(self):
        setup = validate_setup({
            "launcher": "OfflineLegendary",
            "players": [{"kind": "human", "team": 0}],
        }, {})
        p = build_match(setup, {})
        self.assertEqual("NoLaunch", str(load_match_config(p).launcher).rsplit(".", 1)[-1])

    def test_running_game_pids_are_valid(self):
        self.assertTrue(all(isinstance(x, int) and x > 0 for x in running_game_pids()))


if __name__ == "__main__":
    unittest.main()
