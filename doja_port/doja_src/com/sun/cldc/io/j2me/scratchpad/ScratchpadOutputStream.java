package com.sun.cldc.io.j2me.scratchpad;

import java.io.IOException;
import java.io.OutputStream;

/**
 * Sparse overlay writer backed by the native persistent ScratchPad save.
 * The native layer writes an atomic sparse .sav file when this stream closes.
 */
final class ScratchpadOutputStream extends OutputStream {
    private int position;
    private int remaining;
    private boolean closed;

    ScratchpadOutputStream(int position, int length) {
        this.position = position;
        this.remaining = length;
    }

    public void write(int value) throws IOException {
        ensureOpen();
        if (remaining == 0) {
            return;
        }
        Protocol.nativeWrite(position++, value);
        if (remaining > 0) {
            remaining--;
        }
    }

    public void write(byte[] data, int offset, int length) throws IOException {
        ensureOpen();
        if (data == null) {
            throw new NullPointerException();
        }
        if (offset < 0 || length < 0 || offset > data.length - length) {
            throw new IndexOutOfBoundsException();
        }
        if (remaining >= 0 && length > remaining) {
            length = remaining;
        }
        if (length <= 0) {
            return;
        }
        Protocol.nativeWriteBytes(position, data, offset, length);
        position += length;
        if (remaining > 0) {
            remaining -= length;
        }
    }

    public void flush() {
        if (!closed) {
            Protocol.nativeFlush();
        }
    }

    public void close() {
        if (!closed) {
            // Flush before marking closed so an explicit close is also a
            // persistence boundary for DataOutputStream callers.
            Protocol.nativeFlush();
            closed = true;
        }
    }

    private void ensureOpen() throws IOException {
        if (closed) {
            throw new IOException("closed");
        }
    }
}
