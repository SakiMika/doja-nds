package com.sun.cldc.io.j2me.scratchpad;

import com.sun.cldc.io.ConnectionBaseInterface;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import javax.microedition.io.Connection;
import javax.microedition.io.Connector;
import javax.microedition.io.StreamConnection;

/**
 * DoJa ScratchPad connection backed directly by the ROM-linked .sp payload.
 *
 * v36 keeps the connection and returned streams as separate top-level
 * objects. Connector.openDataInputStream() closes the Connection immediately
 * after obtaining the stream.  In v14 Protocol was also the InputStream, so
 * that close made the returned stream unusable and the game retried forever.
 */
public final class Protocol
        implements ConnectionBaseInterface, StreamConnection {
    private int startPosition;
    private int length = -1;
    private int mode = Connector.READ;
    private boolean closed;
    private boolean inputOpened;
    private boolean outputOpened;

    public Protocol() {
    }

    private static native int nativeSize();

    static int sizeUnchecked() {
        return nativeSize();
    }
    static native int nativeRead(int position);
    static native int nativeReadBytes(int position, byte[] data,
                                      int offset, int length);
    static native void nativeWrite(int position, int value);
    static native void nativeWriteBytes(int position, byte[] data,
                                        int offset, int length);
    static native int nativeFlush();

    /** Used by the offline HTTP compatibility handler without reflection. */
    public static InputStream openRange(int position, int rangeLength)
            throws IOException {
        int size = nativeSize();
        validateRange(position, rangeLength, size);
        int available = size - position;
        int actualLength = rangeLength < 0 || rangeLength > available
                ? available : rangeLength;
        return new ScratchpadInputStream(position, actualLength);
    }

    public Connection openPrim(String name, int accessMode, boolean timeouts)
            throws IOException {
        int position = 0;
        int rangeLength = -1;
        int posIndex = name.indexOf(";pos=");
        int lengthIndex = name.indexOf(",length=");
        if (posIndex >= 0) {
            int end = lengthIndex >= 0 ? lengthIndex : name.length();
            position = parseInt(name.substring(posIndex + 5, end), 0);
        }
        if (lengthIndex >= 0) {
            rangeLength = parseInt(name.substring(lengthIndex + 8), -1);
        }
        configure(position, rangeLength, accessMode);
        return this;
    }

    private void configure(int position, int rangeLength, int accessMode)
            throws IOException {
        int size = nativeSize();
        validateRange(position, rangeLength, size);
        int available = size - position;
        startPosition = position;
        length = rangeLength < 0 || rangeLength > available
                ? available : rangeLength;
        mode = accessMode;
        closed = false;
        inputOpened = false;
        outputOpened = false;
    }

    private static void validateRange(int position, int rangeLength, int size)
            throws IOException {
        if (position < 0 || position > size || rangeLength < -1) {
            throw new IOException("ScratchPad range");
        }
    }

    private static int parseInt(String value, int fallback) {
        try {
            return Integer.parseInt(value);
        } catch (Exception e) {
            return fallback;
        }
    }

    public InputStream openInputStream() throws IOException {
        ensureConnectionOpen();
        if ((mode & Connector.READ) == 0) {
            throw new IOException("not readable");
        }
        if (inputOpened) {
            throw new IOException("input already open");
        }
        inputOpened = true;
        return new ScratchpadInputStream(startPosition, length);
    }

    public DataInputStream openDataInputStream() throws IOException {
        return new DataInputStream(openInputStream());
    }

    public OutputStream openOutputStream() throws IOException {
        ensureConnectionOpen();
        if ((mode & Connector.WRITE) == 0) {
            throw new IOException("not writable");
        }
        if (outputOpened) {
            throw new IOException("output already open");
        }
        outputOpened = true;
        return new ScratchpadOutputStream(startPosition, length);
    }

    public DataOutputStream openDataOutputStream() throws IOException {
        return new DataOutputStream(openOutputStream());
    }

    /**
     * Close only the connection object. Streams already returned by this
     * connection remain valid, matching the Connector convenience methods.
     */
    public void close() {
        closed = true;
    }

    private void ensureConnectionOpen() throws IOException {
        if (closed) {
            throw new IOException("connection closed");
        }
    }
}
