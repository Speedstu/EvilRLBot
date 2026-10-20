from pathlib import Path
import sys
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
from ui import bot_importer,server
from ui.match_config import build_match
from rlbot.config import load_match_config
root=Path(__file__).resolve().parents[2]
archives=[
 root/"build/fixtures/Nyx62b.zip",
 root/"build/fixtures/Nyx62b.7z",
 root/"build/fixtures/Nyx62b.rar"
]
for source in archives:
 imported=bot_importer.import_path(source)
 repeated=bot_importer.import_path(source)
 assert len(imported)==1, (source,imported)
 assert repeated[0]["id"]==imported[0]["id"],source
 assert repeated[0]["new"] is False,source
 lib=server._load_library()
 assert sum(x["id"]==imported[0]["id"] for x in lib)==1
 print("IMPORTED_ONCE",source.suffix,imported[0]["framework"],flush=True)
paths={x["id"]:x["path"] for x in server._load_library()}
first=bot_importer.import_path(archives[0])[0]
lineup={"players":[
    {"kind":"bot","id":first["id"],"team":0},
    {"kind":"bot","id":first["id"],"team":1},
], "launcher":"NoLaunch","map":"Stadium_P","mode":"Soccar"}
config=build_match(lineup,paths)
parsed=load_match_config(config)
assert len(parsed.player_configurations)==2
print("WINDOWS_IMPORT_AND_MATCH_CONFIGURATION_PASS",flush=True)
