package javax.microedition.lcdui;
public abstract class Canvas extends Displayable {
    public static final int UP=1, LEFT=2, RIGHT=5, DOWN=6, FIRE=8;
    public static final int SOFT_L=24, SOFT_C=25, SOFT_R=26;
    public static final int KEY_NUM0=48, KEY_NUM1=49, KEY_NUM2=50, KEY_NUM3=51, KEY_NUM4=52;
    public static final int KEY_NUM5=53, KEY_NUM6=54, KEY_NUM7=55, KEY_NUM8=56, KEY_NUM9=57;
    public static final int KEY_STAR=42, KEY_POUND=35;
    protected Canvas() {}
    public void setFullScreenMode(boolean mode) {}
    public final void repaint() {}
    public final void serviceRepaints() {}
    protected void keyPressed(int keyCode) {}
    protected void keyRepeated(int keyCode) {}
    protected void keyReleased(int keyCode) {}
    protected abstract void paint(Graphics g);
}
