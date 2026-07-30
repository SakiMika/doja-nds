package com.nttdocomo.ui;

public final class Image {
    final javax.microedition.lcdui.Image midpImage;
    private Graphics graphics;

    Image(javax.microedition.lcdui.Image image) {
        if (image == null) {
            throw new NullPointerException();
        }
        midpImage = image;
    }

    public static Image createImage(int width, int height) {
        return new Image(javax.microedition.lcdui.Image.createImage(width, height));
    }

    public Graphics getGraphics() {
        if (graphics == null) {
            graphics = new Graphics(midpImage.getGraphics(), null, getWidth(), getHeight());
        }
        return graphics;
    }

    public int getWidth() {
        return midpImage.getWidth();
    }

    public int getHeight() {
        return midpImage.getHeight();
    }

    public void dispose() {
        graphics = null;
    }
}
