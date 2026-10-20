"""Regression checks for the Windows RLBot match lifecycle.

These intentionally never launch or terminate real processes.
"""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows process ownership")
class OwnedProcessesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "ports/windows/overrides/ui/match_processes.py"
        spec = importlib.util.spec_from_file_location("win_match_processes", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.base = str(ROOT)  # Simulates repo paths, not installed runtime paths.

    def fake(self, name, exe, command):
        class Process:
            def name(self): return name
            def exe(self): return exe
            def cmdline(self): return command
        return Process()

    def test_never_owns_rocket_league(self):
        m = self.module
        p = self.fake("RocketLeague.exe", r"G:\RocketLeague\Binaries\Win64\RocketLeague.exe",
                      ["RocketLeague.exe", "-rlbot"])
        self.assertFalse(m._ours(p))

    def test_only_own_server(self):
        m = self.module
        own = self.fake("RLBotServer.exe", str(m.ROOT / "RLBotServer.exe"),
                        [str(m.ROOT / "RLBotServer.exe")])
        thirdparty = self.fake("RLBotServer.exe", r"D:\OtherRLBot\RLBotServer.exe",
                               [r"D:\OtherRLBot\RLBotServer.exe"])
        self.assertTrue(m._ours(own))
        self.assertFalse(m._ours(thirdparty))

    def test_only_own_worker(self):
        m = self.module
        source = str(m.ROOT / "v4_runtime/worker.py")
        p = self.fake("python.exe", r"C:\Python311\python.exe",
                      [r"C:\Python311\python.exe", source, '["127.0.0.1",52000]'])
        unrelated = self.fake("python.exe", r"C:\Python311\python.exe",
                              [r"C:\Python311\python.exe", r"D:\Other\worker.py"])
        self.assertTrue(m._ours(p))
        self.assertFalse(m._ours(unrelated))


if __name__ == "__main__":
    unittest.main()
