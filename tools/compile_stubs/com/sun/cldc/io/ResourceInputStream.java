package com.sun.cldc.io;
import java.io.InputStream;
import java.io.IOException;
public class ResourceInputStream extends InputStream {
    public ResourceInputStream(String name) throws IOException {}
    public int read() throws IOException { return -1; }
    public int read(byte[] b,int off,int len) throws IOException { return -1; }
    public int available() throws IOException { return 0; }
    public void close() throws IOException {}
}
