/*
 * Copyright © 2003 Sun Microsystems, Inc. All rights reserved.
 * SUN PROPRIETARY/CONFIDENTIAL. Use is subject to license terms.
 */

/*=========================================================================
 * KVM
 *=========================================================================
 * SYSTEM:    KVM
 * SUBSYSTEM: resource access (Generic Connection framework)
 * FILE:      resource.c
 * OVERVIEW:  This file implements the native functions for
 *            a Generic Connection protocol that is used for
 *            accessing external resources.
 * AUTHOR:    Nik Shaylor
 *=======================================================================*/

/*=========================================================================
 * Include files
 *=======================================================================*/

#include <global.h>
#include <inflate.h>

/*=========================================================================
 * Forward declarations
 *=======================================================================*/

void Java_com_sun_cldc_io_ResourceInputStream_open(void);
void Java_com_sun_cldc_io_ResourceInputStream_close(void);
void Java_com_sun_cldc_io_ResourceInputStream_read(void);

/*=========================================================================
 * Functions
 *=======================================================================*/

 /*=========================================================================
  * FUNCTION:      Object open(String) (STATIC)
  * CLASS:         com.sun.cldc.io.ResourceInputStream
  * TYPE:          virtual native function
  * OVERVIEW:      Open resource stream
  * INTERFACE (operand stack manipulation):
  *   parameters:  this
  *   returns:     the integer value
  *=======================================================================*/

void Java_com_sun_cldc_io_ResourceInputStream_open(void) {
    STRING_INSTANCE string = popStackAsType(STRING_INSTANCE);
    char           *name;
    FILEPOINTER     fp;

    START_TEMPORARY_ROOTS
        DECLARE_TEMPORARY_ROOT(STRING_INSTANCE, _string, string);
        long buflen = _string->length + 1;
        DECLARE_TEMPORARY_ROOT(char *, buf,
                               (char *)mallocHeapObject((buflen+CELL-1)>>log2CELL,
                               GCT_NOPOINTERS));

        name = getStringContentsSafely(_string, buf, buflen);
        if (buf == NULL) {
            THROW(OutOfMemoryObject);
        } else {
            fp = openResourcefile(name);
            if (fp == NULL) {
                raiseException(IOException);
            } else {
                pushStackAsType(FILEPOINTER, fp);
            }
        }
    END_TEMPORARY_ROOTS
}

 /*=========================================================================
  * FUNCTION:      void close(Object) static   [Object is fp]
  * CLASS:         com.sun.cldc.io.ResourceInputStream
  * TYPE:          virtual native function
  * OVERVIEW:      Read an integer from the resource
  * INTERFACE (operand stack manipulation):
  *   parameters:  this
  *   returns:     the integer value
  *=======================================================================*/

void Java_com_sun_cldc_io_ResourceInputStream_close(void) {
    START_TEMPORARY_ROOTS
        DECLARE_TEMPORARY_ROOT(FILEPOINTER, fp, popStackAsType(FILEPOINTER));
        if (fp == NULL) {
            raiseException(IOException);
        } else {
            closeClassfile(&fp);
        }
    END_TEMPORARY_ROOTS
    /* Java code will set the handle to NULL */
}

 /*=========================================================================
  * FUNCTION:      read()I (VIRTUAL)
  * CLASS:         com.sun.cldc.io.ResourceInputStream
  * TYPE:          virtual native function
  * OVERVIEW:      Read an integer from the resource
  * INTERFACE (operand stack manipulation):
  *   parameters:  this
  *   returns:     the integer value
  *=======================================================================*/

void Java_com_sun_cldc_io_ResourceInputStream_read(void) {
    START_TEMPORARY_ROOTS
        int result;
        DECLARE_TEMPORARY_ROOT(FILEPOINTER, fp, popStackAsType(FILEPOINTER));
        if (fp == NULL) {
            raiseException(IOException);
        } else {
            result = loadByteNoEOFCheck(&fp);
            pushStack(result);
        }
    END_TEMPORARY_ROOTS
}

 /*=========================================================================
  * FUNCTION:      readAll()I (VIRTUAL)
  * CLASS:         com.sun.cldc.io.ResourceInputStream
  * TYPE:          virtual native function
  * OVERVIEW:      Read an array of bytes from the stream
  * INTERFACE (operand stack manipulation):
  *   parameters:  this, byte array, offset, filepos, len
  *   returns:     the number of bytes read
  *=======================================================================*/

void Java_com_sun_cldc_io_ResourceInputStream_readBytes(void) {
    int result;
    int length = popStack();
    int pos = popStack();
    int offset = popStack();
    BYTEARRAY bytes = popStackAsType(BYTEARRAY);
    FILEPOINTER fp = popStackAsType(FILEPOINTER);

    if (fp == NULL || bytes == NULL) {
        raiseException(IOException);
    } else {
        result = loadBytesNoEOFCheck(&fp, (char *)&bytes->bdata[offset], pos, length);
        pushStack(result);
    }
}

 /*=========================================================================
  * FUNCTION:      size()I (VIRTUAL)
  * CLASS:         com.sun.cldc.io.ResourceInputStream
  * TYPE:          virtual native function
  * OVERVIEW:      return amount of data on this stream
  * INTERFACE (operand stack manipulation):
  *   parameters:  this
  *   returns:     the number of bytes available
  *=======================================================================*/

void Java_com_sun_cldc_io_ResourceInputStream_size(void) {
    int result;
    FILEPOINTER fp = popStackAsType(FILEPOINTER);
    if (fp == NULL) {
        raiseException(IOException);
    } else {
        result = getBytesAvailable(&fp);
        pushStack(result);
    }
}

/*=========================================================================
 * DoJa v56 ScratchPad ROM access with persistent same-name .sav saves.
 *
 * build-doja converts the selected game's ScratchPad to a Nintendo LZ77
 * type-0x10 stream. The wrapper is expanded once into RAM before KVM starts.
 * Runtime reads are then plain memcpy() operations; no NitroFS, DLDI or
 * filesystem probe is involved in the boot path.
 *=======================================================================*/
#include <stdio.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

#include "standalone_game.h"

#define DOJA_SP_LZ77_WRAPPER_HEADER_SIZE 20
#define DOJA_SP_LZ77_VERSION 1UL

extern const unsigned char _binary_embedded_doja_scratchpad_lz7b_start[];
extern const unsigned char _binary_embedded_doja_scratchpad_lz7b_end[];

static unsigned char *dojaSpRomData = NULL;

static int dojaSpBaseRead(int position, unsigned char *dst, int length);

static unsigned long dojaSpBlobReadLe32(const unsigned char *p) {
    return ((unsigned long)p[0]) |
           ((unsigned long)p[1] << 8) |
           ((unsigned long)p[2] << 16) |
           ((unsigned long)p[3] << 24);
}

static unsigned long dojaSpCrc32(const unsigned char *data, unsigned long length) {
    static unsigned long table[256];
    static int tableReady = 0;
    unsigned long crc = 0xFFFFFFFFUL;
    unsigned int i;

    if (!tableReady) {
        for (i = 0; i < 256; ++i) {
            unsigned long value = i;
            unsigned int bit;
            for (bit = 0; bit < 8; ++bit) {
                value = (value & 1UL) ?
                    ((value >> 1) ^ 0xEDB88320UL) : (value >> 1);
            }
            table[i] = value;
        }
        tableReady = 1;
    }
    while (length-- > 0) {
        crc = table[(crc ^ *data++) & 0xFFU] ^ (crc >> 8);
    }
    return ~crc;
}

/* Decode the standard Nintendo/GBA/NDS LZ77 type-0x10 stream generated by
 * tools/prepare_doja.py. It is deliberately independent of the BIOS so the
 * same ROM behaves in melonDS, DSi mode and homebrew loaders. */
static int dojaSpLz77Decode(const unsigned char *src, int srcLength,
                            unsigned char *dst, int dstCapacity) {
    const unsigned char *ip;
    const unsigned char *iend;
    unsigned char *op = dst;
    unsigned char *oend = dst + dstCapacity;
    unsigned long declaredSize;

    if (src == NULL || dst == NULL || srcLength < 4 || src[0] != 0x10)
        return -1;
    declaredSize = ((unsigned long)src[1]) |
                   ((unsigned long)src[2] << 8) |
                   ((unsigned long)src[3] << 16);
    if (declaredSize != (unsigned long)dstCapacity) return -2;
    ip = src + 4;
    iend = src + srcLength;

    while (op < oend) {
        unsigned int flags;
        unsigned int mask;
        if (ip >= iend) return -3;
        flags = *ip++;
        for (mask = 0x80; mask != 0 && op < oend; mask >>= 1) {
            if ((flags & mask) != 0) {
                unsigned int first, second, length, displacement;
                unsigned char *match;
                if ((iend - ip) < 2) return -4;
                first = *ip++;
                second = *ip++;
                length = (first >> 4) + 3;
                displacement = (((first & 0x0F) << 8) | second) + 1;
                if (displacement > (unsigned int)(op - dst)) return -5;
                if ((unsigned long)(oend - op) < length) return -6;
                match = op - displacement;
                while (length-- > 0) *op++ = *match++;
            } else {
                if (ip >= iend) return -7;
                *op++ = *ip++;
            }
        }
    }
    return (int)(op - dst);
}

int dojaSpRomInit(const char *unusedPath) {
    const unsigned char *blob = _binary_embedded_doja_scratchpad_lz7b_start;
    const unsigned char *blobEnd = _binary_embedded_doja_scratchpad_lz7b_end;
    unsigned long version;
    unsigned long rawSize;
    unsigned long packedSize;
    unsigned long expectedCrc;
    int decoded;

    (void)unusedPath;
    if (dojaSpRomData != NULL) return 1;
    if (blob == NULL || blobEnd <= blob ||
        (unsigned long)(blobEnd - blob) < DOJA_SP_LZ77_WRAPPER_HEADER_SIZE) {
        return 0;
    }
    if (blob[0] != 'D' || blob[1] != '7' || blob[2] != 'S' || blob[3] != 'P') {
        return 0;
    }

    version = dojaSpBlobReadLe32(blob + 4);
    rawSize = dojaSpBlobReadLe32(blob + 8);
    packedSize = dojaSpBlobReadLe32(blob + 12);
    expectedCrc = dojaSpBlobReadLe32(blob + 16);
    if (version != DOJA_SP_LZ77_VERSION ||
        rawSize != (unsigned long)DOJA_SCRATCHPAD_SIZE ||
        expectedCrc != (unsigned long)DOJA_SCRATCHPAD_CRC32 ||
        packedSize != (unsigned long)(blobEnd - blob - DOJA_SP_LZ77_WRAPPER_HEADER_SIZE)) {
        return 0;
    }

    dojaSpRomData = (unsigned char *)malloc(DOJA_SCRATCHPAD_SIZE);
    if (dojaSpRomData == NULL) return 0;
    decoded = dojaSpLz77Decode(blob + DOJA_SP_LZ77_WRAPPER_HEADER_SIZE,
                               (int)packedSize,
                               dojaSpRomData,
                               DOJA_SCRATCHPAD_SIZE);
    if (decoded != DOJA_SCRATCHPAD_SIZE ||
        dojaSpCrc32(dojaSpRomData, DOJA_SCRATCHPAD_SIZE) != expectedCrc) {
        free(dojaSpRomData);
        dojaSpRomData = NULL;
        return 0;
    }
    return 1;
}

static int dojaSpBaseRead(int position, unsigned char *dst, int length) {
    int available;
    if (dojaSpRomData == NULL || dst == NULL || position < 0 || length < 0)
        return 0;
    if (position >= DOJA_SCRATCHPAD_SIZE) return 0;
    available = DOJA_SCRATCHPAD_SIZE - position;
    if (length > available) length = available;
    if (length <= 0) return 0;
    memcpy(dst, dojaSpRomData + position, length);
    return length;
}

#define DOJA_SP_CHUNK_SIZE 256
#define DOJA_SP_MAX_DIRTY_CHUNKS 256
#define DOJA_SP_SAVE_HEADER_SIZE 28
#define DOJA_SP_SAVE_VERSION 1
#define DOJA_SP_PATH_MAX 255

static int dojaSpChunkIds[DOJA_SP_MAX_DIRTY_CHUNKS];
static unsigned char dojaSpChunks[DOJA_SP_MAX_DIRTY_CHUNKS][DOJA_SP_CHUNK_SIZE];
static int dojaSpChunkCount = 0;
static int dojaSpDirty = 0;
static int dojaSpPersistenceReady = 0;
/* Once storage is known to be absent, writes stay in the sparse RAM overlay.
 * Do not retry media detection from the byte-write hot path. */
static int dojaSpStorageUnavailable = 0;
static int dojaSpRamBufferReported = 0;
static char dojaSpSavePath[DOJA_SP_PATH_MAX + 1];
static char dojaSpTempPath[DOJA_SP_PATH_MAX + 1];
static char dojaSpLegacyPath[DOJA_SP_PATH_MAX + 1];

extern int pstrosMountSaveStorageDirect(void);
extern int pstrosMountSaveStorageExplicit(void);
extern const char *pstrosGetSavePath(void);
extern int pstrosGetSaveErrno(void);
extern void dojaSaveUiAttaching(void);
extern void dojaSaveUiStorage(int ready, int errorCode);
extern void dojaSaveUiLoaded(int loadedChunks);
extern void dojaSaveUiSaving(int slot);
extern void dojaSaveUiResult(int success, int slot, int resultCode);
extern void dojaSaveUiBuffered(int dirtyChunks);

int dojaSpPersistenceInit(const char *path);
int dojaSpPersistenceFlush(void);


static int dojaSpConfigurePersistencePath(const char *path) {
    size_t length;
    if (path == NULL || path[0] == 0 || strlen(path) > DOJA_SP_PATH_MAX - 5) {
        dojaSpPersistenceReady = 0;
        return 0;
    }
    snprintf(dojaSpSavePath, sizeof(dojaSpSavePath), "%s", path);

    /* Keep the temporary file extension short. Both the same-name .sav path
       and any short-name fallback become a sibling .TMP file. */
    snprintf(dojaSpTempPath, sizeof(dojaSpTempPath), "%s", path);
    length = strlen(dojaSpTempPath);
    if (length >= 4 && dojaSpTempPath[length - 4] == '.') {
        memcpy(dojaSpTempPath + length - 4, ".TMP", 5);
    } else {
        snprintf(dojaSpTempPath, sizeof(dojaSpTempPath), "%s.tmp", path);
    }

    snprintf(dojaSpLegacyPath, sizeof(dojaSpLegacyPath), "%s",
             STANDALONE_LEGACY_SAVE_PATH);
    dojaSpPersistenceReady = 1;
    return 1;
}

static int dojaSpEnsurePersistence(void) {
    int restored;
    if (dojaSpPersistenceReady) return 1;
    if (dojaSpStorageUnavailable) return 0;
    if (!pstrosMountSaveStorageDirect()) {
        /* Physical persistence is absent, but the virtual ScratchPad overlay
         * remains a valid save device.  Do not turn that into an ENODEV UI
         * state or an application-visible failure. */
        dojaSpStorageUnavailable = 1;
        return 0;
    }
    /* If RAM writes already happened while FAT was unavailable, do not call
       the normal loader because it resets the overlay. Attach the path and
       immediately persist the in-memory changes instead. */
    if (dojaSpDirty || dojaSpChunkCount > 0) {
        if (!dojaSpConfigurePersistencePath(pstrosGetSavePath())) return 0;
        dojaSpRamBufferReported = 0;
        dojaSaveUiStorage(1, 0);
        return 1;
    }
    restored = dojaSpPersistenceInit(pstrosGetSavePath());
    dojaSaveUiStorage(1, 0);
    dojaSaveUiLoaded(restored);
    return dojaSpPersistenceReady;
}

int dojaSpPersistenceAttachStorage(void) {
    int restored;

    if (dojaSpPersistenceReady) return 1;

    dojaSaveUiAttaching();
    dojaSpStorageUnavailable = 0;
    if (!pstrosMountSaveStorageExplicit()) {
        dojaSpStorageUnavailable = 1;
        /* Keep RAM-VIRTUAL reported as ready.  START+SELECT is only an
         * optional persistence request, not a requirement for saving. */
        dojaSaveUiStorage(1, 0);
        return 0;
    }

    /* Preserve data already written to the RAM overlay.  Attaching media must
     * not reset FF4A's current ScratchPad state. */
    if (dojaSpDirty || dojaSpChunkCount > 0) {
        if (!dojaSpConfigurePersistencePath(pstrosGetSavePath())) {
            dojaSpStorageUnavailable = 1;
            dojaSaveUiStorage(0, pstrosGetSaveErrno());
            return 0;
        }
        dojaSpRamBufferReported = 0;
        dojaSaveUiStorage(1, 0);
        if (dojaSpDirty) return dojaSpPersistenceFlush();
        return 1;
    }

    restored = dojaSpPersistenceInit(pstrosGetSavePath());
    dojaSaveUiStorage(1, 0);
    dojaSaveUiLoaded(restored);
    return dojaSpPersistenceReady;
}

static int dojaSpFail(int code) {
    dojaSaveUiResult(0, 0, code);
    return code;
}

static unsigned int dojaSpReadLe16(const unsigned char *p) {
    return (unsigned int)p[0] | ((unsigned int)p[1] << 8);
}

static unsigned long dojaSpReadLe32(const unsigned char *p) {
    return (unsigned long)p[0] |
           ((unsigned long)p[1] << 8) |
           ((unsigned long)p[2] << 16) |
           ((unsigned long)p[3] << 24);
}

static void dojaSpWriteLe16(unsigned char *p, unsigned int value) {
    p[0] = (unsigned char)(value & 0xff);
    p[1] = (unsigned char)((value >> 8) & 0xff);
}

static void dojaSpWriteLe32(unsigned char *p, unsigned long value) {
    p[0] = (unsigned char)(value & 0xff);
    p[1] = (unsigned char)((value >> 8) & 0xff);
    p[2] = (unsigned char)((value >> 16) & 0xff);
    p[3] = (unsigned char)((value >> 24) & 0xff);
}

static unsigned long dojaSpCrc32Update(unsigned long crc,
                                       const unsigned char *data, int length) {
    int i;
    crc = ~crc;
    for (i = 0; i < length; i++) {
        int bit;
        crc ^= data[i];
        for (bit = 0; bit < 8; bit++) {
            unsigned long mask = (unsigned long)-(long)(crc & 1UL);
            crc = (crc >> 1) ^ (0xEDB88320UL & mask);
        }
    }
    return ~crc;
}

static int dojaSpSize(void) {
    return DOJA_SCRATCHPAD_SIZE;
}

static void dojaSpResetOverlay(void) {
    dojaSpChunkCount = 0;
    dojaSpDirty = 0;
}

static int dojaSpFindChunk(int id, int create) {
    int i;
    for (i = 0; i < dojaSpChunkCount; i++) {
        if (dojaSpChunkIds[i] == id) return i;
    }
    if (!create) return -1;
    if (dojaSpChunkCount >= DOJA_SP_MAX_DIRTY_CHUNKS) {
        static int warned = 0;
        if (!warned) {
            printf("DoJa SAVE overlay full: max=%d chunks\n",
                   DOJA_SP_MAX_DIRTY_CHUNKS);
            warned = 1;
        }
        return -1;
    }
    i = dojaSpChunkCount++;
    dojaSpChunkIds[i] = id;
    {
        int base = id * DOJA_SP_CHUNK_SIZE;
        int size = dojaSpSize();
        int count = size - base;
        if (count > DOJA_SP_CHUNK_SIZE) count = DOJA_SP_CHUNK_SIZE;
        if (count > 0) {
            if (dojaSpBaseRead(base, dojaSpChunks[i], count) != count) {
                memset(dojaSpChunks[i], 0, count);
            }
        } else {
            count = 0;
        }
        if (count < DOJA_SP_CHUNK_SIZE) {
            memset(dojaSpChunks[i] + count, 0,
                   DOJA_SP_CHUNK_SIZE - count);
        }
    }
    return i;
}

static int dojaSpReadAt(int position) {
    int chunk = dojaSpFindChunk(position / DOJA_SP_CHUNK_SIZE, 0);
    if (chunk >= 0) return dojaSpChunks[chunk][position % DOJA_SP_CHUNK_SIZE];
    {
        unsigned char value = 0;
        if (dojaSpBaseRead(position, &value, 1) != 1) return 0;
        return value;
    }
}

static unsigned long dojaSpPayloadCrc(void) {
    unsigned long crc = 0;
    int i;
    unsigned char idBytes[4];
    for (i = 0; i < dojaSpChunkCount; i++) {
        dojaSpWriteLe32(idBytes, (unsigned long)dojaSpChunkIds[i]);
        crc = dojaSpCrc32Update(crc, idBytes, 4);
        crc = dojaSpCrc32Update(crc, dojaSpChunks[i], DOJA_SP_CHUNK_SIZE);
    }
    return crc;
}

static int dojaSpValidateFile(const char *path) {
    FILE *fp;
    unsigned char header[DOJA_SP_SAVE_HEADER_SIZE];
    unsigned char buffer[DOJA_SP_CHUNK_SIZE];
    unsigned char idBytes[4];
    unsigned long expectedCrc;
    unsigned long actualCrc = 0;
    unsigned long count;
    unsigned long i;
    long expectedSize;
    long actualSize;

    fp = fopen(path, "rb");
    if (fp == NULL) return 0;
    if ((int)fread(header, 1, sizeof(header), fp) != (int)sizeof(header)) {
        fclose(fp);
        return 0;
    }
    if (memcmp(header, "DJSP", 4) != 0 ||
        dojaSpReadLe16(header + 4) != DOJA_SP_SAVE_VERSION ||
        dojaSpReadLe16(header + 6) != DOJA_SP_CHUNK_SIZE ||
        dojaSpReadLe32(header + 8) != (unsigned long)dojaSpSize() ||
        dojaSpReadLe32(header + 12) != (unsigned long)DOJA_SCRATCHPAD_CRC32) {
        fclose(fp);
        return 0;
    }
    count = dojaSpReadLe32(header + 16);
    expectedCrc = dojaSpReadLe32(header + 20);
    if (count > DOJA_SP_MAX_DIRTY_CHUNKS) {
        fclose(fp);
        return 0;
    }
    expectedSize = DOJA_SP_SAVE_HEADER_SIZE +
                   (long)count * (4 + DOJA_SP_CHUNK_SIZE);
    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return 0;
    }
    actualSize = ftell(fp);
    if (actualSize != expectedSize ||
        fseek(fp, DOJA_SP_SAVE_HEADER_SIZE, SEEK_SET) != 0) {
        fclose(fp);
        return 0;
    }
    for (i = 0; i < count; i++) {
        if ((int)fread(idBytes, 1, 4, fp) != 4 ||
            (int)fread(buffer, 1, DOJA_SP_CHUNK_SIZE, fp) != DOJA_SP_CHUNK_SIZE) {
            fclose(fp);
            return 0;
        }
        actualCrc = dojaSpCrc32Update(actualCrc, idBytes, 4);
        actualCrc = dojaSpCrc32Update(actualCrc, buffer, DOJA_SP_CHUNK_SIZE);
    }
    fclose(fp);
    return actualCrc == expectedCrc;
}

static int dojaSpCopyFile(const char *source, const char *destination) {
    FILE *in;
    FILE *out;
    unsigned char buffer[512];
    size_t count;
    int ok = 1;

    in = fopen(source, "rb");
    if (in == NULL) return 0;
    out = fopen(destination, "wb");
    if (out == NULL) {
        fclose(in);
        return 0;
    }
    while ((count = fread(buffer, 1, sizeof(buffer), in)) > 0) {
        if (fwrite(buffer, 1, count, out) != count) {
            ok = 0;
            break;
        }
    }
    if (ferror(in)) ok = 0;
    if (fflush(out) != 0) ok = 0;
    if (fclose(out) != 0) ok = 0;
    fclose(in);
    return ok;
}

static int dojaSpLoadFile(const char *path) {
    FILE *fp;
    unsigned char header[DOJA_SP_SAVE_HEADER_SIZE];
    unsigned long expectedCrc;
    unsigned long actualCrc = 0;
    unsigned long count;
    long expectedSize;
    long actualSize;
    unsigned long i;

    fp = fopen(path, "rb");
    if (fp == NULL) return 0;
    if ((int)fread(header, 1, sizeof(header), fp) != (int)sizeof(header)) {
        fclose(fp);
        return 0;
    }
    if (memcmp(header, "DJSP", 4) != 0 ||
        dojaSpReadLe16(header + 4) != DOJA_SP_SAVE_VERSION ||
        dojaSpReadLe16(header + 6) != DOJA_SP_CHUNK_SIZE ||
        dojaSpReadLe32(header + 8) != (unsigned long)dojaSpSize() ||
        dojaSpReadLe32(header + 12) != (unsigned long)DOJA_SCRATCHPAD_CRC32) {
        fclose(fp);
        return 0;
    }
    count = dojaSpReadLe32(header + 16);
    expectedCrc = dojaSpReadLe32(header + 20);
    if (count > DOJA_SP_MAX_DIRTY_CHUNKS) {
        fclose(fp);
        return 0;
    }
    expectedSize = DOJA_SP_SAVE_HEADER_SIZE +
                   (long)count * (4 + DOJA_SP_CHUNK_SIZE);
    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return 0;
    }
    actualSize = ftell(fp);
    if (actualSize != expectedSize || fseek(fp, DOJA_SP_SAVE_HEADER_SIZE,
                                            SEEK_SET) != 0) {
        fclose(fp);
        return 0;
    }

    dojaSpResetOverlay();
    for (i = 0; i < count; i++) {
        unsigned char idBytes[4];
        unsigned long id;
        unsigned long j;
        if ((int)fread(idBytes, 1, 4, fp) != 4) goto invalid;
        id = dojaSpReadLe32(idBytes);
        if (id >= (unsigned long)((dojaSpSize() + DOJA_SP_CHUNK_SIZE - 1) /
                                  DOJA_SP_CHUNK_SIZE)) goto invalid;
        for (j = 0; j < i; j++) {
            if ((unsigned long)dojaSpChunkIds[j] == id) goto invalid;
        }
        dojaSpChunkIds[i] = (int)id;
        if ((int)fread(dojaSpChunks[i], 1, DOJA_SP_CHUNK_SIZE, fp) !=
                DOJA_SP_CHUNK_SIZE) goto invalid;
        actualCrc = dojaSpCrc32Update(actualCrc, idBytes, 4);
        actualCrc = dojaSpCrc32Update(actualCrc, dojaSpChunks[i],
                                      DOJA_SP_CHUNK_SIZE);
        dojaSpChunkCount++;
    }
    fclose(fp);
    if (actualCrc != expectedCrc) {
        dojaSpResetOverlay();
        return 0;
    }
    dojaSpDirty = 0;
    return dojaSpChunkCount + 1; /* 1 means a valid empty save. */

invalid:
    fclose(fp);
    dojaSpResetOverlay();
    return 0;
}

static int dojaSpWriteOverlayFile(const char *path) {
    FILE *fp;
    unsigned char header[DOJA_SP_SAVE_HEADER_SIZE];
    unsigned char idBytes[4];
    unsigned long payloadCrc;
    int i;

    payloadCrc = dojaSpPayloadCrc();
    memset(header, 0, sizeof(header));
    memcpy(header, "DJSP", 4);
    dojaSpWriteLe16(header + 4, DOJA_SP_SAVE_VERSION);
    dojaSpWriteLe16(header + 6, DOJA_SP_CHUNK_SIZE);
    dojaSpWriteLe32(header + 8, (unsigned long)dojaSpSize());
    dojaSpWriteLe32(header + 12, (unsigned long)DOJA_SCRATCHPAD_CRC32);
    dojaSpWriteLe32(header + 16, (unsigned long)dojaSpChunkCount);
    dojaSpWriteLe32(header + 20, payloadCrc);

    errno = 0;
    fp = fopen(path, "wb");
    if (fp == NULL) return -2;
    if ((int)fwrite(header, 1, sizeof(header), fp) != (int)sizeof(header)) {
        fclose(fp);
        return -3;
    }
    for (i = 0; i < dojaSpChunkCount; i++) {
        dojaSpWriteLe32(idBytes, (unsigned long)dojaSpChunkIds[i]);
        if ((int)fwrite(idBytes, 1, 4, fp) != 4 ||
            (int)fwrite(dojaSpChunks[i], 1, DOJA_SP_CHUNK_SIZE, fp) !=
                DOJA_SP_CHUNK_SIZE) {
            fclose(fp);
            return -4;
        }
    }
    if (fflush(fp) != 0) {
        fclose(fp);
        return -5;
    }
    if (fclose(fp) != 0) return -6;
    return 1;
}

int dojaSpPersistenceFlush(void) {
    int writeResult;
    int renamed = 0;

    if (!dojaSpDirty) return 0;
    if (!dojaSpPersistenceReady && !dojaSpEnsurePersistence()) {
        /* RAM-VIRTUAL is a successful save backend, not a failed fallback.
         * The sparse overlay is already updated and immediately readable by
         * the game.  Return success even when no persistent media exists. */
        if (!dojaSpRamBufferReported) {
            dojaSaveUiBuffered(dojaSpChunkCount);
            dojaSpRamBufferReported = 1;
        }
        return 1;
    }
    dojaSaveUiSaving(0);

    /* First use a sibling temporary file.
       If the launcher cannot create/verify it, fall back to a direct verified
       write of the final .sav file instead of silently losing the save. */
    writeResult = dojaSpWriteOverlayFile(dojaSpTempPath);
    if (writeResult < 0 || !dojaSpValidateFile(dojaSpTempPath)) {
        remove(dojaSpTempPath);
        writeResult = dojaSpWriteOverlayFile(dojaSpSavePath);
        if (writeResult < 0) return dojaSpFail(writeResult);
        if (!dojaSpValidateFile(dojaSpSavePath)) return dojaSpFail(-9);
        dojaSpDirty = 0;
        dojaSaveUiResult(1, 0, 2); /* direct-write fallback */
        return 1;
    }

    /* Prefer rename after a verified temporary write. If rename/copy is not
       supported by this DLDI driver, perform one direct verified final write. */
    remove(dojaSpSavePath);
    if (rename(dojaSpTempPath, dojaSpSavePath) == 0) {
        renamed = 1;
    } else if (!dojaSpCopyFile(dojaSpTempPath, dojaSpSavePath)) {
        writeResult = dojaSpWriteOverlayFile(dojaSpSavePath);
        if (writeResult < 0) return dojaSpFail(-8);
    }
    if (!dojaSpValidateFile(dojaSpSavePath)) {
        writeResult = dojaSpWriteOverlayFile(dojaSpSavePath);
        if (writeResult < 0 || !dojaSpValidateFile(dojaSpSavePath)) {
            return dojaSpFail(-9);
        }
    }
    if (!renamed) remove(dojaSpTempPath);
    dojaSpDirty = 0;
    dojaSaveUiResult(1, 0, 1);
    return 1;
}

int dojaSpPersistenceInit(const char *path) {
    int loaded;
    if (!dojaSpConfigurePersistencePath(path)) return -1;
    dojaSpStorageUnavailable = 0;
    dojaSpRamBufferReported = 0;
    dojaSpResetOverlay();

    loaded = dojaSpLoadFile(dojaSpSavePath);
    if (loaded > 0) {
        remove(dojaSpTempPath);
        return dojaSpChunkCount;
    }
    loaded = dojaSpLoadFile(dojaSpTempPath);
    if (loaded > 0) {
        dojaSpDirty = 1;
        dojaSpPersistenceFlush();
        return dojaSpChunkCount;
    }
    if (dojaSpLegacyPath[0] != 0) {
        loaded = dojaSpLoadFile(dojaSpLegacyPath);
        if (loaded > 0) {
            dojaSpDirty = 1;
            dojaSpPersistenceFlush();
            return dojaSpChunkCount;
        }
    }
    dojaSpResetOverlay();
    return 0;
}

void Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeSize(void) {
    pushStack(dojaSpSize());
}

void Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeRead(void) {
    int position = popStack();
    int size = dojaSpSize();
    if (position < 0 || position >= size) pushStack(-1);
    else pushStack(dojaSpReadAt(position));
}

void Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeReadBytes(void) {
    int length = popStack();
    int offset = popStack();
    BYTEARRAY bytes = popStackAsType(BYTEARRAY);
    int position = popStack();
    int size = dojaSpSize();
    int available;
    int i;

    if (bytes == NULL) {
        raiseException(NullPointerException);
        return;
    }
    if (position < 0 || offset < 0 || length < 0 ||
        offset > (int)bytes->length || length > (int)bytes->length - offset) {
        raiseException(IndexOutOfBoundsException);
        return;
    }
    if (length == 0) { pushStack(0); return; }
    if (position >= size) { pushStack(-1); return; }
    available = size - position;
    if (length > available) length = available;
    if (dojaSpBaseRead(position, &bytes->bdata[offset], length) != length) {
        raiseException(IOException);
        return;
    }
    if (dojaSpChunkCount > 0) {
        for (i = 0; i < length; i++) {
            int chunk = dojaSpFindChunk((position + i) / DOJA_SP_CHUNK_SIZE, 0);
            if (chunk >= 0) {
                bytes->bdata[offset + i] =
                    dojaSpChunks[chunk][(position + i) % DOJA_SP_CHUNK_SIZE];
            }
        }
    }
    pushStack(length);
}

void Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeWrite(void) {
    int value = popStack();
    int position = popStack();
    int size = dojaSpSize();
    int chunk;
    if (position < 0 || position >= size) return;
    /* v48 Empty: single-byte writes always succeed in the RAM overlay. */
    chunk = dojaSpFindChunk(position / DOJA_SP_CHUNK_SIZE, 1);
    if (chunk >= 0) {
        dojaSpChunks[chunk][position % DOJA_SP_CHUNK_SIZE] =
            (unsigned char)value;
        dojaSpDirty = 1;
    }
}

void Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeWriteBytes(void) {
    int length = popStack();
    int offset = popStack();
    BYTEARRAY bytes = popStackAsType(BYTEARRAY);
    int position = popStack();
    int size = dojaSpSize();
    int i;
    int wrote = 0;
    if (bytes == NULL) { raiseException(NullPointerException); return; }
    if (position < 0 || offset < 0 || length < 0 ||
        offset > (int)bytes->length || length > (int)bytes->length - offset) {
        raiseException(IndexOutOfBoundsException);
        return;
    }
    if (position >= size) return;
    if (length > size - position) length = size - position;
    /* Buffer into RAM first; physical persistence is optional. */
    for (i = 0; i < length; i++) {
        int absolute = position + i;
        int chunk = dojaSpFindChunk(absolute / DOJA_SP_CHUNK_SIZE, 1);
        if (chunk >= 0) {
            dojaSpChunks[chunk][absolute % DOJA_SP_CHUNK_SIZE] =
                bytes->bdata[offset + i];
            wrote = 1;
        }
    }
    if (wrote) {
        dojaSpDirty = 1;
        /* One bounded persistence attempt at the bulk-write boundary. */
        dojaSpPersistenceFlush();
    }
}

void Java_com_sun_cldc_io_j2me_scratchpad_Protocol_nativeFlush(void) {
    pushStack(dojaSpPersistenceFlush());
}



/* DoJa v56: raw RFC1951 inflater bridge for JarInflater.
 * The output is decoded into stable C memory while the KVM inflater may
 * allocate temporary Huffman tables, then copied back to the rooted byte[]. */
typedef struct DoJaNativeInflateInput {
    const unsigned char *cursor;
    int remaining;
} DoJaNativeInflateInput;

static int dojaNativeInflateGetBytes(unsigned char *dst, int length, void *info) {
    DoJaNativeInflateInput *input = (DoJaNativeInflateInput *)info;
    int count = length;
    if (input == NULL || dst == NULL || length <= 0) return 0;
    if (count > input->remaining) count = input->remaining;
    if (count > 0) {
        memcpy(dst, input->cursor, count);
        input->cursor += count;
        input->remaining -= count;
    }
    return count;
}

void Java_com_nttdocomo_util_NativeInflater_inflate(void) {
    BYTEARRAY output = popStackAsType(BYTEARRAY);
    int compressedLength = popStack();
    int offset = popStack();
    BYTEARRAY input = popStackAsType(BYTEARRAY);
    unsigned char *compressed = NULL;
    unsigned char *decoded = NULL;
    unsigned char *decodedHandle;
    DoJaNativeInflateInput source;
    int expected;
    int ok = 0;

    if (input == NULL || output == NULL) {
        raiseException(NullPointerException);
        return;
    }
    expected = (int)output->length;
    if (offset < 0 || compressedLength < 0 ||
        offset > (int)input->length ||
        compressedLength > (int)input->length - offset) {
        raiseException(IndexOutOfBoundsException);
        return;
    }

    compressed = (unsigned char *)malloc((size_t)compressedLength + INFLATER_EXTRA_BYTES);
    decoded = (unsigned char *)malloc(expected > 0 ? (size_t)expected : 1U);
    if (compressed == NULL || decoded == NULL) {
        if (compressed != NULL) free(compressed);
        if (decoded != NULL) free(decoded);
        pushStack(-1);
        return;
    }

    if (compressedLength > 0)
        memcpy(compressed, &input->bdata[offset], compressedLength);
    memset(compressed + compressedLength, 0, INFLATER_EXTRA_BYTES);

    source.cursor = compressed;
    source.remaining = compressedLength + INFLATER_EXTRA_BYTES;
    decodedHandle = decoded;

    START_TEMPORARY_ROOTS
        DECLARE_TEMPORARY_ROOT(BYTEARRAY, outputRoot, output);
        ok = inflateData(&source,
                         (JarGetByteFunctionType)dojaNativeInflateGetBytes,
                         compressedLength, &decodedHandle, expected);
        output = outputRoot;
        if (ok && expected > 0) {
            memcpy(output->bdata, decoded, expected);
        }
    END_TEMPORARY_ROOTS

    free(decoded);
    free(compressed);
    pushStack(ok ? expected : -1);
}
