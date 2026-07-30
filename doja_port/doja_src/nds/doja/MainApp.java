package nds.doja;

import com.nttdocomo.ui.IApplication;
import nds.pstros.EmuCanvas;
import nds.pstros.ConfigData;

public final class MainApp {
    private static boolean terminateRequested;
    private static boolean inputPumpStarted;

    private MainApp() {
    }

    public static void main(String[] args) {
        String className = "Main";
        String appParam = "0";
        int screenY = 0;
        int i;

        for (i = 0; args != null && i < args.length; i++) {
            String arg = args[i];
            if (arg.startsWith("-C")) {
                className = arg.substring(2);
            } else if (arg.startsWith("-P")) {
                appParam = arg.substring(2);
            } else if (arg.startsWith("-Y")) {
                screenY = Integer.parseInt(arg.substring(2));
            }
        }

        javax.microedition.lcdui.Display.WIDTH = 240;
        javax.microedition.lcdui.Display.HEIGHT = 240;
        EmuCanvas.screenPosX = 0;
        EmuCanvas.screenPosY = 0;
        System.out.println("DoJa display: force 240x240 -> NDS 256x192");

        EmuCanvas.keyA = javax.microedition.lcdui.Display.keyFire;
        EmuCanvas.keyB = javax.microedition.lcdui.Display.keySoftRight;
        EmuCanvas.keyX = javax.microedition.lcdui.Display.keySoftLeft;
        EmuCanvas.keyY = javax.microedition.lcdui.Display.keyNum5;
        EmuCanvas.keyL = javax.microedition.lcdui.Display.keyNum1;
        EmuCanvas.keyR = javax.microedition.lcdui.Display.keyNum3;
        EmuCanvas.keyStart = javax.microedition.lcdui.Display.keyCross;
        EmuCanvas.keySelect = javax.microedition.lcdui.Display.keyStar;

        /*
         * The inherited MIDP Canvas bridge normally rewrites game actions
         * to configurable negative key codes (-1..-7). DoJa expects its own
         * absolute keypad values (0..22), so keep the MIDP bridge in standard
         * game-action mode for this standalone DoJa branch.
         */
        ConfigData.configActive = false;
        System.out.println("DoJa input mapping: MIDP actions + negative-code fallback");

        startInputPump();

        try {
            Class appClass = Class.forName(className);
            IApplication app = (IApplication) appClass.newInstance();
            IApplication._bind(app, new String[] { appParam }, "http://localhost/");
            System.out.println("DoJa NDS v36: FULLSCREEN + LATIN FIX");
            System.out.println("microedition.encoding=SJIS");
            System.out.println("DoJa NDS: start");
            app.start();
        } catch (Throwable error) {
            System.out.println("DoJa boot error:");
            error.printStackTrace();
        }
    }

    private static synchronized void startInputPump() {
        if (inputPumpStarted) {
            return;
        }
        inputPumpStarted = true;

        new Thread("doja-input") {
            public void run() {
                EmuCanvas canvas = EmuCanvas.getInstance();
                System.out.println("DoJa NDS: input pump started");

                while (!terminateRequested) {
                    try {
                        /*
                         * Do not tie input polling to repaint/flushGraphics.
                         * Many DoJa title/menu screens stay visually static
                         * while waiting for processEvent(), so the old path
                         * stopped calling scanKeys() and lost every button.
                         */
                        canvas.checkKeys();
                        Thread.sleep(10);
                    } catch (InterruptedException ignored) {
                    } catch (Throwable error) {
                        System.out.println("DoJa input error:");
                        error.printStackTrace();
                        try {
                            Thread.sleep(50);
                        } catch (InterruptedException ignored) {
                        }
                    }
                }
            }
        }.start();
    }

    public static void requestTerminate() {
        terminateRequested = true;
    }

    public static boolean isTerminateRequested() {
        return terminateRequested;
    }
}
