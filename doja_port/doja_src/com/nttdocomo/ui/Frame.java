package com.nttdocomo.ui;

public abstract class Frame extends javax.microedition.lcdui.Canvas {
    public static final int SOFT_KEY_1 = 0;
    public static final int SOFT_KEY_2 = 1;

    private String soft1;
    private String soft2;

    protected Frame() {
        super();
        setFullScreenMode(true);
    }

    public void setSoftLabel(int key, String label) {
        if (key == SOFT_KEY_1) {
            soft1 = label;
        } else if (key == SOFT_KEY_2) {
            soft2 = label;
        }
    }

    public String _getSoftLabel(int key) {
        return key == SOFT_KEY_1 ? soft1 : soft2;
    }
}
