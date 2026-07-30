package nds.doja.font;

import com.nttdocomo.ui.Graphics;
import com.sun.cldc.io.ResourceInputStream;
import java.io.DataInputStream;
import nds.doja.encoding.Cp932Codec;

public final class BitmapJapaneseFont {
    private static char[] characters;
    private static byte[] glyphs;
    private static int baseWidth = 12;
    private static int baseHeight = 12;
    private static int bytesPerGlyph = 18;
    private static int[] renderBuffer = new int[24 * 24];
    private static boolean loaded;
    private static int missingReported;

    private BitmapJapaneseFont() {
    }

    public static int stringWidth(String text, int height) {
        if (text == null) {
            return 0;
        }
        text = Cp932Codec.normalizeForDisplay(text);
        int width = 0;
        int i;
        for (i = 0; i < text.length(); i++) {
            width += advance(text.charAt(i), height);
        }
        return width;
    }

    public static void drawString(Graphics graphics, String text, int x, int baseline, int height) {
        if (text == null || graphics == null) {
            return;
        }
        text = Cp932Codec.normalizeForDisplay(text);
        ensureLoaded();
        int cursor = x;
        int top = baseline - height;
        int i;
        for (i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (isNonPrintingControl(c)) {
                continue;
            }
            drawGlyph(graphics, c, cursor, top, height);
            cursor += advance(c, height);
        }
    }

    private static boolean isNonPrintingControl(char c) {
        // Corpse Party stores several fixed-width CP932 labels with trailing
        // NUL padding. The original DoJa renderer treats these bytes as
        // non-printing; drawing a missing glyph created the square boxes seen
        // after otherwise-correct Japanese text.
        return c < 0x0020 || c == 0x007F;
    }

    private static int advance(char c, int height) {
        if (isNonPrintingControl(c)) {
            return 0;
        }
        if (c <= 0x007F) {
            return (height + 1) / 2;
        }
        return height;
    }

    private static void ensureLoaded() {
        if (loaded) {
            return;
        }
        loaded = true;
        try {
            DataInputStream input = new DataInputStream(new ResourceInputStream("doja/jpfont.bin"));
            if (input.readInt() != 0x444A4631) {
                input.close();
                return;
            }
            baseWidth = input.readUnsignedShort();
            baseHeight = input.readUnsignedShort();
            int count = input.readUnsignedShort();
            bytesPerGlyph = input.readUnsignedShort();
            characters = new char[count];
            glyphs = new byte[count * bytesPerGlyph];
            int i;
            for (i = 0; i < count; i++) {
                characters[i] = input.readChar();
                input.readFully(glyphs, i * bytesPerGlyph, bytesPerGlyph);
            }
            input.close();
            System.out.print("DoJa font ready: glyphs=");
            System.out.print(count);
            System.out.println(" full-cp932 sjis-decoded nul-padding-skip latin-half-cell-preserve");
        } catch (Exception ignored) {
            characters = null;
            glyphs = null;
        }
    }

    private static int find(char c) {
        if (characters == null) {
            return -1;
        }
        int low = 0;
        int high = characters.length - 1;
        while (low <= high) {
            int mid = (low + high) >>> 1;
            char value = characters[mid];
            if (value == c) {
                return mid;
            }
            if (value < c) {
                low = mid + 1;
            } else {
                high = mid - 1;
            }
        }
        return -1;
    }

    private static void drawGlyph(Graphics graphics, char c, int x, int y, int size) {
        if (isNonPrintingControl(c)) {
            return;
        }
        int width = c <= 0x007F ? (size + 1) / 2 : size;
        int needed = width * size;
        if (renderBuffer.length < needed) {
            renderBuffer = new int[needed];
        }
        int i;
        for (i = 0; i < needed; i++) {
            renderBuffer[i] = 0;
        }

        int index = find(c);
        int color = 0xFF000000 | graphics.getColor();
        if (index < 0 && glyphs != null) {
            if (missingReported < 8) {
                System.out.print("FONT MISS U+");
                System.out.println(Integer.toHexString((int)c));
                missingReported++;
            }
            index = find('〓');
            if (index < 0) {
                index = find('?');
            }
        }
        if (index < 0 || glyphs == null) {
            drawMissing(color, width, size);
        } else {
            int srcBase = index * bytesPerGlyph;
            int dx;
            int dy;
            for (dy = 0; dy < size; dy++) {
                int sy = (dy * baseHeight) / size;
                int sourceWidth = c <= 0x007F ? (baseWidth + 1) / 2 : baseWidth;
                for (dx = 0; dx < width; dx++) {
                    int sx = (dx * sourceWidth) / width;
                    int bit = sy * baseWidth + sx;
                    int value = glyphs[srcBase + (bit >> 3)] & (0x80 >> (bit & 7));
                    if (value != 0) {
                        renderBuffer[dy * width + dx] = color;
                    }
                }
            }
        }
        graphics._drawGlyph(renderBuffer, x, y, width, size);
    }

    private static void drawMissing(int color, int width, int height) {
        int x;
        int y;
        for (y = 0; y < height; y++) {
            for (x = 0; x < width; x++) {
                if (x == 0 || y == 0 || x == width - 1 || y == height - 1) {
                    renderBuffer[y * width + x] = color;
                }
            }
        }
    }
}
