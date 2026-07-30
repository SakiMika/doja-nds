package javax.microedition.lcdui;
import javax.microedition.midlet.MIDlet;
public class Display {
    public static int WIDTH=176, HEIGHT=192;
    public static int keySoftLeft='Z', keySoftRight='C', keyFire=17;
    public static int keyNum1=103, keyNum3=105, keyNum5=101, keyStar=106, keyCross=111;
    public static Display getDisplay(MIDlet m) { return null; }
    public void setCurrent(Displayable d) {}
    public static void emuRunEmulation() {}
}
