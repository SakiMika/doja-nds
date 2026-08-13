package com.nttdocomo.ui.graphics3d;

import nds.doja.image.IndexedBmpDecoder;

/** Indexed DoJa texture. FF4A supplies uncompressed 8-bit BMP textures. */
public class Texture extends Object3D {
    private static int traceSequence;
    private int width;
    private int height;
    private byte[] indexes;
    private int[] palette;
    private boolean decoded;

    Texture(byte[] data) {
        super(data);
        decode(data);
    }

    private void decode(byte[] data) {
        int id = ++traceSequence;
        if (data == null) {
            System.out.print("3D TEX#"); System.out.print(id); System.out.println(" NULL");
            return;
        }
        try {
            if (IndexedBmpDecoder.isBmp(data)) {
                IndexedBmpDecoder.Result result = IndexedBmpDecoder.decode(data);
                width = result.width;
                height = result.height;
                indexes = result.indexes;
                palette = result.palette;
                decoded = true;
            } else {
                System.out.print("3D TEX#"); System.out.print(id); System.out.println(" unsupported");
            }
        } catch (Exception ignored) {
            decoded = false;
            System.out.print("3D TEX#"); System.out.print(id); System.out.println(" decode-error");
        }
    }

    public int _width() { return width; }
    public int _height() { return height; }
    public byte[] _indexes() { return indexes; }
    public int[] _palette() { return palette; }
    public boolean _decoded() { return decoded; }

    /** DoJa textures tile when UV coordinates exceed their physical size. */
    public int _sampleIndex(int u, int v) {
        if (!decoded || width <= 0 || height <= 0) return 0;
        u %= width;
        v %= height;
        if (u < 0) u += width;
        if (v < 0) v += height;
        return indexes[v * width + u] & 255;
    }

    public int _sampleRGB(int index) {
        if (palette == null || index < 0 || index >= palette.length) return 0;
        return palette[index] & 0x00FFFFFF;
    }
}
