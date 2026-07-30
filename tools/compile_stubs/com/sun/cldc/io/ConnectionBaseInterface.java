package com.sun.cldc.io;
import java.io.IOException;
import javax.microedition.io.Connection;
public interface ConnectionBaseInterface {
    Connection openPrim(String name,int mode,boolean timeouts) throws IOException;
}
