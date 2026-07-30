package com.nttdocomo.opt.ui.j3d;

public final class Math {
    private Math() {
    }

    public static int sin(int angle) {
        double radians = ((double) angle) * 6.283185307179586 / 4096.0;
        return (int) (java.lang.Math.sin(radians) * 4096.0);
    }
}
