package com.nttdocomo.ui.util3d;

/** DoJa-compatible row-major 4x4 transform. */
public final class Transform {
    private final float[] m = new float[16];

    public Transform() {
        setIdentity();
    }

    public Transform(Transform other) {
        if (other == null) throw new NullPointerException();
        System.arraycopy(other.m, 0, m, 0, 16);
    }

    public void setIdentity() {
        int i;
        for (i = 0; i < 16; i++) m[i] = 0.0f;
        m[0] = m[5] = m[10] = m[15] = 1.0f;
    }

    /* DoJa signature: rotate(axisX, axisY, axisZ, angleDegrees). */
    public void rotate(float x, float y, float z, float angle) {
        float length = FastMath.sqrt(x * x + y * y + z * z);
        if (length == 0.0f) return;
        x /= length;
        y /= length;
        z /= length;

        float c = FastMath.cos(angle);
        float s = FastMath.sin(angle);
        float t = 1.0f - c;
        float[] r = new float[16];

        r[0]  = t*x*x + c;
        r[1]  = t*x*y - s*z;
        r[2]  = t*x*z + s*y;
        r[3]  = 0.0f;

        r[4]  = t*x*y + s*z;
        r[5]  = t*y*y + c;
        r[6]  = t*y*z - s*x;
        r[7]  = 0.0f;

        r[8]  = t*x*z - s*y;
        r[9]  = t*y*z + s*x;
        r[10] = t*z*z + c;
        r[11] = 0.0f;

        r[12] = r[13] = r[14] = 0.0f;
        r[15] = 1.0f;
        multiply(r);
    }

    public void translate(float x, float y, float z) {
        float[] t = new float[16];
        t[0] = t[5] = t[10] = t[15] = 1.0f;
        t[3] = x;
        t[7] = y;
        t[11] = z;
        multiply(t);
    }

    public void scale(float x, float y, float z) {
        float[] s = new float[16];
        s[0] = x;
        s[5] = y;
        s[10] = z;
        s[15] = 1.0f;
        multiply(s);
    }

    /** Builds the DoJa view transform: camera looks along its positive Z axis. */
    public void lookAt(Vector3D eye, Vector3D center, Vector3D up) {
        if (eye == null || center == null || up == null) throw new NullPointerException();

        Vector3D f = new Vector3D(center.getX() - eye.getX(),
                                  center.getY() - eye.getY(),
                                  center.getZ() - eye.getZ());
        f.normalize();

        /* Right = forward x up. */
        Vector3D right = new Vector3D(f);
        right.cross(up);
        right.normalize();

        Vector3D realUp = new Vector3D(right);
        realUp.cross(f);
        realUp.normalize();

        setIdentity();
        m[0] = right.getX();
        m[1] = right.getY();
        m[2] = right.getZ();
        m[3] = -(right.getX()*eye.getX() + right.getY()*eye.getY() + right.getZ()*eye.getZ());

        m[4] = realUp.getX();
        m[5] = realUp.getY();
        m[6] = realUp.getZ();
        m[7] = -(realUp.getX()*eye.getX() + realUp.getY()*eye.getY() + realUp.getZ()*eye.getZ());

        m[8] = f.getX();
        m[9] = f.getY();
        m[10] = f.getZ();
        m[11] = -(f.getX()*eye.getX() + f.getY()*eye.getY() + f.getZ()*eye.getZ());

        m[12] = m[13] = m[14] = 0.0f;
        m[15] = 1.0f;
    }

    public void set(Transform other) {
        if (other == null) throw new NullPointerException();
        System.arraycopy(other.m, 0, m, 0, 16);
    }

    public float[] _matrix() { return m; }

    private void multiply(float[] r) {
        float[] out = new float[16];
        int row, col, k;
        for (row = 0; row < 4; row++) {
            for (col = 0; col < 4; col++) {
                float value = 0.0f;
                for (k = 0; k < 4; k++) {
                    value += m[row * 4 + k] * r[k * 4 + col];
                }
                out[row * 4 + col] = value;
            }
        }
        System.arraycopy(out, 0, m, 0, 16);
    }
}
