"""Persistent per-bot environments and more forgiving V4 bundle importing."""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from ui import bot_importer, preflight, server
from ui.match_config import build_match
from rlbot.config import load_match_config

class StableV4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.data = self.base / "dependencies"
        self.p1 = self.base / "Nox"
        self.p2 = self.base / "Nyx"
        for folder in (self.p1,self.p2):
            folder.mkdir(parents=True)
            (folder / "bot.cfg").write_text(
                "[Locations]\nname = Test Bot\npython_file = bot.py\n"
            )
            (folder / "bot.py").write_text(
                "from rlbot.agents.base_agent import BaseAgent\n"
                "import numpy\n"
                "class TestBot(BaseAgent):\n"
                "  def get_output(self, packet):\n"
                "    return None\n"
            )
            (folder / "requirements.txt").write_text("six==1.17.0\n")

    def test_identical_packages_download_once_for_two_v4_bots(self):
        with patch.object(bot_importer, "DEPS_DIR", self.data):
            a=self.p1/"bot.cfg"
            b=self.p2/"bot.cfg"
            first=bot_importer.install_dependencies(
                a,self.p1/"requirements.txt","rlbot-v4",timeout_seconds=150
            )
            self.assertIn("Dependencies installed", first)
            self.assertTrue(bot_importer.dependency_path(a).is_symlink())
            self.assertTrue((bot_importer.dependency_path(a)/"six.py").is_file())
            # Preflight itself launches an isolated Python process; only pip
            # must be skipped for a repeated package install.
            actual_popen = bot_importer.subprocess.Popen
            def assert_not_pip(cmd, *args, **kwargs):
                if "-m" in cmd and "pip" in cmd:
                    raise AssertionError("Pip MUST NOT run again")
                return actual_popen(cmd,*args,**kwargs)
            with patch.object(bot_importer.subprocess,"Popen",side_effect=assert_not_pip):
                second=bot_importer.install_dependencies(
                    b,self.p2/"requirements.txt","rlbot-v4",timeout_seconds=30
                )
            self.assertIn("reused from cache",second)
            self.assertTrue((bot_importer.dependency_path(b)/"six.py").is_file())
            self.assertEqual(
                bot_importer.dependency_path(a).resolve(),
                bot_importer.dependency_path(b).resolve()
            )

    def test_source_package_without_botcfg_imported_once_from_zip(self):
        archive=self.base/"Nyx62b.zip"
        with zipfile.ZipFile(archive,"w") as f:
            f.writestr(
                "Nyx62b/src/agent.py",
                "from rlbot.agents.base_agent import BaseAgent\n"
                "class Nyx62b(BaseAgent):\n"
                "  def get_output(self, packet):\n"
                "    return None\n"
            )
            f.writestr("Nyx62b/model.lt","mock data")
        memory=[]
        with patch.object(bot_importer,"USER_DIR",self.base/"unpacked"), \
             patch.object(server,"_load_library",side_effect=lambda:list(memory)), \
             patch.object(server,"_save_json",side_effect=lambda p,d:(memory.clear(),memory.extend(d))):
            first=bot_importer.import_path(archive)
            second=bot_importer.import_path(archive)
        self.assertEqual(len(first),1)
        self.assertEqual(len(memory),1)
        self.assertEqual(first[0]["id"],second[0]["id"])
        self.assertFalse(second[0]["new"])
        self.assertEqual(memory[0]["display_name"],"Nyx62b")
        setup={"players":[{"kind":"human","team":0},{"kind":"bot","id":first[0]["id"],"team":1}]}
        match=build_match(setup,{first[0]["id"]:first[0]["path"]})
        self.assertTrue(match.exists())
        parsed=load_match_config(match)
        self.assertEqual(len(parsed.player_configurations),2)

    def test_bundle_with_numpy_already_available(self):
        c=bot_importer.discover(self.p1/"bot.cfg")[0]
        # V4 NumPy is bundled; user must not need to reinstall it per match.
        self.assertIn("numpy",preflight._required_modules(c.path,c))
        self.assertTrue(preflight.dependencies_ready(c.path,c))

if __name__=="__main__":
    unittest.main()
