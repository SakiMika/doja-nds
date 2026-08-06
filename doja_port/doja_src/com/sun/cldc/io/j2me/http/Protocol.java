package com.sun.cldc.io.j2me.http;

import com.nttdocomo.io.HttpConnection;
import com.sun.cldc.io.ConnectionBaseInterface;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import javax.microedition.io.Connection;

/**
 * DoJa standalone HTTP bridge.
 *
 * Network access is unavailable on this standalone NDS target. The one
 * legacy offline downloader bridge is enabled only when prepare_doja.py
 * detects the exact supported Corpse Party signature. Other games are never
 * redirected into another title's ScratchPad layout.
 */
public final class Protocol implements ConnectionBaseInterface, HttpConnection {
    private static final int DATA_OFFSET = 8192;
    private static final int DOWNLOAD_CHUNK = 102400;

    private boolean closed;
    private String method = "GET";
    private String target = "";

    public Connection openPrim(String name, int mode, boolean timeouts) {
        target = name == null ? "" : name;
        return this;
    }

    public void setRequestMethod(String value) throws IOException {
        ensureOpen();
        method = value;
    }

    public void connect() throws IOException {
        ensureOpen();
    }

    public InputStream openInputStream() throws IOException {
        ensureOpen();

        if (!corpsePartyCompatEnabled()) {
            throw new IOException("HTTP unavailable on standalone NDS");
        }

        String file = finalPathPart(target);
        if ("init.bin".equals(file)) {
            System.out.println("OFFLINE HTTP init.bin native SP");
            return com.sun.cldc.io.j2me.scratchpad.Protocol.openRange(1, 4);
        }

        int chunk = parseChunkName(file);
        if (chunk >= 0) {
            int total = readDownloadLength();
            int offset = chunk * DOWNLOAD_CHUNK;
            int length = total - offset;
            if (length > DOWNLOAD_CHUNK) {
                length = DOWNLOAD_CHUNK;
            }
            if (length < 0) {
                length = 0;
            }
            StringBuffer message = new StringBuffer("OFFLINE HTTP chunk ");
            message.append(chunk);
            message.append(" pos=");
            message.append(DATA_OFFSET + offset);
            message.append(" len=");
            message.append(length);
            System.out.println(message.toString());
            return com.sun.cldc.io.j2me.scratchpad.Protocol.openRange(DATA_OFFSET + offset, length);
        }

        StringBuffer blocked = new StringBuffer("OFFLINE HTTP blocked: ");
        blocked.append(target);
        System.out.println(blocked.toString());
        return new ByteArrayInputStream(new byte[0]);
    }

    public void close() {
        closed = true;
    }

    private void ensureOpen() throws IOException {
        if (closed) {
            throw new IOException("closed");
        }
    }

    private static boolean corpsePartyCompatEnabled() {
        return "1".equals(System.getProperty("DoJa-Compat-Corpse-Party"));
    }

    private static String finalPathPart(String value) {
        int query = value.indexOf('?');
        if (query >= 0) {
            value = value.substring(0, query);
        }
        int slash = value.lastIndexOf('/');
        return slash >= 0 ? value.substring(slash + 1) : value;
    }

    private static int parseChunkName(String file) {
        if (file == null || !file.endsWith(".bin") || file.length() <= 4) {
            return -1;
        }
        int value = 0;
        int end = file.length() - 4;
        int i;
        for (i = 0; i < end; i++) {
            char c = file.charAt(i);
            if (c < '0' || c > '9') {
                return -1;
            }
            value = value * 10 + (c - '0');
            if (value > 9999) {
                return -1;
            }
        }
        return value;
    }

    private static int readDownloadLength() throws IOException {
        InputStream in = com.sun.cldc.io.j2me.scratchpad.Protocol.openRange(1, 4);
        int b0 = in.read();
        int b1 = in.read();
        int b2 = in.read();
        int b3 = in.read();
        in.close();
        if ((b0 | b1 | b2 | b3) < 0) {
            throw new IOException("ScratchPad marker truncated");
        }
        return (b0 << 24) | (b1 << 16) | (b2 << 8) | b3;
    }
}
