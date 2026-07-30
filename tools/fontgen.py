#!/usr/bin/env python3
from __future__ import annotations

import os
import struct
import zipfile
import unicodedata
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit('Pillow is required: py -3 -m pip install pillow') from exc


def _modified_utf8(raw: bytes) -> str:
    # Japanese constants use ordinary UTF-8 byte sequences. Replacing the
    # modified-NUL sequence is enough for the strings needed by this port.
    return raw.replace(b'\xC0\x80', b'\x00').decode('utf-8', errors='ignore')


def class_utf8_strings(data: bytes) -> list[str]:
    if len(data) < 10 or data[:4] != b'\xca\xfe\xba\xbe':
        return []
    count = struct.unpack_from('>H', data, 8)[0]
    pos = 10
    strings: list[str] = []
    index = 1
    while index < count and pos < len(data):
        tag = data[pos]
        pos += 1
        if tag == 1:
            if pos + 2 > len(data): break
            size = struct.unpack_from('>H', data, pos)[0]
            pos += 2
            if pos + size > len(data): break
            strings.append(_modified_utf8(data[pos:pos + size]))
            pos += size
        elif tag in (3, 4):
            pos += 4
        elif tag in (5, 6):
            pos += 8
            index += 1
        elif tag in (7, 8, 16, 19, 20):
            pos += 2
        elif tag in (9, 10, 11, 12, 17, 18):
            pos += 4
        elif tag == 15:
            pos += 3
        else:
            break
        index += 1
    return strings


def full_cp932_repertoire() -> set[str]:
    """Return the complete printable Windows-31J/CP932 repertoire.

    Corpse Party stores most dialogue in compressed ScratchPad blocks. Scanning
    the raw .sp therefore cannot discover every character that appears after the
    game decompresses its script. Building the complete standard CP932 set keeps
    the font deterministic and avoids hollow missing-glyph boxes in dialogue.

    CP932 also defines an EUDC/private-use byte range. Those code points depend on
    user-installed glyphs and are blank in ordinary Japanese fonts, so they are
    deliberately excluded.
    """
    chars: set[str] = set()

    def add_decoded(raw: bytes) -> None:
        try:
            text = raw.decode('cp932')
        except UnicodeDecodeError:
            return
        if len(text) != 1:
            return
        char = text[0]
        code = ord(char)
        if code < 0x20 or code > 0xFFFF:
            return
        if 0xD800 <= code <= 0xDFFF or 0xE000 <= code <= 0xF8FF:
            return
        if unicodedata.category(char).startswith('C'):
            return
        chars.add(char)

    for value in range(0x100):
        add_decoded(bytes((value,)))
    for lead in range(0x100):
        for trail in range(0x100):
            add_decoded(bytes((lead, trail)))
    return chars


def collect_characters(jar_path: Path, scratchpad_path: Path) -> list[str]:
    chars = {chr(i) for i in range(0x20, 0x7F)}
    chars.update('　、。・「」『』【】（）［］！？ー〜…‥：；％＆＋－×÷＝☆★♪→←↑↓〓')

    with zipfile.ZipFile(jar_path) as archive:
        for name in archive.namelist():
            if not name.endswith('.class'):
                continue
            for text in class_utf8_strings(archive.read(name)):
                for char in text:
                    code = ord(char)
                    if code >= 0x20 and code <= 0xFFFF and not (0xD800 <= code <= 0xDFFF):
                        chars.add(char)

    if scratchpad_path.exists():
        # DoJa games of this period commonly store dialogue as Shift-JIS in
        # the preinstalled ScratchPad. Decoding the whole file can include a
        # few harmless false-positive glyphs from compressed image data, but
        # guarantees that dialogue characters are built into the ROM font.
        text = scratchpad_path.read_bytes().decode('cp932', errors='ignore')
        for char in text:
            code = ord(char)
            if (0x3000 <= code <= 0x30FF or
                0x3400 <= code <= 0x9FFF or
                0xF900 <= code <= 0xFAFF or
                0xFF00 <= code <= 0xFFEF):
                chars.add(char)

    # Raw ScratchPad scanning is only an optimization. The complete CP932
    # repertoire is mandatory because script text is compressed in this game.
    chars.update(full_cp932_repertoire())
    return sorted(chars, key=ord)


def find_font(explicit: str | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    windir = Path(os.environ.get('WINDIR', 'C:/Windows'))
    candidates.extend([
        windir / 'Fonts' / 'msgothic.ttc',
        windir / 'Fonts' / 'meiryo.ttc',
        windir / 'Fonts' / 'YuGothM.ttc',
        windir / 'Fonts' / 'YuGothR.ttc',
        Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
        Path('/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
    ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        'No Japanese font found. Pass --font with a local .ttf/.ttc file '
        '(for example C:\\Windows\\Fonts\\msgothic.ttc).'
    )


def _glyph_bits(font: ImageFont.FreeTypeFont, char: str, width: int, height: int) -> bytes:
    # Render on a larger temporary surface, then fit the visible glyph into
    # the 12x12 cell. This works consistently across Windows TTC fonts.
    temp = Image.new('L', (48, 48), 0)
    draw = ImageDraw.Draw(temp)
    try:
        bbox = draw.textbbox((0, 0), char, font=font)
    except AttributeError:
        bbox = font.getbbox(char)
    if bbox is None:
        bbox = (0, 0, width, height)
    x0, y0, x1, y1 = bbox
    glyph_w = max(1, x1 - x0)
    glyph_h = max(1, y1 - y0)
    draw.text((2 - x0, 2 - y0), char, fill=255, font=font)
    crop = temp.crop((2, 2, min(48, 2 + glyph_w), min(48, 2 + glyph_h)))
    # Store every glyph in a full-width cell. The runtime samples every
    # second source column for ASCII to produce a half-width advance.
    target_w = width
    scale = min(target_w / max(1, crop.width), height / max(1, crop.height))
    resized_w = max(1, min(target_w, int(crop.width * scale + 0.5)))
    resized_h = max(1, min(height, int(crop.height * scale + 0.5)))
    crop = crop.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
    cell = Image.new('L', (width, height), 0)
    ox = (target_w - resized_w) // 2
    oy = (height - resized_h) // 2
    cell.paste(crop, (ox, oy))

    bits = bytearray((width * height + 7) // 8)
    pixels = cell.load()
    for y in range(height):
        for x in range(width):
            if pixels[x, y] >= 96:
                bit = y * width + x
                bits[bit >> 3] |= 0x80 >> (bit & 7)
    return bytes(bits)


def generate_font(jar_path: Path, scratchpad_path: Path, output_path: Path,
                  font_path: str | None = None, width: int = 12, height: int = 12) -> tuple[Path, int]:
    chars = collect_characters(jar_path, scratchpad_path)
    selected_font = find_font(font_path)
    font = ImageFont.truetype(str(selected_font), 14)
    bytes_per_glyph = (width * height + 7) // 8
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('wb') as out:
        out.write(b'DJF1')
        out.write(struct.pack('>HHHH', width, height, len(chars), bytes_per_glyph))
        for char in chars:
            out.write(struct.pack('>H', ord(char)))
            out.write(_glyph_bits(font, char, width, height))
    return selected_font, len(chars)
