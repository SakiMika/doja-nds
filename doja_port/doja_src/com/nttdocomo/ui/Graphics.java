package com.nttdocomo.ui;

public final class Graphics {
    public static final int BLACK = 0;
    public static final int BLUE = 1;
    public static final int LIME = 2;
    public static final int AQUA = 3;
    public static final int RED = 4;
    public static final int FUCHSIA = 5;
    public static final int YELLOW = 6;
    public static final int WHITE = 7;
    public static final int GRAY = 8;
    public static final int NAVY = 9;
    public static final int GREEN = 10;
    public static final int TEAL = 11;
    public static final int MAROON = 12;
    public static final int PURPLE = 13;
    public static final int OLIVE = 14;
    public static final int SILVER = 15;

    private final javax.microedition.lcdui.Graphics midp;
    private final Canvas owner;
    private final int width;
    private final int height;
    private Font font = Font.getFont(Font.FACE_SYSTEM | Font.STYLE_PLAIN | Font.SIZE_TINY);
    private int color;
    private int lockDepth;

    Graphics(javax.microedition.lcdui.Graphics graphics, Canvas canvas, int w, int h) {
        midp = graphics;
        owner = canvas;
        width = w;
        height = h;
        clearClip();
    }

    public void lock() {
        lockDepth++;
    }

    public void unlock(boolean flush) {
        if (lockDepth > 0) {
            lockDepth--;
        }
        if (flush && owner != null) {
            owner._flush();
        }
    }

    public void setOrigin(int x, int y) {
        midp.translate(x - midp.getTranslateX(), y - midp.getTranslateY());
    }

    public void clearClip() {
        int tx = midp.getTranslateX();
        int ty = midp.getTranslateY();
        midp.setClip(-tx, -ty, width, height);
    }

    public void clipRect(int x, int y, int w, int h) {
        midp.clipRect(x, y, w, h);
    }

    public void setColor(int rgb) {
        color = rgb & 0x00FFFFFF;
        midp.setColor(color);
    }

    public int getColor() {
        return color;
    }

    public void setFont(Font value) {
        if (value != null) {
            font = value;
        }
    }

    public void fillRect(int x, int y, int w, int h) {
        midp.fillRect(x, y, w, h);
    }

    public void drawRect(int x, int y, int w, int h) {
        midp.drawRect(x, y, w, h);
    }

    public void drawLine(int x1, int y1, int x2, int y2) {
        midp.drawLine(x1, y1, x2, y2);
    }

    public void drawString(String text, int x, int y) {
        if (text != null) {
            font.drawString(this, text, x, y);
        }
    }

    public void drawImage(Image image, int x, int y) {
        if (image != null) {
            midp.drawImage(image.midpImage, x, y,
                javax.microedition.lcdui.Graphics.TOP | javax.microedition.lcdui.Graphics.LEFT);
        }
    }

    public void drawImage(Image image, int x, int y, int sx, int sy, int w, int h) {
        if (image != null && w > 0 && h > 0) {
            midp.drawRegion(image.midpImage, sx, sy, w, h, 0, x, y,
                javax.microedition.lcdui.Graphics.TOP | javax.microedition.lcdui.Graphics.LEFT);
        }
    }

    public int[] getRGBPixels(int x, int y, int w, int h, int[] pixels, int offset) {
        if (pixels == null) {
            pixels = new int[offset + w * h];
        }
        midp.getPixels(pixels, offset, w, x, y, w, h, 8888);
        return pixels;
    }

    public void setRGBPixels(int x, int y, int w, int h, int[] pixels, int offset) {
        midp.drawRGB(pixels, offset, w, x, y, w, h, false);
    }

    public static int getColorOfRGB(int red, int green, int blue) {
        return ((red & 255) << 16) | ((green & 255) << 8) | (blue & 255);
    }

    public static int getColorOfName(int name) {
        switch (name) {
            case BLACK: return 0x000000;
            case BLUE: return 0x0000FF;
            case LIME: return 0x00FF00;
            case AQUA: return 0x00FFFF;
            case RED: return 0xFF0000;
            case FUCHSIA: return 0xFF00FF;
            case YELLOW: return 0xFFFF00;
            case WHITE: return 0xFFFFFF;
            case GRAY: return 0x808080;
            case NAVY: return 0x000080;
            case GREEN: return 0x008000;
            case TEAL: return 0x008080;
            case MAROON: return 0x800000;
            case PURPLE: return 0x800080;
            case OLIVE: return 0x808000;
            case SILVER: return 0xC0C0C0;
            default: return 0;
        }
    }

    public void _drawGlyph(int[] pixels, int x, int y, int w, int h) {
        midp.drawRGB(pixels, 0, w, x, y, w, h, true);
    }
}
