package nds.doja.image;

import java.io.IOException;

/** Minimal GIF87a/GIF89a first-frame decoder for DoJa resources. */
public final class GifDecoder {
    private byte[] data;
    private int pos;
    private int width;
    private int height;
    private int[] globalPalette;
    private int transparentIndex = -1;

    private GifDecoder(byte[] source) {
        data = source;
    }

    public static javax.microedition.lcdui.Image decode(byte[] source) throws IOException {
        if (!isGif(source)) {
            throw new IOException("not GIF");
        }
        return new GifDecoder(source).decodeImage();
    }

    public static boolean isGif(byte[] source) {
        return source != null && source.length >= 13 &&
            source[0] == 'G' && source[1] == 'I' && source[2] == 'F' &&
            source[3] == '8' && (source[4] == '7' || source[4] == '9') && source[5] == 'a';
    }

    private javax.microedition.lcdui.Image decodeImage() throws IOException {
        pos = 6;
        width = readU16();
        height = readU16();
        int packed = readU8();
        readU8();
        readU8();
        if ((packed & 0x80) != 0) {
            globalPalette = readPalette(1 << ((packed & 7) + 1));
        }

        while (pos < data.length) {
            int marker = readU8();
            if (marker == 0x21) {
                readExtension();
            } else if (marker == 0x2C) {
                return readImageBlock();
            } else if (marker == 0x3B) {
                break;
            } else {
                throw new IOException("bad GIF block");
            }
        }
        throw new IOException("GIF has no image");
    }

    private void readExtension() throws IOException {
        int label = readU8();
        if (label == 0xF9) {
            int size = readU8();
            if (size == 4) {
                int packed = readU8();
                readU16();
                int index = readU8();
                transparentIndex = (packed & 1) != 0 ? index : -1;
                if (readU8() != 0) {
                    throw new IOException("bad GCE");
                }
                return;
            }
            skipBytes(size);
        }
        skipSubBlocks();
    }

    private javax.microedition.lcdui.Image readImageBlock() throws IOException {
        int left = readU16();
        int top = readU16();
        int imageWidth = readU16();
        int imageHeight = readU16();
        int packed = readU8();
        boolean interlaced = (packed & 0x40) != 0;
        int[] palette = globalPalette;
        if ((packed & 0x80) != 0) {
            palette = readPalette(1 << ((packed & 7) + 1));
        }
        if (palette == null || imageWidth <= 0 || imageHeight <= 0) {
            throw new IOException("invalid GIF image");
        }

        int minCodeSize = readU8();
        byte[] compressed = readSubBlocks();
        byte[] indexes = lzwDecode(compressed, minCodeSize, imageWidth * imageHeight);
        int canvasWidth = width > 0 ? width : imageWidth;
        int canvasHeight = height > 0 ? height : imageHeight;
        int[] argb = new int[canvasWidth * canvasHeight];

        int[] rowOrder = null;
        if (interlaced) {
            rowOrder = new int[imageHeight];
            int outRow = 0;
            int[] starts = new int[] { 0, 4, 2, 1 };
            int[] steps = new int[] { 8, 8, 4, 2 };
            int pass;
            for (pass = 0; pass < 4; pass++) {
                int value;
                for (value = starts[pass]; value < imageHeight; value += steps[pass]) {
                    rowOrder[outRow++] = value;
                }
            }
        }
        int i;
        for (i = 0; i < imageHeight; i++) {
            int row = interlaced ? rowOrder[i] : i;
            int src = i * imageWidth;
            int dstY = top + row;
            if (dstY < 0 || dstY >= canvasHeight) {
                continue;
            }
            int x;
            for (x = 0; x < imageWidth; x++) {
                int dstX = left + x;
                if (dstX < 0 || dstX >= canvasWidth) {
                    continue;
                }
                int index = indexes[src + x] & 255;
                if (index == transparentIndex) {
                    argb[dstY * canvasWidth + dstX] = 0;
                } else if (index < palette.length) {
                    argb[dstY * canvasWidth + dstX] = palette[index];
                }
            }
        }
        return javax.microedition.lcdui.Image.createRGBImage(argb, canvasWidth, canvasHeight, true);
    }

    private byte[] lzwDecode(byte[] input, int minimumCodeSize, int expected) throws IOException {
        if (minimumCodeSize < 2 || minimumCodeSize > 8) {
            throw new IOException("bad LZW size");
        }
        short[] prefix = new short[4096];
        byte[] suffix = new byte[4096];
        byte[] stack = new byte[4097];
        byte[] output = new byte[expected];
        int clear = 1 << minimumCodeSize;
        int end = clear + 1;
        int available = clear + 2;
        int oldCode = -1;
        int codeSize = minimumCodeSize + 1;
        int codeMask = (1 << codeSize) - 1;
        int datum = 0;
        int bits = 0;
        int inputPos = 0;
        int outputPos = 0;
        int first = 0;
        int top = 0;
        int i;
        for (i = 0; i < clear; i++) {
            prefix[i] = 0;
            suffix[i] = (byte)i;
        }

        while (outputPos < expected) {
            if (top == 0) {
                while (bits < codeSize) {
                    if (inputPos >= input.length) {
                        while (outputPos < expected) output[outputPos++] = 0;
                        return output;
                    }
                    datum |= (input[inputPos++] & 255) << bits;
                    bits += 8;
                }
                int code = datum & codeMask;
                datum >>>= codeSize;
                bits -= codeSize;

                if (code == clear) {
                    codeSize = minimumCodeSize + 1;
                    codeMask = (1 << codeSize) - 1;
                    available = clear + 2;
                    oldCode = -1;
                    continue;
                }
                if (code == end) {
                    break;
                }
                if (oldCode == -1) {
                    if (code >= suffix.length) throw new IOException("bad LZW code");
                    output[outputPos++] = suffix[code];
                    first = suffix[code] & 255;
                    oldCode = code;
                    continue;
                }

                int inCode = code;
                if (code >= available) {
                    if (code != available) throw new IOException("bad LZW stream");
                    stack[top++] = (byte)first;
                    code = oldCode;
                }
                while (code >= clear) {
                    if (code >= available || top >= stack.length) throw new IOException("bad LZW chain");
                    stack[top++] = suffix[code];
                    code = prefix[code] & 0xFFFF;
                }
                first = suffix[code] & 255;
                stack[top++] = (byte)first;

                if (available < 4096) {
                    prefix[available] = (short)oldCode;
                    suffix[available] = (byte)first;
                    available++;
                    if ((available & codeMask) == 0 && available < 4096) {
                        codeSize++;
                        codeMask = (1 << codeSize) - 1;
                    }
                }
                oldCode = inCode;
            }
            top--;
            output[outputPos++] = stack[top];
        }
        while (outputPos < expected) output[outputPos++] = 0;
        return output;
    }

    private int[] readPalette(int count) throws IOException {
        int[] palette = new int[count];
        int i;
        for (i = 0; i < count; i++) {
            int red = readU8();
            int green = readU8();
            int blue = readU8();
            palette[i] = 0xFF000000 | (red << 16) | (green << 8) | blue;
        }
        return palette;
    }

    private byte[] readSubBlocks() throws IOException {
        int total = 0;
        int scan = pos;
        while (scan < data.length) {
            int size = data[scan++] & 255;
            if (size == 0) break;
            if (scan + size > data.length) throw new IOException("truncated GIF");
            total += size;
            scan += size;
        }
        byte[] result = new byte[total];
        int out = 0;
        while (true) {
            int size = readU8();
            if (size == 0) break;
            require(size);
            System.arraycopy(data, pos, result, out, size);
            pos += size;
            out += size;
        }
        return result;
    }

    private void skipSubBlocks() throws IOException {
        while (true) {
            int size = readU8();
            if (size == 0) return;
            skipBytes(size);
        }
    }

    private void skipBytes(int count) throws IOException {
        require(count);
        pos += count;
    }

    private int readU8() throws IOException {
        require(1);
        return data[pos++] & 255;
    }

    private int readU16() throws IOException {
        int lo = readU8();
        return lo | (readU8() << 8);
    }

    private void require(int count) throws IOException {
        if (count < 0 || pos + count > data.length) {
            throw new IOException("truncated GIF");
        }
    }
}
