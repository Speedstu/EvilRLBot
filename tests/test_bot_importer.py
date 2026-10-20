"""Safety and compatibility tests for drag/drop RLBot package imports."""
from __future__ import annotations
import io
import os
import stat
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from ui import bot_importer


CFG = """[Locations]
python_file = src/agent.py
name = OldSchool V4
requirements_file = requirements.txt
[Details]
developer = local fixture
"""
V5 = """[settings]
name = "Native V5"
agent_id = "local-fixture-v5"
run_command_linux = "./run.sh"
"""


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bots = self.root / "bots"
        self.bots.mkdir()
        (self.bots / "old").mkdir()
        (self.bots / "old" / "src").mkdir()
        (self.bots / "old" / "src" / "agent.py").write_text("from rlbot.agents.base_agent import BaseAgent\n")
        (self.bots / "old" / "bot.cfg").write_text(CFG)
        (self.bots / "old" / "requirements.txt").write_text("numpy\n")
        (self.bots / "new").mkdir()
        (self.bots / "new" / "bot.toml").write_text(V5)
        (self.bots / "new" / "run.sh").write_text("#!/bin/sh\necho test\n")
        self.patch_output = patch.object(bot_importer, "USER_DIR", self.root / "imported")
        self.patch_output.start()
        self.addCleanup(self.patch_output.stop)

    def test_mixed_folder_detection(self):
        bots = bot_importer.discover(self.bots)
        self.assertEqual({"rlbot-v4", "rlbot-v5"}, {b.framework for b in bots})
        v4 = next(b for b in bots if b.framework == "rlbot-v4")
        self.assertEqual("OldSchool V4", v4.name)
        self.assertEqual("requirements.txt", v4.requirements.name)
        self.assertFalse(v4.warning)

    def test_zip_with_executable(self):
        archive = self.root / "pack.zip"
        with zipfile.ZipFile(archive, "w") as zip:
            for p in self.bots.rglob("*"):
                if p.is_file():
                    zi = zipfile.ZipInfo(p.relative_to(self.bots).as_posix())
                    zi.external_attr = (0o755 if p.name == "run.sh" else 0o644) << 16
                    zip.writestr(zi, p.read_bytes())
        extracted = bot_importer.extract_archive(archive)
        self.assertTrue((extracted / "new/run.sh").stat().st_mode & stat.S_IXUSR)
        self.assertEqual(2, len(bot_importer.discover(extracted)))

    def test_reimport_identical_archive_reuses_directory(self):
        archive = self.root / "pack.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("v4/bot.cfg", CFG)
            z.writestr("v4/src/agent.py", "pass")
        one = bot_importer.extract_archive(archive)
        two = bot_importer.extract_archive(archive)
        self.assertEqual(one, two)
        self.assertEqual(1, len(bot_importer.discover(one)))

    def test_real_rar5_if_present(self):
        source = Path.home() / "Downloads/yukan-velo.rar"
        if not source.is_file():
            self.skipTest("User's RAR5 pack is not on this machine")
        unpacked = bot_importer.extract_archive(source)
        bots = bot_importer.discover(unpacked)
        self.assertEqual(1, len(bots))
        self.assertEqual("rlbot-v4", bots[0].framework)
        self.assertTrue((unpacked / "yukan-velo/latest.pt").is_file())
        self.assertEqual(unpacked, bot_importer.extract_archive(source))

    def test_configless_v4_python_runner_recognized(self):
        package = self.root / "nyx62b"
        package.mkdir()
        (package / "policy.lt").write_bytes(b"fake weights")
        source = package / "agent.py"
        source.write_text(
            "from rlbot.agents.base_agent import BaseAgent\n"
            "class Nyx62b(BaseAgent):\n"
            "    def get_output(self, packet):\n"
            "        return None\n"
        )
        items = bot_importer.discover(package)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].framework, "rlbot-v4")
        self.assertEqual(items[0].path, source)

    def test_model_only_requires_runner(self):
        package = self.root / "modelonly"
        package.mkdir()
        (package / "nyx62b.lt").write_bytes(b"weights")
        with self.assertRaisesRegex(ValueError, "matching BaseAgent"):
            bot_importer.import_path(package)

    def test_tar_archive(self):
        archive = self.root / "pack.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(self.bots, arcname="package")
        extracted = bot_importer.extract_archive(archive)
        self.assertEqual(2, len(bot_importer.discover(extracted)))

    def test_traversal_blocked(self):
        archive = self.root / "malicious.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("../outside.txt", "not allowed")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            bot_importer.extract_archive(archive)
        self.assertFalse((self.root / "outside.txt").exists())

    def test_symlink_blocked(self):
        archive = self.root / "link.zip"
        with zipfile.ZipFile(archive, "w") as z:
            info = zipfile.ZipInfo("link")
            info.create_system = 3
            info.external_attr = ((stat.S_IFLNK | 0o777) << 16)
            z.writestr(info, "../../../sensitive")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            bot_importer.extract_archive(archive)

    def test_seven_zip(self):
        try:
            import py7zr
        except ImportError:
            self.skipTest("py7zr not installed")
        archive = self.root / "pack.7z"
        with py7zr.SevenZipFile(archive, "w") as z:
            z.writeall(self.bots, arcname="folder")
        extracted = bot_importer.extract_archive(archive)
        self.assertEqual(2, len(bot_importer.discover(extracted)))

    def test_libraries_stay_idempotent(self):
        from ui import server
        state = []
        with patch.object(server, "_load_library", side_effect=lambda: list(state)), \
             patch.object(server, "_save_json", side_effect=lambda path, entries: (state.clear(), state.extend(entries))):
            first = bot_importer.import_path(self.bots)
            second = bot_importer.import_path(self.bots)
        self.assertEqual(2, len(first))
        self.assertEqual(2, len(state))
        self.assertFalse(any(x["new"] for x in second))

    def test_unconfigured_model_rejected(self):
        model = self.root / "weights.onnx"
        model.write_bytes(b"no runnable code")
        self.assertEqual([], bot_importer.discover(model))
        with self.assertRaisesRegex(ValueError, "no runnable"):
            bot_importer.import_path(model)


if __name__ == "__main__":
    unittest.main()
