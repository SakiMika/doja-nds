#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import struct
import zipfile
from pathlib import Path

from segment_stream_patch import segment_stream_patch_counts

PORT_VERSION = 41
MARKER_NAME = 'prepared_v41.ok'


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
    version_header_path = project / 'include' / 'doja_port_version.h'
    if not version_header_path.is_file():
        return fail('Missing source version header.')
    version_header = version_header_path.read_text(encoding='ascii')
    if ('#define DOJA_SOURCE_PORT_VERSION %d' % PORT_VERSION) not in version_header:
        return fail('Source version header does not match verifier.')
    if ('#define DOJA_SOURCE_PORT_TAG "v%d"' % PORT_VERSION) not in version_header:
        return fail('Source version tag does not match verifier.')
    marker_path = project / 'build_doja' / MARKER_NAME
    if not marker_path.is_file():
        return fail('Missing v41 preparation marker. Run build_doja.bat.')
    try:
        marker = json.loads(marker_path.read_text(encoding='utf-8'))
    except Exception as exc:
        return fail('Invalid preparation marker: ' + str(exc))
    if marker.get('port_version') != PORT_VERSION or marker.get('port_tag') != 'v41':
        return fail('Preparation marker is not for v41.')
    output_stem = marker.get('output_stem', '')
    if not output_stem.endswith('_doja_v41'):
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
        'video_source_sha256': project / 'kvm' / 'VmSkel' / 'src' / 'Java_nds_Video.c',
        'machine_md_source_sha256': project / 'kvm' / 'VmSkel' / 'h' / 'machine_md.h',
        'collector_source_sha256': project / 'kvm' / 'VmCommon' / 'src' / 'collector.c',
        'doja_canvas_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Canvas.java',
        'doja_graphics_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Graphics.java',
        'doja_image_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Image.java',
        'doja_palette_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Palette.java',
        'doja_paletted_image_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'PalettedImage.java',
        'doja_indexed_gif_source_sha256': project / 'doja_port' / 'doja_src' / 'nds' / 'doja' / 'image' / 'IndexedGifDecoder.java',
        'doja_jar_inflater_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'util' / 'JarInflater.java',
        'doja_graphics3d_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'graphics3d' / 'Graphics3D.java',
        'doja_primitive_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'graphics3d' / 'Primitive.java',
        'doja_transform_source_sha256': project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'util3d' / 'Transform.java',
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
    scratchpad_path = project / 'embedded' / 'doja_scratchpad.bin'
    scratchpad_size = scratchpad_path.stat().st_size
    if scratchpad_size <= 0:
        return fail('ScratchPad is empty.')
    if marker.get('scratchpad_size') != scratchpad_size:
        return fail('ScratchPad size does not match the preparation marker.')
    mk = (project / 'standalone_game.mk').read_text(encoding='utf-8')
    header = (project / 'include' / 'standalone_game.h').read_text(encoding='utf-8')
    if 'TARGET := ' + output_stem not in mk or 'TEXT2 := DoJa NDS Port v41' not in mk:
        return fail('standalone_game.mk is not v41.')
    if '#define DOJA_PORT_BUILD_VERSION 41' not in header:
        return fail('standalone_game.h is not v41.')
    size_match = re.search(r'^#define DOJA_SCRATCHPAD_SIZE (\d+)\s*$', header, re.M)
    if not size_match or int(size_match.group(1)) != scratchpad_size:
        return fail('Generated ScratchPad size metadata is missing or stale.')
    if (not re.search(r'^#define DOJA_SCREEN_X -?\d+\s*$', header, re.M)
            or not re.search(r'^#define DOJA_SCREEN_Y -?\d+\s*$', header, re.M)
            or '.sav"' not in header or 'STANDALONE_RMS_SAVE_PATH' not in header
            or 'STANDALONE_LEGACY_SAVE_PATH' not in header
            or 'STANDALONE_SHORT_SAVE_PATH' not in header
            or 'STANDALONE_SAVE_MODE_TEXT "SAV FILE"' not in header
            or '#define DOJA_COMPAT_CORPSE_PARTY ' not in header):
        return fail('v41 game-independent display/save metadata is missing.')
    with zipfile.ZipFile(project / 'embedded' / 'game.jar', 'r') as archive:
        manifest = archive.read('META-INF/MANIFEST.MF')
        names = set(archive.namelist())
        expected_manifest_version = ('DoJa-Port-Version: %d\r\n' % PORT_VERSION).encode('ascii')
        if expected_manifest_version not in manifest:
            return fail('game.jar manifest version mismatch; expected %d.' % PORT_VERSION)
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
            http = archive.read('com/sun/cldc/io/j2me/http/Protocol.class')
            jpfont = archive.read('doja/jpfont.bin')
            cp932table = archive.read('doja/cp932.tbl')
            cp932codec = archive.read('nds/doja/encoding/Cp932Codec.class')
            bitmap_font_class = archive.read('nds/doja/font/BitmapJapaneseFont.class')
            sjis_reader = archive.read('com/sun/cldc/i18n/j2me/SJIS_Reader.class')
            sjis_writer = archive.read('com/sun/cldc/i18n/j2me/SJIS_Writer.class')
            doja_palette = archive.read('com/nttdocomo/ui/Palette.class')
            doja_paletted = archive.read('com/nttdocomo/ui/PalettedImage.class')
            doja_graphics = archive.read('com/nttdocomo/ui/Graphics.class')
            doja_graphics3d = archive.read('com/nttdocomo/ui/graphics3d/Graphics3D.class')
            doja_object3d = archive.read('com/nttdocomo/ui/graphics3d/Object3D.class')
            doja_drawable3d = archive.read('com/nttdocomo/ui/graphics3d/DrawableObject3D.class')
            doja_primitive = archive.read('com/nttdocomo/ui/graphics3d/Primitive.class')
            doja_texture = archive.read('com/nttdocomo/ui/graphics3d/Texture.class')
            doja_fog = archive.read('com/nttdocomo/ui/graphics3d/Fog.class')
            doja_fastmath = archive.read('com/nttdocomo/ui/util3d/FastMath.class')
            doja_transform = archive.read('com/nttdocomo/ui/util3d/Transform.class')
            doja_vector = archive.read('com/nttdocomo/ui/util3d/Vector3D.class')
            doja_inflater = archive.read('com/nttdocomo/util/JarInflater.class')
            doja_raw_inflater = archive.read('com/nttdocomo/util/JarInflater$RawInflater.class')
            archive.read('com/nttdocomo/util/JarInflater$BitReader.class')
            archive.read('com/nttdocomo/util/JarInflater$Huffman.class')
            archive.read('nds/doja/image/IndexedGifDecoder.class')
        except KeyError as exc:
            return fail('Missing v41 runtime class/resource: ' + str(exc))
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
        if not all(token in doja_paletted for token in (b'createPalettedImage', b'getPalette', b'setTransparentIndex')):
            return fail('PalettedImage.class is stale or incomplete.')
        if b'setEntry' not in doja_palette:
            return fail('Palette.class is stale.')
        if not all(token in doja_graphics for token in (b'Graphics3D', b'setFlipMode', b'getPixels', b'setPixels')):
            return fail('Graphics.class lacks the v41 image/3D API.')
        if not all(token in doja_graphics3d for token in (b'renderObject3D', b'setPerspectiveView', b'setTransform')):
            return fail('Graphics3D.class is stale.')
        if not all(token in doja_primitive for token in (b'getVertexArray', b'getTextureCoordArray', b'setTexture')):
            return fail('Primitive.class is stale.')
        if not all(token in doja_transform for token in (b'lookAt', b'rotate', b'setIdentity')):
            return fail('Transform.class is stale.')
        if not all(token in doja_vector for token in (b'normalize', b'cross')) or b'sqrt' not in doja_fastmath:
            return fail('DoJa util3d classes are stale.')
        if not all(token in doja_inflater for token in (b'getInputStream', b'getSize', b'missing zip directory')):
            return fail('JarInflater.class is stale.')
        if not all(token in doja_raw_inflater for token in (b'LENGTH_BASE', b'DIST_BASE', b'inflate')):
            return fail('JarInflater raw-DEFLATE engine is missing.')
        if not all((doja_object3d, doja_drawable3d, doja_texture, doja_fog)):
            return fail('DoJa graphics3d class set is incomplete.')
        scratchpad_classes = [
            name for name in names
            if name.startswith('com/sun/cldc/io/j2me/scratchpad/')
            and name.endswith('.class')]
        if any('$' in name for name in scratchpad_classes):
            return fail('Nested ScratchPad classes are forbidden in v41.')
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
            return fail('v41 separate-stream ScratchPad methods are missing.')
        if (b'DoJa-Compat-Corpse-Party' not in http
                or b'HTTP unavailable on standalone NDS' not in http):
            return fail('HTTP compatibility gate is missing or stale.')
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
        if marker.get('corpse_party_compat'):
            try:
                game_j = archive.read('j.class')
            except KeyError:
                return fail('Corpse Party compatibility was enabled without j.class.')
            patched_count, legacy_count = segment_stream_patch_counts(game_j)
            if patched_count != 13 or legacy_count != 0:
                return fail('Corpse Party j.class patch mismatch: patched=%d legacy=%d' % (
                    patched_count, legacy_count))
        elif 'j.class' in names:
            # A generic game may legitimately use this class name. It must remain untouched.
            game_j = archive.read('j.class')
            _patched_count, legacy_count = segment_stream_patch_counts(game_j)
            if legacy_count and (b'init.bin' in game_j):
                return fail('A Corpse Party-like j.class was left unclassified.')
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
    standalone_header_source = (project / 'include' / 'standalone_game.h').read_text(encoding='utf-8')
    standalone_mk_source = (project / 'standalone_game.mk').read_text(encoding='utf-8')
    makefile_source = (project / 'Makefile').read_text(encoding='utf-8')
    if ('#define STANDALONE_NDS_GAME_CODE "####"' not in standalone_header_source or
            '#define STANDALONE_APP_STORAGE_CODE "' not in standalone_header_source or
            'NDS_GAME_CODE := \\#\\#\\#\\#' not in standalone_mk_source or
            '-g "$(NDS_GAME_CODE)"' not in makefile_source):
        return fail('Generated ROM header is not marked as homebrew for DLDI patching.')
    if ('int canUseSd = isDSiMode();' not in nds_file_source or
            'MEDIA: NOT ATTACHED' not in nds_main_source or
            'MODE: RAM-FIRST SAVE' not in nds_main_source or
            'GAME: CONTINUES IN RAM' not in nds_main_source):
        return fail('v41 RAM-first save diagnostics are missing or stale.')

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
    if ('DOJA_PORT_BUILD_VERSION != DOJA_SOURCE_PORT_VERSION' not in nds_main_source
            or 'SAVE: READY' not in nds_main_source
            or 'MEDIA: %s' not in nds_main_source
            or 'STAGE: %s' not in nds_main_source
            or 'pstrosSetVmConsoleEnabled(1)' not in nds_main_source
            or '#include "doja_port_version.h"' not in nds_main_source):
        return fail('NDS entry point is not the v41 compact save-status build.')
    if ('pstrosMountSaveStorageAuto(launchPath)' not in nds_main_source or
            'argc > 0 && argv != NULL' not in nds_main_source or
            'dojaSpPersistenceInit' not in nds_main_source or
            'screenXArg' not in nds_main_source or 'screenYArg' not in nds_main_source or
            'DOJA_SCREEN_X' not in nds_main_source or 'DOJA_SCREEN_Y' not in nds_main_source or
            'StartJVM(5, kvm_argv)' not in nds_main_source or
            'fatInitDefault()' in nds_main_source):
        return fail('NDS entry point is not using dynamic viewport/save metadata.')
    if '#define DEFAULTHEAPSIZE (2432*1024)' not in machine_md_source:
        return fail('DS fallback heap is not 2432 KiB for v41.')
    if ('#define DOJA_DSI_HEAPSIZE (8*1024*1024)' not in nds_main_source or
            'dojaHeapBytes = isDSiMode() ? DOJA_DSI_HEAPSIZE : DEFAULTHEAPSIZE' not in nds_main_source or
            'RequestedHeapSize = dojaHeapBytes' not in nds_main_source):
        return fail('v41 dynamic DS/DSi heap selection is missing.')
    if 'DoJa v41 heap allocated:' not in nds_runtime_source:
        return fail('v41 heap allocation diagnostics are missing.')
    if ('DoJa v41 heap fallback:' not in nds_runtime_source or
            'attempt -= 1024 * 1024' not in nds_runtime_source):
        return fail('v41 DSi heap fallback ladder is missing.')
    if 'KVM HEAP OOM req=' not in collector_source:
        return fail('Heap fragmentation diagnostics are missing.')
    save_mount_tokens = (
        'int pstrosMountSaveStorageAuto(const char *launchPath)',
        'int pstrosMountSaveStorageDirect(void)',
        'fatInitDefault()',
        'pstrosFatInitAttempted',
        'pstrosProbeMountedVolumes(0)',
        'pstrosProbeMountedVolumes(1)',
        'pstrosConfigureSaveStorageOn',
        'fopen(probePath, "wb")',
        'fopen(probePath, "rb")',
        'STANDALONE_SHORT_SAVE_NAME',
        'pstrosRememberLaunchSavePath',
        'pstrosChooseFinalSavePath',
        'pstrosLaunchSavePath',
        'pstrosPreferredBackend',
        'DLDI/FAT',
        'DSI-SD',
    )
    if not all(token in nds_file_source for token in save_mount_tokens):
        return fail('libdvm-compatible argv-aware save backend is missing or stale.')
    forbidden_storage_tokens = (
        '_FAT_disc_interfaces',
        'dldiGetInternal',
        'get_io_dsisd',
        'fatMountSimple(',
        'pstrosResolveFatInterface',
    )
    if any(token in nds_file_source for token in forbidden_storage_tokens):
        return fail('Removed/private storage interface reference is still present.')
    if 'open(probePath, O_' in nds_file_source or 'fatInitDefault()' in nds_main_source:
        return fail('Storage initialization is in the wrong layer or raw-open probing is enabled.')

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
        return fail('DoJa v41 input mapping fix is missing or stale.')
    if 'DoJa boot error:' not in doja_mainapp_source or 'error.toString()' not in doja_mainapp_source:
        return fail('DoJa v41 fatal Java diagnostics are missing.')
    forbidden_success_logs = (
        'DoJa boot class:',
        'DoJa boot: class loaded',
        'DoJa boot: app created',
        'DoJa input mapping:',
        'DoJa NDS: input pump started',
    )
    if any(token in doja_mainapp_source for token in forbidden_success_logs):
        return fail('DoJa v41 production runtime still prints successful boot/input traces.')
    display_tokens = (
        'Display.WIDTH = 240',
        'Display.HEIGHT = 240',
        'EmuCanvas.screenPosX = screenX',
        'EmuCanvas.screenPosY = screenY',
    )
    if not all(token in doja_mainapp_source for token in display_tokens):
        return fail('DoJa v41 native viewport setup is missing or stale.')
    video_source = (project / 'kvm' / 'VmSkel' / 'src' / 'Java_nds_Video.c').read_text(encoding='latin-1')
    if 'DoJa v41 native viewport: never resample the game frame.' not in video_source:
        return fail('DoJa v41 native viewport blitter marker is missing.')
    forbidden_scaler_tokens = (
        'srcW == 240 && srcH == 240 && dstW == 256 && dstH == 192',
        'int sourceY = ((outY * 5) + 2) >> 2',
        'int sourceX = ((outX * 15) + 7) >> 4',
        'goto blit_done;',
        '\nblit_done:\n',
        'forced final-frame resize',
    )
    if any(token in video_source for token in forbidden_scaler_tokens):
        return fail('A forced 240x240 to 256x192 scaler is still present.')

    graphics_source = (project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'ui' / 'Graphics.java').read_text(encoding='utf-8')
    frame_tokens = (
        'private boolean presentPending',
        'if (lockDepth > 0)',
        'if (lockDepth == 0 && presentPending)',
        'presentOwner();',
    )
    if not all(token in graphics_source for token in frame_tokens):
        return fail('v41 deferred single-present frame path is missing or stale.')
    if 'owner._flush();' not in graphics_source:
        return fail('v41 frame presenter is not connected to the Canvas owner.')

    jar_inflater_source = (project / 'doja_port' / 'doja_src' / 'com' / 'nttdocomo' / 'util' / 'JarInflater.java').read_text(encoding='utf-8')
    inflater_tokens = (
        'FIXED_LITERAL',
        'FIXED_DISTANCE',
        'copyMatch(byte[] output',
        'System.arraycopy(output, start, output, start + copied, chunk)',
        'new byte[8192]',
    )
    if not all(token in jar_inflater_source for token in inflater_tokens):
        return fail('v41 ScratchPad JAR loading optimizations are missing or stale.')

    quiet_sources = (
        doja_canvas_source,
        (project / 'kvm' / 'VmCommon' / 'src' / 'nativeCore.c').read_text(encoding='latin-1'),
        (project / 'kvm' / 'VmExtra' / 'src' / 'jar.c').read_text(encoding='latin-1'),
        (project / 'kvm' / 'VmExtra' / 'src' / 'loaderFile.c').read_text(encoding='latin-1'),
    )
    forbidden_hot_logs = ('DOJA SENT', 'Thread.start native enter', 'jar entry search', 'open class result:')
    if any(token in source for source in quiet_sources for token in forbidden_hot_logs):
        return fail('v41 still contains a hot-path class/thread/input console trace.')
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
    if "find('〓')" not in bitmap_font_source:
        return fail('Japanese font fallback is missing or stale.')
    if 'FONT MISS U+' in bitmap_font_source or 'DoJa font ready:' in bitmap_font_source:
        return fail('Per-glyph/font-load console diagnostics must be disabled in v41.')
    if 'Cp932Codec.normalizeForDisplay' not in bitmap_font_source:
        return fail('Bitmap font is not using the SJIS display fallback.')
    latin_font_tokens = (
        'target_w = (width + 1) // 2 if ord(char) <= 0x007F else width',
        'threshold = 80 if ord(char) <= 0x007F else 96',
    )
    if not all(token in fontgen_source for token in latin_font_tokens):
        return fail('Latin half-width glyph generation fix is missing or stale.')
    runtime_latin_tokens = (
        'int sourceWidth = c <= 0x007F ? (baseWidth + 1) / 2 : baseWidth',
        'int sx = (dx * sourceWidth) / width',
    )
    if not all(token in bitmap_font_source for token in runtime_latin_tokens):
        return fail('Latin glyph renderer still skips source columns.')
    if 'NFTR' in fontgen_source or 'nftr' in fontgen_source:
        return fail('NFTR hybrid font support must not be enabled in v41.')
    nul_padding_tokens = (
        'isNonPrintingControl',
        'return c < 0x0020 || c == 0x007F',
    )
    if not all(token in bitmap_font_source for token in nul_padding_tokens):
        return fail('v41 NUL/control padding font fix is missing or stale.')
    if b'isNonPrintingControl' not in bitmap_font_class:
        return fail('Compiled BitmapJapaneseFont.class lacks the v41 padding fix.')

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
    if ('dojaSpStorageUnavailable' not in resource_source or
            'never mount/probe storage from a single-byte write' not in resource_source or
            'dojaSaveUiBuffered' not in resource_source):
        return fail('v41 RAM-first ScratchPad hot-path fix is missing.')
    if 'if (!dojaSpPersistenceReady) dojaSpEnsurePersistence();' in resource_source:
        return fail('ScratchPad writes still probe storage from the hot path.')
    save_tokens = (
        'DoJa v41 ScratchPad ROM access with persistent same-name .sav saves',
        'dojaSpPersistenceInit',
        'dojaSpPersistenceFlush',
        'dojaSpEnsurePersistence',
        'DOJA_SP_MAX_DIRTY_CHUNKS 256',
        'DOJA_SP_SAVE_HEADER_SIZE 28',
        'DOJA_SCRATCHPAD_CRC32',
        'Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeFlush',
        'dojaSaveUiSaving(0)',
        'dojaSaveUiResult',
        'dojaSpValidateFile',
        'dojaSpCopyFile',
        'memcpy(dojaSpTempPath + length - 4, ".TMP", 5)',
        "dojaSpTempPath[length - 4] == '.'",
        'dojaSpWriteOverlayFile',
    )
    if not all(token in resource_source for token in save_tokens):
        return fail('v41 game-independent persistent ScratchPad backend is missing or stale.')
    if 'DOJA_CP_' in resource_source or 'dojaSpDetectSlot' in resource_source:
        return fail('Corpse Party-specific save-slot logic is still hardcoded in the runtime.')
    if 'fsync(fileno' in resource_source:
        return fail('Unsupported fsync calls are still present in the save writer.')
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
    print('[OK] DoJa v41 preparation verified')
    print('[OK] Expected ROM:', output_stem + '.nds')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
