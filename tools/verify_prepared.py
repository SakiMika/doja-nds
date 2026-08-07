#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import zipfile
import zlib
from pathlib import Path

PORT_VERSION = 48
MARKER_NAME = 'prepared_v48.ok'
WRAPPER = struct.Struct('<4sIIII')


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> int:
    print('[ERROR]', message)
    return 1


def decode_lz77(stream: bytes, expected_size: int) -> bytes:
    if len(stream) < 4 or stream[0] != 0x10:
        raise ValueError('missing Nintendo LZ77 0x10 header')
    declared = stream[1] | (stream[2] << 8) | (stream[3] << 16)
    if declared != expected_size:
        raise ValueError(f'declared size {declared} != {expected_size}')
    ip = 4
    out = bytearray()
    while len(out) < expected_size:
        if ip >= len(stream):
            raise ValueError('truncated flag byte')
        flags = stream[ip]
        ip += 1
        for bit in range(8):
            if len(out) >= expected_size:
                break
            if flags & (0x80 >> bit):
                if ip + 2 > len(stream):
                    raise ValueError('truncated match')
                first, second = stream[ip], stream[ip + 1]
                ip += 2
                length = (first >> 4) + 3
                displacement = (((first & 0x0F) << 8) | second) + 1
                if displacement > len(out):
                    raise ValueError('invalid displacement')
                if len(out) + length > expected_size:
                    raise ValueError('match exceeds output')
                start = len(out) - displacement
                for index in range(length):
                    out.append(out[start + index])
            else:
                if ip >= len(stream):
                    raise ValueError('truncated literal')
                out.append(stream[ip])
                ip += 1
    return bytes(out)


def macro_int(text: str, name: str, base: int = 10) -> int:
    match = re.search(rf'^#define\s+{re.escape(name)}\s+([^\r\n]+)$', text, re.M)
    if not match:
        raise ValueError(name)
    token = match.group(1).replace('UL', '').strip()
    return int(token, base)


def macro_string(text: str, name: str) -> str:
    match = re.search(rf'^#define\s+{re.escape(name)}\s+"([^"]*)"\s*$', text, re.M)
    if not match:
        raise ValueError(name)
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default='.')
    args = parser.parse_args()
    project = Path(args.project).resolve()

    marker_path = project / 'build_doja' / MARKER_NAME
    if not marker_path.is_file():
        return fail('Source is empty. Run build-doja.bat first.')
    marker = json.loads(marker_path.read_text(encoding='utf-8'))
    if marker.get('port_version') != PORT_VERSION or marker.get('edition') != 'empty':
        return fail('Preparation marker is not DoJa v48 Empty.')
    if marker.get('codec') != 'Nintendo-LZ77-0x10':
        return fail('Preparation marker does not use Nintendo LZ77.')

    required = {
        'game_jar_sha256': project / 'embedded' / 'game.jar',
        'scratchpad_lz77_sha256': project / 'embedded' / 'doja_scratchpad.lz7b',
        'generated_jam_sha256': project / 'build_doja' / 'prepared_game.jam',
        'header_sha256': project / 'include' / 'standalone_game.h',
        'metadata_sha256': project / 'standalone_game.mk',
        'resource_source_sha256': project / 'kvm' / 'VmExtra' / 'src' / 'resource.c',
        'nds_main_source_sha256': project / 'kvm' / 'VmSkel' / 'src' / 'nds_main.c',
        'makefile_sha256': project / 'Makefile',
    }
    for key, path in required.items():
        if not path.is_file():
            return fail(f'Missing {path.relative_to(project)}')
        if marker.get(key) != sha256(path):
            return fail(f'{path.relative_to(project)} changed after preparation.')

    header_text = (project / 'include' / 'standalone_game.h').read_text(encoding='utf-8')
    try:
        raw_size = macro_int(header_text, 'DOJA_SCRATCHPAD_SIZE')
        expected_crc = macro_int(header_text, 'DOJA_SCRATCHPAD_CRC32', 16)
        expected_packed = macro_int(header_text, 'DOJA_SCRATCHPAD_PACKED_SIZE')
        expected_wrapper = macro_int(header_text, 'DOJA_SCRATCHPAD_WRAPPER_SIZE')
        app_class = macro_string(header_text, 'DOJA_APP_CLASS')
    except ValueError as exc:
        return fail(f'Missing generated macro: {exc}')

    wrapper = (project / 'embedded' / 'doja_scratchpad.lz7b').read_bytes()
    if len(wrapper) != expected_wrapper or len(wrapper) < WRAPPER.size:
        return fail('LZ77 wrapper size mismatch.')
    magic, version, stored_raw, packed_size, stored_crc = WRAPPER.unpack_from(wrapper)
    if magic != b'D7SP' or version != 1:
        return fail('Invalid D7SP wrapper header.')
    if (stored_raw, packed_size, stored_crc) != (raw_size, expected_packed, expected_crc):
        return fail('D7SP metadata does not match standalone_game.h.')
    if packed_size != len(wrapper) - WRAPPER.size:
        return fail('D7SP packed length is invalid.')
    try:
        raw = decode_lz77(wrapper[WRAPPER.size:], raw_size)
    except ValueError as exc:
        return fail(f'LZ77 decode failed: {exc}')
    if (zlib.crc32(raw) & 0xFFFFFFFF) != expected_crc:
        return fail('Decoded ScratchPad CRC32 mismatch.')

    jar_path = project / 'embedded' / 'game.jar'
    try:
        with zipfile.ZipFile(jar_path) as archive:
            infos = archive.infolist()
            if not infos:
                return fail('game.jar is empty.')
            compressed = [info.filename for info in infos if info.compress_type != zipfile.ZIP_STORED]
            if compressed:
                return fail('game.jar has non-STORED entries: ' + ', '.join(compressed[:3]))
            main_entry = app_class.replace('.', '/').replace('\\', '/') + '.class'
            if main_entry not in archive.namelist():
                return fail(f'JAM AppClass is missing from game.jar: {main_entry}')
            bad = archive.testzip()
            if bad:
                return fail(f'game.jar CRC failure: {bad}')
    except zipfile.BadZipFile:
        return fail('game.jar is not a valid JAR/ZIP.')

    source = (project / 'kvm' / 'VmExtra' / 'src' / 'resource.c').read_text(encoding='utf-8')
    main_source = (project / 'kvm' / 'VmSkel' / 'src' / 'nds_main.c').read_text(encoding='utf-8')
    if 'dojaSpLz77Decode' not in source or '_binary_embedded_doja_scratchpad_lz7b_start' not in source:
        return fail('Native LZ77 ScratchPad backend is missing.')
    if 'DoJa v48 Empty' not in main_source or 'SP EXPAND' not in main_source:
        return fail('DoJa v48 Empty boot markers are missing.')
    if 'nitroFSInit' in main_source:
        return fail('Blocking NitroFS boot path is present.')

    ratio = 100.0 * packed_size / raw_size if raw_size else 0.0
    print(f'[OK] DoJa v48 Empty: {app_class}; LZ77 {packed_size} -> {raw_size} bytes ({ratio:.1f}%); game.jar STORED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
