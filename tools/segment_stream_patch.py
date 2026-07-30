#!/usr/bin/env python3
"""Patch Corpse Party's preverified j.class to stream SP segments.

The patch preserves every Code attribute length and every operand-stack shape.
Only three constant-pool operands are redirected at each exact loader pattern:

  j.k(segment) -> SegmentToken.open(segment)
  new ByteArrayInputStream -> new ScratchpadByteArrayInputStream
  ByteArrayInputStream.<init>(byte[]) -> patched subclass constructor

The custom subclass remains assignable to ByteArrayInputStream, so the original
CLDC/KVM StackMap frames remain valid.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class CpEntry:
    tag: int
    value: object
    raw: bytes


class ClassPatchError(RuntimeError):
    pass


def _u2(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from('>H', data, offset)[0]


def _u4(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from('>I', data, offset)[0]


def _parse_cp(data: bytes) -> tuple[list[CpEntry | None], int]:
    if len(data) < 10 or data[:4] != b'\xca\xfe\xba\xbe':
        raise ClassPatchError('not a class file')
    count = _u2(data, 8)
    cp: list[CpEntry | None] = [None] * count
    offset = 10
    index = 1
    while index < count:
        start = offset
        tag = data[offset]
        offset += 1
        if tag == 1:
            length = _u2(data, offset)
            offset += 2
            payload = data[offset:offset + length]
            offset += length
            value: object = payload.decode('utf-8', errors='surrogateescape')
        elif tag in (3, 4):
            value = data[offset:offset + 4]
            offset += 4
        elif tag in (5, 6):
            value = data[offset:offset + 8]
            offset += 8
            cp[index] = CpEntry(tag, value, data[start:offset])
            index += 1
            if index < count:
                cp[index] = None
            index += 1
            continue
        elif tag in (7, 8, 16):
            value = _u2(data, offset)
            offset += 2
        elif tag in (9, 10, 11, 12, 18):
            value = (_u2(data, offset), _u2(data, offset + 2))
            offset += 4
        elif tag == 15:
            value = (data[offset], _u2(data, offset + 1))
            offset += 3
        else:
            raise ClassPatchError('unsupported constant-pool tag %d' % tag)
        cp[index] = CpEntry(tag, value, data[start:offset])
        index += 1
    return cp, offset


def _utf8(cp: list[CpEntry | None], index: int) -> str:
    entry = cp[index]
    if entry is None or entry.tag != 1 or not isinstance(entry.value, str):
        raise ClassPatchError('invalid Utf8 constant #%d' % index)
    return entry.value


def _class_name(cp: list[CpEntry | None], index: int) -> str:
    entry = cp[index]
    if entry is None or entry.tag != 7 or not isinstance(entry.value, int):
        raise ClassPatchError('invalid Class constant #%d' % index)
    return _utf8(cp, entry.value)


def _name_and_type(cp: list[CpEntry | None], index: int) -> tuple[str, str]:
    entry = cp[index]
    if entry is None or entry.tag != 12 or not isinstance(entry.value, tuple):
        raise ClassPatchError('invalid NameAndType constant #%d' % index)
    return _utf8(cp, entry.value[0]), _utf8(cp, entry.value[1])


def _methodref(cp: list[CpEntry | None], index: int) -> tuple[str, str, str] | None:
    entry = cp[index]
    if entry is None or entry.tag not in (10, 11) or not isinstance(entry.value, tuple):
        return None
    owner = _class_name(cp, entry.value[0])
    name, descriptor = _name_and_type(cp, entry.value[1])
    return owner, name, descriptor


def _find_methodref(cp: list[CpEntry | None], owner: str, name: str,
                    descriptor: str) -> int:
    for index in range(1, len(cp)):
        if _methodref(cp, index) == (owner, name, descriptor):
            return index
    raise ClassPatchError('missing methodref %s.%s%s' % (owner, name, descriptor))


def _find_class(cp: list[CpEntry | None], name: str) -> int:
    for index, entry in enumerate(cp):
        if index and entry is not None and entry.tag == 7:
            if _class_name(cp, index) == name:
                return index
    raise ClassPatchError('missing class constant ' + name)


class CpAppender:
    def __init__(self, original_count: int):
        self.next_index = original_count
        self.payload = bytearray()
        self.cache: dict[tuple[object, ...], int] = {}

    def _add(self, key: tuple[object, ...], raw: bytes) -> int:
        if key in self.cache:
            return self.cache[key]
        index = self.next_index
        self.next_index += 1
        if self.next_index > 65535:
            raise ClassPatchError('constant pool overflow')
        self.payload.extend(raw)
        self.cache[key] = index
        return index

    def utf8(self, value: str) -> int:
        encoded = value.encode('utf-8')
        if len(encoded) > 65535:
            raise ClassPatchError('Utf8 constant too long')
        return self._add(('utf8', value), b'\x01' + struct.pack('>H', len(encoded)) + encoded)

    def clazz(self, name: str) -> int:
        name_index = self.utf8(name)
        return self._add(('class', name), b'\x07' + struct.pack('>H', name_index))

    def name_and_type(self, name: str, descriptor: str) -> int:
        name_index = self.utf8(name)
        descriptor_index = self.utf8(descriptor)
        return self._add(('nat', name, descriptor),
                         b'\x0c' + struct.pack('>HH', name_index, descriptor_index))

    def methodref(self, owner: str, name: str, descriptor: str) -> int:
        class_index = self.clazz(owner)
        nat_index = self.name_and_type(name, descriptor)
        return self._add(('method', owner, name, descriptor),
                         b'\x0a' + struct.pack('>HH', class_index, nat_index))


def _skip_attributes(data: bytes, offset: int, count: int) -> int:
    for _ in range(count):
        offset += 2
        length = _u4(data, offset)
        offset += 4 + length
    return offset


def _code_ranges(data: bytes, cp: list[CpEntry | None], cp_end: int) -> list[tuple[int, int]]:
    offset = cp_end
    # access_flags, this_class, super_class
    offset += 6
    interfaces_count = _u2(data, offset)
    offset += 2 + 2 * interfaces_count
    fields_count = _u2(data, offset)
    offset += 2
    for _ in range(fields_count):
        offset += 6
        attr_count = _u2(data, offset)
        offset += 2
        offset = _skip_attributes(data, offset, attr_count)
    methods_count = _u2(data, offset)
    offset += 2
    result: list[tuple[int, int]] = []
    for _ in range(methods_count):
        offset += 6
        attr_count = _u2(data, offset)
        offset += 2
        for _ in range(attr_count):
            name_index = _u2(data, offset)
            length = _u4(data, offset + 2)
            info = offset + 6
            if _utf8(cp, name_index) == 'Code':
                code_length = _u4(data, info + 4)
                code_start = info + 8
                result.append((code_start, code_start + code_length))
            offset = info + length
    return result


def _constant_push_length(code: bytearray, pos: int) -> int:
    opcode = code[pos]
    if 0x02 <= opcode <= 0x08:  # iconst_m1 .. iconst_5
        return 1
    if opcode == 0x10:  # bipush
        return 2
    if opcode == 0x11:  # sipush
        return 3
    return 0


def _local_load_length(code: bytearray, pos: int) -> tuple[int, int] | None:
    opcode = code[pos]
    if 0x2a <= opcode <= 0x2d:  # aload_0..aload_3
        return opcode - 0x2a, 1
    if opcode == 0x19:
        return code[pos + 1], 2
    return None


def _local_store_length(code: bytearray, pos: int) -> tuple[int, int] | None:
    opcode = code[pos]
    if 0x4b <= opcode <= 0x4e:  # astore_0..astore_3
        return opcode - 0x4b, 1
    if opcode == 0x3a:
        return code[pos + 1], 2
    return None


def patch_segment_streams(payload: bytes) -> tuple[bytes, int]:
    """Return patched j.class bytes and number of loader call sites."""
    cp, cp_end = _parse_cp(payload)
    this_class_index = _u2(payload, cp_end + 2)
    if _class_name(cp, this_class_index) != 'j':
        return payload, 0

    old_k = _find_methodref(cp, 'j', 'k', '(I)[B')
    old_bais_class = _find_class(cp, 'java/io/ByteArrayInputStream')
    old_bais_ctor = _find_methodref(
        cp, 'java/io/ByteArrayInputStream', '<init>', '([B)V')

    appender = CpAppender(len(cp))
    token_open = appender.methodref(
        'com/sun/cldc/io/j2me/scratchpad/SegmentToken', 'open', '(I)[B')
    stream_class = appender.clazz(
        'com/sun/cldc/io/j2me/scratchpad/ScratchpadByteArrayInputStream')
    stream_ctor = appender.methodref(
        'com/sun/cldc/io/j2me/scratchpad/ScratchpadByteArrayInputStream',
        '<init>', '([B)V')

    mutable = bytearray(payload)
    patched = 0
    for code_start, code_end in _code_ranges(payload, cp, cp_end):
        pos = code_start
        while pos < code_end - 12:
            call_pos = pos
            if mutable[call_pos] != 0xb8 or _u2(mutable, call_pos + 1) != old_k:
                pos += 1
                continue
            store = _local_store_length(mutable, call_pos + 3)
            if store is None:
                pos += 1
                continue
            byte_local, store_len = store
            new_pos = call_pos + 3 + store_len
            if (mutable[new_pos] != 0xbb or
                    _u2(mutable, new_pos + 1) != old_bais_class or
                    mutable[new_pos + 3] != 0x59):
                pos += 1
                continue
            load = _local_load_length(mutable, new_pos + 4)
            if load is None or load[0] != byte_local:
                pos += 1
                continue
            ctor_pos = new_pos + 4 + load[1]
            if (mutable[ctor_pos] != 0xb7 or
                    _u2(mutable, ctor_pos + 1) != old_bais_ctor):
                pos += 1
                continue

            struct.pack_into('>H', mutable, call_pos + 1, token_open)
            struct.pack_into('>H', mutable, new_pos + 1, stream_class)
            struct.pack_into('>H', mutable, ctor_pos + 1, stream_ctor)
            patched += 1
            pos = ctor_pos + 3

    # This exact Corpse Party build has thirteen byte[] -> ByteArrayInputStream
    # segment loaders, including one helper whose segment index is dynamic.
    # Failing closed avoids silently producing another stale ROM if a
    # different j.class is supplied.
    if patched != 13:
        raise ClassPatchError(
            'expected 13 Corpse Party segment loaders, found %d' % patched)

    new_count = appender.next_index
    result = bytearray()
    result.extend(mutable[:8])
    result.extend(struct.pack('>H', new_count))
    result.extend(mutable[10:cp_end])
    result.extend(appender.payload)
    result.extend(mutable[cp_end:])
    return bytes(result), patched


def segment_stream_patch_counts(payload: bytes) -> tuple[int, int]:
    """Return (patched_loader_count, legacy_loader_count)."""
    cp, cp_end = _parse_cp(payload)
    try:
        old_k = _find_methodref(cp, 'j', 'k', '(I)[B')
        old_class = _find_class(cp, 'java/io/ByteArrayInputStream')
        old_ctor = _find_methodref(cp, 'java/io/ByteArrayInputStream', '<init>', '([B)V')
        new_call = _find_methodref(
            cp, 'com/sun/cldc/io/j2me/scratchpad/SegmentToken', 'open', '(I)[B')
        new_class = _find_class(
            cp, 'com/sun/cldc/io/j2me/scratchpad/ScratchpadByteArrayInputStream')
        new_ctor = _find_methodref(
            cp,
            'com/sun/cldc/io/j2me/scratchpad/ScratchpadByteArrayInputStream',
            '<init>', '([B)V')
    except ClassPatchError:
        return 0, 0

    patched = 0
    legacy = 0
    code = bytearray(payload)
    for start, end in _code_ranges(payload, cp, cp_end):
        pos = start
        while pos < end - 12:
            call_pos = pos
            if code[call_pos] != 0xb8:
                pos += 1
                continue
            call_ref = _u2(code, call_pos + 1)
            store = _local_store_length(code, call_pos + 3)
            if store is None:
                pos += 1
                continue
            local, store_len = store
            new_pos = call_pos + 3 + store_len
            if code[new_pos] != 0xbb or code[new_pos + 3] != 0x59:
                pos += 1
                continue
            load = _local_load_length(code, new_pos + 4)
            if load is None or load[0] != local:
                pos += 1
                continue
            ctor_pos = new_pos + 4 + load[1]
            if code[ctor_pos] != 0xb7:
                pos += 1
                continue
            class_ref = _u2(code, new_pos + 1)
            ctor_ref = _u2(code, ctor_pos + 1)
            if (call_ref, class_ref, ctor_ref) == (new_call, new_class, new_ctor):
                patched += 1
            elif (call_ref, class_ref, ctor_ref) == (old_k, old_class, old_ctor):
                legacy += 1
            pos = ctor_pos + 3
    return patched, legacy
