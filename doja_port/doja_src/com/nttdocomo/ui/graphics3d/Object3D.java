package com.nttdocomo.ui.graphics3d;

/** Base DoJa 3D resource. */
public class Object3D {
    private byte[] encoded;

    protected Object3D() {
    }

    protected Object3D(byte[] data) {
        encoded = data;
    }

    public static Object3D createInstance(byte[] data) {
        if (data == null) throw new NullPointerException();
        // FF4A and many DoJa titles use Object3D.createInstance for textures.
        // Texture retains the encoded payload for the software renderer.
        return new Texture(data);
    }

    public void dispose() {
        encoded = null;
    }

    public byte[] _encoded() {
        return encoded;
    }
}
