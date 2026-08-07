package com.nttdocomo.util;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Hashtable;

/**
 * Small ZIP/JAR reader for DoJa resource bundles.
 *
 * v46 is optimized for FF4A's repacked one-entry STORED bundles. STORED
 * entries keep a slice of the already-read ZIP array instead of allocating
 * and copying a second full payload. DEFLATE remains available for generic
 * games and older packages.
 */
public final class JarInflater {
    private static final boolean STORED_ZERO_COPY = true;

    private static final class Entry {
        final byte[] data;
        final int offset;
        final int length;

        Entry(byte[] data, int offset, int length) {
            this.data = data;
            this.offset = offset;
            this.length = length;
        }
    }

    private final Hashtable entries = new Hashtable();
    private boolean closed;

    public JarInflater(InputStream input) {
        if (input == null) throw new NullPointerException();
        try {
            parse(readAll(input));
        } catch (IOException e) {
            throw new IllegalArgumentException("invalid jar");
        }
    }

    public InputStream getInputStream(String name) {
        checkOpen();
        Entry entry = (Entry)entries.get(name);
        return entry == null ? null :
            new ByteArrayInputStream(entry.data, entry.offset, entry.length);
    }

    public long getSize(String name) {
        checkOpen();
        Entry entry = (Entry)entries.get(name);
        return entry == null ? -1L : (long)entry.length;
    }

    public void close() {
        entries.clear();
        closed = true;
    }

    private void checkOpen() {
        if (closed) throw new RuntimeException("closed");
    }

    private void parse(byte[] zip) {
        int eocd = findSignatureBackward(zip, 0x06054b50L, zip.length - 22);
        if (eocd < 0 || eocd + 22 > zip.length) {
            throw new IllegalArgumentException("missing zip directory");
        }
        int count = u16(zip, eocd + 10);
        int directory = checkedInt(u32(zip, eocd + 16));
        int p = directory;
        int i;
        for (i = 0; i < count; i++) {
            if (p < 0 || p + 46 > zip.length || u32(zip, p) != 0x02014b50L) {
                throw new IllegalArgumentException("bad zip directory");
            }
            int method = u16(zip, p + 10);
            int compressed = checkedInt(u32(zip, p + 20));
            int uncompressed = checkedInt(u32(zip, p + 24));
            int nameLength = u16(zip, p + 28);
            int extraLength = u16(zip, p + 30);
            int commentLength = u16(zip, p + 32);
            int localOffset = checkedInt(u32(zip, p + 42));
            if (p + 46 + nameLength + extraLength + commentLength > zip.length) {
                throw new IllegalArgumentException("truncated zip directory");
            }
            String name = decodeName(zip, p + 46, nameLength);
            if (localOffset < 0 || localOffset + 30 > zip.length ||
                    u32(zip, localOffset) != 0x04034b50L) {
                throw new IllegalArgumentException("bad local header");
            }
            int localNameLength = u16(zip, localOffset + 26);
            int localExtraLength = u16(zip, localOffset + 28);
            int dataOffset = localOffset + 30 + localNameLength + localExtraLength;
            if (dataOffset < 0 || compressed < 0 || dataOffset + compressed > zip.length) {
                throw new IllegalArgumentException("truncated zip entry");
            }
            Entry entry;
            if (method == 0) {
                if (compressed != uncompressed) {
                    throw new IllegalArgumentException("bad stored entry");
                }
                // v46 STORED_ZERO_COPY: retain a slice of the ZIP backing array.
                entry = new Entry(zip, dataOffset, uncompressed);
            } else if (method == 8) {
                byte[] data = RawInflater.inflate(zip, dataOffset, compressed, uncompressed);
                entry = new Entry(data, 0, data.length);
            } else {
                throw new IllegalArgumentException("unsupported zip method");
            }
            entries.put(name, entry);
            p += 46 + nameLength + extraLength + commentLength;
        }
    }

    private static byte[] readAll(InputStream input) throws IOException {
        // ScratchpadInputStream reports its exact segment length. Allocate once
        // and fill it directly, avoiding ByteArrayOutputStream growth and the
        // extra full-size copy performed by toByteArray().
        int expected = input.available();
        if (expected > 0) {
            byte[] exact = new byte[expected];
            int position = 0;
            while (position < expected) {
                int count = input.read(exact, position, expected - position);
                if (count < 0) break;
                if (count == 0) continue;
                position += count;
            }
            if (position == expected) return exact;

            ByteArrayOutputStream partial = new ByteArrayOutputStream(expected + 16384);
            if (position > 0) partial.write(exact, 0, position);
            byte[] buffer = new byte[16384];
            int n;
            while ((n = input.read(buffer)) >= 0) {
                if (n > 0) partial.write(buffer, 0, n);
            }
            return partial.toByteArray();
        }

        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[16384];
        int n;
        while ((n = input.read(buffer)) >= 0) {
            if (n > 0) out.write(buffer, 0, n);
        }
        return out.toByteArray();
    }

    private static int findSignatureBackward(byte[] data, long signature, int start) {
        int p = start;
        if (p > data.length - 4) p = data.length - 4;
        int minimum = data.length - 65557;
        if (minimum < 0) minimum = 0;
        for (; p >= minimum; p--) if (u32(data, p) == signature) return p;
        return -1;
    }

    private static String decodeName(byte[] data, int offset, int length) {
        StringBuffer value = new StringBuffer(length);
        int i;
        for (i = 0; i < length; i++) value.append((char)(data[offset + i] & 255));
        return value.toString();
    }

    private static int checkedInt(long value) {
        if (value < 0 || value > 0x7fffffffL) throw new IllegalArgumentException("zip too large");
        return (int)value;
    }

    private static int u16(byte[] b, int p) {
        return (b[p] & 255) | ((b[p + 1] & 255) << 8);
    }

    private static long u32(byte[] b, int p) {
        return ((long)b[p] & 255L) |
               (((long)b[p + 1] & 255L) << 8) |
               (((long)b[p + 2] & 255L) << 16) |
               (((long)b[p + 3] & 255L) << 24);
    }

    /** Raw RFC1951 inflater with no java.util.zip dependency (CLDC safe). */
    private static final class RawInflater {
        private static final int[] LENGTH_BASE = {
            3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,
            35,43,51,59,67,83,99,115,131,163,195,227,258
        };
        private static final int[] LENGTH_EXTRA = {
            0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,
            3,3,3,3,4,4,4,4,5,5,5,5,0
        };
        private static final int[] DIST_BASE = {
            1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,
            257,385,513,769,1025,1537,2049,3073,4097,6145,
            8193,12289,16385,24577
        };
        private static final int[] DIST_EXTRA = {
            0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,
            7,7,8,8,9,9,10,10,11,11,12,12,13,13
        };
        private static final int[] CODE_ORDER = {
            16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15
        };

        private static final Huffman FIXED_LITERAL = createFixedLiteral();
        private static final Huffman FIXED_DISTANCE = createFixedDistance();

        static byte[] inflate(byte[] input, int offset, int length, int expected) {
            BitReader bits = new BitReader(input, offset, length);
            byte[] output = new byte[expected];
            int out = 0;
            boolean last;
            do {
                last = bits.readBits(1) != 0;
                int type = bits.readBits(2);
                if (type == 0) {
                    bits.alignByte();
                    int stored = bits.readBits(16);
                    int inverse = bits.readBits(16);
                    if (((stored ^ 0xffff) & 0xffff) != inverse) {
                        throw new IllegalArgumentException("bad stored block");
                    }
                    if (out + stored > output.length) throw new IllegalArgumentException("inflate overflow");
                    int i;
                    for (i = 0; i < stored; i++) output[out++] = (byte)bits.readBits(8);
                } else if (type == 1 || type == 2) {
                    Huffman literal;
                    Huffman distance;
                    if (type == 1) {
                        /* Fixed RFC1951 trees never change.  Reusing them avoids
                         * rebuilding 320 tree nodes for every compressed block,
                         * which is especially expensive on the DS CPU. */
                        literal = FIXED_LITERAL;
                        distance = FIXED_DISTANCE;
                    } else {
                        int hlit = bits.readBits(5) + 257;
                        int hdist = bits.readBits(5) + 1;
                        int hclen = bits.readBits(4) + 4;
                        int[] codeLengths = new int[19];
                        int i;
                        for (i = 0; i < hclen; i++) codeLengths[CODE_ORDER[i]] = bits.readBits(3);
                        Huffman codeTree = new Huffman(codeLengths);
                        int[] all = new int[hlit + hdist];
                        int position = 0;
                        while (position < all.length) {
                            int symbol = codeTree.decode(bits);
                            if (symbol <= 15) {
                                all[position++] = symbol;
                            } else if (symbol == 16) {
                                if (position == 0) throw new IllegalArgumentException("bad repeat");
                                int repeat = bits.readBits(2) + 3;
                                int value = all[position - 1];
                                while (repeat-- > 0 && position < all.length) all[position++] = value;
                            } else if (symbol == 17) {
                                int repeat = bits.readBits(3) + 3;
                                while (repeat-- > 0 && position < all.length) all[position++] = 0;
                            } else if (symbol == 18) {
                                int repeat = bits.readBits(7) + 11;
                                while (repeat-- > 0 && position < all.length) all[position++] = 0;
                            } else {
                                throw new IllegalArgumentException("bad code length");
                            }
                        }
                        int[] ll = new int[hlit];
                        int[] dd = new int[hdist];
                        System.arraycopy(all, 0, ll, 0, hlit);
                        System.arraycopy(all, hlit, dd, 0, hdist);
                        literal = new Huffman(ll);
                        distance = new Huffman(dd);
                    }
                    while (true) {
                        int symbol = literal.decode(bits);
                        if (symbol < 256) {
                            if (out >= output.length) throw new IllegalArgumentException("inflate overflow");
                            output[out++] = (byte)symbol;
                        } else if (symbol == 256) {
                            break;
                        } else if (symbol <= 285) {
                            int index = symbol - 257;
                            int copyLength = LENGTH_BASE[index] + bits.readBits(LENGTH_EXTRA[index]);
                            int distSymbol = distance.decode(bits);
                            if (distSymbol < 0 || distSymbol >= DIST_BASE.length) {
                                throw new IllegalArgumentException("bad distance");
                            }
                            int back = DIST_BASE[distSymbol] + bits.readBits(DIST_EXTRA[distSymbol]);
                            if (back <= 0 || back > out || out + copyLength > output.length) {
                                throw new IllegalArgumentException("bad back reference");
                            }
                            out = copyMatch(output, out, back, copyLength);
                        } else {
                            throw new IllegalArgumentException("bad literal");
                        }
                    }
                } else {
                    throw new IllegalArgumentException("reserved block");
                }
            } while (!last);
            if (out != expected) {
                byte[] exact = new byte[out];
                System.arraycopy(output, 0, exact, 0, out);
                return exact;
            }
            return output;
        }

        private static int copyMatch(byte[] output, int out, int back, int length) {
            /* Start with one complete source period, then double the bytes that
             * have already been produced.  This preserves RFC1951 overlapping
             * match semantics while replacing long byte-at-a-time loops with
             * native System.arraycopy operations. */
            int copied = back < length ? back : length;
            System.arraycopy(output, out - back, output, out, copied);
            int start = out;
            while (copied < length) {
                int chunk = copied;
                if (chunk > length - copied) chunk = length - copied;
                System.arraycopy(output, start, output, start + copied, chunk);
                copied += chunk;
            }
            return out + length;
        }

        private static Huffman createFixedLiteral() {
            int[] lengths = new int[288];
            int i;
            for (i = 0; i <= 143; i++) lengths[i] = 8;
            for (; i <= 255; i++) lengths[i] = 9;
            for (; i <= 279; i++) lengths[i] = 7;
            for (; i <= 287; i++) lengths[i] = 8;
            return new Huffman(lengths);
        }

        private static Huffman createFixedDistance() {
            int[] lengths = new int[32];
            int i;
            for (i = 0; i < lengths.length; i++) lengths[i] = 5;
            return new Huffman(lengths);
        }
    }

    private static final class BitReader {
        private final byte[] input;
        private final int end;
        private int position;
        private int hold;
        private int count;

        BitReader(byte[] bytes, int offset, int length) {
            input = bytes;
            position = offset;
            end = offset + length;
        }

        int readBits(int amount) {
            while (count < amount) {
                if (position >= end) throw new IllegalArgumentException("truncated deflate");
                hold |= (input[position++] & 255) << count;
                count += 8;
            }
            int mask = amount == 32 ? -1 : ((1 << amount) - 1);
            int value = hold & mask;
            hold >>>= amount;
            count -= amount;
            return value;
        }

        void alignByte() {
            hold = 0;
            count = 0;
        }
    }

    private static final class Huffman {
        private int[] zero;
        private int[] one;
        private int[] symbol;
        private int nodes = 1;

        Huffman(int[] lengths) {
            int maxNodes = lengths.length * 2 + 1;
            zero = new int[maxNodes];
            one = new int[maxNodes];
            symbol = new int[maxNodes];
            int i;
            for (i = 0; i < symbol.length; i++) symbol[i] = -1;
            int[] count = new int[16];
            int max = 0;
            for (i = 0; i < lengths.length; i++) {
                int length = lengths[i];
                if (length < 0 || length > 15) throw new IllegalArgumentException("bad huffman length");
                if (length > 0) { count[length]++; if (length > max) max = length; }
            }
            if (max == 0) {
                // RFC1951 permits a single unused distance alphabet in a block
                // that never emits a length. Give it a harmless zero symbol.
                lengths = new int[] { 1 };
                count[1] = 1;
                max = 1;
            }
            int[] next = new int[16];
            int code = 0;
            for (i = 1; i <= 15; i++) {
                code = (code + count[i - 1]) << 1;
                next[i] = code;
            }
            int s;
            for (s = 0; s < lengths.length; s++) {
                int length = lengths[s];
                if (length == 0) continue;
                int canonical = next[length]++;
                int reversed = reverse(canonical, length);
                int node = 0;
                int bit;
                for (bit = 0; bit < length; bit++) {
                    boolean right = ((reversed >>> bit) & 1) != 0;
                    int child = right ? one[node] : zero[node];
                    if (child == 0) {
                        if (nodes >= symbol.length) throw new IllegalArgumentException("huffman overflow");
                        child = nodes++;
                        if (right) one[node] = child; else zero[node] = child;
                    }
                    node = child;
                }
                symbol[node] = s;
            }
        }

        int decode(BitReader bits) {
            int node = 0;
            while (symbol[node] < 0) {
                node = bits.readBits(1) == 0 ? zero[node] : one[node];
                if (node == 0) throw new IllegalArgumentException("invalid huffman code");
            }
            return symbol[node];
        }

        private static int reverse(int value, int length) {
            int result = 0;
            int i;
            for (i = 0; i < length; i++) {
                result = (result << 1) | (value & 1);
                value >>>= 1;
            }
            return result;
        }
    }
}
