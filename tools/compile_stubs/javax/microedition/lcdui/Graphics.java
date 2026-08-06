package javax.microedition.lcdui;
public class Graphics {
    public static final int TOP=16, LEFT=4;
    public void translate(int x, int y) {}
    public int getTranslateX() { return 0; }
    public int getTranslateY() { return 0; }
    public nds.pstros.video.NDSGraphics emuGetGraphics() { return null; }
    public void setClip(int x,int y,int w,int h) {}
    public void clipRect(int x,int y,int w,int h) {}
    public void setColor(int rgb) {}
    public void fillRect(int x,int y,int w,int h) {}
    public void drawRect(int x,int y,int w,int h) {}
    public void drawLine(int x1,int y1,int x2,int y2) {}
    public void drawImage(Image image,int x,int y,int anchor) {}
    public void drawRegion(Image image,int sx,int sy,int w,int h,int transform,int x,int y,int anchor) {}
    public void getPixels(int[] pixels,int offset,int scanlength,int x,int y,int width,int height,int format) {}
    public void drawRGB(int[] pixels,int offset,int scanlength,int x,int y,int width,int height,boolean alpha) {}
}
