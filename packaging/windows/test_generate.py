import os,sys,tempfile,tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ui.match_config import build_match
from rlbot.config import load_match_config
from ui import bot_importer,server
with tempfile.TemporaryDirectory(prefix="evilrlbot-wintest-") as d:
    root=Path(d)
    bot=root/"Nyx64"
    bot.mkdir()
    (bot/"looks.cfg").write_text("[Bot Loadout]\n")
    (bot/"bot.py").write_text("from rlbot.agents.base_agent import BaseAgent\nclass Nyx(BaseAgent):\n pass\n")
    (bot/"bot.cfg").write_text("[Locations]\npython_file=bot.py\nname=Nyx64\nlooks_config=looks.cfg\n")
    cfg=bot/"bot.cfg"
    game = build_match({
        "players":[
            {"kind":"bot","id":"nyx","team":0},
            {"kind":"bot","id":"nyx","team":1}
        ],"launcher":"Epic","map":"Stadium_P","mode":"Soccar"},
        {"nyx":str(cfg)}
    )
    text=game.read_text()
    print("MATCH",game)
    assert 'launcher = "Epic"' in text
    match=tomllib.loads(text)
    cars=match["cars"]
    assert len(cars)==2
    configs=[Path(car["config_file"]) for car in cars]
    assert configs[0]!=configs[1]
    for p in configs:
        info=tomllib.loads(p.read_text())
        cmd=info["settings"]["run_command_windows"]
        print("AGENT",p,cmd)
        assert "cmd.exe" in cmd
        assert "run_v5.cmd" in cmd
        assert (p.parent/"run_v5.cmd").is_file()
        wrapper=(p.parent/"run_v5.cmd").read_bytes()
        assert b"\r\n" in wrapper and b"cmd.exe" in wrapper
    for run_cmd in game.parent.rglob("run.cmd"):
        raw=run_cmd.read_bytes()
        assert b"\r\n" in raw and b"EVILRLBOT_V4_CONFIG" in raw
        print("V4 BRIDGE CMD:",run_cmd)
    result=load_match_config(game)
    print("V5_CONFIG_LOADED",len(result.player_configurations))
    assert len(result.player_configurations)==2
print("WINDOWS_MATCH_GENERATION_OK")
