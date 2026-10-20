"""Smoke checks for the faithful native RLBot GUI, without starting a game."""
from __future__ import annotations
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch, sentinel

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QMimeData, QUrl, Qt, QPointF
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication

from ui import server, bot_importer
from ui.classic import ClassicWindow, ImportTask, CSS


class ClassicGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(CSS)

    def setUp(self):
        self.window = ClassicWindow()
        self.window.show()
        self.app.processEvents()
        self.window.save = lambda: None
        self.window.save_timer.stop()

    def tearDown(self):
        self.window.save_timer.stop()
        self.window.close()
        self.app.processEvents()

    def test_classic_teams_and_filters(self):
        self.assertEqual("Blue", self.window.blue.objectName())
        self.assertEqual("Orange", self.window.orange.objectName())
        self.assertEqual("All", self.window._selected_filter)
        self.assertGreaterEqual(self.window.bot_grid.count(), 1)
        self.assertEqual("OfflineLegendary", self.window.launcher_combo.currentData())
        self.window.set_filter("Standard")
        self.assertTrue(self.window._filter_Standard.isChecked())
        self.window.set_filter("All")
        self.assertTrue(self.window._filter_All.isChecked())
        self.window.reset_teams()
        self.assertEqual(1, len(self.window.setup["players"]))
        self.window.add_player("psyonix", 1, "Allstar")
        self.assertEqual(2, len(self.window.setup["players"]))
        self.window.move_player(1)
        self.assertEqual(0, self.window.setup["players"][1]["team"])

    def test_native_drop_target_accepts_file_urls(self):
        from unittest.mock import Mock
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile("/tmp/mybot.zip")])
        drop = QDropEvent(QPointF(15, 15), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        with patch.object(self.window, "queue_import") as mock:
            self.window.orange.dropEvent(drop)
            mock.assert_called_once_with(["/tmp/mybot.zip"], target_team=1)

    def test_failed_match_offers_install_and_defers_until_worker_finishes(self):
        with patch("ui.classic.QMessageBox") as messages:
            dialog = messages.return_value
            dialog.addButton.side_effect = [sentinel.install, sentinel.cancel]
            dialog.clickedButton.return_value = sentinel.install
            self.window._busy = True
            self.window._operation_failed(
                "Bots cannot start: Nox (rlbot-v4): No module named 'torch'"
            )
            self.assertTrue(self.window._install_after_failed_match)
            self.assertTrue(self.window._busy)
            dialog.exec.assert_called_once()
            self.window._busy = False
            self.window._install_after_failed_match = False

    def test_import_worker_registers_zip_2_bots(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            archive = home / "pack.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("old/bot.cfg", "[Locations]\nname = Old\npython_file = bot.py\n")
                z.writestr("old/bot.py", "from rlbot.agents.base_agent import BaseAgent\n")
                z.writestr("new/bot.toml", '[settings]\nname="New"\nrun_command_linux="./run.sh"\nagent_id="new"\n')
                z.writestr("new/run.sh", "#!/bin/sh\n")
            saved = []
            with patch.object(bot_importer, "USER_DIR", home / "store"), \
                 patch.object(server, "_load_library", side_effect=lambda: list(saved)), \
                 patch.object(server, "_save_json", side_effect=lambda path, items: (saved.clear(), saved.extend(items))):
                task = ImportTask([str(archive)])
                received = []
                errors = []
                task.imported.connect(lambda items: received.extend(items))
                task.failed.connect(lambda msg: errors.append(msg))
                task.start()
                limit = time.monotonic() + 7
                while task.isRunning() and time.monotonic() < limit:
                    self.app.processEvents()
                    time.sleep(.01)
                task.wait(200)
                self.app.processEvents()
                self.assertFalse(errors, errors)
                self.assertEqual(2, len(saved))
                self.assertEqual(2, len(received))
                self.assertTrue(all(Path(item["path"]).is_file() for item in received))


if __name__ == "__main__":
    unittest.main()
