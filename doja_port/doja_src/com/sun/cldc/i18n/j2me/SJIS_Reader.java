package com.sun.cldc.i18n.j2me;

import com.sun.cldc.i18n.StreamReader;
import java.io.IOException;
import nds.doja.encoding.Cp932Codec;

/** Default DoJa byte decoder: Shift-JIS / Windows-31J (CP932). */
public class SJIS_Reader extends StreamReader {
    public synchronized int read() throws IOException {
        int first = in.read();
        if (first < 0) {
            return -1;
        }
        if (Cp932Codec.isLead(first)) {
            int second = in.read();
            if (second < 0) {
                return '\u3013';
            }
            return Cp932Codec.decodePair(first, second);
        }
        return Cp932Codec.decodeSingle(first);
    }

    public synchronized int read(char[] cbuf, int off, int len) throws IOException {
        if (off < 0 || len < 0 || off > cbuf.length - len) {
            throw new IndexOutOfBoundsException();
        }
        if (len == 0) {
            return 0;
        }
        int count = 0;
        while (count < len) {
            int value = read();
            if (value < 0) {
                return count == 0 ? -1 : count;
            }
            cbuf[off + count] = (char)value;
            count++;
        }
        return count;
    }

    public int sizeOf(byte[] array, int offset, int length) {
        if (offset < 0 || length < 0 || offset > array.length - length) {
            throw new IndexOutOfBoundsException();
        }
        int end = offset + length;
        int count = 0;
        while (offset < end) {
            int first = array[offset++] & 0xFF;
            if (Cp932Codec.isLead(first) && offset < end) {
                offset++;
            }
            count++;
        }
        return count;
    }
}
