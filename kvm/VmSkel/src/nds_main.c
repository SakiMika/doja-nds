// Nintendo DS entry point for the standalone DoJa/KVM build.
// The selected i-appli JAR, ScratchPad and Japanese bitmap font are linked
// directly into ARM9. The lower screen is reserved for compact save status and DLDI state.

#include <global.h>
#include <nds.h>
#include <stdio.h>
#include <string.h>
#include <fat.h>

#include "file.h"
#include "standalone_game.h"
#include "doja_port_version.h"

#if DOJA_PORT_BUILD_VERSION != DOJA_SOURCE_PORT_VERSION
#error "Wrong generated DoJa metadata: run build_doja.bat for this source version"
#endif
#if DEFAULTHEAPSIZE != (2432*1024)
#error "DoJa v59 keeps the 2432 KiB constant for source compatibility"
#endif
#define DOJA_DSI_HEAPSIZE (8*1024*1024)
#if ENABLE_HEAP_COMPACTION != 0
#error "DoJa v59 keeps KVM heap compaction disabled"
#endif

extern char *UserClassPath;
extern void kvm_vblank_handler(void);
extern const unsigned char _binary_embedded_game_jar_start[];
extern const unsigned char _binary_embedded_game_jar_end[];
extern void pstrosSetVmConsoleEnabled(int enabled);
extern void pstrosAudioDiagInit(void);
extern void pstrosAudioDiagVmError(const char *message);
extern void pstrosAudioDiagKvmExit(int result);
extern int pstrosMountSaveStorageAuto(const char *launchPath);
extern const char *pstrosGetSavePath(void);
extern const char *pstrosGetSaveBackendName(void);
extern int pstrosGetSaveErrno(void);
extern int pstrosGetSaveStage(void);
extern int dojaSpRomInit(const char *path);
extern int dojaSpPersistenceInit(const char *path);
extern int dojaSpPersistenceFlush(void);

static int dojaSaveStorageReady = 1;
static int dojaSaveLastState = 0;
static int dojaSaveLastSlot = 0;
static int dojaSaveLastCode = 0;
static int dojaSaveMountErrno = 0;
static int dojaSaveMountStage = 0;
static const char *dojaBootStage = "POWER ON";
static long dojaHeapBytes = DEFAULTHEAPSIZE;

static const char *dojaSaveStageName(int stage) {
    switch (stage) {
        case 10: return "EXISTING VOLUME";
        case 20: return "LIBDVM INIT";
        case 21: return "FAT WRITE TEST";
        case 22: return "SD WRITE TEST";
        case 40: return "MANUAL ATTACH";
        default: return "READY";
    }
}

static void dojaSaveUiRender(void) {
    consoleClear();
    iprintf("DoJa v59 Empty\n");
    iprintf("------------------------------\n");
    iprintf("MODE: VIRTUAL RAM SAVE\n");
    iprintf("BOOT: %s\n", dojaBootStage);
    iprintf("HEAP: %ld KiB (%s)\n", dojaHeapBytes / 1024,
            isDSiMode() ? "DSi" : "DS");
    iprintf("VIDEO: %s %dx%d\n", DOJA_SCALE_MODE_TEXT,
            DOJA_OUTPUT_WIDTH, DOJA_OUTPUT_HEIGHT);

    if (dojaSaveStorageReady > 0) {
        const char *backend = pstrosGetSaveBackendName();
        iprintf("SAVE: READY\n");
        iprintf("MEDIA: %s\n", backend);
        if (backend != NULL && strcmp(backend, "RAM-VIRTUAL") == 0) {
            iprintf("PERSIST: START+SELECT\n");
        }
    } else if (dojaSaveStorageReady < 0) {
        /* This state is reserved for a genuine virtual-backend failure.
         * Missing FAT/SD no longer enters it. */
        iprintf("SAVE: RAM ERROR\n");
    } else {
        iprintf("SAVE: CHECKING...\n");
    }

    switch (dojaSaveLastState) {
        case 1: iprintf("LAST: NO SAVE FILE\n"); break;
        case 2: iprintf("LAST: SAVE LOADED\n"); break;
        case 3:
            if (dojaSaveLastSlot > 0) iprintf("LAST: SAVING SLOT %d...\n", dojaSaveLastSlot);
            else iprintf("LAST: SAVING...\n");
            break;
        case 4:
            if (dojaSaveLastSlot > 0) iprintf("LAST: SAVED SLOT %d\n", dojaSaveLastSlot);
            else iprintf("LAST: SAVED\n");
            break;
        case 5:
            if (dojaSaveLastSlot > 0) iprintf("LAST: FAILED SLOT %d\n", dojaSaveLastSlot);
            else iprintf("LAST: SAVE FAILED\n");
            iprintf("WRITE CODE: %d\n", dojaSaveLastCode);
            break;
        case 6:
            iprintf("LAST: RAM SAVED (%d)\n", dojaSaveLastCode);
            break;
        default: iprintf("LAST: NOT SAVED YET\n"); break;
    }

    if (dojaSaveStorageReady > 0) {
        iprintf("\nFILE: %s\n", pstrosGetSavePath());
    } else if (dojaSaveStorageReady < 0) {
        iprintf("\nSTAGE: %s (%d)\n",
                dojaSaveStageName(dojaSaveMountStage), dojaSaveMountStage);
        if (dojaSaveMountErrno != 88) {
            iprintf("ERRNO: %d\n", dojaSaveMountErrno);
        }
        iprintf("GAME: CONTINUES IN RAM\n");
    }
}


static void dojaBootUiStage(const char *stage) {
    dojaBootStage = stage != NULL ? stage : "UNKNOWN";
    dojaSaveUiRender();
}

void dojaSaveUiAttaching(void) {
    dojaBootStage = "SAVE ATTACH";
    dojaSaveStorageReady = 0;
    dojaSaveUiRender();
}

void dojaSaveUiStorage(int ready, int errorCode) {
    const char *backend = pstrosGetSaveBackendName();
    if (!ready && backend != NULL && strcmp(backend, "RAM-VIRTUAL") == 0) {
        /* Physical attach can fail without invalidating the virtual device. */
        dojaSaveStorageReady = 1;
        dojaSaveMountErrno = 0;
        dojaSaveMountStage = 0;
    } else {
        dojaSaveStorageReady = ready ? 1 : -1;
        if (ready) {
            dojaSaveMountErrno = 0;
            dojaSaveMountStage = 0;
        } else {
            dojaSaveMountErrno = errorCode;
            dojaSaveMountStage = pstrosGetSaveStage();
        }
    }
    dojaSaveUiRender();
}

void dojaSaveUiLoaded(int loadedChunks) {
    dojaSaveLastState = loadedChunks > 0 ? 2 : 1;
    dojaSaveLastSlot = 0;
    dojaSaveLastCode = 0;
    dojaSaveUiRender();
}

void dojaSaveUiSaving(int slot) {
    dojaSaveLastState = 3;
    dojaSaveLastSlot = slot;
    dojaSaveLastCode = 0;
    dojaSaveUiRender();
}

void dojaSaveUiResult(int success, int slot, int resultCode) {
    dojaSaveLastState = success ? 4 : 5;
    dojaSaveLastSlot = slot;
    dojaSaveLastCode = resultCode;
    dojaSaveUiRender();
}

void dojaSaveUiBuffered(int dirtyChunks) {
    dojaSaveLastState = 6;
    dojaSaveLastSlot = 0;
    dojaSaveLastCode = dirtyChunks;
    dojaSaveUiRender();
}

static void wait_forever(void) {
    while (1) swiWaitForVBlank();
}

static int validate_embedded_jar(void) {
    long jarSize = (long)(_binary_embedded_game_jar_end - _binary_embedded_game_jar_start);
    if (jarSize < 4) {
        pstrosAudioDiagVmError("embedded JAR empty");
        return 0;
    }
    if (_binary_embedded_game_jar_start[0] != 'P' ||
        _binary_embedded_game_jar_start[1] != 'K') {
        pstrosAudioDiagVmError("embedded JAR invalid");
        return 0;
    }
    return 1;
}

int main(int argc, char **argv) {
    int result;
    const char *launchPath = NULL;
    char classArg[224];
    char paramArg[128];
    char screenXArg[32];
    char screenYArg[32];
    char canvasWArg[32];
    char canvasHArg[32];
    char logicalWArg[32];
    char logicalHArg[32];
    char *kvm_argv[9];

    if (argc > 0 && argv != NULL) launchPath = argv[0];

    videoSetMode(MODE_0_2D);
    videoSetModeSub(MODE_0_2D);
    vramSetBankA(VRAM_A_MAIN_BG);
    vramSetBankC(VRAM_C_SUB_BG);
    consoleDemoInit();
    soundEnable();
    pstrosAudioDiagInit();
    /* v59 keeps the VM console visible until the game renders.  v38 hid
     * Java exceptions, so a failed app.start() looked identical to a hang. */
    pstrosSetVmConsoleEnabled(1);

    /* Bring the system IRQ path online before libdvm initializes DLDI/DSi SD. */
    irqSet(IRQ_VBLANK, kvm_vblank_handler);
    lcdSetVBlankIrq(true);
    irqEnable(IRQ_VBLANK);

    dojaHeapBytes = isDSiMode() ? DOJA_DSI_HEAPSIZE : DEFAULTHEAPSIZE;
    dojaBootUiStage(isDSiMode() ? "DSI RAM" : "DS RAM");

    dojaBootUiStage("ROM CHECK");
    if (!validate_embedded_jar()) wait_forever();

    /* build-doja stores the game-visible ScratchPad in one Nintendo LZ77
     * wrapper. Expand it once into RAM; no filesystem is touched at boot. */
    dojaBootUiStage("SP EXPAND");
    if (!dojaSpRomInit(NULL)) {
        pstrosAudioDiagVmError("ScratchPad LZ77 expand failed");
        iprintf("\nSCRATCHPAD EXPAND FAILED\n");
        wait_forever();
    }
    /* RAM-VIRTUAL is immediately usable by RMS and ScratchPad.  This performs
     * no fopen(), DLDI, DSi-SD or filesystem initialization operation. */
    dojaBootUiStage("SAVE RAM READY");
    if (pstrosMountSaveStorageAuto(launchPath)) {
        dojaSaveUiStorage(1, 0);
    } else {
        dojaSaveUiStorage(0, pstrosGetSaveErrno());
    }

    dojaBootUiStage("MANIFEST");
    initJadBuffer();
    if (!setJadBufferText(STANDALONE_PROPERTIES_TEXT)) {
        pstrosAudioDiagVmError("manifest memory failed");
        wait_forever();
    }

    /* DSi mode receives the large heap; DS mode remains available for games
     * whose expanded ScratchPad and Java heap fit in the original memory. */
    RequestedHeapSize = dojaHeapBytes;
    UserClassPath = STANDALONE_CLASSPATH;

    kvm_argv[0] = "nds.doja.MainApp";
    snprintf(classArg, sizeof(classArg), "-C%s", DOJA_APP_CLASS);
    snprintf(paramArg, sizeof(paramArg), "-P%s", DOJA_APP_PARAM);
    snprintf(screenXArg, sizeof(screenXArg), "-X%d", DOJA_SCREEN_X);
    snprintf(screenYArg, sizeof(screenYArg), "-Y%d", DOJA_SCREEN_Y);
    snprintf(canvasWArg, sizeof(canvasWArg), "-W%d", DOJA_CANVAS_WIDTH);
    snprintf(canvasHArg, sizeof(canvasHArg), "-H%d", DOJA_CANVAS_HEIGHT);
    snprintf(logicalWArg, sizeof(logicalWArg), "-Q%d", DOJA_LOGICAL_WIDTH);
    snprintf(logicalHArg, sizeof(logicalHArg), "-R%d", DOJA_LOGICAL_HEIGHT);
    kvm_argv[1] = classArg;
    kvm_argv[2] = paramArg;
    kvm_argv[3] = screenXArg;
    kvm_argv[4] = screenYArg;
    kvm_argv[5] = canvasWArg;
    kvm_argv[6] = canvasHArg;
    kvm_argv[7] = logicalWArg;
    kvm_argv[8] = logicalHArg;

    dojaBootUiStage("JVM START");
    iprintf("\nAPP: %s\nPARAM: %s\n", DOJA_APP_CLASS, DOJA_APP_PARAM);
    iprintf("VM CONSOLE: ON\n");
    result = StartJVM(9, kvm_argv);
    iprintf("\nJVM RETURNED: %d\n", result);
    dojaSpPersistenceFlush();
    pstrosAudioDiagKvmExit(result);
    freeJadBuffer();
    wait_forever();
    return result;
}
