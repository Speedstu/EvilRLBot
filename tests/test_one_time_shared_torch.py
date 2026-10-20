"""No duplicated PyTorch downloads across bots with different requirement files."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ui import bot_importer,preflight

class OneTimeTorchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.deps=self.root/"dependencies"
        self.torch=self.deps/".torch-runtime"/"py312-cpu"
        (self.torch/"torch").mkdir(parents=True)
        (self.torch/"torch"/"__init__.py").write_text("__version__='2.2.0'\n")
        metadata=self.torch/"torch-2.2.0.dist-info"
        metadata.mkdir()
        (metadata/"METADATA").write_text("Metadata-Version: 2.1\nName: torch\nVersion: 2.2.0\n")
        (self.torch/".evilrlbot-torch-complete").write_text("cpu\n")
        for name,extra in (("Nox","six==1.17.0"),("Nyx","colorama==0.4.6")):
            folder=self.root/name
            folder.mkdir()
            (folder/"bot.cfg").write_text(
                "[Locations]\nname="+name+"\npython_file=bot.py\n"
            )
            (folder/"bot.py").write_text(
                "import torch\nimport numpy\nfrom rlbot.agents.base_agent import BaseAgent\n"
                "class Agent(BaseAgent):\n"
                "    def get_output(self,packet):return None\n"
            )
            (folder/"requirements.txt").write_text("torch>=2.0,<3\n"+extra+"\n")
        self.patchers=[
            patch.object(bot_importer,"DEPS_DIR",self.deps),
            patch.object(bot_importer,"TORCH_ROOT",self.deps/".torch-runtime"),
            patch.object(bot_importer,"TORCH_CHOICES",self.deps/".torch-choice")
        ]
        for pt in self.patchers:
            pt.start()
            self.addCleanup(pt.stop)

    def test_two_different_requirements_one_torch_and_restart(self):
        nox=self.root/"Nox"/"bot.cfg"
        nyx=self.root/"Nyx"/"bot.cfg"
        pip_calls=[]
        original=bot_importer._run_install_command
        def runner(cmd,*args,**kwargs):
            pip_calls.append(cmd)
            self.assertNotIn("torch", " ".join(cmd).lower())
            return original(cmd,*args,**kwargs)
        with patch.object(bot_importer,"_run_install_command",side_effect=runner):
            first=bot_importer.install_dependencies(
                nox,nox.parent/"requirements.txt","rlbot-v4",timeout_seconds=150
            )
            second=bot_importer.install_dependencies(
                nyx,nyx.parent/"requirements.txt","rlbot-v4",timeout_seconds=150
            )
            restart=bot_importer.install_dependencies(
                nox,nox.parent/"requirements.txt","rlbot-v4",timeout_seconds=35
            )
        self.assertEqual(2,len(pip_calls))
        self.assertTrue("Dependencies installed" in first)
        self.assertTrue("Dependencies installed" in second)
        self.assertTrue("Already installed" in restart or "reused" in restart)
        self.assertTrue(bot_importer.dependency_path(nox).is_dir())
        self.assertTrue(bot_importer.dependency_path(nyx).is_dir())
        self.assertFalse((bot_importer.dependency_path(nox)/"torch").exists())
        self.assertFalse((bot_importer.dependency_path(nyx)/"torch").exists())
        self.assertTrue(preflight.dependencies_ready(nox,bot_importer.discover(nox)[0]))
        self.assertTrue(preflight.dependencies_ready(nyx,bot_importer.discover(nyx)[0]))
        self.assertTrue((self.torch/"torch"/"__init__.py").exists())

    def test_version_incompatibility_does_not_download_again(self):
        nox=self.root/"Nox"/"bot.cfg"
        (nox.parent/"requirements.txt").write_text("torch>=3.0\n")
        with patch.object(bot_importer,"_run_install_command",side_effect=AssertionError("Never download")):
            with self.assertRaisesRegex(RuntimeError,"incompatible"):
                bot_importer.install_dependencies(
                    nox,nox.parent/"requirements.txt","rlbot-v4",timeout_seconds=10
                )

    def test_torch_metadata_reused_without_pip_download(self):
        self.assertTrue(bot_importer._shared_torch_satisfies(self.torch,["torch>=2.1,<3"])[0])
        self.assertFalse(bot_importer._shared_torch_satisfies(self.torch,["torch>=3"])[0])
        self.assertEqual(bot_importer._torch_specs(self.root/"Nox"/"requirements.txt")[0],
                         ["torch>=2.0,<3"])

if __name__=="__main__":
    unittest.main()
