package com.nttdocomo.ui;

import com.nttdocomo.ui.graphics3d.DrawableObject3D;
import com.nttdocomo.ui.graphics3d.Fog;
import com.nttdocomo.ui.graphics3d.Graphics3D;
import com.nttdocomo.ui.util3d.Transform;

/** DoJa drawing facade backed by the MIDP/NDS framebuffer. */
public final class Graphics implements Graphics3D {
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

    public static final int FLIP_NONE = 0;
    public static final int FLIP_HORIZONTAL = 1;
    public static final int FLIP_VERTICAL = 2;
    public static final int FLIP_ROTATE_180 = 3;
    public static final int FLIP_ROTATE_90 = 4;
    public static final int FLIP_ROTATE_90_HORIZONTAL = 5;
    public static final int FLIP_ROTATE_90_VERTICAL = 6;
    public static final int FLIP_ROTATE_270 = 7;

    private final javax.microedition.lcdui.Graphics midp;
    private final Canvas owner;
    private final Image imageOwner;
    private final int width;
    private final int height;
    private Font font = Font.getFont(Font.FACE_SYSTEM | Font.STYLE_PLAIN | Font.SIZE_TINY);
    private int color;
    private int lockDepth;
    private boolean presentPending;
    private int flipMode;
    private Fog fog;
    private Transform transform;

    Graphics(javax.microedition.lcdui.Graphics graphics, Canvas canvas, int w, int h) {
        this(graphics, canvas, null, w, h);
    }

    Graphics(javax.microedition.lcdui.Graphics graphics, Canvas canvas, Image image, int w, int h) {
        if (graphics == null) throw new NullPointerException();
        midp = graphics;
        owner = canvas;
        imageOwner = image;
        width = w;
        height = h;
        clearClip();
    }

    public void lock() {
        lockDepth++;
    }

    public void unlock(boolean flush) {
        if (flush) presentPending = true;
        if (lockDepth > 0) lockDepth--;

        /* DoJa games build a complete frame between lock()/unlock().
         * Publishing from flushBuffer() while the frame is still locked
         * exposes intermediate command-buffer states and makes the NDS
         * display flash. Present at most once when the outer lock closes. */
        if (lockDepth == 0 && presentPending) {
            presentPending = false;
            presentOwner();
        }
    }

    public void dispose() {
        lockDepth = 0;
        presentPending = false;
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

    public void setClip(int x, int y, int w, int h) {
        midp.setClip(x, y, w, h);
    }

    public void setColor(int rgb) {
        color = rgb & 0x00FFFFFF;
        midp.setColor(color);
    }

    public int getColor() {
        return color;
    }

    public void setFont(Font value) {
        if (value != null) font = value;
    }

    public void setFlipMode(int mode) {
        if (mode < FLIP_NONE || mode > FLIP_ROTATE_270) {
            throw new IllegalArgumentException("flip mode");
        }
        flipMode = mode;
    }

    public int getFlipMode() {
        return flipMode;
    }

    public void fillRect(int x, int y, int w, int h) {
        midp.fillRect(x, y, w, h);
        markOwner();
    }

    public void drawRect(int x, int y, int w, int h) {
        midp.drawRect(x, y, w, h);
        markOwner();
    }

    public void drawLine(int x1, int y1, int x2, int y2) {
        midp.drawLine(x1, y1, x2, y2);
        markOwner();
    }

    public void drawString(String text, int x, int y) {
        if (text != null) {
            font.drawString(this, text, x, y);
            markOwner();
        }
    }

    public void drawImage(Image image, int x, int y) {
        if (image == null) return;
        int alpha = image._alpha();
        if (alpha <= 0) return;
        boolean nativeAlpha = alpha < 255 && !image._hasSoftwareColorKey();
        javax.microedition.lcdui.Image src = nativeAlpha
            ? image._baseDisplayImage() : image._displayImage();
        int anchor = javax.microedition.lcdui.Graphics.TOP |
            javax.microedition.lcdui.Graphics.LEFT;
        if (flipMode == FLIP_NONE) {
            if (nativeAlpha) nds.doja.FastPath.drawImageAlpha(midp, src, x, y, 0, alpha);
            else midp.drawImage(src, x, y, anchor);
        } else {
            if (nativeAlpha) {
                nds.doja.FastPath.drawImageAlpha(midp, src, x, y,
                    midpTransform(flipMode), alpha);
            } else {
                midp.drawRegion(src, 0, 0, src.getWidth(), src.getHeight(),
                    midpTransform(flipMode), x, y, anchor);
            }
        }
        markOwner();
    }

    public void drawImage(Image image, int x, int y, int sx, int sy, int w, int h) {
        if (image != null && w > 0 && h > 0) {
            int alpha = image._alpha();
            if (alpha <= 0) return;
            boolean nativeAlpha = alpha < 255 && !image._hasSoftwareColorKey();
            javax.microedition.lcdui.Image src = nativeAlpha
                ? image._baseDisplayImage() : image._displayImage();
            int anchor = javax.microedition.lcdui.Graphics.TOP |
                javax.microedition.lcdui.Graphics.LEFT;
            if (nativeAlpha) {
                nds.doja.FastPath.drawRegionAlpha(midp, src, sx, sy, w, h,
                    midpTransform(flipMode), x, y, alpha);
            } else {
                midp.drawRegion(src, sx, sy, w, h, midpTransform(flipMode),
                    x, y, anchor);
            }
            markOwner();
        }
    }

    public int[] getRGBPixels(int x, int y, int w, int h, int[] pixels, int offset) {
        if (w < 0 || h < 0 || offset < 0) throw new IllegalArgumentException();
        if (pixels == null) pixels = new int[offset + w * h];
        midp.getPixels(pixels, offset, w, x, y, w, h, 8888);
        return pixels;
    }

    public int[] getPixels(int x, int y, int w, int h, int[] pixels, int offset) {
        return getRGBPixels(x, y, w, h, pixels, offset);
    }

    public void setRGBPixels(int x, int y, int w, int h, int[] pixels, int offset) {
        if (pixels == null) throw new NullPointerException();
        midp.drawRGB(pixels, offset, w, x, y, w, h, true);
        markOwner();
    }

    public void setPixels(int x, int y, int w, int h, int[] pixels, int offset) {
        setRGBPixels(x, y, w, h, pixels, offset);
    }

    public static int getColorOfRGB(int red, int green, int blue) {
        return ((red & 255) << 16) | ((green & 255) << 8) | (blue & 255);
    }

    public static int getColorOfRGB(int red, int green, int blue, int alpha) {
        return ((alpha & 255) << 24) | getColorOfRGB(red, green, blue);
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
        markOwner();
    }

    public void _drawGlyphImage(javax.microedition.lcdui.Image image, int x, int y) {
        midp.drawImage(image, x, y,
            javax.microedition.lcdui.Graphics.TOP | javax.microedition.lcdui.Graphics.LEFT);
        markOwner();
    }

    /* Graphics3D compatibility surface. The software renderer can be expanded
       independently without making ordinary 2D DoJa games depend on it. */
    public void flushBuffer() {
        if (owner != null) {
            if (lockDepth > 0) {
                presentPending = true;
            } else {
                presentOwner();
            }
        }
        markOwner();
    }

    private void presentOwner() {
        if (owner != null) owner._flush();
    }

    public void renderObject3D(DrawableObject3D object, Transform value) {
        if (object != null) object._render(this, value == null ? transform : value);
    }

    public void setClipRectFor3D(int x, int y, int w, int h) {
        setClip(x, y, w, h);
    }

    public void setFog(Fog value) {
        fog = value;
    }

    public void setPerspectiveView(float near, float far, float angle) {
        // Stored by native implementations; software compatibility currently
        // projects primitives conservatively through DrawableObject3D._render.
    }

    public void setTransform(Transform value) {
        transform = value;
    }

    public Fog _fog() { return fog; }

    private void markOwner() {
        if (imageOwner != null) imageOwner._markDirty();
    }

    private static int midpTransform(int mode) {
        // MIDP Sprite transform numeric constants.
        switch (mode) {
            case FLIP_HORIZONTAL: return 2;  // TRANS_MIRROR
            case FLIP_VERTICAL: return 1;    // TRANS_MIRROR_ROT180
            case FLIP_ROTATE_180: return 3;  // TRANS_ROT180
            case FLIP_ROTATE_90: return 5;   // TRANS_ROT90
            case FLIP_ROTATE_90_HORIZONTAL: return 7; // TRANS_MIRROR_ROT90
            case FLIP_ROTATE_90_VERTICAL: return 4;   // TRANS_MIRROR_ROT270
            case FLIP_ROTATE_270: return 6;  // TRANS_ROT270
            default: return 0;
        }
    }
}
