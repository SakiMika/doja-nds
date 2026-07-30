package com.sun.cldc.io.j2me.scratchpad;

/**
 * Tiny marker used by the Corpse Party bytecode patch.
 *
 * The original game copied each ScratchPad segment into a temporary byte[]
 * before parsing it.  On the NDS that caused severe heap fragmentation and an
 * OutOfMemoryError near the end of NowLoading.  v21 keeps the original method
 * signatures and verifier stack shape, but returns this one-byte segment token
 * instead of allocating the whole payload.
 */
public final class SegmentToken {
    private SegmentToken() {
    }

    public static byte[] open(int segmentIndex) {
        return new byte[] { (byte)segmentIndex };
    }
}
