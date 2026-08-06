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
    private static final int STRING_CACHE_SIZE = 24;
    private static final String[] cacheText = new String[STRING_CACHE_SIZE];
    private static final int[] cacheHeight = new int[STRING_CACHE_SIZE];
    private static final int[] cacheColor = new int[STRING_CACHE_SIZE];
    private static final int[] cacheAge = new int[STRING_CACHE_SIZE];
    private static final javax.microedition.lcdui.Image[] cacheImage =
        new javax.microedition.lcdui.Image[STRING_CACHE_SIZE];
    private static int cacheClock;
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
        if (text == null || graphics == null) return;
        text = Cp932Codec.normalizeForDisplay(text);
        ensureLoaded();
        int width = measuredWidth(text, height);
        if (width <= 0) return;
        int top = baseline - height;

        // FF4A redraws the same Japanese menu/battle labels every frame.
        // Cache a complete label so subsequent frames are one native blit,
        // not one Java scale loop + drawRGB conversion per glyph.
        if (width <= 240 && height > 0 && height <= 24) {
            javax.microedition.lcdui.Image cached = cachedString(
                text, width, height, graphics.getColor());
            graphics._drawGlyphImage(cached, x, top);
            return;
        }

        int cursor = x;
        int i;
        for (i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (isNonPrintingControl(c)) continue;
            drawGlyph(graphics, c, cursor, top, height);
            cursor += advance(c, height);
        }
    }

    private static int measuredWidth(String text, int height) {
        int width = 0;
        int i;
        for (i = 0; i < text.length(); i++) width += advance(text.charAt(i), height);
        return width;
    }

    private static javax.microedition.lcdui.Image cachedString(
            String text, int width, int height, int rgb) {
        int i;
        int victim = 0;
        int oldest = 0x7FFFFFFF;
        cacheClock++;
        if (cacheClock <= 0) cacheClock = 1;
        for (i = 0; i < STRING_CACHE_SIZE; i++) {
            if (cacheImage[i] != null && cacheHeight[i] == height &&
                    cacheColor[i] == rgb && text.equals(cacheText[i])) {
                cacheAge[i] = cacheClock;
                return cacheImage[i];
            }
            if (cacheImage[i] == null) {
                victim = i;
                oldest = -1;
                break;
            }
            if (cacheAge[i] < oldest) {
                oldest = cacheAge[i];
                victim = i;
            }
        }
        int[] pixels = new int[width * height];
        int cursor = 0;
        int color = 0xFF000000 | rgb;
        for (i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (isNonPrintingControl(c)) continue;
            renderGlyphInto(pixels, width, c, cursor, height, color);
            cursor += advance(c, height);
        }
        javax.microedition.lcdui.Image image =
            javax.microedition.lcdui.Image.createRGBImage(pixels, width, height, true);
        cacheText[victim] = text;
        cacheHeight[victim] = height;
        cacheColor[victim] = rgb;
        cacheAge[victim] = cacheClock;
        cacheImage[victim] = image;
        return image;
    }

    private static void renderGlyphInto(int[] pixels, int stride, char c,
            int destX, int size, int color) {
        int width = c <= 0x007F ? (size + 1) / 2 : size;
        int index = find(c);
        if (index < 0 && glyphs != null) {
            index = find('〓');
            if (index < 0) index = find('?');
        }
        int dx;
        int dy;
        if (index < 0 || glyphs == null) {
            for (dy = 0; dy < size; dy++) {
                for (dx = 0; dx < width; dx++) {
                    if (dx == 0 || dy == 0 || dx == width - 1 || dy == size - 1)
                        pixels[dy * stride + destX + dx] = color;
                }
            }
            return;
        }
        int srcBase = index * bytesPerGlyph;
        int sourceWidth = c <= 0x007F ? (baseWidth + 1) / 2 : baseWidth;
        for (dy = 0; dy < size; dy++) {
            int sy = (dy * baseHeight) / size;
            int row = dy * stride + destX;
            for (dx = 0; dx < width; dx++) {
                int sx = (dx * sourceWidth) / width;
                int bit = sy * baseWidth + sx;
                if ((glyphs[srcBase + (bit >> 3)] & (0x80 >> (bit & 7))) != 0)
                    pixels[row + dx] = color;
            }
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
