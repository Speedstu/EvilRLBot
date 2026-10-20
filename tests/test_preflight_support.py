"""Regression: do not load an empty spectator-only game when bot import fails."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ui import preflight, support, server
from ui.bot_importer import Candidate

class PreflightTests(unittest.TestCase):
    def test_requirements_detect_torch_numpy(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)/"requirements.txt"
            p.write_text("# comment\nnumpy>=1.25\ntorch==2.8.0\n# torchvision\n")
            self.assertEqual(["numpy","torch"],preflight._requirements_modules(p))

    def test_missing_torch_blocks_real_match_launch(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            bot=root/"bot.cfg"
            bot.write_text("[Locations]\nname = FakeV4\npython_file = bot.py\n")
            (root/"bot.py").write_text("pass\n")
            req=root/"requirements.txt"
            req.write_text("torch\n")
            lineup={"launcher":"NoLaunch","players":[{"kind":"bot","id":"fake","team":0}]}
            with patch.object(server,"_bot_paths",return_value={"fake":str(bot)}), \
                 patch.object(preflight,"_python_check",return_value=(False,"torch: ModuleNotFoundError: No module named 'torch'")), \
                 patch.object(server.subprocess,"Popen",side_effect=AssertionError("DO NOT START SERVER")):
                with self.assertRaisesRegex(ValueError,"torch"):
                    server._start_match(lineup)

    def test_clean_v4_runtime_with_installed_deps(self):
        from ui import bot_importer
        from pathlib import Path
        path=Path.home()/".local/share/evilrlbot/bots/yukan-velo-255b0f7cd9b4692/yukan-velo/bot.cfg"
        if path.is_file():
            dep=bot_importer.dependency_path(path)
            ok, err=preflight._python_check("rlbot-v4",dep,["torch","numpy"])
            self.assertTrue(ok,err)

class SupportTests(unittest.TestCase):
    def test_credentials_redacted(self):
        raw="AUTH_PASSWORD=ABCDEF\nAuthorization: Bearer MY_TOKEN\nalice@example.com connected\nhttp://user:secret@private.invalid"
        text=support.sanitize(raw)
        self.assertNotIn("ABCDEF",text)
        self.assertNotIn("MY_TOKEN",text)
        self.assertNotIn("alice@example.com",text)
        self.assertNotIn("user:secret@",text)

    def test_export_log_pack(self):
        with tempfile.TemporaryDirectory() as d:
            archive=support.save_support_zip(Path(d)/"report.zip")
            import zipfile
            with zipfile.ZipFile(archive) as z:
                names=z.namelist()
                self.assertIn("summary.json",names)
                self.assertFalse(any("legendary" in name for name in names))
