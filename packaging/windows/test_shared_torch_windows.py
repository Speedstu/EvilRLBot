"""Real Windows msvcrt locking and persistent Torch re-use, no heavyweight download."""
from pathlib import Path
from unittest.mock import patch
import tempfile,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ui import bot_importer,preflight
with tempfile.TemporaryDirectory(prefix="evil-win-torch-") as td:
    work=Path(td)
    shared=work/"dependencies"/".torch-runtime"/"py312-cpu"
    (shared/"torch").mkdir(parents=True)
    (shared/"torch"/"__init__.py").write_text("__version__='2.2.0'\n")
    metadata=shared/"torch-2.2.0.dist-info"
    metadata.mkdir()
    (metadata/"METADATA").write_text("Metadata-Version: 2.1\nName: torch\nVersion: 2.2.0\n")
    (shared/".evilrlbot-torch-complete").write_text("cpu\n")
    bots=[]
    for name in ("Nox","Nyx"):
        base=work/name
        base.mkdir()
        (base/"bot.cfg").write_text(f"[Locations]\nname={name}\npython_file=bot.py\n")
        (base/"bot.py").write_text("import torch\nimport numpy as np\nfrom rlbot.agents.base_agent import BaseAgent\nclass TestBot(BaseAgent):\n def get_output(self,p): return None\n")
        (base/"requirements.txt").write_text(f"# bot={name}\ntorch==2.2.0\n")
        bots.append(base/"bot.cfg")
    with patch.object(bot_importer,"DEPS_DIR",work/"dependencies"), \
         patch.object(bot_importer,"TORCH_ROOT",shared.parent), \
         patch.object(bot_importer,"TORCH_CHOICES",work/"dependencies"/".torch-choice"), \
         patch.object(bot_importer,"MANIFEST_DIR",work/"manifests"), \
         patch.object(bot_importer,"LOG_DIR",work/"logs"), \
         patch.object(preflight,"ROOT",ROOT):
        with patch.object(bot_importer,"_run_install_command",side_effect=AssertionError("pip MUST NOT DOWNLOAD")):
            for bot in bots:
                msg=bot_importer.install_dependencies(bot,bot.parent/"requirements.txt","rlbot-v4")
                print("WIN_INSTALL",bot.parent.name,msg,flush=True)
                assert preflight.dependencies_ready(bot,bot_importer.discover(bot)[0])
            for bot in bots:
                msg=bot_importer.install_dependencies(bot,bot.parent/"requirements.txt","rlbot-v4")
                print("WIN_RESTART",bot.parent.name,msg,flush=True)
    print("WINDOWS_SHARED_TORCH_AND_LOCK_PASS",flush=True)
