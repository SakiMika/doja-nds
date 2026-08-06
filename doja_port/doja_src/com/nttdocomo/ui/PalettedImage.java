package com.nttdocomo.ui;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import nds.doja.image.IndexedGifDecoder;

/** Indexed GIF image with a mutable DoJa Palette. */
public class PalettedImage extends Image {
    private byte[] indexes;
    private int width;
    private int height;
    private Palette palette;
    private int transparentIndex;
    private boolean transparentIndexEnabled;
    private int renderedPaletteRevision = -1;
    private boolean indexedDirty = true;

    private PalettedImage(int w, int h, byte[] pixelIndexes, int[] colors) {
        super(javax.microedition.lcdui.Image.createImage(w, h));
        width = w;
        height = h;
        indexes = pixelIndexes;
        palette = new Palette(colors);
    }

    public static PalettedImage createPalettedImage(byte[] data) {
        if (data == null) throw new NullPointerException();
        try {
            IndexedGifDecoder.Result decoded = IndexedGifDecoder.decode(data);
            PalettedImage image = new PalettedImage(decoded.width, decoded.height, decoded.indexes, decoded.palette);
            if (decoded.transparentIndex >= 0) {
                image.transparentIndex = decoded.transparentIndex;
                image.transparentIndexEnabled = true;
            }
            image.rebuild();
            return image;
        } catch (Exception ignored) {
            try {
                javax.microedition.lcdui.Image decoded = javax.microedition.lcdui.Image.createImage(data, 0, data.length);
                int w = decoded.getWidth(), h = decoded.getHeight();
                int[] argb = new int[w * h];
                decoded.getRGB(argb, 0, w, 0, 0, w, h);
                int[] colors = new int[256];
                byte[] idx = new byte[w * h];
                int count = 0, i, j;
                for (i = 0; i < argb.length; i++) {
                    int rgb = argb[i] & 0x00FFFFFF;
                    int found = -1;
                    for (j = 0; j < count; j++) if (colors[j] == rgb) { found = j; break; }
                    if (found < 0) {
                        if (count < 256) { found = count; colors[count++] = rgb; }
                        else found = 0;
                    }
                    idx[i] = (byte)found;
                }
                if (count == 0) count = 1;
                int[] compact = new int[count];
                System.arraycopy(colors, 0, compact, 0, count);
                PalettedImage image = new PalettedImage(w, h, idx, compact);
                image.rebuild();
                return image;
            } catch (Exception bad) {
                throw new IllegalArgumentException("unsupported paletted image");
            }
        }
    }

    public static PalettedImage createPalettedImage(InputStream in) {
        if (in == null) throw new NullPointerException();
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[1024];
            int count;
            while ((count = in.read(buffer)) > 0) out.write(buffer, 0, count);
            return createPalettedImage(out.toByteArray());
        } catch (Exception e) {
            throw new IllegalArgumentException("unsupported paletted image");
        }
    }

    public static PalettedImage createPalettedImage(int width, int height) {
        if (width <= 0 || height <= 0) throw new IllegalArgumentException();
        return new PalettedImage(width, height, new byte[width * height], new int[] { 0 });
    }

    public void changeData(byte[] data) {
        PalettedImage replacement = createPalettedImage(data);
        width = replacement.width;
        height = replacement.height;
        indexes = replacement.indexes;
        palette = replacement.palette;
        transparentIndex = replacement.transparentIndex;
        transparentIndexEnabled = replacement.transparentIndexEnabled;
        indexedDirty = true;
        rebuild();
    }

    public void changeData(InputStream in) {
        PalettedImage replacement = createPalettedImage(in);
        width = replacement.width;
        height = replacement.height;
        indexes = replacement.indexes;
        palette = replacement.palette;
        transparentIndex = replacement.transparentIndex;
        transparentIndexEnabled = replacement.transparentIndexEnabled;
        indexedDirty = true;
        rebuild();
    }

    public Palette getPalette() { return palette; }

    public void setPalette(Palette value) {
        if (value == null) throw new NullPointerException();
        if (value.getEntryCount() < palette.getEntryCount()) throw new IllegalArgumentException();
        palette = value;
        indexedDirty = true;
    }

    public int getTransparentIndex() { return transparentIndex; }

    public void setTransparentIndex(int index) {
        if (index < 0 || index > 255) throw new IllegalArgumentException();
        transparentIndex = index;
        indexedDirty = true;
    }

    public void setTransparentEnabled(boolean enabled) {
        transparentIndexEnabled = enabled;
        indexedDirty = true;
    }

    public Graphics getGraphics() {
        throw new RuntimeException("paletted image is immutable");
    }

    void _beforeDisplay() {
        if (indexedDirty || renderedPaletteRevision != palette._revision()) rebuild();
    }

    private void rebuild() {
        int[] argb = new int[width * height];
        int count = palette.getEntryCount();
        int i;
        for (i = 0; i < argb.length; i++) {
            int index = indexes[i] & 255;
            int rgb = index < count ? palette.getEntry(index) & 0x00FFFFFF : 0;
            int alpha = transparentIndexEnabled && index == transparentIndex ? 0 : 255;
            argb[i] = (alpha << 24) | rgb;
        }
        _replaceImage(javax.microedition.lcdui.Image.createRGBImage(argb, width, height, true));
        renderedPaletteRevision = palette._revision();
        indexedDirty = false;
    }
}
