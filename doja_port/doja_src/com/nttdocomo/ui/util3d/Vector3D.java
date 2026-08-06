package com.nttdocomo.ui.util3d;

public final class Vector3D {
    private float x;
    private float y;
    private float z;

    public Vector3D(float xValue, float yValue, float zValue) {
        x = xValue; y = yValue; z = zValue;
    }

    public Vector3D(Vector3D other) {
        if (other == null) throw new NullPointerException();
        x = other.x; y = other.y; z = other.z;
    }

    public float getX() { return x; }
    public float getY() { return y; }
    public float getZ() { return z; }

    public void normalize() {
        float length = FastMath.sqrt(x * x + y * y + z * z);
        if (length != 0.0f) {
            x /= length; y /= length; z /= length;
        }
    }

    public void cross(Vector3D other) {
        if (other == null) throw new NullPointerException();
        float nx = y * other.z - z * other.y;
        float ny = z * other.x - x * other.z;
        float nz = x * other.y - y * other.x;
        x = nx; y = ny; z = nz;
    }
}
