import tempfile,sys
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
from ui import bot_importer as b
from ui.winpaths import V4_PY
with tempfile.TemporaryDirectory(prefix="evil-win-torchlock-") as d:
    store=Path(d)/"torch-runtime"
    cpu=store/"py312-cpu"
    cpu.mkdir(parents=True)
    (cpu/"torch-2.2.0.dist-info").mkdir()
    (cpu/"torch-2.2.0.dist-info"/"METADATA").write_text(
        "Metadata-Version: 2.1\nName: torch\nVersion: 2.2.0\n"
    )
    (cpu/".evilrlbot-torch-complete").write_text("cpu\n")
    with patch.object(b,"TORCH_ROOT",store):
        output=b._ensure_shared_torch(
            V4_PY, ["torch>=2.0,<3"], "cpu", root, Path(d), None, None, 5
        )
        print("WINDOWS_PERSISTENT_TORCH_LOCK_PASS",output,flush=True)
        assert output==cpu
