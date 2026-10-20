"""Confirm official RLBotServer.exe starts, without launching Rocket League."""
from pathlib import Path
import sys,time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ui import server,bot_importer
source=ROOT/"build/fixtures/Nyx62b.zip"
assert source.is_file()
bot=bot_importer.import_path(source)[0]
setup={
    "players":[{"kind":"bot","id":bot["id"],"team":0}],
    "launcher":"NoLaunch","map":"Stadium_P","mode":"Soccar",
}
print("TRY_NATIVE_RLBOT_SERVER_WITHOUT_GAME",flush=True)
started=False
try:
    status=server._start_match(setup)
    started=True
    print("MATCH_PROCESS",status["pid"],flush=True)
    time.sleep(8)
    log=server.LOG.read_text(errors="replace")
    print("SERVER_LOG_TAIL",repr(log[-1500:]),flush=True)
    assert "RLBotServer" in log and ("Waiting for connections" in log or "Server will use port" in log),log[-1200:]
    print("V5_SERVER_STARTED",flush=True)
finally:
    if started:
        server._stop_match()
        print("V5_SERVER_STOPPED",flush=True)
