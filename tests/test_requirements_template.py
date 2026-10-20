"""RLBot's standard requirements.txt template must install, not be refused."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ui.bot_importer import _cache_key, _torch_specs

TEMPLATE = """# Include everything the framework requires
# You will automatically get updates for all versions starting with "1.".
rlbot==1.*
--find-links https://download.pytorch.org/whl/torch_stable.html
torch
numpy<2.0

# This will cause pip to auto-upgrade and stop scaring people with warning messages
pip
"""


class RequirementsTemplateTests(unittest.TestCase):
    def write(self, text):
        folder = Path(tempfile.mkdtemp())
        path = folder / "requirements.txt"
        path.write_text(text)
        return path

    def test_rlbot_template_is_ordinary(self):
        torch, rest, ordinary = _torch_specs(self.write(TEMPLATE))
        self.assertTrue(ordinary)
        self.assertEqual(["torch"], torch)
        self.assertEqual(["rlbot==1.*", "numpy<2.0"], rest)
        self.assertIsNotNone(_cache_key(self.write(TEMPLATE), "rlbot-v4", "cpu"))

    def test_other_pip_options_are_still_refused(self):
        for line in ("--find-links https://example.com/wheels", "--index-url https://example.com/simple",
                     "-e ./local", "git+https://github.com/x/y.git"):
            _, _, ordinary = _torch_specs(self.write(f"torch\n{line}\n"))
            self.assertFalse(ordinary, line)


if __name__ == "__main__":
    unittest.main()
