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
        if (value == TYPE_HEADING || size == 0x300) {
            return new Font(24);
        }
        if (size == 0x200) {
            return new Font(16);
        }
        if (size == 0x100) {
            return new Font(12);
        }
        return new Font(10);
    }

    public int getHeight() {
        return height;
    }

    public int stringWidth(String text) {
        return BitmapJapaneseFont.stringWidth(text, height);
    }

    void drawString(Graphics graphics, String text, int x, int baseline) {
        BitmapJapaneseFont.drawString(graphics, text, x, baseline, height);
    }
}
