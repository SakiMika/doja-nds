package com.nttdocomo.ui.graphics3d;

import com.nttdocomo.ui.util3d.Transform;

public interface Graphics3D {
    void flushBuffer();
    void renderObject3D(DrawableObject3D object, Transform transform);
    void setClipRectFor3D(int x, int y, int width, int height);
    void setFog(Fog fog);
    void setPerspectiveView(float near, float far, float angle);
    void setTransform(Transform transform);
}
