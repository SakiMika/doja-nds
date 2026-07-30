"""Generate the compact CP932/SJIS mapping used by the DoJa CLDC runtime."""
from __future__ import annotations

import struct
from pathlib import Path

MAGIC = 0x444A4332  # DJC2
VERSION = 1
REPLACEMENT = 0x3013  # GETA MARK; guaranteed by the built-in Japanese font

LEADS = tuple(range(0x81, 0xA0)) + tuple(range(0xE0, 0xFD))
TRAILS = tuple(range(0x40, 0x7F)) + tuple(range(0x80, 0xFD))


def _decode(data: bytes) -> int:
    try:
        text = data.decode('cp932')
    except UnicodeDecodeError:
        return REPLACEMENT
    if len(text) != 1:
        return REPLACEMENT
    codepoint = ord(text)
    return codepoint if codepoint <= 0xFFFF else REPLACEMENT


def generate_cp932_table(output: Path) -> tuple[int, int, int]:
    single = [_decode(bytes((value,))) for value in range(256)]
    double = [_decode(bytes((lead, trail))) for lead in LEADS for trail in TRAILS]

    reverse: list[tuple[int, int]] = []
    for codepoint in range(0x10000):
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        try:
            encoded = chr(codepoint).encode('cp932')
        except UnicodeEncodeError:
            continue
        if len(encoded) == 1:
            sjis = encoded[0]
        elif len(encoded) == 2:
            sjis = (encoded[0] << 8) | encoded[1]
        else:
            continue
        reverse.append((codepoint, sjis))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('wb') as stream:
        stream.write(struct.pack('>IHHHH', MAGIC, VERSION, len(single), len(double), len(reverse)))
        for value in single:
            stream.write(struct.pack('>H', value))
        for value in double:
            stream.write(struct.pack('>H', value))
        for unicode_value, sjis in reverse:
            stream.write(struct.pack('>HH', unicode_value, sjis))

    return len(single), len(double), len(reverse)
