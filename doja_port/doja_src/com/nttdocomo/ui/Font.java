package com.nttdocomo.ui;

import nds.doja.font.BitmapJapaneseFont;

public final class Font {
    public static final int TYPE_DEFAULT = 0;
    public static final int TYPE_HEADING = 1;
    public static final int FACE_SYSTEM = 0x71000000;
    public static final int FACE_MONOSPACE = 0x72000000;
    public static final int FACE_PROPORTIONAL = 0x73000000;
    public static final int STYLE_PLAIN = 0x70100000;
    public static final int STYLE_BOLD = 0x70110000;
    public static final int STYLE_ITALIC = 0x70120000;
    public static final int STYLE_BOLDITALIC = 0x70130000;
    public static final int SIZE_SMALL = 0x70000100;
    public static final int SIZE_MEDIUM = 0x70000200;
    public static final int SIZE_LARGE = 0x70000300;
    public static final int SIZE_TINY = 0x70000400;

    private final int height;

    private Font(int h) {
        height = h;
    }

    public static Font getFont(int value) {
        int size = value & 0x00000F00;
        if (value == TYPE_HEADING || size == 0x300) return new Font(24);
        if (size == 0x200) return new Font(16);
        if (size == 0x100) return new Font(12);
        return new Font(10);
    }

    public int getHeight() { return height; }

    public int getAscent() {
        return (height * 3 + 3) / 4;
    }

    public int getDescent() {
        return height - getAscent();
    }

    public int stringWidth(String text) {
        return BitmapJapaneseFont.stringWidth(text, height);
    }

    public int getBBoxWidth(String text) {
        return text == null ? 0 : stringWidth(text);
    }

    /** Returns the number of characters fitting in maxWidth. */
    public int getLineBreak(String text, int offset, int count, int maxWidth) {
        if (text == null) throw new NullPointerException();
        if (offset < 0 || count < 0 || offset + count > text.length()) {
            throw new StringIndexOutOfBoundsException();
        }
        if (maxWidth <= 0 || count == 0) return 0;
        int used = 0;
        int i;
        for (i = 0; i < count; i++) {
            char ch = text.charAt(offset + i);
            if (ch == '\n' || ch == '\r') return i;
            int next = stringWidth(text.substring(offset, offset + i + 1));
            if (next > maxWidth) break;
            used = i + 1;
        }
        return used;
    }

    void drawString(Graphics graphics, String text, int x, int baseline) {
        BitmapJapaneseFont.drawString(graphics, text, x, baseline, height);
    }
}
