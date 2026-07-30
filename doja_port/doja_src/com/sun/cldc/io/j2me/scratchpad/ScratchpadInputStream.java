package com.sun.cldc.io.j2me.scratchpad;

import java.io.IOException;
import java.io.InputStream;

/**
 * Independent top-level ScratchPad input stream.
 *
 * This must not be an inner class: the old KVM previously failed while
 * linking synthetic nested stream classes. It also must not be the Protocol
 * connection itself, because Connector closes that connection before
 * returning its convenience DataInputStream.
 */
final class ScratchpadInputStream extends InputStream {
    private int position;
    private int remaining;
    private boolean closed;

    ScratchpadInputStream(int position, int length) {
        this.position = position;
        this.remaining = length;
    }

    public int read() throws IOException {
        ensureOpen();
        if (remaining == 0) {
            return -1;
        }
        int value = Protocol.nativeRead(position);
        if (value < 0) {
            remaining = 0;
            return -1;
        }
        position++;
        if (remaining > 0) {
            remaining--;
        }
        return value;
    }

    public int read(byte[] data, int offset, int length) throws IOException {
        ensureOpen();
        if (data == null) {
            throw new NullPointerException();
        }
        if (offset < 0 || length < 0 || offset > data.length - length) {
            throw new IndexOutOfBoundsException();
        }
        if (remaining == 0) {
            return -1;
        }
        if (remaining > 0 && length > remaining) {
            length = remaining;
        }
        if (length == 0) {
            return 0;
        }
        int count = Protocol.nativeReadBytes(position, data, offset, length);
        if (count <= 0) {
            remaining = 0;
            return -1;
        }
        position += count;
        if (remaining > 0) {
            remaining -= count;
        }
        return count;
    }

    public int available() {
        return remaining < 0 ? 0 : remaining;
    }

    public void close() {
        closed = true;
    }

    private void ensureOpen() throws IOException {
        if (closed) {
            throw new IOException("stream closed");
        }
    }
}
