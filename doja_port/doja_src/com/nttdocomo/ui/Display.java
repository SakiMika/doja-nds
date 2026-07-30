package com.nttdocomo.ui;

import javax.microedition.midlet.MIDlet;

public final class Display {
    public static final int KEY_PRESSED_EVENT = 0;
    public static final int KEY_RELEASED_EVENT = 1;

    private static Frame current;
    private static final BridgeMidlet BRIDGE = new BridgeMidlet();

    private Display() {
    }

    public static void setCurrent(Frame frame) {
        current = frame;
        javax.microedition.lcdui.Display.getDisplay(BRIDGE).setCurrent(frame);
    }

    public static Frame getCurrent() {
        return current;
    }

    private static final class BridgeMidlet extends MIDlet {
        protected void startApp() {
        }

        protected void pauseApp() {
        }

        protected void destroyApp(boolean unconditional) {
        }
    }
}
