#include <nds.h>
#include <nds/arm9/input.h>
#include <kni.h>
#include <stdio.h>

/* v48 Empty virtual-save input path.
 * START+SELECT optionally attaches FAT/SD persistence.  The game already has
 * a fully valid RAM save device, so this gesture is never required to play or
 * to satisfy save/RMS checks. */
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
