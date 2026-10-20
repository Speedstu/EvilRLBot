"""Offline real pip install from bundled Win Python; restart must not reinstall."""
import sys,tempfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ui import bot_importer
with tempfile.TemporaryDirectory() as t:
    folder=Path(t)
    cfg=folder/"bot.cfg"
    cfg.write_text("[Locations]\nname=CacheTest\npython_file=bot.py\n")
    (folder/"bot.py").write_text(
        "from rlbot.agents.base_agent import BaseAgent\n"
        "class TestBot(BaseAgent):\n"
        " def get_output(self,p): return None\n"
    )
    req=folder/"requirements.txt"
    req.write_text("six==1.17.0\n")
    print("INSTALL_1",bot_importer.install_dependencies(cfg,req,"rlbot-v4",timeout_seconds=65),flush=True)
    target=bot_importer.dependency_path(cfg)
    assert (target/"six.py").exists(),target
    print("INSTALL_2",bot_importer.install_dependencies(cfg,req,"rlbot-v4",timeout_seconds=65),flush=True)
    print("PERSISTENT_DEPENDENCY_WINDOWS_PASS",flush=True)
