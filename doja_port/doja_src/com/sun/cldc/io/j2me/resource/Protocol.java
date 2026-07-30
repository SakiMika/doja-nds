package com.sun.cldc.io.j2me.resource;

import com.sun.cldc.io.ConnectionBaseInterface;
import com.sun.cldc.io.ResourceInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import javax.microedition.io.Connection;
import javax.microedition.io.InputConnection;

public final class Protocol implements ConnectionBaseInterface, InputConnection {
    private String resourceName;
    private boolean closed;

    public Connection openPrim(String name, int mode, boolean timeouts) {
        resourceName = name;
        while (resourceName.startsWith("/")) {
            resourceName = resourceName.substring(1);
        }
        return this;
    }

    public InputStream openInputStream() throws IOException {
        if (closed) {
            throw new IOException("closed");
        }
        return new ResourceInputStream(resourceName);
    }

    public DataInputStream openDataInputStream() throws IOException {
        return new DataInputStream(openInputStream());
    }

    public void close() {
        closed = true;
    }
}
