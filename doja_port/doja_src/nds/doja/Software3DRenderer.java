package nds.doja;

import com.nttdocomo.ui.graphics3d.Fog;
import com.nttdocomo.ui.graphics3d.Primitive;
import com.nttdocomo.ui.graphics3d.Texture;
import com.nttdocomo.ui.util3d.FastMath;
import com.nttdocomo.ui.util3d.Transform;

/**
 * Small software renderer for the textured Primitive path used by DoJa titles.
 * It deliberately focuses on points/triangles/quads with indexed BMP textures;
 * FF4A's world map is built from textured quads through this API.
 */
public final class Software3DRenderer {
    private final javax.microedition.lcdui.Graphics graphics;
    private final int width;
    private final int height;
    private int[] framebuffer;
    private boolean active;

    /* v59 compact diagnostic state. v58 printed every quad/object and hid the
     * useful final line. v59 prints one completed-frame summary plus a one-shot
     * watchdog warning if the same stage makes no progress for >= 3 seconds. */
    private static final int WATCH_IDLE = 0;
    private static final int WATCH_TEX = 1;
    private static final int WATCH_FB = 2;
    private static final int WATCH_FB_ALLOC = 3;
    private static final int WATCH_FB_READ = 4;
    private static final int WATCH_QUADS = 5;
    private static final int WATCH_RASTER = 6;
    private static final int WATCH_TRI = 7;
    private static final int WATCH_FLUSH = 8;

    private static int renderSequence;
    private int renderId;

    private static volatile int watchStage = WATCH_IDLE;
    private static volatile int watchRender;
    private static volatile int watchProgress;
    private static volatile int watchTotal;
    private static volatile long watchSince;
    private static volatile int watchToken;
    private static volatile int watchReportedToken = -1;
    private static volatile boolean watchRunning;

    private static void printWatchStage(int stage) {
        switch (stage) {
            case WATCH_TEX: System.out.print("TEX"); break;
            case WATCH_FB: System.out.print("FB"); break;
            case WATCH_FB_ALLOC: System.out.print("FB_ALLOC"); break;
            case WATCH_FB_READ: System.out.print("FB_READ"); break;
            case WATCH_QUADS: System.out.print("QUADS"); break;
            case WATCH_RASTER: System.out.print("RASTER"); break;
            case WATCH_TRI: System.out.print("TRI"); break;
            case WATCH_FLUSH: System.out.print("FLUSH"); break;
            default: System.out.print("IDLE"); break;
        }
    }

    private static void printWatchState(String prefix, long age) {
        System.out.print(prefix);
        System.out.print(" R"); System.out.print(watchRender);
        System.out.print(" "); printWatchStage(watchStage);
        if (watchTotal > 0) {
            System.out.print(" "); System.out.print(watchProgress);
            System.out.print("/"); System.out.print(watchTotal);
        }
        System.out.print(" age="); System.out.print((int)age); System.out.println("ms");
    }

    private static synchronized void ensureWatchdog() {
        if (watchRunning) return;
        watchRunning = true;
        new Thread("doja-3d-watch") {
            public void run() {
                long born = System.currentTimeMillis();
                for (;;) {
                    try { Thread.sleep(500); } catch (InterruptedException ignored) {}
                    long now = System.currentTimeMillis();
                    int token = watchToken;
                    if (watchStage != WATCH_IDLE) {
                        long age = now - watchSince;
                        if (age >= 3000 && watchReportedToken != token) {
                            printWatchState("3D WATCH: HANG?", age);
                            watchReportedToken = token;
                        }
                    } else if (now - watchSince >= 3000) {
                        watchRunning = false;
                        return;
                    }
                    if (now - born >= 60000) {
                        watchRunning = false;
                        return;
                    }
                }
            }
        }.start();
    }

    private static void watch(int stage, int render, int progress, int total) {
        long now = System.currentTimeMillis();
        if (watchReportedToken == watchToken && watchStage != WATCH_IDLE) {
            printWatchState("3D WATCH: RESUME", now - watchSince);
        }
        watchStage = stage;
        watchRender = render;
        watchProgress = progress;
        watchTotal = total;
        watchSince = now;
        watchToken++;
        ensureWatchdog();
    }

    private static void watchIdle() {
        long now = System.currentTimeMillis();
        if (watchReportedToken == watchToken && watchStage != WATCH_IDLE) {
            printWatchState("3D WATCH: RESUME", now - watchSince);
        }
        watchStage = WATCH_IDLE;
        watchSince = now;
        watchToken++;
    }

    private boolean frameOpen;
    private int frameId;
    private long frameStart;
    private int frameRenders;
    private int frameQuads;
    private int frameTriangles;
    private int frameFbReads;
    private int frameSkippedBig;

    private void beginFrameIfNeeded() {
        if (frameOpen) return;
        frameOpen = true;
        frameId++;
        frameStart = System.currentTimeMillis();
        frameRenders = 0;
        frameQuads = 0;
        frameTriangles = 0;
        frameFbReads = 0;
        frameSkippedBig = 0;
    }

    private void printFrameSummary() {
        if (!frameOpen) return;
        long elapsed = System.currentTimeMillis() - frameStart;
        System.out.print("3D F#"); System.out.print(frameId);
        System.out.print(" r="); System.out.print(frameRenders);
        System.out.print(" q="); System.out.print(frameQuads);
        System.out.print(" t="); System.out.print(frameTriangles);
        System.out.print(" fb="); System.out.print(frameFbReads);
        if (frameSkippedBig != 0) {
            System.out.print(" skip="); System.out.print(frameSkippedBig);
        }
        System.out.print(" time="); System.out.print((int)elapsed); System.out.print("ms ");
        if (elapsed >= 3000) System.out.println("SLOW");
        else System.out.println("OK");
        frameOpen = false;
    }

    private int clipX;
    private int clipY;
    private int clipW;
    private int clipH;

    private float nearPlane = 1.0f;
    private float farPlane = 1000.0f;
    private float viewAngle = 45.0f;
    private Transform viewTransform = new Transform();
    private Fog fog;

    /* One reusable projected-vertex block: x,y,z,u,v,1/z,u/z,v/z. */
    private final float[] pv = new float[8 * 4];

    public Software3DRenderer(javax.microedition.lcdui.Graphics g, int w, int h) {
        graphics = g;
        width = w;
        height = h;
        clipX = 0;
        clipY = 0;
        clipW = w;
        clipH = h;
    }

    public void setClip(int x, int y, int w, int h) {
        if (w < 0 || h < 0) {
            clipX = clipY = clipW = clipH = 0;
            return;
        }
        if (x < 0) { w += x; x = 0; }
        if (y < 0) { h += y; y = 0; }
        if (x + w > width) w = width - x;
        if (y + h > height) h = height - y;
        if (w < 0) w = 0;
        if (h < 0) h = 0;
        clipX = x;
        clipY = y;
        clipW = w;
        clipH = h;
    }

    public void setPerspective(float near, float far, float angle) {
        if (near > 0.0f) nearPlane = near;
        if (far > nearPlane) farPlane = far;
        if (angle > 1.0f && angle < 179.0f) viewAngle = angle;
    }

    public void setTransform(Transform t) {
        if (t == null) viewTransform = new Transform();
        else viewTransform = new Transform(t);
    }

    public void setFog(Fog value) {
        fog = value;
    }

    public void render(Primitive primitive, Transform model) {
        beginFrameIfNeeded();
        renderId = ++renderSequence;
        frameRenders++;
        if (primitive == null || clipW <= 0 || clipH <= 0) return;

        watch(WATCH_TEX, renderId, 0, 0);
        Texture texture = primitive._texture();
        if (texture == null || !texture._decoded()) {
            watchIdle();
            return;
        }

        watch(WATCH_FB, renderId, 0, 0);
        ensureFramebuffer();

        switch (primitive._type()) {
            case Primitive.QUADS:
                frameQuads += primitive._count();
                watch(WATCH_QUADS, renderId, 0, primitive._count());
                renderQuads(primitive, model, texture);
                break;
            case Primitive.TRIANGLES:
                frameTriangles += primitive._count();
                watch(WATCH_TRI, renderId, 0, primitive._count());
                renderTriangles(primitive, model, texture);
                break;
            default:
                break;
        }
        watchIdle();
    }

    public void flush() {
        if (active && framebuffer != null) {
            watch(WATCH_FLUSH, frameId, 0, 0);
            graphics.drawRGB(framebuffer, 0, width, 0, 0, width, height, true);
            active = false;
            watchIdle();
        }
        printFrameSummary();
    }

    private void ensureFramebuffer() {
        if (framebuffer == null || framebuffer.length != width * height) {
            watch(WATCH_FB_ALLOC, renderId, 0, 0);
            framebuffer = new int[width * height];
        }
        if (!active) {
            frameFbReads++;
            watch(WATCH_FB_READ, renderId, 0, 0);
            graphics.getPixels(framebuffer, 0, width, 0, 0, width, height, 8888);
            active = true;
        }
    }

    private void renderQuads(Primitive primitive, Transform model, Texture texture) {
        int[] vertices = primitive._vertices();
        int[] uv = primitive._texcoords();
        int count = primitive._count();
        int i;

        /* v59: FF4A world maps are 19x12 = 228 textured quads.  The v56
         * generic barycentric renderer performed floating-point edge tests,
         * perspective division and texture interpolation for every candidate
         * pixel in the KVM interpreter, which made a map frame look frozen.
         *
         * Large quad batches use a fixed-point tiled fast path.  Vertices are
         * still projected with the DoJa transform/camera, but each projected
         * tile is sampled across its clipped screen-space rectangle using
         * integer increments.  Small 3D objects retain the full triangle path.
         */
        boolean tiledFastPath = count >= 32;

        for (i = 0; i < count; i++) {
            if ((i & 15) == 0) watch(WATCH_QUADS, renderId, i, count);
            int vo = i * 12;
            int to = i * 8;
            if (vo + 11 >= vertices.length || to + 7 >= uv.length) break;

            if (!projectVertex(0, vertices[vo], vertices[vo+1], vertices[vo+2], uv[to], uv[to+1], model)) { continue; }
            if (!projectVertex(1, vertices[vo+3], vertices[vo+4], vertices[vo+5], uv[to+2], uv[to+3], model)) { continue; }
            if (!projectVertex(2, vertices[vo+6], vertices[vo+7], vertices[vo+8], uv[to+4], uv[to+5], model)) { continue; }
            if (!projectVertex(3, vertices[vo+9], vertices[vo+10], vertices[vo+11], uv[to+6], uv[to+7], model)) { continue; }

            if (tiledFastPath) {
                drawFastQuad(texture, primitive);
            } else {
                drawTriangle(0, 1, 2, texture, primitive);
                drawTriangle(0, 2, 3, texture, primitive);
            }
        }
    }

    private void drawFastQuad(Texture texture, Primitive primitive) {
        float ax = pv[0], ay = pv[1];
        float bx = pv[8], by = pv[9];
        float cx = pv[16], cy = pv[17];
        float dx = pv[24], dy = pv[25];

        int minX = (int)min4(ax, bx, cx, dx);
        int maxX = (int)max4(ax, bx, cx, dx) + 1;
        int minY = (int)min4(ay, by, cy, dy);
        int maxY = (int)max4(ay, by, cy, dy) + 1;
        if (minX < clipX) minX = clipX;
        if (minY < clipY) minY = clipY;
        if (maxX > clipX + clipW) maxX = clipX + clipW;
        if (maxY > clipY + clipH) maxY = clipY + clipH;
        if (minX >= maxX || minY >= maxY) return;

        int dstW = maxX - minX;
        int dstH = maxY - minY;

        /* Bad/near-plane projections must never turn one small map tile into
         * a screen-sized KVM loop.  A 228-quad FF4A map tile is normally far
         * smaller than this. */
        if (dstW > 96 || dstH > 96 || dstW * dstH > 4096) {
            frameSkippedBig++;
            return;
        }

        int u0 = (int)pv[3],  v0 = (int)pv[4];
        int u1 = (int)pv[11], v1 = (int)pv[12];
        int u2 = (int)pv[19], v2 = (int)pv[20];
        int u3 = (int)pv[27], v3 = (int)pv[28];

        /* Pick the dominant texture range. FF4A's world-map grid supplies
         * rectangular UV tiles, so this also handles reversed orientation. */
        int uMin = min4i(u0, u1, u2, u3);
        int uMax = max4i(u0, u1, u2, u3);
        int vMin = min4i(v0, v1, v2, v3);
        int vMax = max4i(v0, v1, v2, v3);
        if (uMax == uMin) uMax = uMin + 1;
        if (vMax == vMin) vMax = vMin + 1;

        boolean reverseU = (u1 + u2) < (u0 + u3);
        boolean reverseV = (v2 + v3) < (v0 + v1);
        int uSpan = uMax - uMin;
        int vSpan = vMax - vMin;
        int uStep = (uSpan << 12) / dstW;
        int vStep = (vSpan << 12) / dstH;

        int blend = primitive._blendMode();
        float transparency = primitive._transparency();
        if (transparency < 0.0f) transparency = 0.0f;
        if (transparency > 100.0f) transparency = 100.0f;
        int opacity = (int)(transparency * 255.0f / 100.0f + 0.5f);
        if (blend == Primitive.BLEND_NORMAL) opacity = 255;

        byte[] indexes = texture._indexes();
        int[] palette = texture._palette();
        int tw = texture._width();
        int th = texture._height();
        if (indexes == null || palette == null || tw <= 0 || th <= 0) return;

        int yy;
        watch(WATCH_RASTER, renderId, 0, 0);
        for (yy = 0; yy < dstH; yy++) {
            int vf = yy * vStep;
            int sv = vMin + (vf >> 12);
            if (reverseV) sv = vMax - 1 - (vf >> 12);
            sv %= th; if (sv < 0) sv += th;
            int texRow = sv * tw;
            int dstRow = (minY + yy) * width + minX;
            int xx;
            for (xx = 0; xx < dstW; xx++) {
                int uf = xx * uStep;
                int su = uMin + (uf >> 12);
                if (reverseU) su = uMax - 1 - (uf >> 12);
                su %= tw; if (su < 0) su += tw;
                int index = indexes[texRow + su] & 255;
                if (index == 0 || index >= palette.length) continue;
                int src = palette[index] & 0x00FFFFFF;
                int pos = dstRow + xx;
                if (blend == Primitive.BLEND_ALPHA) {
                    framebuffer[pos] = blendAlpha(framebuffer[pos], src, opacity);
                } else if (blend == Primitive.BLEND_ADD) {
                    framebuffer[pos] = blendAdd(framebuffer[pos], src, opacity);
                } else {
                    framebuffer[pos] = 0xFF000000 | src;
                }
            }
        }
    }

    private void renderTriangles(Primitive primitive, Transform model, Texture texture) {
        int[] vertices = primitive._vertices();
        int[] uv = primitive._texcoords();
        int count = primitive._count();
        int i;
        for (i = 0; i < count; i++) {
            if ((i & 15) == 0) watch(WATCH_TRI, renderId, i, count);
            int vo = i * 9;
            int to = i * 6;
            if (vo + 8 >= vertices.length || to + 5 >= uv.length) break;
            if (!projectVertex(0, vertices[vo], vertices[vo+1], vertices[vo+2], uv[to], uv[to+1], model)) continue;
            if (!projectVertex(1, vertices[vo+3], vertices[vo+4], vertices[vo+5], uv[to+2], uv[to+3], model)) continue;
            if (!projectVertex(2, vertices[vo+6], vertices[vo+7], vertices[vo+8], uv[to+4], uv[to+5], model)) continue;
            drawTriangle(0, 1, 2, texture, primitive);
        }
    }

    private boolean projectVertex(int slot, float x, float y, float z,
                                  float u, float v, Transform model) {
        float mx = x, my = y, mz = z;
        if (model != null) {
            float[] lm = model._matrix();
            mx = lm[0]*x + lm[1]*y + lm[2]*z + lm[3];
            my = lm[4]*x + lm[5]*y + lm[6]*z + lm[7];
            mz = lm[8]*x + lm[9]*y + lm[10]*z + lm[11];
        }

        float[] vm = viewTransform._matrix();
        float vx = vm[0]*mx + vm[1]*my + vm[2]*mz + vm[3];
        float vy = vm[4]*mx + vm[5]*my + vm[6]*mz + vm[7];
        float vz = vm[8]*mx + vm[9]*my + vm[10]*mz + vm[11];
        if (vz <= nearPlane || vz >= farPlane) return false;

        float tangent = FastMath.tan(viewAngle * 0.5f);
        if (tangent > -0.0001f && tangent < 0.0001f) tangent = 1.0f;
        float focal = ((float)clipH * 0.5f) / tangent;
        float sx = (float)clipX + (float)clipW * 0.5f + vx * focal / vz;
        float sy = (float)clipY + (float)clipH * 0.5f - vy * focal / vz;
        float iz = 1.0f / vz;

        int o = slot * 8;
        pv[o] = sx;
        pv[o+1] = sy;
        pv[o+2] = vz;
        pv[o+3] = u;
        pv[o+4] = v;
        pv[o+5] = iz;
        pv[o+6] = u * iz;
        pv[o+7] = v * iz;
        return true;
    }

    private void drawTriangle(int ia, int ib, int ic, Texture texture, Primitive primitive) {
        int a = ia * 8, b = ib * 8, c = ic * 8;
        float ax = pv[a], ay = pv[a+1];
        float bx = pv[b], by = pv[b+1];
        float cx = pv[c], cy = pv[c+1];

        float area = edge(ax, ay, bx, by, cx, cy);
        if (area > -0.0001f && area < 0.0001f) return;

        int minX = (int)min3(ax, bx, cx);
        int maxX = (int)max3(ax, bx, cx) + 1;
        int minY = (int)min3(ay, by, cy);
        int maxY = (int)max3(ay, by, cy) + 1;
        if (minX < clipX) minX = clipX;
        if (minY < clipY) minY = clipY;
        if (maxX > clipX + clipW) maxX = clipX + clipW;
        if (maxY > clipY + clipH) maxY = clipY + clipH;
        if (minX >= maxX || minY >= maxY) return;

        float invArea = 1.0f / area;
        boolean perspective = primitive._perspectiveCorrection();
        int blend = primitive._blendMode();
        float transparency = primitive._transparency();
        if (transparency < 0.0f) transparency = 0.0f;
        if (transparency > 100.0f) transparency = 100.0f;
        int opacity = (int)(transparency * 255.0f / 100.0f + 0.5f);
        if (blend == Primitive.BLEND_NORMAL) opacity = 255;

        int y;
        for (y = minY; y < maxY; y++) {
            float py = (float)y + 0.5f;
            int row = y * width;
            int x;
            for (x = minX; x < maxX; x++) {
                float px = (float)x + 0.5f;
                float w0 = edge(bx, by, cx, cy, px, py) * invArea;
                float w1 = edge(cx, cy, ax, ay, px, py) * invArea;
                float w2 = 1.0f - w0 - w1;
                if (w0 < -0.0001f || w1 < -0.0001f || w2 < -0.0001f) continue;

                float uf, vf;
                if (perspective) {
                    float iz = w0*pv[a+5] + w1*pv[b+5] + w2*pv[c+5];
                    if (iz > -0.000001f && iz < 0.000001f) continue;
                    uf = (w0*pv[a+6] + w1*pv[b+6] + w2*pv[c+6]) / iz;
                    vf = (w0*pv[a+7] + w1*pv[b+7] + w2*pv[c+7]) / iz;
                } else {
                    uf = w0*pv[a+3] + w1*pv[b+3] + w2*pv[c+3];
                    vf = w0*pv[a+4] + w1*pv[b+4] + w2*pv[c+4];
                }

                int index = texture._sampleIndex((int)uf, (int)vf);
                /* DoJa indexed textures reserve palette index 0 as color-key. */
                if (index == 0) continue;
                int src = texture._sampleRGB(index);
                src = applyFog(src, w0*pv[a+2] + w1*pv[b+2] + w2*pv[c+2]);
                int pos = row + x;
                if (blend == Primitive.BLEND_ALPHA) {
                    framebuffer[pos] = blendAlpha(framebuffer[pos], src, opacity);
                } else if (blend == Primitive.BLEND_ADD) {
                    framebuffer[pos] = blendAdd(framebuffer[pos], src, opacity);
                } else {
                    framebuffer[pos] = 0xFF000000 | src;
                }
            }
        }
    }

    private int applyFog(int rgb, float z) {
        if (fog == null || fog.getMode() == Fog.NONE) return rgb;
        if (fog.getMode() != Fog.LINEAR) return rgb;
        float start = fog.getNear();
        float end = fog.getFar();
        if (end <= start) return rgb;
        float amount = (z - start) / (end - start);
        if (amount <= 0.0f) return rgb;
        if (amount >= 1.0f) return fog.getColor() & 0x00FFFFFF;
        int fogRGB = fog.getColor() & 0x00FFFFFF;
        int a = (int)(amount * 255.0f);
        return blendAlpha(0xFF000000 | rgb, fogRGB, a) & 0x00FFFFFF;
    }

    private static int blendAlpha(int dst, int src, int alpha) {
        if (alpha <= 0) return dst;
        if (alpha >= 255) return 0xFF000000 | src;
        int inv = 255 - alpha;
        int dr = (dst >> 16) & 255, dg = (dst >> 8) & 255, db = dst & 255;
        int sr = (src >> 16) & 255, sg = (src >> 8) & 255, sb = src & 255;
        int r = (dr * inv + sr * alpha + 127) / 255;
        int g = (dg * inv + sg * alpha + 127) / 255;
        int b = (db * inv + sb * alpha + 127) / 255;
        return 0xFF000000 | (r << 16) | (g << 8) | b;
    }

    private static int blendAdd(int dst, int src, int alpha) {
        int dr = (dst >> 16) & 255, dg = (dst >> 8) & 255, db = dst & 255;
        int sr = ((src >> 16) & 255) * alpha / 255;
        int sg = ((src >> 8) & 255) * alpha / 255;
        int sb = (src & 255) * alpha / 255;
        dr += sr; if (dr > 255) dr = 255;
        dg += sg; if (dg > 255) dg = 255;
        db += sb; if (db > 255) db = 255;
        return 0xFF000000 | (dr << 16) | (dg << 8) | db;
    }

    private static float edge(float ax, float ay, float bx, float by, float px, float py) {
        return (px - ax) * (by - ay) - (py - ay) * (bx - ax);
    }

    private static float min3(float a, float b, float c) {
        float v = a < b ? a : b;
        return v < c ? v : c;
    }

    private static float max3(float a, float b, float c) {
        float v = a > b ? a : b;
        return v > c ? v : c;
    }

    private static float min4(float a, float b, float c, float d) {
        float v = a < b ? a : b;
        v = v < c ? v : c;
        return v < d ? v : d;
    }

    private static float max4(float a, float b, float c, float d) {
        float v = a > b ? a : b;
        v = v > c ? v : c;
        return v > d ? v : d;
    }

    private static int min4i(int a, int b, int c, int d) {
        int v = a < b ? a : b;
        v = v < c ? v : c;
        return v < d ? v : d;
    }

    private static int max4i(int a, int b, int c, int d) {
        int v = a > b ? a : b;
        v = v > c ? v : c;
        return v > d ? v : d;
    }
}
