package com.sun.cldc.io.j2me.scratchpad;

import java.io.ByteArrayInputStream;
import java.io.IOException;

/**
 * ByteArrayInputStream-compatible view over one indexed ScratchPad segment.
 *
 * Corpse Party's preverified bytecode declares its local variable as
 * ByteArrayInputStream.  Extending that class keeps the old verifier frames
 * valid while all reads are served directly from the ROM-linked ScratchPad.
 * The superclass receives only the one-byte token; the segment itself is
 * never copied into the KVM heap.
 */
public final class ScratchpadByteArrayInputStream extends ByteArrayInputStream {
    private int startPosition;
    private int position;
    private int endPosition;
    private int markedPosition;
    private boolean closed;

    public ScratchpadByteArrayInputStream(byte[] token) {
        super(token == null ? new byte[0] : token);
        int index = token == null || token.length == 0 ? -1 : token[0] & 255;
        if (index < 0) {
            startPosition = 0;
            position = 0;
            endPosition = 0;
            markedPosition = 0;
            closed = true;
            return;
        }
        int tablePosition = 8192 + index * 8;
        int segmentPosition = readInt(tablePosition);
        int segmentLength = readInt(tablePosition + 4);
        int size = Protocol.sizeUnchecked();
        if (segmentPosition < 0 || segmentLength < 0 ||
                segmentPosition > size || segmentLength > size - segmentPosition) {
            startPosition = 0;
            position = 0;
            endPosition = 0;
            markedPosition = 0;
            closed = true;
            return;
        }
        startPosition = segmentPosition;
        position = segmentPosition;
        endPosition = segmentPosition + segmentLength;
        markedPosition = segmentPosition;
    }

    private static int readInt(int offset) {
        return (Protocol.nativeRead(offset) << 24) |
               (Protocol.nativeRead(offset + 1) << 16) |
               (Protocol.nativeRead(offset + 2) << 8) |
               Protocol.nativeRead(offset + 3);
    }

    public synchronized int read() {
        if (closed || position >= endPosition) {
            return -1;
        }
        return Protocol.nativeRead(position++);
    }

    public synchronized int read(byte[] data, int offset, int length) {
        if (data == null) {
            throw new NullPointerException();
        }
        if (offset < 0 || length < 0 || offset > data.length - length) {
            throw new IndexOutOfBoundsException();
        }
        if (closed || position >= endPosition) {
            return -1;
        }
        if (length > endPosition - position) {
            length = endPosition - position;
        }
        if (length == 0) {
            return 0;
        }
        int count = Protocol.nativeReadBytes(position, data, offset, length);
        if (count <= 0) {
            position = endPosition;
            return -1;
        }
        position += count;
        return count;
    }

    public synchronized long skip(long count) {
        if (closed || count <= 0) {
            return 0;
        }
        int available = endPosition - position;
        if (count > available) {
            count = available;
        }
        position += (int)count;
        return count;
    }

    public synchronized int available() {
        return closed ? 0 : endPosition - position;
    }

    public boolean markSupported() {
        return true;
    }

    public synchronized void mark(int readAheadLimit) {
        if (!closed) {
            markedPosition = position;
        }
    }

    public synchronized void reset() {
        if (!closed) {
            position = markedPosition;
        }
    }

    public synchronized void close() throws IOException {
        closed = true;
        position = endPosition;
    }
}
