"""Regression: RLBot runs V4 bridges from a bot's cwd, not project root.

The earlier build launched spectators because importing ui.winpaths failed
before the bridge could add the EvilRLBot application root to sys.path.
This smoke test exercises the *actual file path launch* while avoiding RL.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
python = ROOT / "runtime/v5/python.exe"
bridge = ROOT / "src/v5_bridge.py"
with tempfile.TemporaryDirectory() as d:
    probe = ('import runpy; runpy.run_path(' + repr(str(bridge)) +
             ');print("V4_BRIDGE_IMPORT_FROM_BOT_CWD_OK")')
    result = subprocess.run([str(python), "-c", probe], cwd=d,
                            capture_output=True, text=True, timeout=35)
    print(result.stdout, result.stderr[-1200:], flush=True)
    assert result.returncode == 0, f"Bridge exited {result.returncode}"
    assert "V4_BRIDGE_IMPORT_FROM_BOT_CWD_OK" in result.stdout
