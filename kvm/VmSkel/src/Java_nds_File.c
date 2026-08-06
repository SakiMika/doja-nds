#include <nds.h>
#include <nds/arm9/video.h>
#include <kni.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fat.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>

#include "standalone_game.h"

/*
 * libnds 2.x uses libdvm behind the libfat-compatible API.  Legacy private
 * device getters are no longer exported to applications. Use fatInitDefault(),
 * which asks libdvm to initialize and mount available DLDI and DSi-SD block
 * devices as fat:/ and sd:/.
 */

/*
 * Keep the standalone target buildable even if an older metadata generator
 * rewrites standalone_game.h without the save-path macro. Adjacent string
 * literals are concatenated by the C compiler.
 */
#ifndef STANDALONE_OUTPUT_BASENAME
#define STANDALONE_OUTPUT_BASENAME "standalone_game"
#endif
#ifndef STANDALONE_SAVE_PATH
#define STANDALONE_SAVE_PATH "fat:/" STANDALONE_OUTPUT_BASENAME ".sav"
#endif
#ifndef STANDALONE_RMS_SAVE_PATH
#define STANDALONE_RMS_SAVE_PATH "fat:/" STANDALONE_OUTPUT_BASENAME ".rms"
#endif
#ifndef STANDALONE_LEGACY_SAVE_PATH
#define STANDALONE_LEGACY_SAVE_PATH "fat:/" STANDALONE_OUTPUT_BASENAME ".djs"
#endif

#define NDS_FILE_PATH_MAX 255
#define NDS_FILE_IO_CHUNK 512

#ifndef STANDALONE_RMS_FILTER_ENABLED
#define STANDALONE_RMS_FILTER_ENABLED 0
#endif
#ifndef STANDALONE_RMS_STORE_1
#define STANDALONE_RMS_STORE_1 ""
#endif
#ifndef STANDALONE_RMS_STORE_2
#define STANDALONE_RMS_STORE_2 ""
#endif

#define PSTROS_RMS_MAGIC 0x5053524dUL /* PSRM */
#define PSTROS_RMS_VERSION 2

static unsigned int pstrosReadBe16(const unsigned char *p) {
    return ((unsigned int)p[0] << 8) | (unsigned int)p[1];
}

static unsigned long pstrosReadBe32(const unsigned char *p) {
    return ((unsigned long)p[0] << 24) |
           ((unsigned long)p[1] << 16) |
           ((unsigned long)p[2] << 8) |
           (unsigned long)p[3];
}

static void pstrosWriteBe16(unsigned char *p, unsigned int value) {
    p[0] = (unsigned char)((value >> 8) & 0xff);
    p[1] = (unsigned char)(value & 0xff);
}

static void pstrosWriteBe32(unsigned char *p, unsigned long value) {
    p[0] = (unsigned char)((value >> 24) & 0xff);
    p[1] = (unsigned char)((value >> 16) & 0xff);
    p[2] = (unsigned char)((value >> 8) & 0xff);
    p[3] = (unsigned char)(value & 0xff);
}

static int pstrosUtfEqualsAscii(const unsigned char *utf, int utfLen,
                                const char *ascii) {
    int asciiLen;
    if (utf == NULL || ascii == NULL) {
        return 0;
    }
    asciiLen = (int)strlen(ascii);
    return utfLen == asciiLen && memcmp(utf, ascii, utfLen) == 0;
}

static int pstrosKeepRmsGroup(const unsigned char *name, int nameLen) {
#if STANDALONE_RMS_FILTER_ENABLED
    return pstrosUtfEqualsAscii(name, nameLen, STANDALONE_RMS_STORE_1) ||
           pstrosUtfEqualsAscii(name, nameLen, STANDALONE_RMS_STORE_2);
#else
    (void)name;
    (void)nameLen;
    return 1;
#endif
}

/*
 * Diamond Rush contains Gameloft registration/demo stores (generalInfo and
 * bonuses) alongside the actual gameplay stores. Persisting those device/time
 * values makes the redistributed build terminate normally on the next boot.
 *
 * Pstros NDS currently ROMizes an older RmsManager implementation whose file
 * begins directly with a 16-bit group count. Newer source trees use the PSRM
 * magic/version header. Support both formats here because this native layer is
 * the last point before bytes reach FAT and the first point after they return.
 */
static int pstrosFilterLegacyRmsInPlace(unsigned char *data, int length) {
    int inputPos = 2;
    int groupCount;
    int i;
    int store1Start = -1;
    int store1Len = 0;
    int store2Start = -1;
    int store2Len = 0;
    unsigned char *tmp;
    int outputPos = 2;

    if (data == NULL || length < 2) return -1;
    groupCount = (int)pstrosReadBe16(data);

    for (i = 0; i < groupCount; i++) {
        int groupStart = inputPos;
        int nameLen;
        const unsigned char *name;
        int recordCount;
        int j;

        if (inputPos + 2 > length) return -1;
        nameLen = (int)pstrosReadBe16(data + inputPos);
        inputPos += 2;
        if (nameLen < 0 || inputPos + nameLen > length) return -1;
        name = data + inputPos;
        inputPos += nameLen;

        if (inputPos + 3 > length) return -1;
        inputPos += 1; /* public flag */
        recordCount = (int)pstrosReadBe16(data + inputPos);
        inputPos += 2;

        for (j = 0; j < recordCount; j++) {
            unsigned long recordLen;
            if (inputPos + 4 > length) return -1;
            recordLen = pstrosReadBe32(data + inputPos);
            inputPos += 4;
            if (recordLen > (unsigned long)(length - inputPos)) return -1;
            inputPos += (int)recordLen;
        }

        if (pstrosUtfEqualsAscii(name, nameLen, STANDALONE_RMS_STORE_1)) {
            store1Start = groupStart;
            store1Len = inputPos - groupStart;
        } else if (pstrosUtfEqualsAscii(name, nameLen, STANDALONE_RMS_STORE_2)) {
            store2Start = groupStart;
            store2Len = inputPos - groupStart;
        }
    }

    if (inputPos != length) return -1;

#if STANDALONE_RMS_FILTER_ENABLED
    /* Diamond Rush expects the same stable legacy layout as the confirmed
     * working save: Preferences first, then DiamondRush. Canonicalizing the
     * order also prevents early RecordStore creation order from changing the
     * next-boot behaviour. */
    tmp = (unsigned char *)malloc(length > 0 ? length : 1);
    if (tmp == NULL) return -1;
    pstrosWriteBe16(tmp, 0);
    if (store2Start >= 0) {
        memcpy(tmp + outputPos, data + store2Start, store2Len);
        outputPos += store2Len;
    }
    if (store1Start >= 0) {
        memcpy(tmp + outputPos, data + store1Start, store1Len);
        outputPos += store1Len;
    }
    pstrosWriteBe16(tmp, (unsigned int)((store2Start >= 0 ? 1 : 0) +
                                        (store1Start >= 0 ? 1 : 0)));
    memcpy(data, tmp, outputPos);
    free(tmp);
    return outputPos;
#else
    (void)tmp;
    return length;
#endif
}

static int pstrosFilterVersionedRmsInPlace(unsigned char *data, int length) {
    int inputPos;
    int outputPos;
    int groupCount;
    int keptCount = 0;
    int i;

    if (length < 8 || pstrosReadBe16(data + 4) != PSTROS_RMS_VERSION) {
        return -1;
    }

    groupCount = (int)pstrosReadBe16(data + 6);
    inputPos = 8;
    outputPos = 8;

    for (i = 0; i < groupCount; i++) {
        int groupStart = inputPos;
        int appLen;
        int nameLen;
        const unsigned char *name;
        int recordCount;
        int j;
        int keep;

        if (inputPos + 2 > length) return -1;
        appLen = (int)pstrosReadBe16(data + inputPos);
        inputPos += 2;
        if (appLen < 0 || inputPos + appLen > length) return -1;
        inputPos += appLen;

        if (inputPos + 2 > length) return -1;
        nameLen = (int)pstrosReadBe16(data + inputPos);
        inputPos += 2;
        if (nameLen < 0 || inputPos + nameLen > length) return -1;
        name = data + inputPos;
        inputPos += nameLen;
        keep = pstrosKeepRmsGroup(name, nameLen);

        /* public flag + nextRecordId + record count */
        if (inputPos + 7 > length) return -1;
        inputPos += 1;
        inputPos += 4;
        recordCount = (int)pstrosReadBe16(data + inputPos);
        inputPos += 2;

        for (j = 0; j < recordCount; j++) {
            unsigned long recordLen;
            if (inputPos + 8 > length) return -1;
            recordLen = pstrosReadBe32(data + inputPos + 4);
            inputPos += 8;
            if (recordLen > (unsigned long)(length - inputPos)) return -1;
            inputPos += (int)recordLen;
        }

        if (keep) {
            int groupLen = inputPos - groupStart;
            if (outputPos != groupStart) {
                memmove(data + outputPos, data + groupStart, groupLen);
            }
            outputPos += groupLen;
            keptCount++;
        }
    }

    if (inputPos != length) return -1;
    pstrosWriteBe16(data + 6, (unsigned int)keptCount);
    return outputPos;
}

static int pstrosFilterRmsInPlace(unsigned char *data, int length) {
#if !STANDALONE_RMS_FILTER_ENABLED
    return length;
#else
    if (data == NULL || length < 2) return length;
    if (length >= 4 && pstrosReadBe32(data) == PSTROS_RMS_MAGIC) {
        return pstrosFilterVersionedRmsInPlace(data, length);
    }
    return pstrosFilterLegacyRmsInPlace(data, length);
#endif
}

/*
 * A fresh Diamond Rush boot creates several RMS groups in sequence. Autosave
 * fires after every RecordStore mutation, so the early snapshots contain no
 * usable gameplay data yet. Writing one of those partial snapshots creates a
 * file that is syntactically valid but makes the next boot take the wrong
 * initialization path. Persist only after both allowed stores exist and each
 * contains at least one non-empty record.
 */
static int pstrosLegacyRmsReady(const unsigned char *data, int length) {
    int pos = 2;
    int groups;
    int havePreferences = 0;
    int haveDiamondRush = 0;
    int i;

    if (data == NULL || length < 2) return 0;
    groups = (int)pstrosReadBe16(data);
    if (groups != 2) return 0;

    for (i = 0; i < groups; i++) {
        int nameLen;
        const unsigned char *name;
        int records;
        int firstPayloadLen = -1;
        int j;

        if (pos + 2 > length) return 0;
        nameLen = (int)pstrosReadBe16(data + pos);
        pos += 2;
        if (nameLen < 0 || pos + nameLen > length) return 0;
        name = data + pos;
        pos += nameLen;

        if (pos + 3 > length) return 0;
        pos += 1;
        records = (int)pstrosReadBe16(data + pos);
        pos += 2;
        if (records < 1) return 0;

        for (j = 0; j < records; j++) {
            unsigned long recordLen;
            if (pos + 4 > length) return 0;
            recordLen = pstrosReadBe32(data + pos);
            pos += 4;
            if (recordLen > (unsigned long)(length - pos)) return 0;
            if (j == 0) firstPayloadLen = (int)recordLen;
            pos += (int)recordLen;
        }

        if (i == 0 &&
            pstrosUtfEqualsAscii(name, nameLen, STANDALONE_RMS_STORE_2) &&
            firstPayloadLen >= 1) {
            havePreferences = 1;
        } else if (i == 1 &&
                   pstrosUtfEqualsAscii(name, nameLen, STANDALONE_RMS_STORE_1) &&
                   firstPayloadLen >= 900) {
            /* The confirmed working Diamond Rush record is 994 bytes. A
             * threshold safely rejects small bootstrap snapshots while still
             * allowing compatible revisions with a slightly larger payload. */
            haveDiamondRush = 1;
        }
    }

    return pos == length && havePreferences && haveDiamondRush;
}

static int pstrosVersionedRmsReady(const unsigned char *data, int length) {
    int pos = 8;
    int groups;
    int haveStore1 = 0;
    int haveStore2 = 0;
    int i;

    if (data == NULL || length < 8 ||
        pstrosReadBe32(data) != PSTROS_RMS_MAGIC ||
        pstrosReadBe16(data + 4) != PSTROS_RMS_VERSION) {
        return 0;
    }
    groups = (int)pstrosReadBe16(data + 6);

    for (i = 0; i < groups; i++) {
        int appLen;
        int nameLen;
        const unsigned char *name;
        int records;
        int hasPayload = 0;
        int j;

        if (pos + 2 > length) return 0;
        appLen = (int)pstrosReadBe16(data + pos);
        pos += 2;
        if (appLen < 0 || pos + appLen > length) return 0;
        pos += appLen;

        if (pos + 2 > length) return 0;
        nameLen = (int)pstrosReadBe16(data + pos);
        pos += 2;
        if (nameLen < 0 || pos + nameLen > length) return 0;
        name = data + pos;
        pos += nameLen;

        if (pos + 7 > length) return 0;
        pos += 1; /* public flag */
        pos += 4; /* nextRecordId */
        records = (int)pstrosReadBe16(data + pos);
        pos += 2;

        for (j = 0; j < records; j++) {
            unsigned long recordLen;
            if (pos + 8 > length) return 0;
            pos += 4; /* record id */
            recordLen = pstrosReadBe32(data + pos);
            pos += 4;
            if (recordLen > (unsigned long)(length - pos)) return 0;
            if (recordLen > 0) hasPayload = 1;
            pos += (int)recordLen;
        }

        if (hasPayload && pstrosUtfEqualsAscii(name, nameLen, STANDALONE_RMS_STORE_1)) {
            haveStore1 = 1;
        }
        if (hasPayload && pstrosUtfEqualsAscii(name, nameLen, STANDALONE_RMS_STORE_2)) {
            haveStore2 = 1;
        }
    }

    return pos == length && haveStore1 && haveStore2;
}

static int pstrosRmsReadyToPersist(const unsigned char *data, int length) {
#if !STANDALONE_RMS_FILTER_ENABLED
    (void)data;
    (void)length;
    return 1;
#else
    if (data == NULL || length < 2) return 0;
    if (length >= 4 && pstrosReadBe32(data) == PSTROS_RMS_MAGIC) {
        return pstrosVersionedRmsReady(data, length);
    }
    return pstrosLegacyRmsReady(data, length);
#endif
}

static void pstrosMakeEmptyRms(unsigned char *data) {
    pstrosWriteBe32(data, PSTROS_RMS_MAGIC);
    pstrosWriteBe16(data + 4, PSTROS_RMS_VERSION);
    pstrosWriteBe16(data + 6, 0);
}

/*
 * DoJa v41 same-name .sav storage selection.
 *
 * The v27-v30 backends called legacy private device getters directly. Those
 * symbols are not exported by the current Calico/libdvm stack, so the final
 * link failed even though every C file compiled.
 *
 * v41 keeps the supported libfat compatibility entry point fatInitDefault().
 * On libnds 2.x this delegates to libdvm, initializes the block-device layer,
 * and mounts DLDI as fat:/ plus DSi SD as sd:/ when available.  We first probe
 * any volume already registered by the launcher, then initialize libdvm once,
 * then repeat the same write/read verification.  Save writes continue to use
 * normal stdio and never depend on private storage symbols.
 */
static char pstrosSavePath[NDS_FILE_PATH_MAX + 1] = STANDALONE_SAVE_PATH;
static char pstrosRmsSavePath[NDS_FILE_PATH_MAX + 1] = STANDALONE_RMS_SAVE_PATH;
static char pstrosLaunchSavePath[NDS_FILE_PATH_MAX + 1] = "";
static char pstrosSaveBackend[12] = "NONE";
static int pstrosSaveErrno = 0;
static int pstrosSaveStage = 0;
static int pstrosSaveConfigured = 0;
static int pstrosPreferredBackend = 0; /* 1=DLDI/fat, 2=DSi-SD/sd */
static int pstrosFatInitAttempted = 0;
/* v41: one complete mount attempt per boot. A missing melonDS SD/DLDI
 * device must not be probed again for every ScratchPad byte written. */
static int pstrosSaveProbeLocked = 0;

static int pstrosAsciiLower(int c) {
    if (c >= 'A' && c <= 'Z') return c + ('a' - 'A');
    return c;
}

static int pstrosPathStartsWithNoCase(const char *path, const char *prefix) {
    if (path == NULL || prefix == NULL) return 0;
    while (*prefix != 0) {
        if (*path == 0 || pstrosAsciiLower((unsigned char)*path) !=
                          pstrosAsciiLower((unsigned char)*prefix)) return 0;
        path++;
        prefix++;
    }
    return 1;
}

static void pstrosRememberLaunchSavePath(const char *launchPath) {
    const char *lastSlash;
    const char *lastDot;
    size_t length;

    if (launchPath == NULL || launchPath[0] == 0) return;
    if (!pstrosPathStartsWithNoCase(launchPath, "fat:/") &&
        !pstrosPathStartsWithNoCase(launchPath, "sd:/") &&
        !pstrosPathStartsWithNoCase(launchPath, "sdmc:/")) return;

    snprintf(pstrosLaunchSavePath, sizeof(pstrosLaunchSavePath), "%s", launchPath);
    if (pstrosPathStartsWithNoCase(pstrosLaunchSavePath, "sdmc:/")) {
        memmove(pstrosLaunchSavePath + 3, pstrosLaunchSavePath + 5,
                strlen(pstrosLaunchSavePath + 5) + 1);
        memcpy(pstrosLaunchSavePath, "sd:", 3);
    }

    lastSlash = strrchr(pstrosLaunchSavePath, '/');
    lastDot = strrchr(pstrosLaunchSavePath, '.');
    if (lastDot != NULL && (lastSlash == NULL || lastDot > lastSlash)) {
        length = (size_t)(lastDot - pstrosLaunchSavePath);
        if (length + 4 < sizeof(pstrosLaunchSavePath)) {
            memcpy(pstrosLaunchSavePath + length, ".sav", 5);
        } else {
            pstrosLaunchSavePath[0] = 0;
        }
    } else {
        length = strlen(pstrosLaunchSavePath);
        if (length + 4 < sizeof(pstrosLaunchSavePath)) {
            memcpy(pstrosLaunchSavePath + length, ".sav", 5);
        } else {
            pstrosLaunchSavePath[0] = 0;
        }
    }
}

static int pstrosLaunchPathMatchesVolume(const char *volume) {
    char prefix[8];
    if (volume == NULL || pstrosLaunchSavePath[0] == 0) return 0;
    snprintf(prefix, sizeof(prefix), "%s:/", volume);
    return pstrosPathStartsWithNoCase(pstrosLaunchSavePath, prefix);
}

static void pstrosChooseFinalSavePath(char *out, int outSize, const char *volume) {
    if (pstrosLaunchPathMatchesVolume(volume)) {
        snprintf(out, outSize, "%s", pstrosLaunchSavePath);
    } else {
        snprintf(out, outSize, "%s:/%s", volume, STANDALONE_SHORT_SAVE_NAME);
    }
}

static void pstrosSetRmsPathFromSave(void) {
    size_t pathLen;
    snprintf(pstrosRmsSavePath, sizeof(pstrosRmsSavePath), "%s", pstrosSavePath);
    pathLen = strlen(pstrosRmsSavePath);
    if (pathLen >= 4 && pstrosRmsSavePath[pathLen - 4] == '.') {
        memcpy(pstrosRmsSavePath + pathLen - 4, ".RMS", 5);
    } else {
        snprintf(pstrosRmsSavePath, sizeof(pstrosRmsSavePath), "%s",
                 STANDALONE_RMS_SAVE_PATH);
    }
}

static void pstrosMakeProbeName(char *out, int outSize,
                                const char *volume, const char *finalPath) {
    const char *slash;
    size_t dirLength;
    char shortName[32];
    size_t length;

    snprintf(shortName, sizeof(shortName), "%s", STANDALONE_SHORT_SAVE_NAME);
    length = strlen(shortName);
    if (length >= 4 && shortName[length - 4] == '.') {
        memcpy(shortName + length - 4, ".TST", 5);
    } else {
        snprintf(shortName, sizeof(shortName), "DOJASAVE.TST");
    }

    slash = finalPath != NULL ? strrchr(finalPath, '/') : NULL;
    if (slash != NULL) {
        dirLength = (size_t)(slash - finalPath + 1);
        if (dirLength + strlen(shortName) < (size_t)outSize) {
            memcpy(out, finalPath, dirLength);
            snprintf(out + dirLength, outSize - (int)dirLength, "%s", shortName);
            return;
        }
    }
    snprintf(out, outSize, "%s:/%s", volume, shortName);
}

/* Verify the complete stdio route, not merely volume registration. */
static int pstrosConfigureSaveStorageOn(const char *volume, const char *backend) {
    char probePath[NDS_FILE_PATH_MAX + 1];
    char finalPath[NDS_FILE_PATH_MAX + 1];
    static const unsigned char probeBytes[4] = { 'S', 'V', '3', '8' };
    unsigned char verifyBytes[4];
    FILE *fp;
    int savedErrno = 0;

    if (volume == NULL || backend == NULL) return 0;
    pstrosChooseFinalSavePath(finalPath, sizeof(finalPath), volume);
    pstrosMakeProbeName(probePath, sizeof(probePath), volume, finalPath);

    errno = 0;
    fp = fopen(probePath, "wb");
    if (fp == NULL) {
        pstrosSaveErrno = errno != 0 ? errno : EIO;
        return 0;
    }
    if (fwrite(probeBytes, 1, sizeof(probeBytes), fp) != sizeof(probeBytes)) {
        savedErrno = errno != 0 ? errno : EIO;
        fclose(fp);
        remove(probePath);
        pstrosSaveErrno = savedErrno;
        return 0;
    }
    if (fflush(fp) != 0) {
        savedErrno = errno != 0 ? errno : EIO;
        fclose(fp);
        remove(probePath);
        pstrosSaveErrno = savedErrno;
        return 0;
    }
    if (fclose(fp) != 0) {
        savedErrno = errno != 0 ? errno : EIO;
        remove(probePath);
        pstrosSaveErrno = savedErrno;
        return 0;
    }

    errno = 0;
    fp = fopen(probePath, "rb");
    if (fp == NULL ||
        fread(verifyBytes, 1, sizeof(verifyBytes), fp) != sizeof(verifyBytes) ||
        memcmp(verifyBytes, probeBytes, sizeof(probeBytes)) != 0) {
        savedErrno = errno != 0 ? errno : EIO;
        if (fp != NULL) fclose(fp);
        remove(probePath);
        pstrosSaveErrno = savedErrno;
        return 0;
    }
    if (fclose(fp) != 0) {
        savedErrno = errno != 0 ? errno : EIO;
        remove(probePath);
        pstrosSaveErrno = savedErrno;
        return 0;
    }
    remove(probePath);

    snprintf(pstrosSavePath, sizeof(pstrosSavePath), "%s", finalPath);
    snprintf(pstrosSaveBackend, sizeof(pstrosSaveBackend), "%s", backend);
    pstrosSetRmsPathFromSave();
    pstrosSaveConfigured = 1;
    pstrosSaveErrno = 0;
    pstrosSaveStage = 0;
    return 1;
}

static int pstrosProbeMountedVolumes(int afterInit) {
    const char *fatBackend = afterInit ? "DLDI/FAT" : "FAT-MOUNT";
    const char *sdBackend = afterInit ? "DSI-SD" : "SD-MOUNT";
    int canUseSd = isDSiMode();

    /* A 3DS running this ROM in normal DS/NTR mode cannot access sd:/
       directly. Probing sd:/ there only overwrote the useful DLDI error with
       ENOTSUP (88). The homebrew header now makes TWiLight/flashcart loaders
       DLDI-patch fat:/; sd:/ is tried only in actual DSi mode. */
    if (pstrosPreferredBackend == 2 && canUseSd) {
        pstrosSaveStage = afterInit ? 22 : 10;
        if (pstrosConfigureSaveStorageOn("sd", sdBackend)) return 1;
    }

    pstrosSaveStage = afterInit ? 21 : 10;
    if (pstrosConfigureSaveStorageOn("fat", fatBackend)) {
        pstrosPreferredBackend = 1;
        return 1;
    }

    if (canUseSd && pstrosPreferredBackend != 2) {
        pstrosSaveStage = afterInit ? 22 : 10;
        if (pstrosConfigureSaveStorageOn("sd", sdBackend)) {
            pstrosPreferredBackend = 2;
            return 1;
        }
    }
    return 0;
}

int pstrosMountSaveStorageAuto(const char *launchPath) {
    int preferSd;
    int preferFat;
    int initErr = 0;

    if (pstrosSaveConfigured) return 1;
    if (pstrosSaveProbeLocked) return 0;

    pstrosRememberLaunchSavePath(launchPath);
    preferSd = pstrosPathStartsWithNoCase(launchPath, "sd:/") ||
               pstrosPathStartsWithNoCase(launchPath, "sdmc:/");
    preferFat = pstrosPathStartsWithNoCase(launchPath, "fat:/");
    if (preferSd) pstrosPreferredBackend = 2;
    else if (preferFat) pstrosPreferredBackend = 1;

    pstrosSaveErrno = 0;
    snprintf(pstrosSaveBackend, sizeof(pstrosSaveBackend), "NONE");

    /* A launcher may already have registered one or both devoptab volumes. */
    if (pstrosProbeMountedVolumes(0)) return 1;

    /* Current libnds 2.x exposes block devices through libdvm.  Initialize the
     * supported compatibility layer exactly once; do not call removed private
     * DLDI/DSi-SD getters or construct DISC_INTERFACE objects ourselves. */
    if (!pstrosFatInitAttempted) {
        pstrosFatInitAttempted = 1;
        pstrosSaveStage = 20; /* libdvm/libfat compatibility init */
        errno = 0;
        if (!fatInitDefault()) {
            initErr = errno != 0 ? errno : ENODEV;
        }
    }

    /* fatInitDefault can return false when no new medium was mounted.  Probe
     * the registered names regardless, because a launcher-owned mount may
     * still be usable and because the write/read test is authoritative. */
    if (pstrosProbeMountedVolumes(1)) return 1;

    if (pstrosSaveErrno == 0) {
        pstrosSaveErrno = initErr != 0 ? initErr : ENODEV;
    }
    if (pstrosSaveStage == 0) pstrosSaveStage = 40;
    pstrosSaveProbeLocked = 1;
    return 0;
}

/* v41 deliberately does not re-probe after the complete boot-time attempt.
 * Some i-appli write ScratchPad one byte at a time during startup.
 * Re-running fopen/fatInit probes from that hot path made melonDS
 * appear frozen whenever no DLDI/SD image was attached. */
int pstrosMountSaveStorageDirect(void) {
    if (pstrosSaveConfigured) return 1;
    if (pstrosSaveProbeLocked) return 0;
    return pstrosMountSaveStorageAuto(NULL);
}

const char *pstrosGetSavePath(void) {
    return pstrosSavePath;
}

const char *pstrosGetSaveBackendName(void) {
    return pstrosSaveBackend;
}

int pstrosGetSaveErrno(void) {
    return pstrosSaveErrno;
}

int pstrosGetSaveStage(void) {
    return pstrosSaveStage;
}

/*
 * First-boot policy:
 * Never seed RMS before the MIDlet starts. Diamond Rush must see a genuinely
 * empty RecordStore on its first run. The writer below waits until both
 * gameplay stores are complete before creating the first persistent file.
 */

/*
 * nds_main.c asks the supported libdvm/libfat compatibility layer to expose
 * writable fat:/ or sd:/ storage once before the Java VM. Native RMS calls reuse
 * the verified path and never touch private device-interface symbols.
 */
static int ensure_fat_ready(void) {
    return 1;
}

static void map_standalone_save_path(char *path, int pathSize) {
    size_t len;

    if (path == NULL || pathSize <= 0) {
        return;
    }

    len = strlen(path);
    if (len >= 4 && strcmp(path + len - 4, ".sav") == 0) {
        /* Every standalone ROM owns one RMS file. The path was selected by a
         * real write-open probe before the JVM starts. */
        snprintf(path, pathSize, "%s",
                 pstrosSaveConfigured ? pstrosRmsSavePath : STANDALONE_RMS_SAVE_PATH);
    }
}

static int copy_java_string_to_c(jobject stringHandle, char *out, int outSize) {
    jchar buffer[NDS_FILE_PATH_MAX + 1];
    jsize size;
    int i;

    if (out == NULL || outSize <= 0 || KNI_IsNullHandle(stringHandle)) {
        return -1;
    }

    size = KNI_GetStringLength(stringHandle);
    if (size < 0) {
        return -1;
    }
    if (size >= outSize) {
        size = outSize - 1;
    }

    KNI_GetStringRegion(stringHandle, 0, size, buffer);
    for (i = 0; i < size; i++) {
        out[i] = (char)(buffer[i] & 0xff);
    }
    out[size] = 0;
    map_standalone_save_path(out, outSize);
    return (int)strlen(out);
}

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_File_exists() {
    char path[NDS_FILE_PATH_MAX + 1];
    FILE *fp = NULL;
    int result = KNI_FALSE;

    KNI_StartHandles(1);
    KNI_DeclareHandle(stringHandle);
    KNI_GetParameterAsObject(1, stringHandle);

    if (ensure_fat_ready() && copy_java_string_to_c(stringHandle, path, sizeof(path)) >= 0) {
        fp = fopen(path, "rb");
        if (fp != NULL) {
            result = KNI_TRUE;
            fclose(fp);
        }
    }

    KNI_EndHandles();
    KNI_ReturnBoolean(result);
}

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_File_size() {
    char path[NDS_FILE_PATH_MAX + 1];
    FILE *fp = NULL;
    int result = -1;

    KNI_StartHandles(1);
    KNI_DeclareHandle(stringHandle);
    KNI_GetParameterAsObject(1, stringHandle);

    if (ensure_fat_ready() && copy_java_string_to_c(stringHandle, path, sizeof(path)) >= 0) {
        fp = fopen(path, "rb");
        if (fp != NULL) {
            if (fseek(fp, 0, SEEK_END) == 0) {
                long len = ftell(fp);
                if (len >= 0) {
                    result = (int)len;
                }
            }
            fclose(fp);
        }
    }

    KNI_EndHandles();
    KNI_ReturnInt(result);
}

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_File_load() {
    char path[NDS_FILE_PATH_MAX + 1];
    FILE *fp = NULL;
    int result = -1;
    int requestedMaxLen;
    int arrayLen;
    int got = 0;
    unsigned char *buffer = NULL;

    KNI_StartHandles(2);
    KNI_DeclareHandle(stringHandle);
    KNI_DeclareHandle(arrayHandle);

    KNI_GetParameterAsObject(1, stringHandle);
    KNI_GetParameterAsObject(2, arrayHandle);
    requestedMaxLen = KNI_GetParameterAsInt(3);

    if (!ensure_fat_ready() ||
        copy_java_string_to_c(stringHandle, path, sizeof(path)) < 0 ||
        KNI_IsNullHandle(arrayHandle)) {
        result = -1;
    } else {
        arrayLen = KNI_GetArrayLength(arrayHandle);
        if (requestedMaxLen < 0 || requestedMaxLen > arrayLen) {
            requestedMaxLen = arrayLen;
        }

        buffer = (unsigned char *)malloc(requestedMaxLen > 0 ? requestedMaxLen : 1);
        if (buffer == NULL) {
            result = -2;
        } else {
            fp = fopen(path, "rb");
            if (fp == NULL) {
                result = -1000 - errno;
            } else {
                while (got < requestedMaxLen) {
                    int chunkLen = requestedMaxLen - got;
                    int count;
                    if (chunkLen > NDS_FILE_IO_CHUNK) chunkLen = NDS_FILE_IO_CHUNK;
                    count = (int)fread(buffer + got, 1, chunkLen, fp);
                    if (count > 0) got += count;
                    if (count < chunkLen) break;
                }
                if (ferror(fp)) {
                    result = -2000 - errno;
                } else {
                    int filteredLen = pstrosFilterRmsInPlace(buffer, got);
                    if (filteredLen < 0) {
                        /* A torn/corrupt versioned save must not poison boot. */
                        if (requestedMaxLen >= 8) {
                            pstrosMakeEmptyRms(buffer);
                            filteredLen = 8;
                        } else {
                            filteredLen = 0;
                        }
                    }
                    if (filteredLen > 0) {
                        KNI_SetRawArrayRegion(arrayHandle, 0, filteredLen,
                                              (jbyte *)buffer);
                    }
                    result = filteredLen;
                }
                fclose(fp);
            }
            free(buffer);
        }
    }

    KNI_EndHandles();
    KNI_ReturnInt(result);
}

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_File_save() {
    char path[NDS_FILE_PATH_MAX + 1];
    int fd = -1;
    int result = -1;
    int arrayLen;
    int writeLen;
    int pos = 0;
    unsigned char *buffer = NULL;

    KNI_StartHandles(2);
    KNI_DeclareHandle(stringHandle);
    KNI_DeclareHandle(arrayHandle);

    KNI_GetParameterAsObject(1, stringHandle);
    KNI_GetParameterAsObject(2, arrayHandle);

    if (!ensure_fat_ready() ||
        copy_java_string_to_c(stringHandle, path, sizeof(path)) < 0 ||
        KNI_IsNullHandle(arrayHandle)) {
        result = -1;
    } else {
        arrayLen = KNI_GetArrayLength(arrayHandle);
        buffer = (unsigned char *)malloc(arrayLen > 0 ? arrayLen : 1);
        if (buffer == NULL) {
            result = -2;
        } else {
            if (arrayLen > 0) {
                KNI_GetRawArrayRegion(arrayHandle, 0, arrayLen, (jbyte *)buffer);
            }
            writeLen = pstrosFilterRmsInPlace(buffer, arrayLen);
            if (writeLen < 0) {
                result = -4000;
            } else if (!pstrosRmsReadyToPersist(buffer, writeLen)) {
                /* First boot is still constructing RecordStores. Report a
                 * successful deferred autosave, but do not create/truncate
                 * the persistent file until the gameplay RMS is complete. */
                result = arrayLen;
            } else {
                errno = 0;
                fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (fd < 0) {
                    result = -1000 - errno;
                } else {
                    result = 0;
                    while (pos < writeLen) {
                        int chunkLen = writeLen - pos;
                        int written;
                        if (chunkLen > NDS_FILE_IO_CHUNK) chunkLen = NDS_FILE_IO_CHUNK;
                        errno = 0;
                        written = (int)write(fd, buffer + pos, chunkLen);
                        if (written <= 0) {
                            result = -2000 - errno;
                            break;
                        }
                        pos += written;
                    }
                    errno = 0;
                    if (close(fd) != 0 && result >= 0) {
                        result = -3000 - errno;
                    } else if (result >= 0) {
                        /* Java compares the result with its unfiltered buffer
                         * length. Report the source length after a complete
                         * filtered write so it does not print a false failure. */
                        result = arrayLen;
                    }
                }
            }
            free(buffer);
        }
    }

    KNI_EndHandles();
    KNI_ReturnInt(result);
}

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_File_loadToVRAM() {
    char path[NDS_FILE_PATH_MAX + 1];
    FILE *fp = NULL;
    int result = -1;
    int len = 0;
    u16 *buffer = NULL;
    u16 *dst;
    int i;

    KNI_StartHandles(1);
    KNI_DeclareHandle(stringHandle);
    KNI_GetParameterAsObject(1, stringHandle);

    if (!ensure_fat_ready() || copy_java_string_to_c(stringHandle, path, sizeof(path)) < 0) {
        result = -1;
    } else {
        fp = fopen(path, "rb");
        if (fp == NULL) {
            result = -2;
        } else if (fseek(fp, 0, SEEK_END) != 0) {
            result = -3;
            fclose(fp);
        } else {
            long fileLen = ftell(fp);
            if (fileLen < 0) {
                result = -3;
                fclose(fp);
            } else {
                len = (int)fileLen;
                buffer = (u16 *)malloc(len > 0 ? len : 2);
                if (buffer == NULL) {
                    result = -2;
                    fclose(fp);
                } else {
                    fseek(fp, 0, SEEK_SET);
                    fread(buffer, 2, len / 2, fp);
                    fclose(fp);

                    dst = (u16 *)KNI_GetParameterAsInt(2);
                    if (dst != NULL) {
                        for (i = 0; i < len / 2; i++) {
                            dst[i] = buffer[i];
                        }
                        result = len;
                    } else {
                        result = -4;
                    }
                    free(buffer);
                }
            }
        }
    }

    KNI_EndHandles();
    KNI_ReturnInt(result);
}
