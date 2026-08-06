package nds.pstros;
public class EmuCanvas {
    public static EmuCanvas getInstance() { return null; }
    public void checkKeys() {}
    public void checkPause() {}
    public void flushGraphics(nds.pstros.video.NDSImage image) {}
    public static int screenPosX, screenPosY;
    public static int keyA,keyB,keyX,keyY,keyL,keyR,keyStart,keySelect;
}
