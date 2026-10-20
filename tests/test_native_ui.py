"""Offscreen smoke tests for native Evil RLBot Qt user interface."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from PySide6.QtWidgets import QApplication
    from ui.native import NativeWindow, QSS, MutatorsDialog, OptionsDialog
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 Essentials not installed")
class QtNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(QSS)

    def setUp(self):
        self.win = NativeWindow()
        # Do not mutate the user's saved match setup during tests.
        self.win.save_setup = lambda: None
        self.win.save_timer.stop()
        self.win.show()
        self.app.processEvents()

    def tearDown(self):
        self.win.save_timer.stop()
        self.win.close()
        self.app.processEvents()

    def test_native_window_has_real_team_builder(self):
        self.assertEqual(4, self.win.stack.count())
        self.assertIn(self.win.launcher_combo.currentData(), {"Heroic", "Steam", "Legendary", "NoLaunch", "OfflineLegendary"})
        self.assertGreaterEqual(self.win.bot_list.count(), 1)
        self.win.preset(2)
        self.app.processEvents()
        self.assertEqual("2 PLAYERS", self.win.blue.count.text())
        self.assertEqual("2 PLAYERS", self.win.orange.count.text())
        self.assertEqual(4, len(self.win.setup["players"]))
        self.win.reset_teams()
        self.app.processEvents()
        self.assertEqual("1 PLAYER", self.win.blue.count.text())
        self.assertEqual("0 PLAYERS", self.win.orange.count.text())

    def test_mutator_options_native_dialogs(self):
        dlg = MutatorsDialog(self.win, self.win.setup)
        self.assertEqual(16, len(dlg.controls))
        self.assertEqual("FiveMinutes", dlg.values()["match_length"])
        dlg.reset()
        self.assertEqual("Unlimited", dlg.values()["max_score"])
        dlg.close()
        extras = OptionsDialog(self.win, self.win.setup)
        self.assertEqual(5, len(extras.checks))
        self.assertTrue(extras.values()["enable_rendering"])
        extras.close()

    def test_bot_assignment_without_browser(self):
        self.win.reset_teams()
        self.app.processEvents()
        bot_id = self.win.chosen_bot_id()
        self.assertTrue(bot_id)
        self.win.add_player("bot", 1, bot_id)
        self.app.processEvents()
        self.assertEqual("1 PLAYER", self.win.orange.count.text())
        self.assertEqual("bot", self.win.setup["players"][-1]["kind"])
        self.win.swap_player(1)
        self.assertEqual("2 PLAYERS", self.win.blue.count.text())


if __name__ == "__main__":
    unittest.main()
