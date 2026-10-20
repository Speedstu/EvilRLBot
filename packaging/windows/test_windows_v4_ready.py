"""Genuine Windows RLBot V4 agent ready through V5's AF_INET IPC (no game)."""
from multiprocessing.connection import Listener
from pathlib import Path
import json,subprocess,sys
root=Path(__file__).resolve().parents[2]
cfg=root/"legacy_bot"/"bot.cfg"
assert cfg.is_file()
with Listener(("127.0.0.1",0),family="AF_INET",authkey=b"evilrlbot-v4-v5") as listener:
 listener._listener._socket.settimeout(23)
 proc=subprocess.Popen(
  [str(root/"runtime/v4/python.exe"),"-I",str(root/"v4_runtime/worker.py"),json.dumps(listener.address)],
  stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=root
 )
 try:
  with listener.accept() as conn:
   conn.send({
    "type":"init","project_root":str(root),"module":"legacy_bot.bot","class":None,
    "bot_config":str(cfg),"v4_config":str(cfg),"python_file":None,
    "name":"Evil RLBot V4 Test","team":0,"index":0,"spawn_id":0,
    "field_info":{},"match":{},"profile":{}
   })
   assert conn.poll(28),"No V4 response"
   answer=conn.recv()
   print("WIN_V4_RESPONSE",answer.get("type"),flush=True)
   if answer.get("type")!="ready":
    print(str(answer.get("traceback"))[-2900:],flush=True)
   assert answer.get("type")=="ready",str(answer)[:1000]
   conn.send({"type":"retire"})
   if conn.poll(12):
    print("RETIRE",conn.recv().get("type"),flush=True)
  proc.wait(timeout=12)
  print("WINDOWS_V4_AGENT_REAL_READY",flush=True)
 finally:
  if proc.poll() is None:proc.kill()
