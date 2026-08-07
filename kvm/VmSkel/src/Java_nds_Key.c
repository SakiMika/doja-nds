#include <nds.h>
#include <nds/arm9/input.h>
#include <kni.h>
#include <stdio.h>

/* v46 production input path: scan keys without RAW/POLL console spam.
 * START+SELECT is reserved as an explicit save-media attachment gesture.
 * Storage initialization is never attempted automatically during boot or
 * from the ScratchPad write path, so a missing DLDI/SD device cannot hide the
 * game behind the SAVE CHECKING screen. */
extern int dojaSpPersistenceAttachStorage(void);
static int dojaSaveAttachLatched = 0;

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_Key_scan() {
    int held;
    scanKeys();
    held = keysHeld();

    if ((held & (KEY_START | KEY_SELECT)) == (KEY_START | KEY_SELECT)) {
        if (!dojaSaveAttachLatched) {
            dojaSaveAttachLatched = 1;
            dojaSpPersistenceAttachStorage();
        }
    } else {
        dojaSaveAttachLatched = 0;
    }

    KNI_ReturnVoid();
}

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_Key_held() {
    KNI_ReturnInt(keysHeld());
}

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_Key_down() {
    KNI_ReturnInt(keysDown());
}

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_Key_downRepeat() {
    KNI_ReturnInt(keysDownRepeat());
}

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_Key_up() {
    KNI_ReturnInt(keysUp());
}

KNIEXPORT KNI_RETURNTYPE_VOID Java_nds_Key_setRepeat() {
    jint delay = KNI_GetParameterAsInt(1);
    jint repeat = KNI_GetParameterAsInt(2);

    keysSetRepeat(delay, repeat);

    KNI_ReturnVoid();
}
