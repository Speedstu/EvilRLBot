#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.detection import detect_bot


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: evil-rlbot-detect <bot-file-or-directory>")
    report = detect_bot(sys.argv[1])
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
