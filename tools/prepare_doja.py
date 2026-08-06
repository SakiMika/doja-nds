#!/usr/bin/env python3
"""Prepare an embedded DoJa game for the standalone NDS KVM port."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

from fontgen import generate_font
from cp932gen import generate_cp932_table
from segment_stream_patch import patch_segment_streams, segment_stream_patch_counts

PORT_VERSION = 42
PORT_TAG = "v42"
PORT_NAME = "DoJa NDS Port v42"
PREPARED_MARKER = "prepared_v42.ok"


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
        'DoJa-FF4A-Optimized: ' + ('1' if app_class == 'FF4A' else '0') + '\r\n\r\n'
    ).encode('utf-8')
    with zipfile.ZipFile(original, 'r') as source, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, 9) as dest:
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
        # v42: ScratchPad is linked separately as native ROM data.  Do not put
        # the full ScratchPad payload in the JAR, because KVM inflates whole JAR
        # resources into its heap before ResourceInputStream can read them.
        dest.write(font_bin, 'doja/jpfont.bin')
        dest.write(cp932_bin, 'doja/cp932.tbl')




def verify_ff4a_performance_jar(jar_path: Path, app_class: str) -> None:
    if app_class != 'FF4A':
        return
    with zipfile.ZipFile(jar_path, 'r') as archive:
        payload = archive.read('m.class')
    if _FF4A_PERIODIC_GC in payload or _FF4A_PERIODIC_PHONE in payload:
        raise RuntimeError('FF4A hot-loop patch was not applied')
    if payload.count(_FF4A_PERIODIC_GC_PATCHED) != 1 or \
            payload.count(_FF4A_PERIODIC_PHONE_PATCHED) != 1:
        raise RuntimeError('FF4A hot-loop patch verification is ambiguous')
    print('[DoJa] FF4A optimization: periodic full GC + redundant phone attribute removed')

def verify_doja_v42_api(jar_path: Path) -> None:
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
            raise RuntimeError('Missing v42 DoJa API class: ' + ', '.join(missing))
        paletted = archive.read('com/nttdocomo/ui/PalettedImage.class')
        graphics = archive.read('com/nttdocomo/ui/Graphics.class')
        inflater = archive.read('com/nttdocomo/util/JarInflater.class')
        raw_inflater = archive.read('com/nttdocomo/util/JarInflater$RawInflater.class')
        fast_path = archive.read('nds/doja/FastPath.class')
        fast_blit = archive.read('nds/pstros/video/DoJaFastBlit.class')
        if not all(token in paletted for token in (b'createPalettedImage', b'getPalette', b'setTransparentIndex')):
            raise RuntimeError('PalettedImage.class is stale')
        if not all(token in graphics for token in (b'Graphics3D', b'setFlipMode', b'getPixels', b'setPixels')):
            raise RuntimeError('Graphics.class lacks v42 DoJa image/3D API')
        if not all(token in inflater for token in (b'getInputStream', b'getSize', b'missing zip directory')):
            raise RuntimeError('JarInflater.class is stale')
        if not all(token in raw_inflater for token in (
                b'LENGTH_BASE', b'DIST_BASE', b'inflate', b'FIXED_LITERAL', b'copyMatch')):
            raise RuntimeError('JarInflater raw-DEFLATE engine is stale')
        if not all(token in fast_path for token in (b'present', b'drawImageAlpha', b'drawRegionAlpha')):
            raise RuntimeError('FastPath.class is stale')
        if not all(token in fast_blit for token in (b'Video', b'blit', b'drawImageAlpha')):
            raise RuntimeError('DoJaFastBlit.class is stale')
    print('[DoJa] v42 API verify: FF4A fast bridge + palette/graphics3d/JAR inflater')


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
                raise RuntimeError('Missing v42 SJIS runtime entry: ' + name)
        table = archive.read('doja/cp932.tbl')
        bitmap_font_class = archive.read('nds/doja/font/BitmapJapaneseFont.class')
        if b'isNonPrintingControl' not in bitmap_font_class:
            raise RuntimeError('Missing v42 NUL/control padding font fix')
    if len(table) < 12 or table[:4] != b'DJC2':
        raise RuntimeError('Invalid v42 CP932 mapping resource')
    version, single_count, double_count, reverse_count = struct.unpack_from('>HHHH', table, 4)
    expected = 12 + single_count * 2 + double_count * 2 + reverse_count * 4
    if version != 1 or single_count != 256 or double_count != 11280:
        raise RuntimeError('Unexpected v42 CP932 table dimensions')
    if reverse_count < 9000 or len(table) != expected:
        raise RuntimeError('Truncated v42 CP932 reverse map')
    print('[DoJa] SJIS verify: default=SJIS decode=%d encode=%d table=%d' % (
        single_count + double_count, reverse_count, len(table)))


def verify_offline_jar(jar_path: Path) -> None:
    """Fail preparation unless the final embedded JAR is offline-safe."""
    import hashlib

    with zipfile.ZipFile(jar_path, 'r') as archive:
        names = set(archive.namelist())
        if 'doja/scratchpad.bin' in names:
            raise RuntimeError('v42 game.jar must not contain doja/scratchpad.bin')
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
        raise RuntimeError('Final embedded/game.jar is missing the v42 zero-copy segment patch')



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
    """Verify v42's separate top-level connection and input stream."""
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
            raise RuntimeError('Missing v42 ScratchPad zero-copy classes') from exc

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
        raise RuntimeError('v42 ScratchPad segment-stream verification failed')

def write_metadata(project: Path, jam: dict[str, str], app_name: str, app_class: str,
                   app_param: str, rom_code: str, output_stem: str,
                   scratchpad_crc32: int, scratchpad_size: int,
                   screen_x: int, screen_y: int,
                   corpse_party_compat: bool) -> None:
    props = [
        ('Manifest-Version', '1.0'),
        ('MIDlet-Name', app_name),
        ('MicroEdition-Configuration', jam.get('ConfigurationVer', 'CLDC-1.0')),
        ('MicroEdition-Profile', jam.get('ProfileVer', 'DoJa-3.5')),
        ('DoJa-App-Class', app_class),
        ('DoJa-App-Param', app_param),
        ('DoJa-Port-Version', str(PORT_VERSION)),
        ('DoJa-Compat-Corpse-Party', '1' if corpse_party_compat else '0'),
    ]
    prop_text = ''.join(k + ': ' + v + '\r\n' for k, v in props) + '\r\n'
    internal = re.sub(r'[^A-Za-z0-9]', '', output_stem).upper()[:12] or 'DOJAGAME'
    header = f'''/* Auto-generated by tools/prepare_doja.py. */
#ifndef PSTROS_STANDALONE_GAME_H
#define PSTROS_STANDALONE_GAME_H

#define DOJA_PORT_BUILD_VERSION {PORT_VERSION}
#define DOJA_PORT_VERSION_TEXT "{PORT_TAG}"
#define STANDALONE_APP_NAME "{c_escape(app_name)}"
#define STANDALONE_MAIN_CLASS "{c_escape(app_class)}"
#define DOJA_APP_CLASS "{c_escape(app_class)}"
#define DOJA_APP_PARAM "{c_escape(app_param)}"
#define DOJA_SCREEN_X {screen_x}
#define DOJA_SCREEN_Y {screen_y}
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
#define STANDALONE_SAVE_MODE_TEXT "SAV FILE"
#define DOJA_SCRATCHPAD_SIZE {scratchpad_size}
#define DOJA_SCRATCHPAD_CRC32 0x{scratchpad_crc32:08X}UL
#define DOJA_COMPAT_CORPSE_PARTY {1 if corpse_party_compat else 0}
#define STANDALONE_PROPERTIES_TEXT "{c_escape(prop_text)}"

#endif
'''
    (project / 'include' / 'standalone_game.h').write_text(header, encoding='utf-8', newline='\n')
    mk = f'''# Auto-generated by tools/prepare_doja.py.
TARGET := {output_stem}
TEXT1 := {app_name}
TEXT2 := {PORT_NAME}
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


def write_prepared_marker(project: Path, output_stem: str, scratchpad_size: int, corpse_party_compat: bool) -> Path:
    marker = project / 'build_doja' / PREPARED_MARKER
    payload = {
        'port_version': PORT_VERSION,
        'port_tag': PORT_TAG,
        'output_stem': output_stem,
        'scratchpad_size': scratchpad_size,
        'corpse_party_compat': corpse_party_compat,
        'game_jar_sha256': sha256_file(project / 'embedded' / 'game.jar'),
        'scratchpad_sha256': sha256_file(project / 'embedded' / 'doja_scratchpad.bin'),
        'default_icon_sha256': sha256_file(project / 'assets' / 'default_standalone_icon.bmp'),
        'generated_icon_sha256': sha256_file(project / 'assets' / 'standalone_icon.bmp'),
        'metadata_sha256': sha256_file(project / 'standalone_game.mk'),
        'header_sha256': sha256_file(project / 'include' / 'standalone_game.h'),
        'protocol_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'Protocol.java'),
        'output_stream_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'ScratchpadOutputStream.java'),
        'input_stream_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'ScratchpadInputStream.java'),
        'segment_token_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'SegmentToken.java'),
        'segment_stream_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'ScratchpadByteArrayInputStream.java'),
        'segment_patcher_sha256': sha256_file(project / 'tools' / 'segment_stream_patch.py'),
        'native_source_sha256': sha256_file(project / 'kvm' / 'VmCommon' / 'src' / 'native.c'),
        'native_table_source_sha256': sha256_file(project / 'kvm' / 'VmSkel' / 'src' / 'nativeFunctionTableGBA.c'),
        'resource_source_sha256': sha256_file(project / 'kvm' / 'VmExtra' / 'src' / 'resource.c'),
        'nds_main_source_sha256': sha256_file(project / 'kvm' / 'VmSkel' / 'src' / 'nds_main.c'),
        'nds_file_source_sha256': sha256_file(project / 'kvm' / 'VmSkel' / 'src' / 'Java_nds_File.c'),
        'nds_runtime_source_sha256': sha256_file(project / 'kvm' / 'VmSkel' / 'src' / 'nds_runtime.c'),
        'video_source_sha256': sha256_file(project / 'kvm' / 'VmSkel' / 'src' / 'Java_nds_Video.c'),
        'machine_md_source_sha256': sha256_file(project / 'kvm' / 'VmSkel' / 'h' / 'machine_md.h'),
        'collector_source_sha256': sha256_file(project / 'kvm' / 'VmCommon' / 'src' / 'collector.c'),
        'doja_canvas_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Canvas.java'),
        'doja_graphics_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Graphics.java'),
        'doja_image_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Image.java'),
        'doja_palette_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Palette.java'),
        'doja_paletted_image_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'PalettedImage.java'),
        'doja_indexed_gif_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'image' / 'IndexedGifDecoder.java'),
        'doja_jar_inflater_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'util' / 'JarInflater.java'),
        'doja_graphics3d_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'graphics3d' / 'Graphics3D.java'),
        'doja_primitive_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'graphics3d' / 'Primitive.java'),
        'doja_transform_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'util3d' / 'Transform.java'),
        'doja_mainapp_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'MainApp.java'),
        'config_stub_sha256': sha256_file(project / 'tools' / 'compile_stubs' / 'nds' / 'pstros' / 'ConfigData.java'),
        'fontgen_source_sha256': sha256_file(project / 'tools' / 'fontgen.py'),
        'bitmap_font_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'font' / 'BitmapJapaneseFont.java'),
        'fast_path_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'FastPath.java'),
        'fast_blit_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'nds' / 'pstros' / 'video' / 'DoJaFastBlit.java'),
        'property_source_sha256': sha256_file(project / 'kvm' / 'VmCommon' / 'src' / 'property.c'),
        'cp932gen_source_sha256': sha256_file(project / 'tools' / 'cp932gen.py'),
        'cp932_codec_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'encoding' / 'Cp932Codec.java'),
        'sjis_reader_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'i18n' / 'j2me' / 'SJIS_Reader.java'),
        'sjis_writer_source_sha256': sha256_file(project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'i18n' / 'j2me' / 'SJIS_Writer.java'),
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
    parser.add_argument('--screen-x', type=int, default=8)
    parser.add_argument('--screen-y', type=int, default=-24)
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
    if not -256 <= args.screen_x <= 256 or not -256 <= args.screen_y <= 256:
        raise ValueError('Screen offsets must be between -256 and 256.')

    rom_code = re.sub(r'[^A-Za-z0-9]', '', args.rom_code).upper()
    if len(rom_code) != 4:
        raise ValueError('ROM code must contain exactly four letters/numbers.')

    jam = parse_jam(jam_path)
    app_class = jam.get('AppClass', 'Main').strip() or 'Main'
    app_param = jam.get('AppParam', '0').strip() or '0'
    app_name = (args.name or jar.stem).strip()
    output_stem = safe_stem(app_name) + '_doja_v42'
    corpse_party_compat = detect_corpse_party_compat(jar)
    work = project / 'build_doja'
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    for generated in (
        project / 'embedded' / 'game.jar',
        project / 'embedded' / 'doja_scratchpad.bin',
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
    print('[DoJa] Viewport  : native 240x240 at X=%d Y=%d (no fit)' % (args.screen_x, args.screen_y))
    print('[DoJa] Compat    :', 'FF4A exact-signature performance build' if app_class == 'FF4A' else ('Corpse Party exact-signature patch' if corpse_party_compat else 'generic game'))
    normalized_sp, _sp_mode = normalize_scratchpad(sp, jam, work / 'scratchpad_payload.bin')
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
    # Keep two copies of the normalized ScratchPad.  The embedded copy is linked
    # into ARM9.  The build_doja backup is deliberately outside the Makefile
    # build directory and lets build.bat/make restore the asset if the user
    # overlays a new source package or a cleanup tool removes embedded output.
    native_payload = normalized_sp.read_bytes()
    native_sp = project / 'embedded' / 'doja_scratchpad.bin'
    native_sp.parent.mkdir(parents=True, exist_ok=True)
    native_sp.write_bytes(native_payload)
    native_sp_backup = project / 'build_doja' / 'doja_scratchpad.bin'
    native_sp_backup.write_bytes(native_payload)
    if native_sp.stat().st_size != len(native_payload):
        raise RuntimeError('Native ScratchPad write verification failed')
    if native_sp_backup.stat().st_size != len(native_payload):
        raise RuntimeError('Native ScratchPad backup verification failed')
    print('[DoJa] Native SP :', native_sp, native_sp.stat().st_size, 'bytes')
    print('[DoJa] Native SP backup:', native_sp_backup, native_sp_backup.stat().st_size, 'bytes')
    verify_cp932_jar(project / 'embedded' / 'game.jar')
    verify_doja_v42_api(project / 'embedded' / 'game.jar')
    verify_ff4a_performance_jar(project / 'embedded' / 'game.jar', app_class)
    verify_offline_jar(project / 'embedded' / 'game.jar')
    verify_direct_scratchpad_jar(project / 'embedded' / 'game.jar')
    # Keep the inherited native audio object linkable. DoJa audio is intentionally
    # stubbed in this first milestone, so this contains no sample data.
    (project / 'embedded' / 'osnd_native.pcm').write_bytes(b'PPCM\x01\x00\x00\x00')
    install_default_icon(project, project / 'assets' / 'standalone_icon.bmp')
    import zlib
    scratchpad_crc32 = zlib.crc32(native_payload) & 0xFFFFFFFF
    print('[DoJa] SP CRC32  : %08X' % scratchpad_crc32)
    write_metadata(project, jam, app_name, app_class, app_param, rom_code,
                   output_stem, scratchpad_crc32, len(native_payload),
                   args.screen_x, args.screen_y, corpse_party_compat)
    prepared_marker = write_prepared_marker(project, output_stem, len(native_payload), corpse_party_compat)
    print('[DoJa] Port version:', PORT_NAME)
    print('[DoJa] Output ROM  :', output_stem + '.nds')
    print('[DoJa] Marker      :', prepared_marker)
    print('[OK] Prepared embedded/game.jar')
    print('[OK] Prepared embedded/doja_scratchpad.bin (v42 same-name SAV file + legacy DJS import + default icon + full CP932/SJIS + Latin fix + native viewport/no fit + generic game metadata + input + zero-copy + DS 2432 KiB / DSi 8192 KiB heap)')
    print('[OK] Prepared build_doja/doja_scratchpad.bin (automatic restore backup)')
    print('[NEXT] Run build.bat')
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
