from pathlib import Path
from time import sleep
import sys

from rlbot import flat
from rlbot.config import load_match_config
from rlbot.managers import MatchManager

ROOT = Path(__file__).resolve().parent
MATCH_CONFIG = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "rlbot.toml"


def prepare_match(path: Path):
    """Keep the RLBot performance HUD visible, including at 100% update rate.

    RLBot Python 2.0.0b56's TOML loader currently ignores the
    performance_monitor setting. Set it on the actual FlatBuffer config.
    """
    config = load_match_config(path)
    config.performance_monitor = flat.PerformanceMonitor.AlwaysShow
    return config


if __name__ == "__main__":
    manager = MatchManager(ROOT / "RLBotServer.exe")
    manager.start_match(prepare_match(MATCH_CONFIG))
    try:
        while manager.packet is None or manager.packet.match_info.match_phase != flat.MatchPhase.Ended:
            sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        manager.shut_down()
