# Here you can configure your bot's general settings

from pathlib import Path

from backend.model import ActivationType, ModelInfo

RLBOT_AGENT_ID = "eastvillage/wisp/v2-75B"  # Must match the bot.toml

TICK_SKIP = 8
ACTION_DELAY = TICK_SKIP - 1
MAX_PLAYERS_PER_TEAM = 3

_BASE_DIR = Path(__file__).resolve().parent
_MODELS_DIR = _BASE_DIR / "models"

MODEL_INFO_POLICY = ModelInfo(_MODELS_DIR / "POLICY.lt", ActivationType.RELU)
MODEL_INFO_SHARED_HEAD = ModelInfo(_MODELS_DIR / "SHARED_HEAD.lt", ActivationType.RELU)
#                         ^ Set to None if you don't have a shared head export

MODEL_DEVICE = "cpu"

# Infer bot deterministically (stochastic otherwise)
DETERMINISTIC = True

ROCKETSIM_COLLISION_DIR = _BASE_DIR / "collision_meshes"
