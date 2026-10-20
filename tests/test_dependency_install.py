"""Regression checks for long PyTorch installs on shared AppImages."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ui import bot_importer


class DependencyInstallerTests(unittest.TestCase):
    def test_cpu_torch_detection_and_redaction(self):
        with tempfile.TemporaryDirectory() as t:
            req = Path(t) / "requirements.txt"
            req.write_text("numpy\n# skip\n torch>=2.3.0\n", encoding="utf-8")
            self.assertTrue(bot_importer._mentions_torch(req))
            req.write_text("numpy\nsympy\n", encoding="utf-8")
            self.assertFalse(bot_importer._mentions_torch(req))
            self.assertNotIn("private_password",
                             bot_importer._safe_progress_line("https://user:private_password@server.example/extra"))

    def test_fast_dependency_install_streams_log(self):
        """Actually install tiny pure-Python wheel without touching global venv."""
        with tempfile.TemporaryDirectory() as t:
            config = Path(t) / "bot.cfg"
            config.write_text("[Locations]\npython_file = bot.py\n")
            req = Path(t) / "requirements.txt"
            req.write_text("six==1.17.0\n")
            progress = []
            with patch.object(bot_importer, "DEPS_DIR", Path(t) / "external_packages"):
                msg = bot_importer.install_dependencies(
                    config, req, "rlbot-v4", progress=progress.append, timeout_seconds=150
                )
                installed = bot_importer.dependency_path(config)
                self.assertTrue((installed / "six.py").is_file())
                self.assertIn("Dependencies installed", msg)
                self.assertTrue(progress)
                self.assertTrue(Path(msg.split("Log: ", 1)[1]).is_file())

    def test_cancel_does_not_corrupt_existing_environment(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = Path(t) / "bot.cfg"
            cfg.write_text("[Locations]\npython_file = bot.py\n")
            req = Path(t) / "requirements.txt"
            req.write_text("six\n")
            with patch.object(bot_importer, "DEPS_DIR", Path(t) / "dependency"):
                previous = bot_importer.dependency_path(cfg)
                previous.mkdir(parents=True)
                (previous / "keep-me.txt").write_text("previous installed dependencies")
                with self.assertRaises(InterruptedError):
                    bot_importer.install_dependencies(
                        cfg, req, "rlbot-v4", stop_requested=lambda: True, timeout_seconds=30
                    )
                self.assertEqual("previous installed dependencies", (previous / "keep-me.txt").read_text())


if __name__ == "__main__":
    unittest.main()
