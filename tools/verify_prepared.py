#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import struct
import zipfile
from pathlib import Path

from segment_stream_patch import segment_stream_patch_counts

PORT_VERSION = 25
MARKER_NAME = 'prepared_v25.ok'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()



def class_super_name(data: bytes) -> str:
    if len(data) < 10 or data[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("invalid class")
    cp_count = struct.unpack_from(">H", data, 8)[0]
    cp = [None] * cp_count
    offset = 10
    index = 1
    while index < cp_count:
        tag = data[offset]
        offset += 1
        if tag == 1:
            length = struct.unpack_from(">H", data, offset)[0]
            offset += 2
            cp[index] = data[offset:offset + length].decode("latin-1")
            offset += length
        elif tag in (3, 4):
            offset += 4
        elif tag in (5, 6):
            offset += 8
            index += 1
        elif tag in (7, 8, 16):
            cp[index] = struct.unpack_from(">H", data, offset)[0]
            offset += 2
        elif tag in (9, 10, 11, 12, 18):
            offset += 4
        elif tag == 15:
            offset += 3
        else:
            raise ValueError("unsupported constant pool tag %d" % tag)
        index += 1
    _access, _this_index, super_index = struct.unpack_from(">HHH", data, offset)
    if super_index == 0:
        return ""
    name_index = cp[super_index]
    if not isinstance(name_index, int) or not isinstance(cp[name_index], str):
        raise ValueError("invalid superclass")
    return cp[name_index]

def fail(message: str) -> int:
    print('[ERROR]', message)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default='.')
    args = parser.parse_args()
    project = Path(args.project).resolve()
    marker_path = project / 'build_doja' / MARKER_NAME
    if not marker_path.is_file():
        return fail('Missing v25 preparation marker. Run build_doja.bat.')
    try:
        marker = json.loads(marker_path.read_text(encoding='utf-8'))
    except Exception as exc:
        return fail('Invalid preparation marker: ' + str(exc))
    if marker.get('port_version') != PORT_VERSION or marker.get('port_tag') != 'v25':
        return fail('Preparation marker is not for v25.')
    output_stem = marker.get('output_stem', '')
    if not output_stem.endswith('_doja_v25'):
        return fail('Output name is stale: ' + repr(output_stem))
    checks = {
        'game_jar_sha256': project / 'embedded' / 'game.jar',
        'scratchpad_sha256': project / 'embedded' / 'doja_scratchpad.bin',
        'default_icon_sha256': project / 'assets' / 'default_standalone_icon.bmp',
        'generated_icon_sha256': project / 'assets' / 'standalone_icon.bmp',
        'metadata_sha256': project / 'standalone_game.mk',
        'header_sha256': project / 'include' / 'standalone_game.h',
        'protocol_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'Protocol.java',
        'output_stream_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'ScratchpadOutputStream.java',
        'input_stream_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'ScratchpadInputStream.java',
        'segment_token_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'SegmentToken.java',
        'segment_stream_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'ScratchpadByteArrayInputStream.java',
        'segment_patcher_sha256': project / 'tools' / 'segment_stream_patch.py',
        'native_source_sha256': project / 'kvm' / 'VmCommon' / 'src' / 'native.c',
        'native_table_source_sha256': project / 'kvm' / 'VmSkel' / 'src' / 'nativeFunctionTableGBA.c',
        'resource_source_sha256': project / 'kvm' / 'VmExtra' / 'src' / 'resource.c',
        'nds_main_source_sha256': project / 'kvm' / 'VmSkel' / 'src' / 'nds_main.c',
        'nds_runtime_source_sha256': project / 'kvm' / 'VmSkel' / 'src' / 'nds_runtime.c',
        'machine_md_source_sha256': project / 'kvm' / 'VmSkel' / 'h' / 'machine_md.h',
        'collector_source_sha256': project / 'kvm' / 'VmCommon' / 'src' / 'collector.c',
        'doja_canvas_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Canvas.java',
        'doja_mainapp_source_sha256': project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'MainApp.java',
        'config_stub_sha256': project / 'tools' / 'compile_stubs' / 'nds' / 'pstros' / 'ConfigData.java',
        'fontgen_source_sha256': project / 'tools' / 'fontgen.py',
        'bitmap_font_source_sha256': project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'font' / 'BitmapJapaneseFont.java',
        'property_source_sha256': project / 'kvm' / 'VmCommon' / 'src' / 'property.c',
        'cp932gen_source_sha256': project / 'tools' / 'cp932gen.py',
        'cp932_codec_source_sha256': project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'encoding' / 'Cp932Codec.java',
        'sjis_reader_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'i18n' / 'j2me' / 'SJIS_Reader.java',
        'sjis_writer_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'i18n' / 'j2me' / 'SJIS_Writer.java',
    }
    for key, path in checks.items():
        if not path.is_file():
            return fail('Missing prepared file: ' + str(path.relative_to(project)))
        actual = sha256_file(path)
        if actual != marker.get(key):
            return fail('Prepared file changed after verification: ' + str(path.relative_to(project)))
    if (project / 'embedded' / 'doja_scratchpad.bin').stat().st_size != 409600:
        return fail('ScratchPad is not exactly 409600 bytes.')
    mk = (project / 'standalone_game.mk').read_text(encoding='utf-8')
    header = (project / 'include' / 'standalone_game.h').read_text(encoding='utf-8')
    if 'TARGET := ' + output_stem not in mk or 'TEXT2 := DoJa NDS Port v25' not in mk:
        return fail('standalone_game.mk is not v25.')
    if '#define DOJA_PORT_BUILD_VERSION 25' not in header:
        return fail('standalone_game.h is not v25.')
    if ('.djs"' not in header or 'STANDALONE_RMS_SAVE_PATH' not in header
            or 'STANDALONE_LEGACY_SAVE_PATH' not in header
            or 'STANDALONE_SHORT_SAVE_PATH' not in header):
        return fail('v25 dedicated save-path metadata is missing.')
    with zipfile.ZipFile(project / 'embedded' / 'game.jar', 'r') as archive:
        manifest = archive.read('META-INF/MANIFEST.MF')
        names = set(archive.namelist())
        if b'DoJa-Port-Version: 25' not in manifest:
            return fail('game.jar manifest is not v25.')
        if 'doja/scratchpad.bin' in names:
            return fail('game.jar still contains legacy ScratchPad resource.')
        try:
            protocol = archive.read('com/sun/cldc/io/j2me/scratchpad/Protocol.class')
            output_stream = archive.read(
                'com/sun/cldc/io/j2me/scratchpad/ScratchpadOutputStream.class')
            input_stream = archive.read(
                'com/sun/cldc/io/j2me/scratchpad/ScratchpadInputStream.class')
            segment_token = archive.read(
                'com/sun/cldc/io/j2me/scratchpad/SegmentToken.class')
            segment_stream = archive.read(
                'com/sun/cldc/io/j2me/scratchpad/ScratchpadByteArrayInputStream.class')
            game_j = archive.read('j.class')
            http = archive.read('com/sun/cldc/io/j2me/http/Protocol.class')
            jpfont = archive.read('doja/jpfont.bin')
            cp932table = archive.read('doja/cp932.tbl')
            cp932codec = archive.read('nds/doja/encoding/Cp932Codec.class')
            bitmap_font_class = archive.read('nds/doja/font/BitmapJapaneseFont.class')
            sjis_reader = archive.read('com/sun/cldc/i18n/j2me/SJIS_Reader.class')
            sjis_writer = archive.read('com/sun/cldc/i18n/j2me/SJIS_Writer.class')
        except KeyError as exc:
            return fail('Missing v25 runtime class/resource: ' + str(exc))
        if len(jpfont) < 12 or jpfont[:4] != b'DJF1':
            return fail('Japanese font resource is missing or invalid.')
        font_width, font_height, glyph_count, bytes_per_glyph = struct.unpack('>HHHH', jpfont[4:12])
        expected_font_size = 12 + glyph_count * (2 + bytes_per_glyph)
        if font_width != 12 or font_height != 12 or bytes_per_glyph != 18:
            return fail('Japanese font geometry is stale.')
        if glyph_count < 7400 or len(jpfont) != expected_font_size:
            return fail('Full CP932 font is incomplete: glyphs=%d bytes=%d expected=%d' % (
                glyph_count, len(jpfont), expected_font_size))
        if len(cp932table) < 12 or cp932table[:4] != b'DJC2':
            return fail('CP932 mapping resource is missing or invalid.')
        table_version, single_count, double_count, reverse_count = struct.unpack_from('>HHHH', cp932table, 4)
        expected_cp932_size = 12 + single_count * 2 + double_count * 2 + reverse_count * 4
        if (table_version != 1 or single_count != 256 or double_count != 11280
                or reverse_count < 9000 or len(cp932table) != expected_cp932_size):
            return fail('CP932 table is incomplete: single=%d double=%d reverse=%d bytes=%d expected=%d' % (
                single_count, double_count, reverse_count, len(cp932table), expected_cp932_size))
        if b'normalizeForDisplay' not in cp932codec or b'doja/cp932.tbl' not in cp932codec:
            return fail('Cp932Codec.class is stale.')
        if b'Cp932Codec' not in sjis_reader or b'Cp932Codec' not in sjis_writer:
            return fail('SJIS reader/writer classes are stale.')
        scratchpad_classes = [
            name for name in names
            if name.startswith('com/sun/cldc/io/j2me/scratchpad/')
            and name.endswith('.class')]
        if any('$' in name for name in scratchpad_classes):
            return fail('Nested ScratchPad classes are forbidden in v25.')
        if b'doja/scratchpad.bin' in protocol or b'ResourceInputStream' in protocol:
            return fail('ScratchPad Protocol.class is stale.')
        if b'nativeFlush' not in output_stream:
            return fail('ScratchpadOutputStream.class does not flush persistent saves.')
        if b'doja/scratchpad.bin' in input_stream or b'ResourceInputStream' in input_stream:
            return fail('ScratchpadInputStream.class is stale.')
        if b'doja/scratchpad.bin' in http or b'ResourceInputStream' in http:
            return fail('HTTP Protocol.class is stale.')
        required = (b'nativeSize', b'nativeRead', b'nativeReadBytes',
                    b'nativeWrite', b'nativeWriteBytes', b'nativeFlush', b'openRange',
                    b'ScratchpadInputStream', b'sizeUnchecked')
        if not all(token in protocol for token in required):
            return fail('v25 separate-stream ScratchPad methods are missing.')
        if b'com/sun/cldc/io/j2me/scratchpad/Protocol' not in http:
            return fail('HTTP fallback does not use the native ScratchPad Protocol.')
        try:
            if class_super_name(protocol) != 'java/lang/Object':
                return fail('Protocol must be a Connection, not the returned InputStream.')
            if class_super_name(input_stream) != 'java/io/InputStream':
                return fail('ScratchpadInputStream must extend java.io.InputStream.')
            if class_super_name(segment_stream) != 'java/io/ByteArrayInputStream':
                return fail('ScratchpadByteArrayInputStream must preserve the old verifier type.')
        except ValueError as exc:
            return fail('Could not validate ScratchPad class hierarchy: ' + str(exc))
        if b'SegmentToken' not in segment_token or b'open' not in segment_token:
            return fail('SegmentToken.class is missing the tiny-token bridge.')
        if (b'nativeReadBytes' not in segment_stream or
                b'ScratchpadByteArrayInputStream' not in segment_stream):
            return fail('ScratchpadByteArrayInputStream.class is stale.')
        patched_count, legacy_count = segment_stream_patch_counts(game_j)
        if patched_count != 13 or legacy_count != 0:
            return fail('j.class segment stream patch mismatch: patched=%d legacy=%d' % (
                patched_count, legacy_count))
    protocol_source = (project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'Protocol.java').read_text(encoding='utf-8')
    output_source = (project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'ScratchpadOutputStream.java').read_text(encoding='utf-8')
    input_source = (project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'ScratchpadInputStream.java').read_text(encoding='utf-8')
    token_source = (project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'SegmentToken.java').read_text(encoding='utf-8')
    segment_source = (project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'io' / 'j2me' / 'scratchpad' / 'ScratchpadByteArrayInputStream.java').read_text(encoding='utf-8')
    nds_main_source = (project / 'kvm' / 'VmSkel' / 'src' / 'nds_main.c').read_text(encoding='latin-1')
    nds_runtime_source = (project / 'kvm' / 'VmSkel' / 'src' / 'nds_runtime.c').read_text(encoding='latin-1')
    machine_md_source = (project / 'kvm' / 'VmSkel' / 'h' / 'machine_md.h').read_text(encoding='latin-1')
    collector_source = (project / 'kvm' / 'VmCommon' / 'src' / 'collector.c').read_text(encoding='latin-1')
    nds_file_source = (project / 'kvm' / 'VmSkel' / 'src' / 'Java_nds_File.c').read_text(encoding='latin-1')
    if 'extends InputStream' in protocol_source:
        return fail('Protocol source still doubles as InputStream.')
    if 'return new ScratchpadInputStream' not in protocol_source:
        return fail('Protocol source does not return a separate input stream.')
    if 'Protocol.nativeFlush()' not in output_source:
        return fail('ScratchpadOutputStream does not flush persistent saves on close.')
    if 'final class ScratchpadInputStream extends InputStream' not in input_source:
        return fail('Top-level ScratchpadInputStream source is missing or stale.')
    if 'public static byte[] open(int segmentIndex)' not in token_source:
        return fail('SegmentToken source is missing the one-byte loader token.')
    if 'extends ByteArrayInputStream' not in segment_source or 'nativeReadBytes' not in segment_source:
        return fail('ScratchpadByteArrayInputStream source is missing the direct ROM stream.')
    if ('DOJA_PORT_BUILD_VERSION != 25' not in nds_main_source
            or 'SAVE: READY' not in nds_main_source
            or 'pstrosSetVmConsoleEnabled(0)' not in nds_main_source):
        return fail('NDS entry point is not the v25 compact save-status build.')
    if ('pstrosMountSaveStorageDirect()' not in nds_main_source or
            'dojaSpPersistenceInit' not in nds_main_source or
            'if (fatInitDefault())' in nds_main_source):
        return fail('NDS entry point is not using the boot-safe direct DLDI save mount.')
    if '#define DEFAULTHEAPSIZE (2432*1024)' not in machine_md_source:
        return fail('Java heap is not fixed at 2432 KiB for v25.')
    if 'DoJa v25 heap allocated:' not in nds_runtime_source:
        return fail('v25 heap allocation diagnostics are missing.')
    if 'KVM HEAP OOM req=' not in collector_source:
        return fail('Heap fragmentation diagnostics are missing.')
    direct_mount_tokens = (
        'int pstrosMountSaveStorageDirect(void)',
        'dldiGetInternal == NULL',
        'fatMountSimple("fat", interface)',
        'STANDALONE_SHORT_SAVE_PATH',
        'Do not call fatInitDefault()/fatInit()',
    )
    if not all(token in nds_file_source for token in direct_mount_tokens):
        return fail('Direct DLDI save mount backend is missing or stale.')
    if '"sd:/" STANDALONE_OUTPUT_BASENAME' in nds_file_source or '"sdmc:/"' in nds_file_source:
        return fail('Unsafe multi-device save probing is still enabled.')

    doja_canvas_source = (project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Canvas.java').read_text(encoding='utf-8')
    doja_mainapp_source = (project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'MainApp.java').read_text(encoding='utf-8')
    input_tokens = (
        'ConfigData.configActive = false',
        'case -1: return KEY_UP',
        'case -2: return KEY_DOWN',
        'case -3: return KEY_LEFT',
        'case -4: return KEY_RIGHT',
        'case -5: return KEY_SELECT',
        'case -6: return KEY_SOFT1',
        'case -7: return KEY_SOFT2',
    )
    if input_tokens[0] not in doja_mainapp_source or not all(token in doja_canvas_source for token in input_tokens[1:]):
        return fail('DoJa v25 input mapping fix is missing or stale.')
    key_source = (project / 'kvm' / 'VmSkel' / 'src' / 'Java_nds_Key.c').read_text(encoding='utf-8')
    if 'POLL n=' in key_source or 'RAW n=' in key_source:
        return fail('Temporary input diagnostics are still enabled.')

    native_source = (project / 'kvm' / 'VmCommon' / 'src' / 'native.c').read_text(encoding='latin-1')
    late_tokens = (
        '#define DOJA_LATE_NATIVE_BIND 1',
        'getDoJaLateNativeFunction(clazz, methodName, methodSignature)',
        'Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeSize',
        'Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeReadBytes',
        'Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeWriteBytes',
        'Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeFlush',
        '(I[BII)I',
        '(I[BII)V',
    )
    if not all(token in native_source for token in late_tokens):
        return fail('ROMIZING late-native ScratchPad bridge is missing or stale.')
    late_call = native_source.find('getDoJaLateNativeFunction(clazz, methodName, methodSignature)')
    rom_guard = native_source.find('#if !ROMIZING', late_call)
    if late_call < 0 or rom_guard < 0 or late_call > rom_guard:
        return fail('Late-native binding must execute before the !ROMIZING table guard.')

    fontgen_source = (project / 'tools' / 'fontgen.py').read_text(encoding='utf-8')
    bitmap_font_source = (project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'font' / 'BitmapJapaneseFont.java').read_text(encoding='utf-8')
    if 'def full_cp932_repertoire()' not in fontgen_source or 'chars.update(full_cp932_repertoire())' not in fontgen_source:
        return fail('Full CP932 font generator is missing or stale.')
    if 'FONT MISS U+' not in bitmap_font_source or "find('〓')" not in bitmap_font_source:
        return fail('Japanese font fallback diagnostics are missing or stale.')
    if 'Cp932Codec.normalizeForDisplay' not in bitmap_font_source:
        return fail('Bitmap font is not using the SJIS display fallback.')
    nul_padding_tokens = (
        'isNonPrintingControl',
        'return c < 0x0020 || c == 0x007F',
        'nul-padding-skip',
    )
    if not all(token in bitmap_font_source for token in nul_padding_tokens):
        return fail('v25 NUL/control padding font fix is missing or stale.')
    if (b'isNonPrintingControl' not in bitmap_font_class
            or b'nul-padding-skip' not in bitmap_font_class):
        return fail('Compiled BitmapJapaneseFont.class lacks the v25 padding fix.')

    property_source = (project / 'kvm' / 'VmCommon' / 'src' / 'property.c').read_text(encoding='latin-1')
    cp932_codec_source = (project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'encoding' / 'Cp932Codec.java').read_text(encoding='utf-8')
    sjis_reader_source = (project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'i18n' / 'j2me' / 'SJIS_Reader.java').read_text(encoding='utf-8')
    sjis_writer_source = (project / 'doja_port' / 'doja_src' / 'com' / 'sun' / 'cldc' / 'i18n' / 'j2me' / 'SJIS_Writer.java').read_text(encoding='utf-8')
    if 'value = "SJIS";' not in property_source:
        return fail('microedition.encoding is not SJIS.')
    if 'doja/cp932.tbl' not in cp932_codec_source or 'normalizeForDisplay' not in cp932_codec_source:
        return fail('CP932 codec source is missing or stale.')
    if 'extends StreamReader' not in sjis_reader_source or 'extends StreamWriter' not in sjis_writer_source:
        return fail('SJIS reader/writer source is missing or stale.')

    resource_source = (project / 'kvm' / 'VmExtra' / 'src' / 'resource.c').read_text(encoding='latin-1')
    save_tokens = (
        'DoJa v25 ScratchPad ROM access with persistent sparse saves',
        'dojaSpPersistenceInit',
        'dojaSpPersistenceFlush',
        'dojaSpEnsurePersistence',
        'dojaSpDetectSlot',
        'DOJA_CP_SLOT_BASE 5',
        'DOJA_CP_SLOT_SIZE 1563',
        'DOJA_CP_SLOT_COUNT 3',
        'DOJA_SP_SAVE_HEADER_SIZE 28',
        'DOJA_SCRATCHPAD_CRC32',
        'Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeFlush',
        'dojaSaveUiSaving',
        'dojaSaveUiResult',
        'dojaSpValidateFile',
        'dojaSpCopyFile',
        'memcpy(dojaSpTempPath + length - 4, ".TMP", 5)',
        'dojaSpWriteOverlayFile',
    )
    if not all(token in resource_source for token in save_tokens):
        return fail('v25 direct-DLDI persistent ScratchPad backend is missing or stale.')
    icon = project / 'assets' / 'default_standalone_icon.bmp'
    icon_data = icon.read_bytes()
    if len(icon_data) < 70 or icon_data[:2] != b'BM':
        return fail('Bundled default icon is invalid.')
    generated_icon_data = (project / 'assets' / 'standalone_icon.bmp').read_bytes()
    if generated_icon_data != icon_data:
        return fail('Generated icon does not match the bundled default icon.')
    if struct.unpack_from('<I', icon_data, 18)[0] != 32 or struct.unpack_from('<I', icon_data, 22)[0] != 32 or struct.unpack_from('<H', icon_data, 28)[0] != 4:
        return fail('Bundled default icon must be 32x32 4bpp.')

    loader = (project / 'kvm' / 'VmExtra' / 'src' / 'loaderFile.c').read_bytes()
    if b'doja/scratchpad.bin' in loader:
        return fail('Native source still contains the legacy ScratchPad resource bridge.')
    print('[OK] DoJa v25 preparation verified')
    print('[OK] Output ROM:', output_stem + '.nds')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
