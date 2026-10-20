"""Windows-only runtime and persistent user data directories."""
from pathlib import Path
import os
ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "EvilRLBot"
CONFIG_DIR = DATA / "config"
BOT_DIR = DATA / "bots"
DEPS_DIR = DATA / "dependencies"
MANIFEST_DIR = DATA / "generated-requirements"
GENERATED_DIR = DATA / "generated"
LOG_DIR = DATA / "logs"
V5_PY = ROOT / "runtime" / "v5" / "python.exe"
V4_PY = ROOT / "runtime" / "v4" / "python.exe"
RL_SERVER = ROOT / "RLBotServer.exe"
