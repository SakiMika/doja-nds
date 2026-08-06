package com.nttdocomo.ui;

public abstract class Canvas extends Frame {
    public static final int KEY_0 = 0;
    public static final int KEY_1 = 1;
    public static final int KEY_2 = 2;
    public static final int KEY_3 = 3;
    public static final int KEY_4 = 4;
    public static final int KEY_5 = 5;
    public static final int KEY_6 = 6;
    public static final int KEY_7 = 7;
    public static final int KEY_8 = 8;
    public static final int KEY_9 = 9;
    public static final int KEY_ASTERISK = 10;
    public static final int KEY_POUND = 11;
    public static final int KEY_LEFT = 16;
    public static final int KEY_UP = 17;
    public static final int KEY_RIGHT = 18;
    public static final int KEY_DOWN = 19;
    public static final int KEY_SELECT = 20;
    public static final int KEY_SOFT1 = 21;
    public static final int KEY_SOFT2 = 22;

    private javax.microedition.lcdui.Image screenImage;
    private Graphics screenGraphics;
    private int keypadState;

    protected Canvas() {
        super();
    }

    public abstract void paint(Graphics graphics);

    public void processEvent(int type, int param) {
    }

    protected final void paint(javax.microedition.lcdui.Graphics graphics) {
        ensureScreen();
        paint(screenGraphics);
        graphics.drawImage(screenImage, 0, 0,
            javax.microedition.lcdui.Graphics.TOP | javax.microedition.lcdui.Graphics.LEFT);
    }

    public final Graphics getGraphics() {
        ensureScreen();
        return screenGraphics;
    }

    private void ensureScreen() {
        if (screenImage == null) {
            screenImage = javax.microedition.lcdui.Image.createImage(getWidth(), getHeight());
            screenGraphics = new Graphics(screenImage.getGraphics(), this, getWidth(), getHeight());
        }
    }

    public final int getKeypadState() {
        return keypadState;
    }

    final void _flush() {
        repaint();
        serviceRepaints();
    }

    protected final void keyPressed(int keyCode) {
        int key = mapKey(keyCode);
        if (key >= 0) {
            keypadState |= (1 << key);
            processEvent(Display.KEY_PRESSED_EVENT, key);
        }
    }

    protected final void keyRepeated(int keyCode) {
        int key = mapKey(keyCode);
        if (key >= 0) {
            keypadState |= (1 << key);
            processEvent(Display.KEY_PRESSED_EVENT, key);
        }
    }

    protected final void keyReleased(int keyCode) {
        int key = mapKey(keyCode);
        if (key >= 0) {
            keypadState &= ~(1 << key);
            processEvent(Display.KEY_RELEASED_EVENT, key);
        }
    }

    private static int mapKey(int keyCode) {
        switch (keyCode) {
            case javax.microedition.lcdui.Canvas.LEFT: return KEY_LEFT;
            case javax.microedition.lcdui.Canvas.UP: return KEY_UP;
            case javax.microedition.lcdui.Canvas.RIGHT: return KEY_RIGHT;
            case javax.microedition.lcdui.Canvas.DOWN: return KEY_DOWN;
            case javax.microedition.lcdui.Canvas.FIRE: return KEY_SELECT;
            case javax.microedition.lcdui.Canvas.SOFT_L: return KEY_SOFT1;
            case javax.microedition.lcdui.Canvas.SOFT_R: return KEY_SOFT2;

            /*
             * Pstros ConfigData uses the conventional MIDP negative key codes
             * when configurable controls are active. Accept them as a fallback
             * so a stale configuration can never turn every DoJa key into -1.
             */
            case -3: return KEY_LEFT;
            case -1: return KEY_UP;
            case -4: return KEY_RIGHT;
            case -2: return KEY_DOWN;
            case -5: return KEY_SELECT;
            case -6: return KEY_SOFT1;
            case -7: return KEY_SOFT2;
            case javax.microedition.lcdui.Canvas.KEY_NUM0: return KEY_0;
            case javax.microedition.lcdui.Canvas.KEY_NUM1: return KEY_1;
            case javax.microedition.lcdui.Canvas.KEY_NUM2: return KEY_2;
            case javax.microedition.lcdui.Canvas.KEY_NUM3: return KEY_3;
            case javax.microedition.lcdui.Canvas.KEY_NUM4: return KEY_4;
            case javax.microedition.lcdui.Canvas.KEY_NUM5: return KEY_5;
            case javax.microedition.lcdui.Canvas.KEY_NUM6: return KEY_6;
            case javax.microedition.lcdui.Canvas.KEY_NUM7: return KEY_7;
            case javax.microedition.lcdui.Canvas.KEY_NUM8: return KEY_8;
            case javax.microedition.lcdui.Canvas.KEY_NUM9: return KEY_9;
            case javax.microedition.lcdui.Canvas.KEY_STAR: return KEY_ASTERISK;
            case javax.microedition.lcdui.Canvas.KEY_POUND: return KEY_POUND;
            default: return -1;
        }
    }
}
