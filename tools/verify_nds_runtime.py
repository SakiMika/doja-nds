#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import sys

REQUIRED = [
    b"DoJa v42",
    b"MODE: RAM-FIRST SAVE",
    b"GAME: CONTINUES IN RAM",
    b"BOOT: %s",
    b"JVM START",
    b"VM CONSOLE: ON",
    b"DoJa boot error:",
]
FORBIDDEN = [
    b"DoJa v37",
    b"MODE: SD FIRST",
]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nds", required=True)
    ns = ap.parse_args()
    path = Path(ns.nds)
    if not path.is_file():
        print(f"[FAIL] Missing ROM: {path}")
        return 2
    data = path.read_bytes()
    missing = [x.decode("ascii") for x in REQUIRED if x not in data]
    stale = [x.decode("ascii") for x in FORBIDDEN if x in data]
    if missing or stale:
        if missing: print("[FAIL] Runtime strings missing:", ", ".join(missing))
        if stale: print("[FAIL] Stale runtime strings found:", ", ".join(stale))
        return 1
    print(f"[OK] ROM runtime verified: {path.name}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
