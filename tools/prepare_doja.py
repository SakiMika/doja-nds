#!/usr/bin/env python3
"""Prepare an embedded DoJa game for the standalone NDS KVM port."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

from fontgen import generate_font
from cp932gen import generate_cp932_table
from segment_stream_patch import patch_segment_streams, segment_stream_patch_counts

PORT_VERSION = 59
PORT_TAG = "v59"
PORT_NAME = "DoJa v59 Empty"
PREPARED_MARKER = "prepared_v59.ok"


def parse_jam(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    # JAM files from Japanese handsets are not guaranteed to be UTF-8.
    for encoding in ('utf-8', 'cp932', 'latin-1'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode('latin-1', errors='replace')
    values: dict[str, str] = {}
    for line in text.replace('\r', '\n').split('\n'):
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def _jam_int(jam: dict[str, str], key: str, default: int) -> int:
    raw = jam.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip(), 0)
    except ValueError as exc:
        raise ValueError('Invalid integer in JAM field %s: %r' % (key, raw)) from exc


def resolve_video_config(jam: dict[str, str], cli_x: int | None, cli_y: int | None) -> dict[str, int | str]:
    """Resolve custom NDS viewport fields carried by the JAM file.

    Unknown JAM keys are ignored by real DoJa handsets, so the original game
    remains usable while this port can select an NDS affine-background mode.
    """
    mode = jam.get('NDSScaleMode', 'native').strip().lower() or 'native'
    canvas_w = _jam_int(jam, 'NDSCanvasWidth', 240)
    canvas_h = _jam_int(jam, 'NDSCanvasHeight', 240)
    logical_w = _jam_int(jam, 'NDSLogicalWidth', canvas_w)
    logical_h = _jam_int(jam, 'NDSLogicalHeight', canvas_h)
    if canvas_w <= 0 or canvas_h <= 0 or canvas_w > 256 or canvas_h > 256:
        raise ValueError('NDS physical canvas must be within 1..256 pixels.')
    if logical_w <= 0 or logical_h <= 0 or logical_w > 256 or logical_h > 256:
        raise ValueError('NDS logical canvas must be within 1..256 pixels.')

    if mode in ('affine-fit', 'hardware-fit', 'fit', 'affine-stretch', 'stretch'):
        mode = 'affine-stretch' if mode in ('affine-stretch', 'stretch') else 'affine-fit'
        output_w = _jam_int(jam, 'NDSOutputWidth', min(256, logical_w))
        output_h = _jam_int(jam, 'NDSOutputHeight', min(192, logical_h))
        if output_w <= 0 or output_h <= 0 or output_w > 256 or output_h > 192:
            raise ValueError('NDS output must be within 1..256 x 1..192 pixels.')
        output_x = _jam_int(jam, 'NDSOutputX', (256 - output_w) // 2)
        output_y = _jam_int(jam, 'NDSOutputY', (192 - output_h) // 2)
        source_x = _jam_int(jam, 'NDSSourceX', (256 - logical_w) // 2)
        source_y = _jam_int(jam, 'NDSSourceY', (256 - logical_h) // 2)
        if cli_x is not None:
            source_x = cli_x
        if cli_y is not None:
            source_y = cli_y
        pa = max(1, (logical_w * 256 + output_w // 2) // output_w)
        pd = max(1, (logical_h * 256 + output_h // 2) // output_h)
        bg_x = source_x * 256 - output_x * pa
        bg_y = source_y * 256 - output_y * pd
        hardware = 1
    elif mode in ('native', 'crop', 'none'):
        mode = 'native'
        source_x = _jam_int(jam, 'NDSSourceX', 8) if cli_x is None else cli_x
        source_y = _jam_int(jam, 'NDSSourceY', -24) if cli_y is None else cli_y
        output_x, output_y = 0, 0
        output_w, output_h = 256, 192
        pa = pd = 256
        bg_x = bg_y = 0
        hardware = 0
    else:
        raise ValueError('Unsupported NDSScaleMode: ' + mode)

    for value, name in ((source_x, 'NDSSourceX'), (source_y, 'NDSSourceY')):
        if value < -256 or value > 256:
            raise ValueError('%s must be between -256 and 256.' % name)
    return {
        'mode': mode, 'canvas_w': canvas_w, 'canvas_h': canvas_h,
        'logical_w': logical_w, 'logical_h': logical_h,
        'source_x': source_x, 'source_y': source_y,
        'output_x': output_x, 'output_y': output_y,
        'output_w': output_w, 'output_h': output_h,
        'pa': pa, 'pd': pd, 'bg_x': bg_x, 'bg_y': bg_y,
        'hardware': hardware,
    }


DOJAEMU_SP_HEADER_BYTES = 64
DOJAEMU_SP_HEADER_ENTRIES = 16


def parse_scratchpad_sizes(raw: str | None) -> list[int]:
    if not raw:
        return []
    sizes: list[int] = []
    for token in re.split(r'[,\s]+', raw.strip()):
        if not token:
            continue
        try:
            sizes.append(max(0, int(token, 0)))
        except ValueError:
            raise ValueError('Invalid SPsize entry in JAM: ' + token)
    return sizes


def _matches_dojaemu_header(header: bytes, configured_sizes: list[int]) -> bool:
    if len(header) < DOJAEMU_SP_HEADER_BYTES or not configured_sizes:
        return False
    for index in range(DOJAEMU_SP_HEADER_ENTRIES):
        actual = struct.unpack_from('<i', header, index * 4)[0]
        if index < len(configured_sizes):
            if actual != configured_sizes[index]:
                return False
        elif actual != -1:
            return False
    return True


def normalize_scratchpad(source: Path, jam: dict[str, str], output: Path) -> tuple[Path, str]:
    """Convert a packed dojaemu .sp file into the device-visible payload.

    dojaemu/OpenDoJa packed files use a 64-byte little-endian segment table
    before the actual ScratchPad bytes. The game must never see that host
    header. Raw payload files are copied unchanged.
    """
    data = source.read_bytes()
    sizes = parse_scratchpad_sizes(jam.get('SPsize'))
    declared = sum(sizes)
    payload = data
    mode = 'raw'

    if len(data) >= DOJAEMU_SP_HEADER_BYTES and _matches_dojaemu_header(
            data[:DOJAEMU_SP_HEADER_BYTES], sizes):
        payload = data[DOJAEMU_SP_HEADER_BYTES:]
        mode = 'dojaemu-header-64-stripped'
    elif declared and len(data) == declared + DOJAEMU_SP_HEADER_BYTES:
        # Size alone is intentionally not enough to shift the data. A corrupt
        # or unrelated 64-byte prefix should remain visible rather than being
        # silently misdetected.
        print('[WARN] SP file is SPsize + 64 bytes, but the 64-byte segment table does not match JAM.')

    if declared:
        if len(payload) < declared:
            print('[WARN] ScratchPad payload is truncated:', len(payload), '<', declared)
        elif len(payload) > declared:
            print('[WARN] ScratchPad payload is larger than SPsize:', len(payload), '>', declared)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    first = payload[:5]
    first_hex = ' '.join('%02X' % b for b in first)
    print('[DoJa] SP source  :', len(data), 'bytes')
    print('[DoJa] SP layout  :', mode)
    print('[DoJa] SP payload :', len(payload), 'bytes')
    print('[DoJa] SP first 5 :', first_hex if first else '(empty)')
    return output, mode


DJSP_MAGIC = b"DJSP"
DJSP_HEADER = struct.Struct("<4sHHIIIII")
DJSP_VERSION = 1
DJSP_CHUNK_SIZE = 256

def _crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF

def _parse_djsp_overlay(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < DJSP_HEADER.size:
        raise ValueError('Save file is too small to be a DJSP overlay: %s' % path)
    magic, version, chunk_size, base_size, base_crc, count, payload_crc, reserved = DJSP_HEADER.unpack_from(raw, 0)
    if magic != DJSP_MAGIC:
        raise ValueError('Unsupported save format (expected DJSP): %s' % path)
    if version != DJSP_VERSION or chunk_size != DJSP_CHUNK_SIZE:
        raise ValueError('Unsupported DJSP version/chunk size: version=%d chunk=%d' % (version, chunk_size))
    expected = DJSP_HEADER.size + count * (4 + chunk_size)
    if len(raw) != expected:
        raise ValueError('DJSP length mismatch: file=%d expected=%d' % (len(raw), expected))
    chunks=[]
    pos=DJSP_HEADER.size
    payload=bytearray()
    seen=set()
    for _ in range(count):
        cid = struct.unpack_from('<I', raw, pos)[0]
        id_bytes = raw[pos:pos+4]
        pos += 4
        data = raw[pos:pos+chunk_size]
        pos += chunk_size
        if cid in seen:
            raise ValueError('DJSP contains duplicate chunk id %d' % cid)
        seen.add(cid)
        payload.extend(id_bytes)
        payload.extend(data)
        chunks.append((cid, data))
    if _crc32(bytes(payload)) != payload_crc:
        raise ValueError('DJSP payload CRC mismatch')
    return {
        'path': path, 'base_size': base_size, 'base_crc': base_crc,
        'count': count, 'chunks': chunks, 'payload_crc': payload_crc,
    }

def _apply_djsp_overlay(base: bytes, overlay: dict, label: str) -> bytes:
    size=len(base)
    crc=_crc32(base)
    if overlay['base_size'] != size or overlay['base_crc'] != crc:
        raise ValueError('%s does not match this ScratchPad base: save expects size=%d crc=%08X, base is size=%d crc=%08X' %
                         (label, overlay['base_size'], overlay['base_crc'], size, crc))
    out=bytearray(base)
    max_chunk=(size + DJSP_CHUNK_SIZE - 1)//DJSP_CHUNK_SIZE
    for cid, chunk in overlay['chunks']:
        if cid >= max_chunk:
            raise ValueError('%s contains out-of-range chunk id %d' % (label, cid))
        start=cid*DJSP_CHUNK_SIZE
        end=min(start+DJSP_CHUNK_SIZE, size)
        out[start:end]=chunk[:end-start]
    print('[DoJa] Existing save: imported %d DJSP chunk(s) into %s ScratchPad' % (overlay['count'], label))
    return bytes(out)

def _find_save_candidate(explicit: str | None, jar: Path, jam: Path, sp: Path) -> Path | None:
    """v59 imports external DJSP saves only when explicitly requested.

    Original handset packages may already include Continue data in the .sp.
    Auto-importing a same-name file can overwrite that bundled state.
    """
    if not explicit:
        return None
    path = Path(explicit).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path

# Corpse Party NewChapter offline-boot patch.
#
# The game startup state machine uses:
#   ag = 12  -> inspect ScratchPad download marker
#   ag = 9   -> network download (init.bin, 0.bin...)
#   ag = 10  -> load the already bundled ScratchPad data
#
# For this standalone port the complete ScratchPad is embedded in the ROM, so
# entering state 9 is both unnecessary and fatal because there is no handset
# network service. These byte patterns preserve every code offset and branch
# target, which is important for the Java 1.1/KVM StackMap verifier.
_CP_OFFLINE_DECISION = bytes.fromhex(
    'b2 03 16 99 00 14 b2 03 15 b2 03 16 13 04 dd 60 '
    '13 04 de 6c a2 00 0b 10 09 b3 02 a9 a7 00 08 '
    '10 0a b3 02 a9'
)
_CP_OFFLINE_DECISION_PATCHED = bytes.fromhex(
    'b2 03 16 99 00 14 b2 03 15 b2 03 16 13 04 dd 60 '
    '13 04 de 6c a2 00 0b 10 0a b3 02 a9 a7 00 08 '
    '10 0a b3 02 a9'
)
_CP_NETWORK_GATE = bytes.fromhex('b2 02 a9 10 09 a0 02 93')
_CP_NETWORK_GATE_PATCHED = bytes.fromhex('10 0a b3 02 a9 a7 02 93')

# State 10 draws the loading bar as (bQ * 4096) / cb.  For one frame after
# the forced state transition, cb is still zero because the original state-10
# initializer has not run yet.  Preserve bytecode length and use the same
# initial total (10) that the game assigns on the following frame.
_CP_LOADING_PROGRESS = bytes.fromhex(
    'b2 02 8f 11 10 00 68 b2 02 90 6c'
)
_CP_LOADING_PROGRESS_PATCHED = bytes.fromhex(
    'b2 02 8f 11 10 00 68 10 0a 00 6c'
)

# Final Fantasy IV The After: exact frame-loop signatures. These edits keep
# bytecode length/branch targets unchanged, but remove two handset-era costs:
# a forced full GC every 75 frames and a redundant PhoneSystem attribute call
# every 30 frames. Unknown games/classes are never modified.
_FF4A_PERIODIC_GC = bytes.fromhex('10 4b 70 9a 00 06 b8 01 fb')
_FF4A_PERIODIC_GC_PATCHED = bytes.fromhex('10 4b 70 9a 00 06 00 00 00')
_FF4A_PERIODIC_PHONE = bytes.fromhex('10 1e 70 9a 00 08 03 04 b8 02 43')
_FF4A_PERIODIC_PHONE_PATCHED = bytes.fromhex('10 1e 70 9a 00 08 00 00 00 00 00')
# Dead timestamp result at the top of every frame: currentTimeMillis(); pop2.
_FF4A_DEAD_CLOCK = bytes.fromhex('b8 01 d7 58 b2 00 b6 10 4b 70 9a 00 06')
_FF4A_DEAD_CLOCK_PATCHED = bytes.fromhex('00 00 00 00 b2 00 b6 10 4b 70 9a 00 06')
# Thread.yield() immediately before the real frame-deadline calculation. The
# following sleep already yields to the KVM scheduler/VBlank path.
_FF4A_FRAME_YIELD = bytes.fromhex('b8 02 5d b2 00 8a b8 01 d7 65')
_FF4A_FRAME_YIELD_PATCHED = bytes.fromhex('00 00 00 b2 00 8a b8 01 d7 65')
_FF4A_ALL_GC_CALL = bytes.fromhex('b8 01 fb')
_FF4A_ALL_GC_NOP = bytes.fromhex('00 00 00')

# FF4A v46 logical-canvas patch. The NDS/MIDP surface reports 256x192, but
# FF4A was authored for a 240x240 DoJa framebuffer. Replace the four
# getWidth()/getHeight() calls in m.<init> with literal 240 values. The
# compatibility Canvas then allocates a 240x240 backing image while BG3
# stretches that image to the physical 256x192 screen. Class length and all
# branch targets remain unchanged.
_FF4A_CANVAS_CTOR = bytes.fromhex(
    '2a b6 02 0c 11 00 f0 64 05 6c '
    '2a b6 02 04 11 00 f0 64 05 6c b8 01 71 '
    'b2 00 5b 2a b6 02 0c 2a b6 02 04 b8 01 72 '
    '05 11 00 f0 11 00 f0 b8 01 73'
)
_FF4A_CANVAS_CTOR_PATCHED = bytes.fromhex(
    '11 00 f0 00 11 00 f0 64 05 6c '
    '11 00 f0 00 11 00 f0 64 05 6c b8 01 71 '
    'b2 00 5b 11 00 f0 00 11 00 f0 00 b8 01 72 '
    '05 11 00 f0 11 00 f0 b8 01 73'
)


# FF4A diagnostic patch for the one-line Japanese "An error occurred" box.
# d.d() intentionally catches java/lang/Exception around the field-engine
# update/render pair z(); L(); and replaces the real exception with a generic
# message.  On the NDS port this hides the actual compatibility failure.
#
# Original method code (exact FF4A 1.3.1 signature):
#   invokestatic d.z
#   invokestatic d.L
#   return
# catch Exception:
#   pop
#   ldc_w "エラーが発生しました"
#   invokestatic m.b
#   return
#
# Replace only the handler body with ATHROW + NOPs.  Code length, exception
# table, offsets, and StackMap positions remain unchanged.  The KVM then prints
# the real uncaught exception/backtrace on the lower screen.
_FF4A_FIELD_CATCH = bytes.fromhex(
    'b8 01 64 b8 00 a4 b1 57 13 01 8b b8 00 d6 b1'
)
_FF4A_FIELD_CATCH_TRACE = bytes.fromhex(
    'b8 01 64 b8 00 a4 b1 bf 00 00 00 00 00 00 00'
)

# FF4A Continue/load diagnostic: m.a(String) is the main loop.  Its broad
# catch(Exception) swallows the actual failure and switches the game to state 7
# with the generic Japanese message.  Replace the handler body with ATHROW and
# NOP padding so the KVM prints the real exception/backtrace without changing
# method length, branch offsets, the exception table, or StackMap offsets.
_FF4A_MAINLOOP_CATCH = bytes.fromhex(
    '57 13 02 cb b3 00 96 b8 01 62 10 07 59 b3 00 c8 b3 00 bf'
)
_FF4A_MAINLOOP_CATCH_TRACE = bytes.fromhex(
    'bf 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00'
)


# v59 outer Continue/load diagnostic. FF4A.start() catches the exception
# rethrown by m.a(String), discards it, calls terminate(), and returns.
# Replace that 6-byte handler with ATHROW + NOP padding so the existing
# nds.doja.MainApp catch(Throwable) prints the real exception and backtrace.
_FF4A_START_CATCH = bytes.fromhex('57 2a b6 00 0d b1')
_FF4A_START_CATCH_TRACE = bytes.fromhex('bf 00 00 00 00 00')


def patch_ff4a_start_exception_trace(name: str, payload: bytes,
                                     app_class: str) -> tuple[bytes, list[str]]:
    normalized = name.replace('\\', '/')
    if app_class != 'FF4A' or normalized != 'FF4A.class':
        return payload, []
    data = payload
    original_count = data.count(_FF4A_START_CATCH)
    trace_count = data.count(_FF4A_START_CATCH_TRACE)
    if original_count == 1:
        data = data.replace(_FF4A_START_CATCH, _FF4A_START_CATCH_TRACE, 1)
        return data, ['ff4a-start-exception-rethrow-trace']
    if original_count == 0 and trace_count == 1:
        return data, ['ff4a-start-exception-rethrow-already-enabled']
    raise RuntimeError('FF4A.start() exception handler signature changed/ambiguous')


def patch_ff4a_mainloop_exception_trace(name: str, payload: bytes,
                                          app_class: str) -> tuple[bytes, list[str]]:
    normalized = name.replace('\\', '/')
    if app_class != 'FF4A' or normalized != 'm.class':
        return payload, []
    data = payload
    original_count = data.count(_FF4A_MAINLOOP_CATCH)
    trace_count = data.count(_FF4A_MAINLOOP_CATCH_TRACE)
    if original_count == 1:
        data = data.replace(_FF4A_MAINLOOP_CATCH, _FF4A_MAINLOOP_CATCH_TRACE, 1)
        return data, ['ff4a-mainloop-exception-rethrow-trace']
    if original_count == 0 and trace_count == 1:
        return data, ['ff4a-mainloop-exception-rethrow-already-enabled']
    raise RuntimeError('FF4A m.a(String) exception handler signature changed/ambiguous')


def patch_ff4a_field_exception_trace(name: str, payload: bytes,
                                      app_class: str) -> tuple[bytes, list[str]]:
    normalized = name.replace('\\', '/')
    if app_class != 'FF4A' or normalized != 'd.class':
        return payload, []
    data = payload
    original_count = data.count(_FF4A_FIELD_CATCH)
    trace_count = data.count(_FF4A_FIELD_CATCH_TRACE)
    if original_count == 1:
        data = data.replace(_FF4A_FIELD_CATCH, _FF4A_FIELD_CATCH_TRACE, 1)
        return data, ['ff4a-field-exception-rethrow-trace']
    if original_count == 0 and trace_count == 1:
        return data, ['ff4a-field-exception-rethrow-already-enabled']
    raise RuntimeError('FF4A d.d() field exception handler signature changed/ambiguous')

def patch_ff4a_performance(name: str, payload: bytes, app_class: str) -> tuple[bytes, list[str]]:
    normalized = name.replace('\\', '/')
    if app_class != 'FF4A' or normalized != 'm.class':
        return payload, []
    data = payload
    tags: list[str] = []
    gc_count = data.count(_FF4A_PERIODIC_GC)
    phone_count = data.count(_FF4A_PERIODIC_PHONE)
    if gc_count == 1:
        data = data.replace(_FF4A_PERIODIC_GC, _FF4A_PERIODIC_GC_PATCHED, 1)
        tags.append('ff4a-periodic-full-gc-removed')
    elif data.count(_FF4A_PERIODIC_GC_PATCHED) == 1:
        tags.append('ff4a-periodic-full-gc-already-removed')
    else:
        raise RuntimeError('FF4A periodic GC signature changed/ambiguous')
    if phone_count == 1:
        data = data.replace(_FF4A_PERIODIC_PHONE, _FF4A_PERIODIC_PHONE_PATCHED, 1)
        tags.append('ff4a-periodic-phone-attribute-removed')
    elif data.count(_FF4A_PERIODIC_PHONE_PATCHED) == 1:
        tags.append('ff4a-periodic-phone-attribute-already-removed')
    else:
        raise RuntimeError('FF4A periodic PhoneSystem signature changed/ambiguous')

    if data.count(_FF4A_DEAD_CLOCK) == 1:
        data = data.replace(_FF4A_DEAD_CLOCK, _FF4A_DEAD_CLOCK_PATCHED, 1)
        tags.append('ff4a-dead-frame-clock-removed')
    elif data.count(_FF4A_DEAD_CLOCK_PATCHED) == 1:
        tags.append('ff4a-dead-frame-clock-already-removed')
    else:
        raise RuntimeError('FF4A dead frame clock signature changed/ambiguous')

    if data.count(_FF4A_FRAME_YIELD) == 1:
        data = data.replace(_FF4A_FRAME_YIELD, _FF4A_FRAME_YIELD_PATCHED, 1)
        tags.append('ff4a-redundant-frame-yield-removed')
    elif data.count(_FF4A_FRAME_YIELD_PATCHED) == 1:
        tags.append('ff4a-redundant-frame-yield-already-removed')
    else:
        raise RuntimeError('FF4A frame yield signature changed/ambiguous')

    if data.count(_FF4A_CANVAS_CTOR) == 1:
        data = data.replace(_FF4A_CANVAS_CTOR, _FF4A_CANVAS_CTOR_PATCHED, 1)
        tags.append('ff4a-logical-canvas-240x240-decoupled-from-physical-screen')
    elif data.count(_FF4A_CANVAS_CTOR_PATCHED) == 1:
        tags.append('ff4a-logical-canvas-already-decoupled')
    else:
        raise RuntimeError('FF4A canvas constructor signature changed/ambiguous')

    # v46: remove every remaining explicit System.gc() in FF4A. The KVM
    # allocator still performs GC automatically on allocation pressure, but
    # scene/resource transitions no longer force full-heap scans.
    remaining_gc = data.count(_FF4A_ALL_GC_CALL)
    if remaining_gc:
        data = data.replace(_FF4A_ALL_GC_CALL, _FF4A_ALL_GC_NOP)
        tags.append('ff4a-all-explicit-full-gc-removed=%d' % remaining_gc)
    return data, tags


def patch_game_for_offline_boot(name: str, payload: bytes) -> tuple[bytes, list[str]]:
    """Force supported network-dependent games to load bundled SP data.

    Returns the possibly patched class bytes and human-readable patch tags.
    Unknown games are copied unchanged.
    """
    normalized = name.replace('\\', '/')
    known_corpse_party_loader = (
        normalized == 'j.class' and
        b'init.bin' in payload and
        b'scratchpad:///0;pos=1,length=4' in payload and
        b'scratchpad:///0;pos=0,length=1' in payload
    )
    if not known_corpse_party_loader:
        return payload, []

    data = payload
    applied: list[str] = []

    decision_count = data.count(_CP_OFFLINE_DECISION)
    gate_count = data.count(_CP_NETWORK_GATE)
    already_decision = data.count(_CP_OFFLINE_DECISION_PATCHED)
    already_gate = data.count(_CP_NETWORK_GATE_PATCHED)
    progress_count = data.count(_CP_LOADING_PROGRESS)
    already_progress = data.count(_CP_LOADING_PROGRESS_PATCHED)

    if decision_count == 1:
        data = data.replace(_CP_OFFLINE_DECISION, _CP_OFFLINE_DECISION_PATCHED, 1)
        applied.append('startup-state-12-forced-to-10')
    elif decision_count > 1:
        raise RuntimeError('Offline startup pattern is ambiguous in ' + normalized)
    elif already_decision == 1:
        applied.append('startup-state-12-already-patched')

    if gate_count == 1:
        data = data.replace(_CP_NETWORK_GATE, _CP_NETWORK_GATE_PATCHED, 1)
        applied.append('network-state-9-redirected-to-10')
    elif gate_count > 1:
        raise RuntimeError('Offline network-gate pattern is ambiguous in ' + normalized)
    elif already_gate == 1:
        applied.append('network-state-9-already-patched')

    if progress_count == 1:
        data = data.replace(_CP_LOADING_PROGRESS, _CP_LOADING_PROGRESS_PATCHED, 1)
        applied.append('state-10-loading-divisor-fixed')
    elif progress_count > 1:
        raise RuntimeError('Loading-progress pattern is ambiguous in ' + normalized)
    elif already_progress == 1:
        applied.append('state-10-loading-divisor-already-fixed')

    # Require every guard for the exact known class. A partial match means the
    # supported version changed and must not be silently altered.
    if applied and len(applied) != 3:
        raise RuntimeError('Only part of the offline boot patch matched ' + normalized)
    if known_corpse_party_loader and not applied:
        raise RuntimeError(
            'Corpse Party network loader was found, but the offline patch did not match ' + normalized
        )

    if known_corpse_party_loader:
        data, stream_count = patch_segment_streams(data)
        applied.append('scratchpad-segment-stream-loaders=%d' % stream_count)
    return data, applied


def detect_corpse_party_compat(jar_path: Path) -> bool:
    """Return True only for the exact legacy downloader layout we support."""
    with zipfile.ZipFile(jar_path, 'r') as archive:
        try:
            payload = archive.read('j.class')
        except KeyError:
            return False
    return (
        b'init.bin' in payload and
        b'scratchpad:///0;pos=1,length=4' in payload and
        b'scratchpad:///0;pos=0,length=1' in payload
    )


def safe_stem(value: str) -> str:
    stem = re.sub(r'[^A-Za-z0-9]+', '_', value).strip('_').lower()
    return stem or 'doja_game'


def c_escape(value: str) -> str:
    return (value.replace('\\', '\\\\').replace('"', '\\"')
            .replace('\r', '\\r').replace('\n', '\\n').replace('\t', '\\t'))



def _zip_stored_single(payload: bytes) -> bytes:
    """Build a deterministic one-entry ZIP using method STORED."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED,
                         allowZip64=False) as archive:
        info = zipfile.ZipInfo('0', date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        info.create_system = 0
        info.external_attr = 0
        archive.writestr(info, payload)
    return buffer.getvalue()


def repack_ff4a_scratchpad_stored(source: Path, output: Path) -> dict[str, int]:
    """Repack FF4A's 14 nested resource JARs as contiguous STORED ZIPs.

    FF4A keeps a 65-record index in the final resource pack. Each record holds
    the pack offset/length plus the offset/length of the requested resource in
    the uncompressed pack payload. Repacking therefore requires rebuilding all
    packs and rewriting every pack offset/length in that index.
    """
    data = bytearray(source.read_bytes())
    base = 25600
    if len(data) < base + 20:
        raise RuntimeError('FF4A ScratchPad is too small')

    old_total = struct.unpack_from('>I', data, base + 8)[0]
    index_rel = struct.unpack_from('>I', data, base + 12)[0]
    index_len = struct.unpack_from('>I', data, base + 16)[0]
    if old_total <= 20 or base + old_total > len(data):
        raise RuntimeError('FF4A ScratchPad resource span is invalid')
    if index_rel < 20 or index_len <= 0 or index_rel + index_len > old_total:
        raise RuntimeError('FF4A ScratchPad index pack is invalid')

    def read_single_pack(rel: int, length: int) -> bytes:
        blob = bytes(data[base + rel:base + rel + length])
        try:
            with zipfile.ZipFile(io.BytesIO(blob), 'r') as archive:
                infos = archive.infolist()
                if len(infos) != 1 or infos[0].filename != '0':
                    raise RuntimeError('FF4A pack is not a one-entry JAR')
                return archive.read('0')
        except zipfile.BadZipFile as exc:
            raise RuntimeError('Invalid FF4A nested resource JAR') from exc

    index_payload = bytearray(read_single_pack(index_rel, index_len))
    if len(index_payload) < 4:
        raise RuntimeError('FF4A resource index is truncated')
    record_count = struct.unpack_from('<I', index_payload, 0)[0]
    if record_count != 65 or 4 + record_count * 24 > len(index_payload):
        raise RuntimeError('Unexpected FF4A resource index layout')

    old_packs: set[tuple[int, int]] = set()
    records: list[tuple[int, int, int, int, int, int]] = []
    for i in range(record_count):
        offset = 4 + i * 24
        record = struct.unpack_from('<6I', index_payload, offset)
        records.append(record)
        old_packs.add((record[2], record[3]))
    old_packs.add((index_rel, index_len))
    ordered = sorted(old_packs)
    if len(ordered) != 14 or ordered[0][0] != 20:
        raise RuntimeError('Expected exactly 14 contiguous FF4A resource packs')

    payloads: dict[tuple[int, int], bytes] = {}
    old_end = 20
    old_compressed = 0
    total_uncompressed = 0
    for key in ordered:
        rel, length = key
        if rel != old_end:
            raise RuntimeError('FF4A resource packs are not contiguous')
        payload = read_single_pack(rel, length)
        payloads[key] = payload
        old_end += length
        old_compressed += length
        total_uncompressed += len(payload)
    if old_end > old_total:
        raise RuntimeError('FF4A resource packs exceed declared resource span')

    stored_blobs = {key: _zip_stored_single(payload) for key, payload in payloads.items()}
    mapping: dict[tuple[int, int], tuple[int, int]] = {}
    cursor = 20
    for key in ordered:
        blob = stored_blobs[key]
        mapping[key] = (cursor, len(blob))
        cursor += len(blob)

    # Rewrite every resource record to the new pack location. The resource
    # offset/length inside the uncompressed payload does not change.
    for i, record in enumerate(records):
        name_offset, name_length, pack_rel, pack_len, entry_offset, entry_len = record
        new_rel, new_len = mapping[(pack_rel, pack_len)]
        struct.pack_into('<6I', index_payload, 4 + i * 24,
                         name_offset, name_length, new_rel, new_len,
                         entry_offset, entry_len)

    index_key = (index_rel, index_len)
    rebuilt_index = _zip_stored_single(bytes(index_payload))
    expected_index_len = mapping[index_key][1]
    if len(rebuilt_index) != expected_index_len:
        raise RuntimeError('FF4A STORED index pack length changed unexpectedly')
    stored_blobs[index_key] = rebuilt_index
    payloads[index_key] = bytes(index_payload)

    # The header stores an aligned resource-span length. Keep the original
    # post-resource save area, but move it after the larger STORED pack region.
    new_end = cursor
    new_total = (new_end + 63) & ~63
    trailing = bytes(data[base + old_total:])
    result = bytearray(data[:base + 20])
    for key in ordered:
        result.extend(stored_blobs[key])
    if len(result) != base + new_end:
        raise RuntimeError('FF4A STORED pack assembly length mismatch')
    result.extend(b'\x00' * (base + new_total - len(result)))
    result.extend(trailing)

    new_index_rel, new_index_len = mapping[index_key]
    struct.pack_into('>I', result, base + 8, new_total)
    struct.pack_into('>I', result, base + 12, new_index_rel)
    struct.pack_into('>I', result, base + 16, new_index_len)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)

    # Full integrity pass: all packs must be STORED, and all indexed resource
    # slices must remain byte-for-byte identical to the original payloads.
    for key in ordered:
        new_rel, new_len = mapping[key]
        blob = bytes(result[base + new_rel:base + new_rel + new_len])
        with zipfile.ZipFile(io.BytesIO(blob), 'r') as archive:
            infos = archive.infolist()
            if len(infos) != 1 or infos[0].compress_type != zipfile.ZIP_STORED:
                raise RuntimeError('FF4A pack was not converted to STORED')
            if archive.read('0') != payloads[key]:
                raise RuntimeError('FF4A STORED pack payload mismatch')

    saved_inflate = total_uncompressed - old_compressed
    print('[DoJa] FF4A STORED packs: 14/14')
    print('[DoJa] FF4A pack bytes   : compressed=%d stored=%d payload=%d' %
          (old_compressed, new_end - 20, total_uncompressed))
    print('[DoJa] FF4A SP size      : %d -> %d bytes' % (len(data), len(result)))
    print('[DoJa] FF4A Java inflate : eliminated for all resource packs')
    return {
        'pack_count': len(ordered),
        'record_count': record_count,
        'old_size': len(data),
        'new_size': len(result),
        'old_pack_bytes': old_compressed,
        'new_pack_bytes': new_end - 20,
        'payload_bytes': total_uncompressed,
        'inflate_bytes_eliminated': saved_inflate,
    }


LZ77_WRAPPER = struct.Struct('<4sIIII')
LZ77_MAGIC = b'D7SP'
LZ77_VERSION = 1


def encode_nintendo_lz77(data: bytes) -> bytes:
    """Encode a Nintendo/GBA/NDS LZ77 (type 0x10) stream.

    The encoder is self-contained so build-doja.bat needs only Python 3. It
    uses a bounded 4 KiB search window and the standard 3..18 byte matches.
    """
    size = len(data)
    if size >= (1 << 24):
        raise ValueError('Nintendo LZ77 supports ScratchPads smaller than 16 MiB.')
    out = bytearray((0x10, size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF))
    chains: dict[int, list[int]] = {}
    pos = 0

    def key_at(index: int) -> int:
        return data[index] | (data[index + 1] << 8) | (data[index + 2] << 16)

    def remember(index: int) -> None:
        if index + 2 >= size:
            return
        key = key_at(index)
        chain = chains.setdefault(key, [])
        chain.append(index)
        # Keep recent candidates only. This bounds preparation time while
        # preserving excellent compression for game resource packs.
        if len(chain) > 128:
            del chain[:-64]

    while pos < size:
        flag_offset = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if pos >= size:
                break
            best_length = 0
            best_distance = 0
            if pos + 2 < size:
                key = key_at(pos)
                chain = chains.get(key, ())
                window_start = max(0, pos - 4096)
                for candidate in reversed(chain[-64:]):
                    if candidate < window_start:
                        break
                    maximum = min(18, size - pos)
                    length = 3
                    while length < maximum and data[candidate + length] == data[pos + length]:
                        length += 1
                    if length > best_length:
                        best_length = length
                        best_distance = pos - candidate
                        if length == 18:
                            break
            if best_length >= 3:
                flags |= 1 << (7 - bit)
                displacement = best_distance - 1
                encoded_length = best_length - 3
                out.append((encoded_length << 4) | ((displacement >> 8) & 0x0F))
                out.append(displacement & 0xFF)
                end = pos + best_length
                while pos < end:
                    remember(pos)
                    pos += 1
            else:
                out.append(data[pos])
                remember(pos)
                pos += 1
        out[flag_offset] = flags

    # objcopy/linking is happier with word-aligned binary resources. The
    # decoder stops after the declared uncompressed size and ignores padding.
    while len(out) & 3:
        out.append(0)
    return bytes(out)


def write_lz77_scratchpad(raw: bytes, output: Path) -> tuple[int, int, int]:
    packed = encode_nintendo_lz77(raw)
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    wrapper = LZ77_WRAPPER.pack(LZ77_MAGIC, LZ77_VERSION, len(raw), len(packed), crc) + packed
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(wrapper)
    ratio = (100.0 * len(packed) / len(raw)) if raw else 0.0
    print('[DoJa] LZ77 pack  : %d -> %d bytes (%.1f%%)' % (len(raw), len(packed), ratio))
    print('[DoJa] LZ77 file  :', output, len(wrapper), 'bytes')
    return len(packed), len(wrapper), crc


def write_prepared_jam(path: Path, jam: dict[str, str], raw_size: int) -> None:
    values = dict(jam)
    values['SPsize'] = str(raw_size)
    values['DoJaPortBuild'] = 'v59-empty'
    values['NDSOuterCompression'] = 'LZ77'
    preferred = [
        'AppName', 'AppVer', 'PackageURL', 'AppSize', 'AppClass', 'AppParam',
        'SPsize', 'ProfileVer', 'ConfigurationVer', 'DoJaPortBuild',
        'NDSOuterCompression', 'NDSScaleMode', 'NDSCanvasWidth',
        'NDSCanvasHeight', 'NDSLogicalWidth', 'NDSLogicalHeight',
        'NDSOutputX', 'NDSOutputY', 'NDSOutputWidth', 'NDSOutputHeight',
    ]
    lines = []
    used = set()
    for key in preferred:
        if key in values:
            lines.append(f'{key} = {values[key]}')
            used.add(key)
    for key in sorted(values):
        if key not in used:
            lines.append(f'{key} = {values[key]}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\r\n'.join(lines) + '\r\n', encoding='utf-8')

def patch_class_version(path: Path) -> None:
    data = bytearray(path.read_bytes())
    if len(data) < 8 or data[:4] != b'\xca\xfe\xba\xbe':
        raise RuntimeError('Not a class file: ' + str(path))
    # KVM/CLDC classes in the target game use Java 1.1 class version 45.3.
    struct.pack_into('>HH', data, 4, 3, 45)
    path.write_bytes(data)


def compile_compat(project: Path, tool_root: Path, build_root: Path) -> Path:
    javac = shutil.which('javac')
    if not javac:
        raise RuntimeError('javac not found. Install Java 17/21 and add it to PATH.')
    boot = project / 'api' / 'classes'
    boot_zip = project / 'api' / 'classes.zip'
    # Fresh source archives do not preserve the generated api/classes tree.
    # Restore it automatically from the bundled CLDC classes.zip before javac.
    if not boot.is_dir() or not any(boot.rglob('*.class')):
        if not boot_zip.is_file():
            raise RuntimeError('Missing base CLDC classes: ' + str(boot_zip))
        shutil.rmtree(boot, ignore_errors=True)
        boot.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(boot_zip, 'r') as archive:
            archive.extractall(boot)
        print('[DoJa] Restored CLDC boot classes:', boot)
    if not any(boot.rglob('java/lang/Object.class')):
        raise RuntimeError('Invalid base CLDC classes: ' + str(boot))
    stub_src = tool_root / 'compile_stubs'
    doja_src = project / 'doja_port' / 'doja_src'
    stub_out = build_root / 'stub_classes'
    class_out = build_root / 'doja_classes'
    shutil.rmtree(stub_out, ignore_errors=True)
    shutil.rmtree(class_out, ignore_errors=True)
    stub_out.mkdir(parents=True)
    class_out.mkdir(parents=True)
    stubs = sorted(str(p) for p in stub_src.rglob('*.java'))
    sources = sorted(str(p) for p in doja_src.rglob('*.java'))
    if not sources:
        raise RuntimeError('DoJa compatibility sources are missing.')
    common = [javac, '-encoding', 'UTF-8', '-source', '8', '-target', '8',
              '-bootclasspath', str(boot)]
    subprocess.run(common + ['-d', str(stub_out)] + stubs, check=True)
    subprocess.run(common + ['-classpath', str(stub_out), '-d', str(class_out)] + sources, check=True)
    for class_file in class_out.rglob('*.class'):
        patch_class_version(class_file)
    return class_out


def install_default_icon(project: Path, output: Path) -> None:
    source = project / 'assets' / 'default_standalone_icon.bmp'
    if not source.is_file():
        raise RuntimeError('Missing bundled default icon: ' + str(source))
    data = source.read_bytes()
    if len(data) < 70 or data[:2] != b'BM':
        raise RuntimeError('Default NDS icon is not a BMP file')
    width = struct.unpack_from('<I', data, 18)[0]
    height = struct.unpack_from('<I', data, 22)[0]
    bits = struct.unpack_from('<H', data, 28)[0]
    if width != 32 or height != 32 or bits != 4:
        raise RuntimeError('Default NDS icon must be 32x32, 4bpp')
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    print('[DoJa] Icon      : bundled assets/default_standalone_icon.bmp')


def merge_jar(original: Path, class_dir: Path, font_bin: Path, cp932_bin: Path,
              output: Path, app_name: str, app_class: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = (
        'Manifest-Version: 1.0\r\n'
        'MIDlet-Name: ' + app_name + '\r\n'
        'MIDlet-1: ' + app_name + ',,nds.doja.MainApp\r\n'
        'MicroEdition-Configuration: CLDC-1.0\r\n'
        'MicroEdition-Profile: DoJa-3.5\r\n'
        'DoJa-App-Class: ' + app_class + '\r\n'
        'DoJa-Port-Version: ' + str(PORT_VERSION) + '\r\n'
        'DoJa-FF4A-Optimized: ' + ('1' if app_class == 'FF4A' else '0') + '\r\n'
        'DoJa-FF4A-Bytecode-Profile: ' + ('v59-continue-exception-trace' if app_class == 'FF4A' else 'none') + '\r\n'
        'DoJa-Physical-Canvas: 256x192\r\n'
        'DoJa-Logical-Canvas: 240x240\r\n\r\n'
    ).encode('utf-8')
    jar_method = zipfile.ZIP_STORED
    jar_level = None
    with zipfile.ZipFile(original, 'r') as source, zipfile.ZipFile(output, 'w', jar_method, compresslevel=jar_level) as dest:
        written: set[str] = set()
        for info in source.infolist():
            name = info.filename.replace('\\', '/')
            upper = name.upper()
            if name.endswith('/') or upper == 'META-INF/MANIFEST.MF' or upper.endswith(('.SF', '.RSA', '.DSA')):
                continue
            game_payload = source.read(info.filename)
            game_payload, patch_tags = patch_game_for_offline_boot(name, game_payload)
            game_payload, perf_tags = patch_ff4a_performance(name, game_payload, app_class)
            patch_tags.extend(perf_tags)
            game_payload, field_trace_tags = patch_ff4a_field_exception_trace(name, game_payload, app_class)
            patch_tags.extend(field_trace_tags)
            game_payload, main_trace_tags = patch_ff4a_mainloop_exception_trace(name, game_payload, app_class)
            patch_tags.extend(main_trace_tags)
            game_payload, start_trace_tags = patch_ff4a_start_exception_trace(name, game_payload, app_class)
            patch_tags.extend(start_trace_tags)
            if patch_tags:
                print('[DoJa] Offline patch:', name)
                for patch_tag in patch_tags:
                    print('[DoJa]   -', patch_tag)
            dest.writestr(name, game_payload)
            written.add(name)
        dest.writestr('META-INF/MANIFEST.MF', manifest)
        for class_file in sorted(class_dir.rglob('*.class')):
            name = class_file.relative_to(class_dir).as_posix()
            if name in written:
                raise RuntimeError('Compatibility class collides with game JAR: ' + name)
            dest.write(class_file, name)
        # v46: ScratchPad is linked separately as native ROM data.  Do not put
        # the full ScratchPad payload in the JAR, because KVM inflates whole JAR
        # resources into its heap before ResourceInputStream can read them.
        dest.write(font_bin, 'doja/jpfont.bin')
        dest.write(cp932_bin, 'doja/cp932.tbl')





def verify_ff4a_field_trace_jar(jar_path: Path, app_class: str) -> None:
    if app_class != 'FF4A':
        return
    with zipfile.ZipFile(jar_path, 'r') as archive:
        payload = archive.read('d.class')
    if payload.count(_FF4A_FIELD_CATCH_TRACE) != 1:
        raise RuntimeError('FF4A field exception trace patch is not present exactly once')
    if _FF4A_FIELD_CATCH in payload:
        raise RuntimeError('FF4A generic field exception catch remains active')
    print('[DoJa] FF4A trace   : d.d() generic field error now rethrows the real exception')


def verify_ff4a_mainloop_trace_jar(jar_path: Path, app_class: str) -> None:
    if app_class != 'FF4A':
        return
    with zipfile.ZipFile(jar_path, 'r') as archive:
        payload = archive.read('m.class')
    if payload.count(_FF4A_MAINLOOP_CATCH_TRACE) != 1:
        raise RuntimeError('FF4A main-loop exception trace patch is not present exactly once')
    if _FF4A_MAINLOOP_CATCH in payload:
        raise RuntimeError('FF4A generic main-loop exception catch remains active')
    print('[DoJa] FF4A trace   : m.a(String) generic Continue/load error now rethrows real exception')


def verify_ff4a_start_trace_jar(jar_path: Path, app_class: str) -> None:
    if app_class != 'FF4A':
        return
    with zipfile.ZipFile(jar_path, 'r') as archive:
        payload = archive.read('FF4A.class')
    if payload.count(_FF4A_START_CATCH_TRACE) != 1:
        raise RuntimeError('FF4A.start exception trace patch is not present exactly once')
    if _FF4A_START_CATCH in payload:
        raise RuntimeError('FF4A.start still swallows Continue/load exceptions')
    print('[DoJa] FF4A trace   : FF4A.start() now rethrows instead of terminate()')


def verify_ff4a_performance_jar(jar_path: Path, app_class: str) -> None:
    if app_class != 'FF4A':
        return
    with zipfile.ZipFile(jar_path, 'r') as archive:
        payload = archive.read('m.class')
    if _FF4A_PERIODIC_GC in payload or _FF4A_PERIODIC_PHONE in payload:
        raise RuntimeError('FF4A hot-loop patch was not applied')
    if payload.count(_FF4A_PERIODIC_GC_PATCHED) != 1 or \
            payload.count(_FF4A_PERIODIC_PHONE_PATCHED) != 1 or \
            payload.count(_FF4A_DEAD_CLOCK_PATCHED) != 1 or \
            payload.count(_FF4A_FRAME_YIELD_PATCHED) != 1:
        raise RuntimeError('FF4A hot-loop patch verification is ambiguous')
    if (_FF4A_DEAD_CLOCK in payload or _FF4A_FRAME_YIELD in payload):
        raise RuntimeError('FF4A v46 frame-loop bytecode patch was not applied')
    if _FF4A_ALL_GC_CALL in payload:
        raise RuntimeError('FF4A still contains explicit System.gc bytecode')
    print('[DoJa] FF4A bytecode: all explicit GC + phone + dead clock + redundant yield removed')

def verify_doja_v46_api(jar_path: Path) -> None:
    """Verify generic DoJa image/3D/archive classes needed by FF4A-class titles."""
    required = (
        'com/nttdocomo/ui/Palette.class',
        'com/nttdocomo/ui/PalettedImage.class',
        'com/nttdocomo/ui/Graphics.class',
        'com/nttdocomo/ui/graphics3d/Graphics3D.class',
        'com/nttdocomo/ui/graphics3d/Object3D.class',
        'com/nttdocomo/ui/graphics3d/DrawableObject3D.class',
        'com/nttdocomo/ui/graphics3d/Primitive.class',
        'com/nttdocomo/ui/graphics3d/Texture.class',
        'com/nttdocomo/ui/graphics3d/Fog.class',
        'com/nttdocomo/ui/util3d/FastMath.class',
        'com/nttdocomo/ui/util3d/Transform.class',
        'com/nttdocomo/ui/util3d/Vector3D.class',
        'com/nttdocomo/util/JarInflater.class',
        'com/nttdocomo/util/JarInflater$RawInflater.class',
        'com/nttdocomo/util/JarInflater$BitReader.class',
        'com/nttdocomo/util/JarInflater$Huffman.class',
        'nds/doja/image/IndexedGifDecoder.class',
        'nds/doja/FastPath.class',
        'nds/pstros/video/DoJaFastBlit.class',
    )
    with zipfile.ZipFile(jar_path, 'r') as archive:
        names = set(archive.namelist())
        missing = [name for name in required if name not in names]
        if missing:
            raise RuntimeError('Missing v46 DoJa API class: ' + ', '.join(missing))
        paletted = archive.read('com/nttdocomo/ui/PalettedImage.class')
        graphics = archive.read('com/nttdocomo/ui/Graphics.class')
        inflater = archive.read('com/nttdocomo/util/JarInflater.class')
        raw_inflater = archive.read('com/nttdocomo/util/JarInflater$RawInflater.class')
        fast_path = archive.read('nds/doja/FastPath.class')
        fast_blit = archive.read('nds/pstros/video/DoJaFastBlit.class')
        if not all(token in paletted for token in (b'createPalettedImage', b'getPalette', b'setTransparentIndex')):
            raise RuntimeError('PalettedImage.class is stale')
        if not all(token in graphics for token in (b'Graphics3D', b'setFlipMode', b'getPixels', b'setPixels')):
            raise RuntimeError('Graphics.class lacks v46 DoJa image/3D API')
        if not all(token in inflater for token in (b'getInputStream', b'getSize', b'missing zip directory')):
            raise RuntimeError('JarInflater.class is stale')
        if not all(token in raw_inflater for token in (
                b'LENGTH_BASE', b'DIST_BASE', b'inflate', b'FIXED_LITERAL', b'copyMatch')):
            raise RuntimeError('JarInflater raw-DEFLATE engine is stale')
        if not all(token in fast_path for token in (b'present', b'drawImageAlpha', b'drawRegionAlpha')):
            raise RuntimeError('FastPath.class is stale')
        if not all(token in fast_blit for token in (b'Video', b'blit', b'drawImageAlpha')):
            raise RuntimeError('DoJaFastBlit.class is stale')
    print('[DoJa] v46 API verify: FF4A fast bridge + palette/graphics3d/JAR inflater')


def verify_cp932_jar(jar_path: Path) -> None:
    """Verify that the runtime default encoding and both conversion directions exist."""
    with zipfile.ZipFile(jar_path, 'r') as archive:
        names = set(archive.namelist())
        required = (
            'doja/cp932.tbl',
            'nds/doja/encoding/Cp932Codec.class',
            'nds/doja/font/BitmapJapaneseFont.class',
            'com/sun/cldc/i18n/j2me/SJIS_Reader.class',
            'com/sun/cldc/i18n/j2me/SJIS_Writer.class',
        )
        for name in required:
            if name not in names:
                raise RuntimeError('Missing v46 SJIS runtime entry: ' + name)
        table = archive.read('doja/cp932.tbl')
        bitmap_font_class = archive.read('nds/doja/font/BitmapJapaneseFont.class')
        if b'isNonPrintingControl' not in bitmap_font_class:
            raise RuntimeError('Missing v46 NUL/control padding font fix')
    if len(table) < 12 or table[:4] != b'DJC2':
        raise RuntimeError('Invalid v46 CP932 mapping resource')
    version, single_count, double_count, reverse_count = struct.unpack_from('>HHHH', table, 4)
    expected = 12 + single_count * 2 + double_count * 2 + reverse_count * 4
    if version != 1 or single_count != 256 or double_count != 11280:
        raise RuntimeError('Unexpected v46 CP932 table dimensions')
    if reverse_count < 9000 or len(table) != expected:
        raise RuntimeError('Truncated v46 CP932 reverse map')
    print('[DoJa] SJIS verify: default=SJIS decode=%d encode=%d table=%d' % (
        single_count + double_count, reverse_count, len(table)))


def verify_offline_jar(jar_path: Path) -> None:
    """Fail preparation unless the final embedded JAR is offline-safe."""
    import hashlib

    with zipfile.ZipFile(jar_path, 'r') as archive:
        names = set(archive.namelist())
        if 'doja/scratchpad.bin' in names:
            raise RuntimeError('v46 game.jar must not contain doja/scratchpad.bin')
        print('[DoJa] Native SP verify: JAR entry absent')
        try:
            data = archive.read('j.class')
        except KeyError:
            print('[DoJa] Offline verify: no j.class (generic game)')
            return

    known_corpse_party_loader = (
        b'init.bin' in data and
        b'scratchpad:///0;pos=1,length=4' in data and
        b'scratchpad:///0;pos=0,length=1' in data
    )
    if not known_corpse_party_loader:
        print('[DoJa] Offline verify: generic j.class, no compatibility patch required')
        return

    direct_network = bytes.fromhex('10 09 b3 02 a9')
    direct_offline = bytes.fromhex('10 0a b3 02 a9')
    original_gate = bytes.fromhex('b2 02 a9 10 09 a0 02 93')
    forced_gate = bytes.fromhex('10 0a b3 02 a9 a7 02 93')
    unsafe_progress = bytes.fromhex('b2 02 8f 11 10 00 68 b2 02 90 6c')
    safe_progress = bytes.fromhex('b2 02 8f 11 10 00 68 10 0a 00 6c')

    network_count = data.count(direct_network)
    offline_count = data.count(direct_offline)
    original_gate_count = data.count(original_gate)
    forced_gate_count = data.count(forced_gate)
    unsafe_progress_count = data.count(unsafe_progress)
    safe_progress_count = data.count(safe_progress)
    digest = hashlib.sha256(data).hexdigest()

    print('[DoJa] Offline verify: j.class sha256=' + digest)
    print('[DoJa] Offline verify: state9=%d state10=%d oldGate=%d forcedGate=%d' % (
        network_count, offline_count, original_gate_count, forced_gate_count))
    print('[DoJa] Loading verify: unsafeDiv=%d safeDiv=%d' % (
        unsafe_progress_count, safe_progress_count))

    if network_count != 0 or original_gate_count != 0:
        raise RuntimeError('Final embedded/game.jar still contains an active network bootstrap')
    if forced_gate_count != 1:
        raise RuntimeError('Final embedded/game.jar is missing the forced state-10 gate')
    if unsafe_progress_count != 0 or safe_progress_count != 1:
        raise RuntimeError('Final embedded/game.jar is missing the state-10 divide-by-zero guard')

    stream_count, legacy_stream_count = segment_stream_patch_counts(data)
    print('[DoJa] Segment stream verify: patched=%d legacy=%d' % (
        stream_count, legacy_stream_count))
    if stream_count != 13 or legacy_stream_count != 0:
        raise RuntimeError('Final embedded/game.jar is missing the v46 zero-copy segment patch')



def _class_super_name(data: bytes) -> str:
    """Return the JVM internal superclass name from a class file."""
    if len(data) < 10 or data[:4] != b'\xca\xfe\xba\xbe':
        raise RuntimeError('Invalid class data')
    cp_count = struct.unpack_from('>H', data, 8)[0]
    cp: list[object | None] = [None] * cp_count
    offset = 10
    index = 1
    while index < cp_count:
        tag = data[offset]
        offset += 1
        if tag == 1:  # Utf8
            length = struct.unpack_from('>H', data, offset)[0]
            offset += 2
            cp[index] = data[offset:offset + length].decode('latin-1')
            offset += length
        elif tag in (3, 4):
            offset += 4
        elif tag in (5, 6):
            offset += 8
            index += 1
        elif tag in (7, 8, 16):
            cp[index] = struct.unpack_from('>H', data, offset)[0]
            offset += 2
        elif tag in (9, 10, 11, 12, 18):
            offset += 4
        elif tag == 15:
            offset += 3
        else:
            raise RuntimeError('Unsupported constant-pool tag: %d' % tag)
        index += 1
    # access_flags, this_class, super_class
    _access, _this_index, super_index = struct.unpack_from('>HHH', data, offset)
    if super_index == 0:
        return ''
    name_index = cp[super_index]
    if not isinstance(name_index, int) or not isinstance(cp[name_index], str):
        raise RuntimeError('Invalid superclass entry')
    return cp[name_index]


def verify_direct_scratchpad_jar(jar_path: Path) -> None:
    """Verify v46's separate top-level connection and input stream."""
    with zipfile.ZipFile(jar_path, 'r') as archive:
        names = set(archive.namelist())
        try:
            protocol = archive.read('com/sun/cldc/io/j2me/scratchpad/Protocol.class')
            input_stream = archive.read(
                'com/sun/cldc/io/j2me/scratchpad/ScratchpadInputStream.class')
            segment_token = archive.read(
                'com/sun/cldc/io/j2me/scratchpad/SegmentToken.class')
            segment_stream = archive.read(
                'com/sun/cldc/io/j2me/scratchpad/ScratchpadByteArrayInputStream.class')
            http = archive.read('com/sun/cldc/io/j2me/http/Protocol.class')
        except KeyError as exc:
            raise RuntimeError('Missing v46 ScratchPad zero-copy classes') from exc

    scratchpad_classes = sorted(
        name for name in names
        if name.startswith('com/sun/cldc/io/j2me/scratchpad/')
        and name.endswith('.class'))
    nested_present = [name for name in scratchpad_classes if '$' in name]
    has_native = all(token in protocol for token in
                     (b'nativeSize', b'nativeRead', b'nativeReadBytes',
                      b'nativeWrite', b'nativeWriteBytes'))
    creates_separate_stream = (
        b'ScratchpadInputStream' in protocol and b'openRange' in protocol)
    legacy = (b'doja/scratchpad.bin' in protocol or
              b'ResourceInputStream' in protocol or
              b'doja/scratchpad.bin' in input_stream or
              b'ResourceInputStream' in input_stream or
              b'doja/scratchpad.bin' in http or
              b'ResourceInputStream' in http)
    http_direct = b'com/sun/cldc/io/j2me/scratchpad/Protocol' in http
    protocol_super = _class_super_name(protocol)
    input_super = _class_super_name(input_stream)
    segment_super = _class_super_name(segment_stream)
    segment_patch_classes = (
        b'open' in segment_token and
        b'SegmentToken' in segment_token and
        b'nativeReadBytes' in segment_stream and
        b'ScratchpadByteArrayInputStream' in segment_stream)
    lifecycle_ok = (protocol_super == 'java/lang/Object' and
                    input_super == 'java/io/InputStream' and
                    segment_super == 'java/io/ByteArrayInputStream')
    print('[DoJa] Stream/OOM verify: native=%s separate=%s segment=%s nested=%d legacy=%s httpDirect=%s super=%s/%s/%s' % (
        'yes' if has_native else 'no',
        'yes' if creates_separate_stream else 'no',
        'yes' if segment_patch_classes else 'no',
        len(nested_present),
        'yes' if legacy else 'no',
        'yes' if http_direct else 'no',
        protocol_super, input_super, segment_super))
    if (not has_native or not creates_separate_stream or
            not segment_patch_classes or nested_present or
            legacy or not http_direct or not lifecycle_ok):
        raise RuntimeError('v46 ScratchPad segment-stream verification failed')

def verify_native_inflater_jar(jar_path: Path) -> None:
    with zipfile.ZipFile(jar_path, 'r') as archive:
        names = set(archive.namelist())
        if 'com/nttdocomo/util/NativeInflater.class' not in names:
            raise RuntimeError('NativeInflater.class is missing from game.jar')
        jar_inflater = archive.read('com/nttdocomo/util/JarInflater$RawInflater.class')
        native = archive.read('com/nttdocomo/util/NativeInflater.class')
    if b'NativeInflater' not in jar_inflater or b'inflate' not in native:
        raise RuntimeError('JarInflater RawInflater native ARM fast path is not linked')
    print('[DoJa] Native inflater: ARM DEFLATE fast path present')


def write_metadata(project: Path, jam: dict[str, str], app_name: str, app_class: str,
                   app_param: str, rom_code: str, output_stem: str,
                   scratchpad_crc32: int, scratchpad_size: int,
                   packed_size: int, wrapper_size: int,
                   video: dict[str, int | str],
                   corpse_party_compat: bool) -> None:
    props = [
        ('Manifest-Version', '1.0'),
        ('MIDlet-Name', app_name),
        ('MicroEdition-Configuration', jam.get('ConfigurationVer', 'CLDC-1.0')),
        ('MicroEdition-Profile', jam.get('ProfileVer', 'DoJa-3.5')),
        ('DoJa-App-Class', app_class),
        ('DoJa-App-Param', app_param),
        ('DoJa-Port-Version', str(PORT_VERSION)),
        ('DoJa-Source-Edition', 'Empty'),
        ('DoJa-Compat-Corpse-Party', '1' if corpse_party_compat else '0'),
        ('NDS-Outer-Compression', 'LZ77'),
        ('NDS-Scale-Mode', str(video['mode'])),
        ('NDS-Canvas-Size', '%dx%d' % (video['canvas_w'], video['canvas_h'])),
        ('NDS-Logical-Canvas-Size', '%dx%d' % (video['logical_w'], video['logical_h'])),
        ('NDS-Output-Rect', '%d,%d,%d,%d' % (video['output_x'], video['output_y'], video['output_w'], video['output_h'])),
        ('NDS-Bytecode-Profile', 'FF4A-v59-continue-exception-trace' if app_class == 'FF4A' else 'generic-v59-lz77'),
    ]
    prop_text = ''.join(k + ': ' + v + '\r\n' for k, v in props) + '\r\n'
    internal = re.sub(r'[^A-Za-z0-9]', '', output_stem).upper()[:12] or 'DOJAGAME'
    header = f'''/* Auto-generated by tools/prepare_doja.py. */
#ifndef PSTROS_STANDALONE_GAME_H
#define PSTROS_STANDALONE_GAME_H

#define DOJA_PORT_BUILD_VERSION {PORT_VERSION}
#define DOJA_PORT_VERSION_TEXT "v59 Empty"
#define STANDALONE_APP_NAME "{c_escape(app_name)}"
#define STANDALONE_MAIN_CLASS "{c_escape(app_class)}"
#define DOJA_APP_CLASS "{c_escape(app_class)}"
#define DOJA_APP_PARAM "{c_escape(app_param)}"
#define DOJA_CANVAS_WIDTH {video['canvas_w']}
#define DOJA_CANVAS_HEIGHT {video['canvas_h']}
#define DOJA_LOGICAL_WIDTH {video['logical_w']}
#define DOJA_LOGICAL_HEIGHT {video['logical_h']}
#define DOJA_SCREEN_X {video['source_x']}
#define DOJA_SCREEN_Y {video['source_y']}
#define DOJA_HW_AFFINE_SCALE {video['hardware']}
#define DOJA_OUTPUT_X {video['output_x']}
#define DOJA_OUTPUT_Y {video['output_y']}
#define DOJA_OUTPUT_WIDTH {video['output_w']}
#define DOJA_OUTPUT_HEIGHT {video['output_h']}
#define DOJA_BG_PA {video['pa']}
#define DOJA_BG_PD {video['pd']}
#define DOJA_BG_X {video['bg_x']}
#define DOJA_BG_Y {video['bg_y']}
#define DOJA_SCALE_MODE_TEXT "{video['mode']}"
#define STANDALONE_CLASSPATH "@embedded"
#define STANDALONE_JAR_FILENAME "game.jar"
#define STANDALONE_NDS_GAME_CODE "####"
#define STANDALONE_APP_STORAGE_CODE "{rom_code}"
#define STANDALONE_NDS_INTERNAL_TITLE "{internal}"
#define STANDALONE_OUTPUT_BASENAME "{output_stem}"
#define STANDALONE_SHORT_SAVE_NAME "{rom_code.upper()}.SAV"
#define STANDALONE_SHORT_SAVE_PATH "fat:/" STANDALONE_SHORT_SAVE_NAME
#define STANDALONE_SAVE_PATH "fat:/" STANDALONE_OUTPUT_BASENAME ".sav"
#define STANDALONE_RMS_SAVE_PATH "fat:/" STANDALONE_OUTPUT_BASENAME ".rms"
#define STANDALONE_LEGACY_SAVE_PATH "fat:/{rom_code.upper()}.DJS"
#define STANDALONE_SAVE_MODE_TEXT "RAM-FIRST SAVE"
#define DOJA_SCRATCHPAD_SIZE {scratchpad_size}
#define DOJA_SCRATCHPAD_CRC32 0x{scratchpad_crc32:08X}UL
#define DOJA_SCRATCHPAD_PACKED_SIZE {packed_size}
#define DOJA_SCRATCHPAD_WRAPPER_SIZE {wrapper_size}
#define DOJA_SCRATCHPAD_CODEC_LZ77 1
#define DOJA_COMPAT_CORPSE_PARTY {1 if corpse_party_compat else 0}
#define STANDALONE_PROPERTIES_TEXT "{c_escape(prop_text)}"

#endif
'''
    (project / 'include' / 'standalone_game.h').write_text(header, encoding='utf-8', newline='\n')
    mk = f'''# Auto-generated by tools/prepare_doja.py.
TARGET := {output_stem}
TEXT1 := {app_name}
TEXT2 := DoJa v59 Empty
TEXT3 := {app_class}
NDS_GAME_CODE := \\#\\#\\#\\#
NDS_MAKER_CODE := HB
NDS_INTERNAL_TITLE := {internal}
NDS_ICON := assets/standalone_icon.bmp
'''
    (project / 'standalone_game.mk').write_text(mk, encoding='utf-8', newline='\n')



def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_prepared_marker(project: Path, output_stem: str, scratchpad_size: int,
                          packed_size: int, wrapper_size: int,
                          corpse_party_compat: bool) -> Path:
    marker = project / 'build_doja' / PREPARED_MARKER
    payload = {
        'port_version': PORT_VERSION,
        'port_tag': PORT_TAG,
        'edition': 'empty',
        'codec': 'Nintendo-LZ77-0x10',
        'output_stem': output_stem,
        'scratchpad_size': scratchpad_size,
        'scratchpad_packed_size': packed_size,
        'scratchpad_wrapper_size': wrapper_size,
        'corpse_party_compat': corpse_party_compat,
        'game_jar_sha256': sha256_file(project / 'embedded' / 'game.jar'),
        'scratchpad_lz77_sha256': sha256_file(project / 'embedded' / 'doja_scratchpad.lz7b'),
        'generated_jam_sha256': sha256_file(project / 'build_doja' / 'prepared_game.jam'),
        'generated_icon_sha256': sha256_file(project / 'assets' / 'standalone_icon.bmp'),
        'metadata_sha256': sha256_file(project / 'standalone_game.mk'),
        'header_sha256': sha256_file(project / 'include' / 'standalone_game.h'),
        'resource_source_sha256': sha256_file(project / 'kvm' / 'VmExtra' / 'src' / 'resource.c'),
        'nds_main_source_sha256': sha256_file(project / 'kvm' / 'VmSkel' / 'src' / 'nds_main.c'),
        'makefile_sha256': sha256_file(project / 'Makefile'),
    }
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return marker



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--jar', required=True)
    parser.add_argument('--jam', required=True)
    parser.add_argument('--sp', required=True)
    parser.add_argument('--rom-code', required=True)
    parser.add_argument('--font')
    parser.add_argument('--name')
    parser.add_argument('--screen-x', type=int)
    parser.add_argument('--screen-y', type=int)
    parser.add_argument('--save', help='Optional existing DJSP .sav/.djs overlay to import into the ScratchPad at build time')
    args = parser.parse_args()

    project = Path(__file__).resolve().parents[1]
    tool_root = Path(__file__).resolve().parent
    version_header = (project / 'include' / 'doja_port_version.h').read_text(encoding='ascii')
    version_match = re.search(r'^#define\s+DOJA_SOURCE_PORT_VERSION\s+(\d+)\s*$', version_header, re.M)
    tag_match = re.search(r'^#define\s+DOJA_SOURCE_PORT_TAG\s+"([^"]+)"\s*$', version_header, re.M)
    if not version_match or int(version_match.group(1)) != PORT_VERSION:
        raise RuntimeError('Source version header does not match prepare_doja.py')
    if not tag_match or tag_match.group(1) != PORT_TAG:
        raise RuntimeError('Source version tag does not match prepare_doja.py')
    jar = Path(args.jar).expanduser().resolve()
    jam_path = Path(args.jam).expanduser().resolve()
    sp = Path(args.sp).expanduser().resolve()
    for path in (jar, jam_path, sp):
        if not path.is_file():
            raise FileNotFoundError(path)
    rom_code = re.sub(r'[^A-Za-z0-9]', '', args.rom_code).upper()
    if len(rom_code) != 4:
        raise ValueError('ROM code must contain exactly four letters/numbers.')

    jam = parse_jam(jam_path)
    app_class = jam.get('AppClass', 'Main').strip() or 'Main'
    app_param = jam.get('AppParam', '0').strip() or '0'
    # FF4A's handset canvas is 240x240. For this exact title, default to the
    # full 256x192 NDS affine output requested by the project. Other games keep
    # their JAM/native behavior unless they provide explicit NDS* fields.
    if app_class == 'FF4A' and 'NDSScaleMode' not in jam:
        jam.update({
            'NDSScaleMode': 'affine-stretch',
            'NDSCanvasWidth': '256', 'NDSCanvasHeight': '192',
            'NDSLogicalWidth': '240', 'NDSLogicalHeight': '240',
            'NDSSourceX': '8', 'NDSSourceY': '8',
            'NDSOutputX': '0', 'NDSOutputY': '0',
            'NDSOutputWidth': '256', 'NDSOutputHeight': '192',
        })
    video = resolve_video_config(jam, args.screen_x, args.screen_y)
    app_name = (args.name or jar.stem).strip()
    output_stem = safe_stem(app_name)
    corpse_party_compat = detect_corpse_party_compat(jar)
    work = project / 'build_doja'
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    for generated in (
        project / 'embedded' / 'game.jar',
        project / 'embedded' / 'doja_scratchpad.lz7b',
        project / 'embedded' / 'osnd_native.pcm',
        project / 'standalone_game.mk',
        project / 'include' / 'standalone_game.h',
        project / 'assets' / 'standalone_icon.bmp',
    ):
        try:
            generated.unlink()
        except FileNotFoundError:
            pass

    print('[DoJa] App class :', app_class)
    print('[DoJa] App param :', app_param)
    print('[DoJa] Profile   :', jam.get('ProfileVer', 'unknown'))
    print('[DoJa] Canvas    : physical %dx%d; logical %dx%d at VRAM X=%d Y=%d' % (video['canvas_w'], video['canvas_h'], video['logical_w'], video['logical_h'], video['source_x'], video['source_y']))
    print('[DoJa] NDS scale : %s -> %dx%d at X=%d Y=%d (BG PA=%d PD=%d)' % (video['mode'], video['output_w'], video['output_h'], video['output_x'], video['output_y'], video['pa'], video['pd']))
    print('[DoJa] Compat    :', 'FF4A exact-signature performance build' if app_class == 'FF4A' else ('Corpse Party exact-signature patch' if corpse_party_compat else 'generic game'))
    normalized_sp, _sp_mode = normalize_scratchpad(sp, jam, work / 'scratchpad_payload.bin')

    # Optional save migration.  DJSP save files are sparse 256-byte overlays
    # tied to the exact ScratchPad size + CRC that created them.  Importing
    # them at build time avoids FAT/DLDI probing during boot and also lets an
    # old pre-STORED FF4A save be migrated safely before resource repacking.
    save_path = _find_save_candidate(args.save, jar, jam_path, sp)
    save_overlay = _parse_djsp_overlay(save_path) if save_path else None
    save_imported = False
    if save_overlay is not None:
        raw = normalized_sp.read_bytes()
        if save_overlay['base_size'] == len(raw) and save_overlay['base_crc'] == _crc32(raw):
            raw = _apply_djsp_overlay(raw, save_overlay, 'original')
            normalized_sp.write_bytes(raw)
            save_imported = True
            jam['NDSImportedSave'] = 'DJSP-pre-stored'
            jam['NDSImportedSaveChunks'] = str(save_overlay['count'])

    if app_class == 'FF4A':
        # v59: FF4A contains real Continue data inside the original ScratchPad.
        # Do not relocate the nested resource JARs. Preserve the game-visible
        # payload exactly; NativeInflater handles their DEFLATE on ARM.
        original_payload = (work / 'scratchpad_payload.bin').read_bytes()
        normalized_sp = work / 'scratchpad_original_layout.bin'
        normalized_sp.write_bytes(original_payload)
        jam['SPsize'] = str(len(original_payload))
        jam['NDSResourcePackMode'] = 'original-layout-native-deflate'
        jam['NDSBundledSaveMode'] = 'preserve-scratchpad'
        jam['NDSBundledSaveBytes'] = '25600'
        print('[DoJa] FF4A SP layout : preserved byte-for-byte')
        print('[DoJa] FF4A Continue  : bundled state 0..25599 preserved')
        print('[DoJa] FF4A resources : original DEFLATE, ARM native inflater')

    if save_overlay is not None and not save_imported:
        raw = normalized_sp.read_bytes()
        if save_overlay['base_size'] == len(raw) and save_overlay['base_crc'] == _crc32(raw):
            raw = _apply_djsp_overlay(raw, save_overlay, 'prepared/STORED')
            normalized_sp.write_bytes(raw)
            save_imported = True
            jam['NDSImportedSave'] = 'DJSP-prepared'
            jam['NDSImportedSaveChunks'] = str(save_overlay['count'])
        else:
            raise ValueError(
                'Existing DJSP save does not match either the original or prepared ScratchPad. '
                'Expected original size=%d crc=%08X or prepared size=%d crc=%08X, save has size=%d crc=%08X' %
                (len((work / 'scratchpad_payload.bin').read_bytes()), _crc32((work / 'scratchpad_payload.bin').read_bytes()),
                 len(raw), _crc32(raw), save_overlay['base_size'], save_overlay['base_crc']))

    if save_path is None:
        print('[DoJa] Existing save: none (fresh ScratchPad base)')
    class_dir = compile_compat(project, tool_root, work)
    font_bin = work / 'jpfont.bin'
    font_used, glyph_count = generate_font(jar, normalized_sp, font_bin, args.font)
    if glyph_count < 7400:
        raise RuntimeError('Full CP932 font generation failed: only %d glyphs' % glyph_count)
    print('[DoJa] Font      :', font_used)
    print('[DoJa] Font set  : full printable CP932 (compressed-script safe)')
    print('[DoJa] Glyphs    :', glyph_count)
    cp932_bin = work / 'cp932.tbl'
    single_count, double_count, reverse_count = generate_cp932_table(cp932_bin)
    print('[DoJa] Encoding  : SJIS/CP932 default')
    print('[DoJa] CP932 map : single=%d double=%d reverse=%d bytes=%d' % (
        single_count, double_count, reverse_count, cp932_bin.stat().st_size))
    merge_jar(jar, class_dir, font_bin, cp932_bin,
              project / 'embedded' / 'game.jar', app_name, app_class)
    # v59 Empty converts the device-visible ScratchPad to an embedded Nintendo
    # LZ77 stream automatically. The game still sees the original uncompressed
    # bytes after the ARM9 expands it once at boot.
    native_payload = normalized_sp.read_bytes()
    packed_size, wrapper_size, scratchpad_crc32 = write_lz77_scratchpad(
        native_payload, project / 'embedded' / 'doja_scratchpad.lz7b')
    raw_backup = project / 'build_doja' / 'doja_scratchpad.raw'
    raw_backup.write_bytes(native_payload)
    write_prepared_jam(project / 'build_doja' / 'prepared_game.jam', jam, len(native_payload))
    verify_cp932_jar(project / 'embedded' / 'game.jar')
    verify_doja_v46_api(project / 'embedded' / 'game.jar')
    verify_ff4a_field_trace_jar(project / 'embedded' / 'game.jar', app_class)
    verify_ff4a_mainloop_trace_jar(project / 'embedded' / 'game.jar', app_class)
    verify_ff4a_start_trace_jar(project / 'embedded' / 'game.jar', app_class)
    verify_ff4a_performance_jar(project / 'embedded' / 'game.jar', app_class)
    verify_offline_jar(project / 'embedded' / 'game.jar')
    verify_direct_scratchpad_jar(project / 'embedded' / 'game.jar')
    verify_native_inflater_jar(project / 'embedded' / 'game.jar')
    # Keep the inherited native audio object linkable. DoJa audio is intentionally
    # stubbed in this first milestone, so this contains no sample data.
    (project / 'embedded' / 'osnd_native.pcm').write_bytes(b'PPCM\x01\x00\x00\x00')
    install_default_icon(project, project / 'assets' / 'standalone_icon.bmp')
    print('[DoJa] SP CRC32  : %08X' % scratchpad_crc32)
    write_metadata(project, jam, app_name, app_class, app_param, rom_code,
                   output_stem, scratchpad_crc32, len(native_payload),
                   packed_size, wrapper_size, video, corpse_party_compat)
    prepared_marker = write_prepared_marker(project, output_stem, len(native_payload),
                                            packed_size, wrapper_size,
                                            corpse_party_compat)
    print('[DoJa] Port version:', PORT_NAME)
    print('[DoJa] Output ROM  :', output_stem + '.nds')
    print('[DoJa] Marker      :', prepared_marker)
    print('[OK] game.jar: all entries STORED for fast class/resource loading')
    print('[OK] ScratchPad: original game-visible layout + Nintendo LZ77 outer pack')
    print('[OK] Prepared JAM:', project / 'build_doja' / 'prepared_game.jam')
    print('[NEXT] build-doja.bat will call build.bat automatically')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print('[ERROR] javac failed with code', exc.returncode, file=sys.stderr)
        raise SystemExit(exc.returncode)
    except Exception as exc:
        print('[ERROR]', exc, file=sys.stderr)
        raise SystemExit(1)
