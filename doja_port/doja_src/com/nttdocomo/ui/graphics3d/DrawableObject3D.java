package com.nttdocomo.ui.graphics3d;

import com.nttdocomo.ui.Graphics;
import com.nttdocomo.ui.util3d.Transform;

public class DrawableObject3D extends Object3D {
    protected DrawableObject3D() {
    }

    public void _render(Graphics graphics, Transform transform) {
        // Generic compatibility hook. Primitive supplies a lightweight path.
    }
}
