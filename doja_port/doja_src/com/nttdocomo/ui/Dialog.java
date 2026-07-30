package com.nttdocomo.ui;

public final class Dialog {
    public static final int DIALOG_INFO = 0;
    public static final int DIALOG_WARNING = 1;
    public static final int DIALOG_ERROR = 2;
    public static final int DIALOG_YESNO = 3;
    public static final int DIALOG_YESNOCANCEL = 4;
    public static final int BUTTON_OK = 1;
    public static final int BUTTON_CANCEL = 2;
    public static final int BUTTON_YES = 4;
    public static final int BUTTON_NO = 8;

    private final String title;
    private String text;

    public Dialog(int type, String value) {
        title = value;
    }

    public void setText(String value) {
        text = value;
    }

    public int show() {
        if (title != null) {
            System.out.println(title);
        }
        if (text != null) {
            System.out.println(text);
        }
        return BUTTON_OK;
    }
}
