package com.nttdocomo.ui.util3d;

/** Compact 4x4 transform used by the DoJa 3D compatibility layer. */
public final class Transform {
    private final float[] m = new float[16];

    public Transform() {
        setIdentity();
    }

    public void setIdentity() {
        int i;
        for (i = 0; i < 16; i++) m[i] = 0.0f;
        m[0] = m[5] = m[10] = m[15] = 1.0f;
    }

    public void rotate(float angle, float x, float y, float z) {
        float length = FastMath.sqrt(x * x + y * y + z * z);
        if (length == 0.0f) return;
        x /= length; y /= length; z /= length;
        float c = FastMath.cos(angle);
        float s = FastMath.sin(angle);
        float t = 1.0f - c;
        float[] r = new float[16];
        r[0] = t*x*x + c;     r[1] = t*x*y - s*z; r[2] = t*x*z + s*y;
        r[4] = t*x*y + s*z;   r[5] = t*y*y + c;   r[6] = t*y*z - s*x;
        r[8] = t*x*z - s*y;   r[9] = t*y*z + s*x; r[10] = t*z*z + c;
        r[15] = 1.0f;
        multiply(r);
    }

    public void lookAt(Vector3D eye, Vector3D center, Vector3D up) {
        if (eye == null || center == null || up == null) throw new NullPointerException();
        Vector3D f = new Vector3D(center.getX() - eye.getX(),
                                  center.getY() - eye.getY(),
                                  center.getZ() - eye.getZ());
        f.normalize();
        Vector3D s = new Vector3D(f);
        s.cross(up);
        s.normalize();
        Vector3D u = new Vector3D(s);
        u.cross(f);
        setIdentity();
        m[0] = s.getX(); m[1] = s.getY(); m[2] = s.getZ();
        m[4] = u.getX(); m[5] = u.getY(); m[6] = u.getZ();
        m[8] = -f.getX(); m[9] = -f.getY(); m[10] = -f.getZ();
        m[12] = -(s.getX()*eye.getX() + s.getY()*eye.getY() + s.getZ()*eye.getZ());
        m[13] = -(u.getX()*eye.getX() + u.getY()*eye.getY() + u.getZ()*eye.getZ());
        m[14] = f.getX()*eye.getX() + f.getY()*eye.getY() + f.getZ()*eye.getZ();
    }

    public float[] _matrix() { return m; }

    private void multiply(float[] r) {
        float[] out = new float[16];
        int row, col, k;
        for (row = 0; row < 4; row++) {
            for (col = 0; col < 4; col++) {
                float value = 0.0f;
                for (k = 0; k < 4; k++) value += m[row * 4 + k] * r[k * 4 + col];
                out[row * 4 + col] = value;
            }
        }
        System.arraycopy(out, 0, m, 0, 16);
    }
}
