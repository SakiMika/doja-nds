package nds.doja.image;

import java.io.IOException;

/** Indexed Windows/OS2 BMP decoder used by DoJa PalettedImage.
 *
 * Supports uncompressed 1, 4 and 8 bit indexed BMP images. This matches the
 * palette-BMP path used by FF4A world-map resources while keeping the original
 * palette indexes available for DoJa Palette replacement/transparency.
 */
public final class IndexedBmpDecoder {
    public static final class Result {
        public int width;
        public int height;
        public byte[] indexes;
        public int[] palette;
        public int transparentIndex = -1;
    }

    private IndexedBmpDecoder() {}

    public static boolean isBmp(byte[] data) {
        return data != null && data.length >= 26 && data[0] == 'B' && data[1] == 'M';
    }

    public static Result decode(byte[] data) throws IOException {
        if (!isBmp(data)) throw new IOException("not BMP");

        int pixelOffset = readU32(data, 10);
        int dibSize = readU32(data, 14);
        int width;
        int signedHeight;
        int planes;
        int bits;
        int compression = 0;
        int colorsUsed = 0;
        int paletteOffset;
        int paletteEntrySize;

        if (dibSize == 12) {
            require(data, 14, 12);
            width = readU16(data, 18);
            signedHeight = readU16(data, 20);
            planes = readU16(data, 22);
            bits = readU16(data, 24);
            paletteOffset = 26;
            paletteEntrySize = 3;
        } else if (dibSize >= 40) {
            if (dibSize > 0x100000 || 14 + dibSize > data.length) throw new IOException("bad BMP DIB header");
            require(data, 14, 40);
            width = readS32(data, 18);
            signedHeight = readS32(data, 22);
            planes = readU16(data, 26);
            bits = readU16(data, 28);
            compression = readU32(data, 30);
            colorsUsed = readU32(data, 46);
            paletteOffset = 14 + dibSize;
            paletteEntrySize = 4;
        } else {
            throw new IOException("unsupported BMP DIB header");
        }

        if (planes != 1 || width <= 0 || signedHeight == 0) throw new IOException("invalid BMP geometry");
        if (bits != 1 && bits != 4 && bits != 8) throw new IOException("BMP is not indexed 1/4/8 bpp");
        if (compression != 0) throw new IOException("compressed BMP is not supported");

        boolean topDown = signedHeight < 0;
        int height = topDown ? -signedHeight : signedHeight;
        if (height <= 0 || width > 4096 || height > 4096) throw new IOException("BMP dimensions out of range");
        if (width > 0x7FFFFFFF / height) throw new IOException("BMP too large");

        int maximumColors = 1 << bits;
        int paletteCount = colorsUsed > 0 ? colorsUsed : maximumColors;
        if (paletteCount <= 0 || paletteCount > maximumColors) throw new IOException("bad BMP palette size");
        if (paletteOffset < 0 || paletteOffset > data.length) throw new IOException("bad BMP palette offset");
        if (paletteCount > (data.length - paletteOffset) / paletteEntrySize) throw new IOException("truncated BMP palette");
        if (pixelOffset < paletteOffset + paletteCount * paletteEntrySize || pixelOffset > data.length)
            throw new IOException("bad BMP pixel offset");

        int[] palette = new int[paletteCount];
        int i;
        for (i = 0; i < paletteCount; i++) {
            int p = paletteOffset + i * paletteEntrySize;
            int blue = data[p] & 255;
            int green = data[p + 1] & 255;
            int red = data[p + 2] & 255;
            palette[i] = (red << 16) | (green << 8) | blue;
        }

        long rowBits = (long)width * (long)bits;
        int rowBytes = (int)(((rowBits + 31L) / 32L) * 4L);
        if (rowBytes <= 0 || (long)pixelOffset + (long)rowBytes * (long)height > data.length)
            throw new IOException("truncated BMP pixels");

        byte[] indexes = new byte[width * height];
        int y;
        for (y = 0; y < height; y++) {
            int sourceY = topDown ? y : (height - 1 - y);
            int row = pixelOffset + sourceY * rowBytes;
            int out = y * width;
            int x;
            if (bits == 8) {
                System.arraycopy(data, row, indexes, out, width);
            } else if (bits == 4) {
                for (x = 0; x < width; x++) {
                    int value = data[row + (x >> 1)] & 255;
                    indexes[out + x] = (byte)(((x & 1) == 0) ? (value >> 4) : (value & 15));
                }
            } else {
                for (x = 0; x < width; x++) {
                    int value = data[row + (x >> 3)] & 255;
                    indexes[out + x] = (byte)((value >> (7 - (x & 7))) & 1);
                }
            }
        }

        Result result = new Result();
        result.width = width;
        result.height = height;
        result.indexes = indexes;
        result.palette = palette;
        result.transparentIndex = guessTransparentIndex(indexes, width, height, palette);
        return result;
    }

    private static int guessTransparentIndex(byte[] indexes, int width, int height, int[] palette) {
        if (indexes == null || palette == null || width <= 0 || height <= 0) return -1;

        int tl = indexes[0] & 255;
        int tr = indexes[width - 1] & 255;
        int bl = indexes[(height - 1) * width] & 255;
        int br = indexes[height * width - 1] & 255;

        int candidate = -1;
        if (tl == tr || tl == bl || tl == br) candidate = tl;
        else if (tr == bl || tr == br) candidate = tr;
        else if (bl == br) candidate = bl;

        if (candidate < 0 || candidate >= palette.length) return -1;
        if ((palette[candidate] & 0x00FFFFFF) != 0x00FF00FF) return -1;

        int matches = 0;
        if (tl == candidate) matches++;
        if (tr == candidate) matches++;
        if (bl == candidate) matches++;
        if (br == candidate) matches++;
        return matches >= 2 ? candidate : -1;
    }

    private static int readU16(byte[] data, int offset) throws IOException {
        require(data, offset, 2);
        return (data[offset] & 255) | ((data[offset + 1] & 255) << 8);
    }

    private static int readU32(byte[] data, int offset) throws IOException {
        require(data, offset, 4);
        long value = (long)(data[offset] & 255)
                   | ((long)(data[offset + 1] & 255) << 8)
                   | ((long)(data[offset + 2] & 255) << 16)
                   | ((long)(data[offset + 3] & 255) << 24);
        if (value > 0x7FFFFFFFL) throw new IOException("BMP value too large");
        return (int)value;
    }

    private static int readS32(byte[] data, int offset) throws IOException {
        require(data, offset, 4);
        return (data[offset] & 255)
             | ((data[offset + 1] & 255) << 8)
             | ((data[offset + 2] & 255) << 16)
             | (data[offset + 3] << 24);
    }

    private static void require(byte[] data, int offset, int count) throws IOException {
        if (offset < 0 || count < 0 || offset > data.length - count) throw new IOException("truncated BMP");
    }
}
