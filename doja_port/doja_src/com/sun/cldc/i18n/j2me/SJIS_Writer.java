package com.sun.cldc.i18n.j2me;

import com.sun.cldc.i18n.StreamWriter;
import java.io.IOException;
import nds.doja.encoding.Cp932Codec;

/** Default DoJa byte encoder: Shift-JIS / Windows-31J (CP932). */
public class SJIS_Writer extends StreamWriter {
    public synchronized void write(int value) throws IOException {
        int encoded = Cp932Codec.encode((char)value);
        if (encoded < 0) {
            encoded = '?';
        }
        if (encoded <= 0xFF) {
            out.write(encoded);
        } else {
            out.write((encoded >>> 8) & 0xFF);
            out.write(encoded & 0xFF);
        }
    }

    public synchronized void write(char[] cbuf, int off, int len) throws IOException {
        if (off < 0 || len < 0 || off > cbuf.length - len) {
            throw new IndexOutOfBoundsException();
        }
        while (len-- > 0) {
            write(cbuf[off++]);
        }
    }

    public synchronized void write(String text, int off, int len) throws IOException {
        if (off < 0 || len < 0 || off > text.length() - len) {
            throw new IndexOutOfBoundsException();
        }
        while (len-- > 0) {
            write(text.charAt(off++));
        }
    }

    public int sizeOf(char[] array, int offset, int length) {
        if (offset < 0 || length < 0 || offset > array.length - length) {
            throw new IndexOutOfBoundsException();
        }
        int size = 0;
        int end = offset + length;
        while (offset < end) {
            int encoded = Cp932Codec.encode(array[offset++]);
            size += encoded > 0xFF ? 2 : 1;
        }
        return size;
    }
}
