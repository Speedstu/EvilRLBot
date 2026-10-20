#!/usr/bin/env python3
"""Install pre-fetched trusted binary Windows wheels offline, without Wine or pip execution."""
from pathlib import Path
from zipfile import ZipFile
import shutil, re

ROOT=Path(__file__).resolve().parents[2]
for framework in ("v4","v5"):
    dest=ROOT/"runtime"/framework
    target=dest/"Lib"/"site-packages"
    target.mkdir(parents=True,exist_ok=True)
    wheelroot=ROOT/"build"/("wheels-"+framework)
    installed=0
    for whl in sorted(wheelroot.glob("*.whl")):
        # Old RLBot 1.68 source-built wheel may be deliberately py3-none-any;
        # all other wheels are for CPython 3.12 win_amd64.
        with ZipFile(whl) as z:
            for info in z.infolist():
                if info.is_dir():continue
                member=Path(info.filename)
                if member.parts[0].endswith(".data"):
                    # Wheel system install schemes; only purelib/platlib are
                    # importable. CLI script stubs are not needed.
                    if len(member.parts)<3 or member.parts[1] not in ("purelib","platlib"):continue
                    member=Path(*member.parts[2:])
                if member.is_absolute() or ".." in member.parts:raise ValueError("Unsafe wheel")
                output=target/member
                output.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as inp, output.open("wb") as out:
                    shutil.copyfileobj(inp,out,1024*1024)
        installed+=1
    print(framework,"wheels",installed,"installed into",target)
    assert (target/"pip").is_dir(),"Pip missing; cannot install extra bot packages"
    assert (target/"packaging").is_dir(),"Packaging missing"
    assert (target/"rlbot").is_dir(),"RLBot framework missing"
    if framework=="v4":
        assert (target/"numpy").is_dir(),"NumPy missing"
        assert (target/"flatbuffers").is_dir(),"FlatBuffers missing"
    else:
        assert (target/"PySide6").is_dir(),"Native Qt UI missing"
print("All offline wheels installed successfully")
