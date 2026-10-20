from pathlib import Path
from time import sleep
import sys

from rlbot import flat
from rlbot.managers import MatchManager

ROOT = Path(__file__).resolve().parent
MATCH_CONFIG = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "rlbot.toml"

if __name__ == "__main__":
    manager = MatchManager(ROOT / "RLBotServer.exe")
    manager.start_match(MATCH_CONFIG)
    try:
        while manager.packet is None or manager.packet.match_info.match_phase != flat.MatchPhase.Ended:
            sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        manager.shut_down()
