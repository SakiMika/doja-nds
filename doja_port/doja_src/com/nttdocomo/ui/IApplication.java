package com.nttdocomo.ui;

import nds.doja.MainApp;

public abstract class IApplication {
    private static IApplication current;
    private String[] args = new String[] { "0" };
    private String sourceURL = "http://localhost/";

    protected IApplication() {
    }

    public abstract void start();

    public void resume() {
    }

    public final String[] getArgs() {
        return args;
    }

    public final String getSourceURL() {
        return sourceURL;
    }

    public final void terminate() {
        MainApp.requestTerminate();
    }

    public static IApplication getCurrentApp() {
        return current;
    }

    public static void _bind(IApplication app, String[] launchArgs, String url) {
        current = app;
        if (launchArgs != null && launchArgs.length > 0) {
            app.args = launchArgs;
        }
        if (url != null) {
            app.sourceURL = url;
        }
    }
}
