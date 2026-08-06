package com.nttdocomo.ui;

/** DoJa image wrapper with alpha and transparent-color support. */
public class Image {
    javax.microedition.lcdui.Image midpImage;
    private Graphics graphics;
    private int alpha = 255;
    private int transparentColor;
    private boolean transparentEnabled;
    private boolean disposed;
    private javax.microedition.lcdui.Image effectCache;
    private boolean effectDirty = true;

    protected Image(javax.microedition.lcdui.Image image) {
        if (image == null) {
            throw new NullPointerException();
        }
        midpImage = image;
    }

    public static Image createImage(int width, int height) {
        if (width <= 0 || height <= 0) {
            throw new IllegalArgumentException();
        }
        return new Image(javax.microedition.lcdui.Image.createImage(width, height));
    }

    public Graphics getGraphics() {
        checkAlive();
        if (graphics == null) {
            graphics = new Graphics(midpImage.getGraphics(), null, this, getWidth(), getHeight());
        }
        return graphics;
    }

    public int getWidth() {
        checkAlive();
        return midpImage.getWidth();
    }

    public int getHeight() {
        checkAlive();
        return midpImage.getHeight();
    }

    public int getAlpha() {
        checkAlive();
        return alpha;
    }

    public void setAlpha(int value) {
        checkAlive();
        if (value < 0) value = 0;
        if (value > 255) value = 255;
        if (alpha != value) {
            alpha = value;
            // v42: ordinary/paletted images are alpha-blended by Video.blit.
            // Only color-key images still need a software effect cache.
            if (transparentEnabled) effectDirty = true;
        }
    }

    public int getTransparentColor() {
        checkAlive();
        return transparentColor;
    }

    public void setTransparentColor(int color) {
        checkAlive();
        transparentColor = color & 0x00FFFFFF;
        effectDirty = true;
    }

    public void setTransparentEnabled(boolean enabled) {
        checkAlive();
        if (transparentEnabled != enabled) {
            transparentEnabled = enabled;
            effectDirty = true;
        }
    }

    public void dispose() {
        disposed = true;
        graphics = null;
        effectCache = null;
        midpImage = null;
    }

    final void _markDirty() {
        effectDirty = true;
    }

    final boolean _isDisposed() {
        return disposed;
    }

    final int _alpha() {
        checkAlive();
        return alpha;
    }

    final boolean _hasSoftwareColorKey() {
        checkAlive();
        return transparentEnabled;
    }

    final javax.microedition.lcdui.Image _baseDisplayImage() {
        checkAlive();
        _beforeDisplay();
        return midpImage;
    }

    /** Returns a MIDP image with DoJa alpha/transparency applied. */
    javax.microedition.lcdui.Image _displayImage() {
        checkAlive();
        _beforeDisplay();
        if (alpha == 255 && !transparentEnabled) {
            return midpImage;
        }
        if (!effectDirty && effectCache != null) {
            return effectCache;
        }
        int width = midpImage.getWidth();
        int height = midpImage.getHeight();
        int[] pixels = new int[width * height];
        midpImage.getRGB(pixels, 0, width, 0, 0, width, height);
        int i;
        int key = transparentColor & 0x00FFFFFF;
        for (i = 0; i < pixels.length; i++) {
            int rgb = pixels[i] & 0x00FFFFFF;
            int sourceAlpha = (pixels[i] >>> 24) & 255;
            if (transparentEnabled && rgb == key) {
                sourceAlpha = 0;
            }
            sourceAlpha = (sourceAlpha * alpha + 127) / 255;
            pixels[i] = (sourceAlpha << 24) | rgb;
        }
        effectCache = javax.microedition.lcdui.Image.createRGBImage(pixels, width, height, true);
        effectDirty = false;
        return effectCache;
    }

    /** Hook used by PalettedImage to rebuild the indexed image lazily. */
    void _beforeDisplay() {
    }

    protected final void _replaceImage(javax.microedition.lcdui.Image image) {
        if (image == null) throw new NullPointerException();
        midpImage = image;
        graphics = null;
        effectDirty = true;
        effectCache = null;
    }

    private void checkAlive() {
        if (disposed || midpImage == null) {
            throw new RuntimeException("disposed image");
        }
    }
}
