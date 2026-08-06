package com.nttdocomo.ui.graphics3d;

import com.nttdocomo.ui.Graphics;
import com.nttdocomo.ui.util3d.Transform;

/** Mutable primitive buffers matching the DoJa binary API. */
public final class Primitive extends DrawableObject3D {
    public static final int POINTS = 1;
    public static final int LINES = 2;
    public static final int TRIANGLES = 3;
    public static final int QUADS = 4;
    public static final int POINT_SPRITES = 5;

    private final int primitiveType;
    private final int attributes;
    private final int count;
    private final int[] vertices;
    private final int[] textureCoordinates;
    private Texture texture;
    private int blendMode;
    private boolean perspectiveCorrection;
    private float transparency;

    public Primitive(int type, int attributeFlags, int primitiveCount) {
        if (primitiveCount < 0) throw new IllegalArgumentException();
        primitiveType = type;
        attributes = attributeFlags;
        count = primitiveCount;
        int vertexComponents;
        int textureComponents;
        switch (type) {
            case POINTS:
            case POINT_SPRITES:
                vertexComponents = 3;
                textureComponents = 2;
                break;
            case LINES:
                vertexComponents = 6;
                textureComponents = 4;
                break;
            case TRIANGLES:
                vertexComponents = 9;
                textureComponents = 6;
                break;
            case QUADS:
            default:
                vertexComponents = 12;
                textureComponents = 8;
                break;
        }
        vertices = new int[primitiveCount * vertexComponents];
        textureCoordinates = new int[primitiveCount * textureComponents];
    }

    public int[] getVertexArray() { return vertices; }
    public int[] getTextureCoordArray() { return textureCoordinates; }
    public int size() { return count; }
    public void setTexture(Texture value) { texture = value; }
    public void setBlendMode(int value) { blendMode = value; }
    public void setPerspectiveCorrectionEnabled(boolean value) { perspectiveCorrection = value; }
    public void setTransparency(float value) { transparency = value; }

    public void _render(Graphics graphics, Transform transform) {
        // Keep a stable, non-crashing software fallback. The buffers and state
        // are preserved exactly so a fuller rasterizer can consume them later.
    }

    public int _type() { return primitiveType; }
    public int _attributes() { return attributes; }
    public Texture _texture() { return texture; }
    public int _blendMode() { return blendMode; }
    public boolean _perspectiveCorrection() { return perspectiveCorrection; }
    public float _transparency() { return transparency; }
}
