package com.nttdocomo.ui.graphics3d;

public final class Fog {
    public static final int NONE = 0;
    public static final int LINEAR = 1;
    public static final int EXP = 2;
    public static final int EXP2 = 3;

    private int mode;
    private int color;
    private float near;
    private float far;

    public Fog() {
    }

    public void setMode(int value) { mode = value; }
    public int getMode() { return mode; }
    public void setColor(int value) { color = value; }
    public int getColor() { return color; }
    public void setLinear(float start, float end) { near = start; far = end; }
    public float getNear() { return near; }
    public float getFar() { return far; }
}
