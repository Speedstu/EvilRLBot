"""Linux V5 bot launcher compatibility regression tests.

No bot model downloads, game launch, Wine execution or third-party bot code.
"""
from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from ui.portable_linux import classify, python_command, select_command
from ui.bot_importer import _v5_toml


class LinuxBotLaunchTests(unittest.TestCase):
    def test_python_windows_venv_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            src=d/"bot.py"
            src.write_text("print('PORTABLE_AGENT_READY')",encoding="utf-8")
            cfg=d/"bot.toml"
            cfg.write_text('[settings]\nname="Nox"\nrun_command="..\\\\venv\\\\Scripts\\\\python.exe bot.py"\n')
            c=_v5_toml(cfg)
            self.assertEqual(c.warning, "")
            cmd, root, wrap=select_command(
                {"run_command":r"..\venv\Scripts\python.exe bot.py"},cfg,Path("/usr/bin/python3"))
            self.assertTrue(wrap)
            self.assertIn(str(src.resolve()),cmd)
            self.assertIn("python3",cmd)
            self.assertEqual(root,d.resolve())

    def test_absolute_windows_python_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            (d/"agent.py").write_text("print('OK')",encoding="utf-8")
            cfg=d/"bot.toml"
            cmd,_,wrap=select_command(
                {"run_command":r'"C:\Python311\python.exe" -u agent.py'},cfg,Path("/usr/bin/python3"))
            self.assertIn(" -u ",cmd)
            self.assertTrue(wrap)
            self.assertIn(str((d/"agent.py").resolve()),cmd)

    def test_compiled_exe_uses_rlbot_wine_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);cfg=d/"bot.toml"
            cfg.write_text('[settings]\nname="Nox"\nrun_command="Nox.exe"\n')
            candidate=_v5_toml(cfg)
            self.assertEqual(candidate.warning,"")
            cmd,root,wrap=select_command({"run_command":"Nox.exe"},cfg,Path("/usr/bin/python3"))
            self.assertEqual(cmd,"Nox.exe")
            self.assertFalse(wrap)
            self.assertEqual(root,d.resolve())
            self.assertEqual(classify(r".\Nox.exe"),"windows-binary")
            self.assertEqual(classify(r'"C:\Bots\Nox\Nox.exe"'),"windows-binary")

    def test_linux_command_precedence(self):
        config=Path("/tmp/nox/bot.toml")
        cmd,root,wrapped=select_command(
            {"run_command":"Nox.exe","run_command_linux":"./run.sh"},config,Path("/usr/bin/python3"))
        self.assertEqual(cmd,"./run.sh")
        self.assertTrue(wrapped)

    def test_missing_portable_python_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/"bot.toml"
            with self.assertRaisesRegex(ValueError,"not present in the imported bot"):
                select_command({"run_command":"python.exe missing.py"},config,Path("/usr/bin/python3"))

    def test_heroic_wine_is_exposed_to_windows_binary(self):
        import os
        from unittest.mock import patch
        from ui.portable_linux import configure_wine_for_match
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            bot=base/"nox.bot.toml"
            bot.write_text("[settings]\nname=\"Nox\"\nrun_command=\"Nox.exe\"\n")
            match=base/"match.toml"
            match.write_text("[[cars]]\nconfig_file=\""+bot.as_posix()+"\"\n")
            wine=base/"proton"/"bin"/"wine"
            wine.parent.mkdir(parents=True)
            wine.write_text("runner")
            prefix=base/"prefix"
            prefix.mkdir()
            with patch("ui.offline_launcher.installation",return_value={"wine":wine,"prefix":prefix}),patch.dict(os.environ,{"PATH":"/usr/bin"},clear=False):
                self.assertTrue(configure_wine_for_match(match))
                self.assertEqual(str(wine.parent),os.environ["PATH"].split(os.pathsep)[0])
                self.assertEqual(str(prefix),os.environ["WINEPREFIX"])
            match.write_text("[[cars]]\nconfig_file=\""+bot.as_posix()+"\"\n")
            bot.write_text("[settings]\nname=\"Portable\"\nrun_command=\"python.exe agent.py\"\n")
            with patch("ui.offline_launcher.installation",side_effect=AssertionError("should not lookup Wine")):
                self.assertFalse(configure_wine_for_match(match))
    def test_no_windows_runcommand_path_mistaken_as_elf(self):
        self.assertEqual(classify(r'..\bin\Nox.exe --headless'),"windows-binary")
        self.assertEqual(classify(r'cmd.exe /c run.bat'),"windows-binary")
        self.assertEqual(classify(r'./run.sh'),"native-shell")


if __name__=="__main__":
    unittest.main()
