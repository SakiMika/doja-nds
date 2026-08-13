#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path

REQUIRED = [b'DoJa v59 Empty', b'SP EXPAND', b'ScratchPad LZ77 expand failed']
FORBIDDEN = [b'BOOT: NITROFS', b'NITROFS INIT FAILED', b'DSI MODE REQUIRED', b'DoJa v47']

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--nds', required=True)
    args = parser.parse_args()
    data = Path(args.nds).read_bytes()
    for marker in REQUIRED:
        if marker not in data:
            print(f'[ERROR] ROM missing marker: {marker!r}')
            return 1
    for marker in FORBIDDEN:
        if marker in data:
            print(f'[ERROR] ROM contains stale marker: {marker!r}')
            return 1
    print('[OK] ROM contains DoJa v59 Empty Nintendo-LZ77 runtime markers.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
