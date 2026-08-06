package nds.doja;

import javax.microedition.lcdui.Graphics;
import javax.microedition.lcdui.Image;
import nds.pstros.EmuCanvas;
import nds.pstros.video.DoJaFastBlit;
import nds.pstros.video.NDSGraphics;
import nds.pstros.video.NDSImage;
import nds.pstros.video.NDSRectangle;

/** Game-JAR bridge to existing Pstros public APIs and the v42 native blitter. */
public final class FastPath {
    private static final NDSRectangle oldClip = new NDSRectangle();

    private FastPath() {
    }

    public static void present(Image image) {
        if (image == null) return;
        EmuCanvas canvas = EmuCanvas.getInstance();
        if (canvas == null) return;
        canvas.flushGraphics((NDSImage)image.getObject());
        canvas.checkPause();
    }

    public static void drawImageAlpha(Graphics graphics, Image image,
            int x, int y, int transform, int alpha) {
        if (graphics == null || image == null || alpha <= 0) return;
        NDSGraphics target = graphics.emuGetGraphics();
        if (target == null) return;
        DoJaFastBlit.drawImageAlpha(target, image.emuGetImage(transform),
            x + graphics.getTranslateX(), y + graphics.getTranslateY(), alpha);
    }

    public static void drawRegionAlpha(Graphics graphics, Image image,
            int sx, int sy, int width, int height, int transform,
            int dx, int dy, int alpha) {
        if (graphics == null || image == null || alpha <= 0) return;
        NDSGraphics target = graphics.emuGetGraphics();
        if (target == null) return;

        int temp;
        switch (transform) {
            case 1:
                sy = image.getHeight() - sy - height;
                break;
            case 2:
                sx = image.getWidth() - sx - width;
                break;
            case 3:
                sy = image.getHeight() - sy - height;
                sx = image.getWidth() - sx - width;
                break;
            case 4:
                temp = width; width = height; height = temp;
                temp = sx; sx = sy; sy = temp;
                break;
            case 5:
                temp = width; width = height; height = temp;
                temp = sx; sx = sy; sy = temp;
                sx = image.getHeight() - sx - width;
                break;
            case 6:
                temp = width; width = height; height = temp;
                temp = sx; sx = sy; sy = temp;
                sy = image.getWidth() - sy - height;
                break;
            case 7:
                temp = width; width = height; height = temp;
                temp = sx; sx = sy; sy = temp;
                sy = image.getWidth() - sy - height;
                sx = image.getHeight() - sx - width;
                break;
            default:
                if (transform != 0) throw new IllegalArgumentException("transform");
        }

        int tx = graphics.getTranslateX();
        int ty = graphics.getTranslateY();
        target.getClipBounds(oldClip);
        target.clipRect(dx + tx, dy + ty, width, height);
        DoJaFastBlit.drawImageAlpha(target, image.emuGetImage(transform),
            dx + tx - sx, dy + ty - sy, alpha);
        target.setClip(oldClip.x, oldClip.y, oldClip.width, oldClip.height);
    }
}
