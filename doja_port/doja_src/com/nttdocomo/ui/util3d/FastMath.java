package com.nttdocomo.ui.util3d;

/** DoJa 3D trigonometry uses degrees, not radians. */
public final class FastMath {
    private static final double DEG_TO_RAD = 0.017453292519943295;
    private FastMath() {
    }

    public static float sin(float value) {
        return (float)java.lang.Math.sin((double)value * DEG_TO_RAD);
    }

    public static float cos(float value) {
        return (float)java.lang.Math.cos((double)value * DEG_TO_RAD);
    }

    public static float tan(float value) {
        return (float)java.lang.Math.tan((double)value * DEG_TO_RAD);
    }

    public static float sqrt(float value) { return (float)java.lang.Math.sqrt(value); }
}
