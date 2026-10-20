"""Real pip exercise in Windows Python, verify no per-match re-download."""
from pathlib import Path
import tempfile,sys
from unittest.mock import patch
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
from ui import bot_importer,preflight
with tempfile.TemporaryDirectory(prefix="evil-cache-pip-") as t:
    base=Path(t)
    deps=base/"dependencies"
    bots=[]
    for name in ("Nox","Nyx"):
        path=base/name
        path.mkdir()
        (path/"bot.cfg").write_text("[Locations]\nname="+name+"\npython_file=bot.py\n")
        (path/"bot.py").write_text("import six\nimport numpy\nfrom rlbot.agents.base_agent import BaseAgent\nclass Bot(BaseAgent):\n def get_output(self,p): return None\n")
        (path/"requirements.txt").write_text("six==1.17.0\n")
        bots.append(path/"bot.cfg")
    with patch.object(bot_importer,"DEPS_DIR",deps), \
         patch.object(bot_importer,"TORCH_ROOT",deps/".torch-runtime"), \
         patch.object(bot_importer,"TORCH_CHOICES",deps/".torch-choice"), \
         patch.object(bot_importer,"LOG_DIR",base/"logs"), \
         patch.object(bot_importer,"MANIFEST_DIR",base/"manifests"):
        first=bots[0]
        assert not preflight.dependencies_ready(first,bot_importer.discover(first)[0]),"unexpected six preinstalled"
        msg=bot_importer.install_dependencies(first,first.parent/"requirements.txt","rlbot-v4",timeout_seconds=100)
        print("FIRST_REAL_PIP",msg,flush=True)
        assert preflight.dependencies_ready(first,bot_importer.discover(first)[0])
        with patch.object(bot_importer,"_run_install_command",side_effect=AssertionError("pip called again!")):
            second=bots[1]
            msg=bot_importer.install_dependencies(second,second.parent/"requirements.txt","rlbot-v4",timeout_seconds=30)
            print("SECOND_BOT_REUSED",msg,flush=True)
            assert preflight.dependencies_ready(second,bot_importer.discover(second)[0])
            msg=bot_importer.install_dependencies(first,first.parent/"requirements.txt","rlbot-v4",timeout_seconds=30)
            print("FIRST_BOT_RESTART",msg,flush=True)
        print("WINDOWS_REAL_PIP_PERSISTENT_CACHE_PASS",flush=True)
