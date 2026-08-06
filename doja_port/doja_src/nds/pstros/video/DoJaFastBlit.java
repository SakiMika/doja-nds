package nds.pstros.video;

import nds.Video;

/** Native global-alpha bridge without changing the ROMized Java API ABI. */
public final class DoJaFastBlit {
    private DoJaFastBlit() {
    }

    public static void drawImageAlpha(NDSGraphics target, NDSImage image,
            int x, int y, int alpha) {
        if (target == null || image == null || alpha <= 0) return;
        if (alpha >= 255) {
            target.drawImage(image, x, y);
            return;
        }
        byte mode = (byte)(0x80 | ((alpha + 1) >> 1));
        Video.blit(
            target.baseImage.pixelData, target.dstW, target.dstH,
            image.pixelData, image.width, image.height,
            x, y,
            target.clX, target.clY, target.clW, target.clH,
            mode, image.pixelDataByte
        );
    }
}
