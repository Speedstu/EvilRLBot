"""Regression for Nox/Nyx empty matches on friend's portable Linux runtime."""
from __future__ import annotations
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ui import bot_importer, preflight

class NoRequirementsV4Tests(unittest.TestCase):
    def test_v4_numpy_is_bundled(self):
        root = Path(__file__).resolve().parents[1]
        p = subprocess.run(
            [str(root / ".venv-v4/bin/python"), "-I", "-c",
             "import numpy;from rlbot.agents.base_agent import BaseAgent;"
             "print(numpy.__version__)"],
            capture_output=True, text=True, timeout=25
        )
        self.assertEqual(p.returncode,0,p.stderr)

    def test_nox_nyx_imports_detected_without_requirements_txt(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            cfg=base/"bot.cfg"
            cfg.write_text("[Locations]\nname=Nox\npython_file=bot.py\n")
            (base/"bot.py").write_text(
                "import numpy as np\n"
                "from torch import jit\n"
                "from submodel import setup\n"
            )
            (base/"submodel.py").write_text("import torch\n")
            (base/"POLICY.lt").write_bytes(b"lt-placeholder")
            c=bot_importer.discover(cfg)[0]
            self.assertIsNone(c.requirements)
            self.assertEqual(["numpy","torch"],preflight._static_modules(cfg,c.framework))
            problems=preflight.check_bots(
                {"players":[{"kind":"bot","id":"nox","team":0}]},
                {"nox":str(cfg)},
            )
            self.assertEqual(1,len(problems))
            self.assertIn("torch",problems[0])
            manifest=preflight.suggested_requirements(cfg,c)
            self.assertIsNotNone(manifest)
            text=manifest.read_text()
            self.assertNotIn("\\nnumpy\\n",text)
            self.assertIn("torch",text)
            self.assertTrue(manifest.is_file())

    def test_v4_worker_imports_numpy_even_with_venv_isolation(self):
        root=Path(__file__).resolve().parents[1]
        p=subprocess.run(
            [str(root/".venv-v4/bin/python"),"-I","-c",
             "from rlbot.agents.base_agent import BaseAgent; import numpy;print('READY')"],
             env={"PATH":"/usr/bin:/bin","PYTHONPATH":"/invalid"},
             capture_output=True, text=True, timeout=25
        )
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("READY",p.stdout)

if __name__=="__main__":
    unittest.main()
