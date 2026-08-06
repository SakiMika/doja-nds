package nds.doja.encoding;

import com.sun.cldc.io.ResourceInputStream;
import java.io.DataInputStream;

/** Compact, deterministic CP932 decoder/encoder for DoJa's default SJIS text. */
public final class Cp932Codec {
    private static final int MAGIC = 0x444A4332;
    private static final char REPLACEMENT = '\u3013';

    private static char[] single;
    private static char[] doubleByte;
    private static char[] reverseUnicode;
    private static char[] reverseSjis;
    private static boolean loaded;

    private Cp932Codec() {
    }

    public static boolean isLead(int value) {
        return (value >= 0x81 && value <= 0x9F)
            || (value >= 0xE0 && value <= 0xFC);
    }

    public static boolean isTrail(int value) {
        return (value >= 0x40 && value <= 0x7E)
            || (value >= 0x80 && value <= 0xFC);
    }

    public static char decodeSingle(int value) {
        ensureLoaded();
        if (single == null) {
            return value >= 0 && value <= 0x7F ? (char)value : REPLACEMENT;
        }
        return single[value & 0xFF];
    }

    public static char decodePair(int lead, int trail) {
        ensureLoaded();
        if (doubleByte == null || !isLead(lead) || !isTrail(trail)) {
            return REPLACEMENT;
        }
        int leadIndex = lead <= 0x9F ? lead - 0x81 : 31 + lead - 0xE0;
        int trailIndex = trail <= 0x7E ? trail - 0x40 : 63 + trail - 0x80;
        int index = leadIndex * 188 + trailIndex;
        if (index < 0 || index >= doubleByte.length) {
            return REPLACEMENT;
        }
        return doubleByte[index];
    }

    /** Returns one byte, a packed two-byte value, or -1 when unmappable. */
    public static int encode(char value) {
        ensureLoaded();
        if (reverseUnicode == null) {
            return value <= 0x7F ? value : -1;
        }
        int low = 0;
        int high = reverseUnicode.length - 1;
        while (low <= high) {
            int mid = (low + high) >>> 1;
            char current = reverseUnicode[mid];
            if (current == value) {
                return reverseSjis[mid];
            }
            if (current < value) {
                low = mid + 1;
            } else {
                high = mid - 1;
            }
        }
        return -1;
    }

    /**
     * Safety net for strings that were created as one-byte characters before
     * the default encoding was initialized. Proper Unicode strings are returned
     * unchanged; raw CP932 byte strings are decoded once for drawing/measurement.
     */
    public static String normalizeForDisplay(String text) {
        if (text == null || text.length() == 0) {
            return text;
        }
        boolean rawPair = false;
        int i;
        for (i = 0; i < text.length(); i++) {
            int value = text.charAt(i);
            if (value > 0xFF) {
                return text;
            }
            if (isLead(value) && i + 1 < text.length()) {
                int trail = text.charAt(i + 1);
                if (trail <= 0xFF && isTrail(trail)) {
                    rawPair = true;
                    break;
                }
            }
        }
        if (!rawPair) {
            return text;
        }

        char[] out = new char[text.length()];
        int inPos = 0;
        int outPos = 0;
        while (inPos < text.length()) {
            int first = text.charAt(inPos++) & 0xFF;
            if (isLead(first) && inPos < text.length()) {
                int second = text.charAt(inPos) & 0xFF;
                if (isTrail(second)) {
                    inPos++;
                    out[outPos++] = decodePair(first, second);
                    continue;
                }
            }
            out[outPos++] = decodeSingle(first);
        }
        return new String(out, 0, outPos);
    }

    private static void ensureLoaded() {
        if (loaded) {
            return;
        }
        loaded = true;
        DataInputStream input = null;
        try {
            input = new DataInputStream(new ResourceInputStream("doja/cp932.tbl"));
            if (input.readInt() != MAGIC || input.readUnsignedShort() != 1) {
                input.close();
                return;
            }
            int singleCount = input.readUnsignedShort();
            int doubleCount = input.readUnsignedShort();
            int reverseCount = input.readUnsignedShort();
            if (singleCount != 256 || doubleCount != 11280 || reverseCount <= 0) {
                input.close();
                return;
            }
            single = new char[singleCount];
            doubleByte = new char[doubleCount];
            reverseUnicode = new char[reverseCount];
            reverseSjis = new char[reverseCount];
            int i;
            for (i = 0; i < singleCount; i++) {
                single[i] = input.readChar();
            }
            for (i = 0; i < doubleCount; i++) {
                doubleByte[i] = input.readChar();
            }
            for (i = 0; i < reverseCount; i++) {
                reverseUnicode[i] = input.readChar();
                reverseSjis[i] = input.readChar();
            }
            input.close();
            input = null;
        } catch (Exception ignored) {
            single = null;
            doubleByte = null;
            reverseUnicode = null;
            reverseSjis = null;
            try {
                if (input != null) {
                    input.close();
                }
            } catch (Exception closeIgnored) {
            }
        }
    }
}
