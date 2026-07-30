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
#error "DoJa v36 requires a 2432 KiB Java heap"
#endif
#if ENABLE_HEAP_COMPACTION != 0
#error "DoJa v36 keeps KVM heap compaction disabled"
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
extern int dojaSpPersistenceInit(const char *path);
extern int dojaSpPersistenceFlush(void);

static int dojaSaveStorageReady = 0;
static int dojaSaveLastState = 0;
static int dojaSaveLastSlot = 0;
static int dojaSaveLastCode = 0;
static int dojaSaveMountErrno = 0;
static int dojaSaveMountStage = 0;

static const char *dojaSaveStageName(int stage) {
    switch (stage) {
        case 10: return "EXISTING VOLUME";
        case 20: return "LIBDVM INIT";
        case 21: return "FAT WRITE TEST";
        case 22: return "SD WRITE TEST";
        case 40: return "NO STORAGE";
        default: return "READY";
    }
}

static void dojaSaveUiRender(void) {
    consoleClear();
    iprintf("DoJa v36\n");
    iprintf("------------------------------\n");
    iprintf("MODE: SAV FILE\n");

    if (dojaSaveStorageReady > 0) {
        iprintf("SAVE: READY\n");
        iprintf("MEDIA: %s\n", pstrosGetSaveBackendName());
    } else if (dojaSaveStorageReady < 0) {
        iprintf("SAVE: RAM ONLY\n");
        iprintf("MEDIA: NO DLDI\n");
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
        default: iprintf("LAST: NOT SAVED YET\n"); break;
    }

    if (dojaSaveStorageReady > 0) {
        iprintf("\nFILE: %s\n", pstrosGetSavePath());
    } else if (dojaSaveStorageReady < 0) {
        iprintf("\nSTAGE: %s (%d)\n",
                dojaSaveStageName(dojaSaveMountStage), dojaSaveMountStage);
        iprintf("ERRNO: %d\n", dojaSaveMountErrno);
        iprintf("TARGET: SAME-NAME .SAV\n");
    }
}

void dojaSaveUiStorage(int ready, int errorCode) {
    dojaSaveStorageReady = ready ? 1 : -1;
    if (ready) {
        dojaSaveMountErrno = 0;
        dojaSaveMountStage = 0;
    } else {
        dojaSaveMountErrno = errorCode;
        dojaSaveMountStage = pstrosGetSaveStage();
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
    char screenArg[32];
    char *kvm_argv[4];

    if (argc > 0 && argv != NULL) launchPath = argv[0];

    videoSetMode(MODE_0_2D);
    videoSetModeSub(MODE_0_2D);
    vramSetBankA(VRAM_A_MAIN_BG);
    vramSetBankC(VRAM_C_SUB_BG);
    consoleDemoInit();
    soundEnable();
    pstrosAudioDiagInit();
    pstrosSetVmConsoleEnabled(0);

    /* Bring the system IRQ path online before libdvm initializes DLDI/DSi SD. */
    irqSet(IRQ_VBLANK, kvm_vblank_handler);
    lcdSetVBlankIrq(true);
    irqEnable(IRQ_VBLANK);

    dojaSaveUiRender();
    if (!validate_embedded_jar()) wait_forever();

    if (pstrosMountSaveStorageAuto(launchPath)) {
        int restored = dojaSpPersistenceInit(pstrosGetSavePath());
        dojaSaveUiStorage(1, 0);
        dojaSaveUiLoaded(restored);
    } else {
        dojaSaveUiStorage(0, pstrosGetSaveErrno());
    }

    initJadBuffer();
    if (!setJadBufferText(STANDALONE_PROPERTIES_TEXT)) {
        pstrosAudioDiagVmError("manifest memory failed");
        wait_forever();
    }

    RequestedHeapSize = DEFAULTHEAPSIZE;
    UserClassPath = STANDALONE_CLASSPATH;

    kvm_argv[0] = "nds.doja.MainApp";
    snprintf(classArg, sizeof(classArg), "-C%s", DOJA_APP_CLASS);
    snprintf(paramArg, sizeof(paramArg), "-P%s", DOJA_APP_PARAM);
    snprintf(screenArg, sizeof(screenArg), "-Y%d", DOJA_SCREEN_Y);
    kvm_argv[1] = classArg;
    kvm_argv[2] = paramArg;
    kvm_argv[3] = screenArg;

    result = StartJVM(4, kvm_argv);
    dojaSpPersistenceFlush();
    pstrosAudioDiagKvmExit(result);
    freeJadBuffer();
    wait_forever();
    return result;
}
