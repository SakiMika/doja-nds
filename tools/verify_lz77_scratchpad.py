#!/usr/bin/env python3
from __future__ import annotations
import argparse, struct, sys, zlib
from pathlib import Path
from verify_prepared import decode_lz77

HEADER = struct.Struct('<4sIIII')

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    args = parser.parse_args()
    data = Path(args.path).read_bytes()
    if len(data) < HEADER.size:
        print('[ERROR] Truncated D7SP file.')
        return 1
    magic, version, raw_size, packed_size, crc = HEADER.unpack_from(data)
    if magic != b'D7SP' or version != 1 or packed_size != len(data) - HEADER.size:
        print('[ERROR] Invalid D7SP header.')
        return 1
    try:
        raw = decode_lz77(data[HEADER.size:], raw_size)
    except ValueError as exc:
        print('[ERROR]', exc)
        return 1
    actual = zlib.crc32(raw) & 0xFFFFFFFF
    if actual != crc:
        print(f'[ERROR] CRC32 {actual:08X} != {crc:08X}')
        return 1
    print(f'[OK] Nintendo LZ77: {packed_size} -> {raw_size} bytes; CRC32 {crc:08X}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
