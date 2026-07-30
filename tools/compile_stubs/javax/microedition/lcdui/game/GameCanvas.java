package javax.microedition.lcdui.game;
import javax.microedition.lcdui.Canvas;
import javax.microedition.lcdui.Graphics;
public abstract class GameCanvas extends Canvas {
    protected GameCanvas(boolean suppressKeyEvents) {}
    protected Graphics getGraphics() { return null; }
    public void flushGraphics() {}
}
