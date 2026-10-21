"""Regression for mixed V4 Yukan + V5 Mirage games (empty match 2026-10-18)."""
from __future__ import annotations
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ui.bot_importer import dependency_path
from ui.match_config import build_match, _v5_with_deps
from ui import bot_importer
ROOT = Path(__file__).resolve().parents[1]

class V4WorkerIsolationTests(unittest.TestCase):
    def test_v4_worker_cannot_be_shadowed_by_v5_bot_requirements(self):
        python = ROOT / '.venv-v4/bin/python'
        contaminated = Path.home() / '.local/share/evilrlbot/dependencies/12d7e4e141322a462f'
        self.assertTrue(contaminated.is_dir())
        cmd = [str(python), '-I', '-c', 'import rlbot; from rlbot.agents.base_agent import BaseAgent; print(rlbot.__file__)']
        process = subprocess.run(cmd, env={**os.environ, 'PYTHONPATH': str(contaminated)},
                                 text=True, capture_output=True, timeout=20)
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertIn('.venv-v4', process.stdout)
        self.assertNotIn('evilrlbot/dependencies', process.stdout)

    def test_v4_bridge_wrapper_never_injects_v5_dependency_pythonpath(self):
        cfg = Path.home() / '.local/share/evilrlbot/bots/yukan-velo-255b0f7cd9b4692/yukan-velo/bot.cfg'
        if not cfg.is_file():
            self.skipTest('Yukan test bot missing')
        with tempfile.TemporaryDirectory() as tmp:
            cfg_v5 = ROOT / 'src/bot.toml'
            out = _v5_with_deps(cfg, cfg_v5, Path(tmp))
            wrapper = (Path(tmp) / 'run_v5.sh').read_text()
            self.assertNotIn('export PYTHONPATH=', wrapper)
            self.assertTrue(out.is_file())

    def test_v4_worker_is_isolated_when_using_bundled_python(self):
        bridge = (ROOT / 'src/v5_bridge.py').read_text()
        self.assertIn('str(ROOT / "v4_runtime" / "worker.py")', bridge)
        self.assertIn('bundled_python("rlbot-v4")', bridge)
        self.assertIn('"-I"', bridge)

if __name__ == '__main__':
    unittest.main()
