"""Native Windows CPU-only bridge smoke test, no Rocket League or user bot needed."""
from multiprocessing.connection import Listener
from pathlib import Path
import json, subprocess, sys
root=Path(__file__).resolve().parents[2]
v4=root/"runtime/v4/python.exe"
with Listener(("127.0.0.1",0),family="AF_INET",authkey=b"evilrlbot-v4-v5") as listener:
    listener._listener._socket.settimeout(20)
    address=json.dumps(listener.address)
    print("BRIDGE_BOUND_LOCALHOST",listener.address,flush=True)
    proc=subprocess.Popen(
        [str(v4),"-I",str(root/"v4_runtime/worker.py"),address],
        cwd=root,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
    )
    try:
        with listener.accept() as conn:
            conn.send({
                "type":"init","project_root":str(root),
                "module":"missing_bot","class":None,
                "bot_config":str(root/"nonexistent.cfg"),
                "python_file":None,"v4_config":str(root/"nonexistent.cfg"),
                "name":"expected-failure","team":0,"index":0,"spawn_id":0,
                "field_info":{},"match":{},"profile":{}
            })
            assert conn.poll(25),"Windows V4 worker never answered V5 bridge"
            result=conn.recv()
            print("BRIDGE_ANSWER",result.get("type"),flush=True)
            assert result.get("type")=="init_error",str(result)[:400]
            print("TRACEBACK_SURFACED",str(result.get("traceback"))[-250:],flush=True)
        proc.wait(timeout=12)
        print("REAL_WINDOWS_IPC_PASS",flush=True)
    finally:
        if proc.poll() is None:proc.kill()
