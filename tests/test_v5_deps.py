"""Test V5 dependency wrapper preservation without installing untrusted bots."""
from __future__ import annotations

import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from ui import bot_importer
from ui.match_config import _v5_with_deps


class DependencyWrapTests(unittest.TestCase):
    def test_native_v5_wrapper_isolated_pythonpath(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "bot.toml"
            source.write_text(
                '[settings]\nname="Test V5"\nroot_dir="."\n'
                'run_command_linux="./run.sh"\nagent_id="test/v5"\n'
                '[details]\ndeveloper="test"\n'
            )
            script = root / "run.sh"
            script.write_text("#!/bin/sh\nexit 0\n")
            script.chmod(0o755)
            deps = root / "deps"
            deps.mkdir()
            (deps / "sample_package").mkdir()
            part = root / "match"
            part.mkdir()
            with patch.object(bot_importer, "dependency_path", return_value=deps):
                wrapped = _v5_with_deps(source, source, part)
            self.assertTrue(wrapped.exists())
            with wrapped.open("rb") as f:
                obj = tomllib.load(f)
            settings = obj["settings"]
            self.assertEqual(str(script.parent), settings["root_dir"])
            self.assertTrue(settings["run_command_linux"].endswith("/run_v5.sh"))
            self.assertTrue(settings["agent_id"].startswith("test/v5/"))
            wrapper = Path(settings["run_command_linux"])
            code = subprocess.run(["bash", "-n", str(wrapper)], capture_output=True)
            self.assertEqual(0, code.returncode, code.stderr)
            self.assertIn("PYTHONPATH", wrapper.read_text())
            self.assertIn("developer", obj["details"])

    def test_unmodified_without_dependencies(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "bot.toml"
            source.write_text('[settings]\nname="Test"\nrun_command_linux="./run.sh"\n')
            with patch.object(bot_importer, "dependency_path", return_value=Path(td) / "missing"):
                wrapper = _v5_with_deps(source, source, Path(td))
                self.assertTrue(wrapper.exists())
                with wrapper.open("rb") as inp:
                    cfg = tomllib.load(inp)
                self.assertTrue(cfg["settings"]["run_command_linux"].endswith("/run_v5.sh"))


if __name__ == "__main__":
    unittest.main()
