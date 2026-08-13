package com.nttdocomo.util;

/** ARM-native raw RFC1951 inflater used by JarInflater on NDS. */
final class NativeInflater {
    private NativeInflater() {}
    static native int inflate(byte[] input, int offset, int length, byte[] output);
}
