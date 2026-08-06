package com.nttdocomo.ui;

/** Mutable indexed-color palette used by PalettedImage. */
public class Palette {
    private final int[] entries;
    private int revision;

    public Palette(int count) {
        if (count <= 0) throw new IllegalArgumentException();
        entries = new int[count];
    }

    public Palette(int[] colors) {
        if (colors == null) throw new NullPointerException();
        if (colors.length == 0) throw new IllegalArgumentException();
        entries = new int[colors.length];
        System.arraycopy(colors, 0, entries, 0, colors.length);
    }

    public int getEntryCount() {
        return entries.length;
    }

    public int getEntry(int index) {
        return entries[index];
    }

    public void setEntry(int index, int color) {
        entries[index] = color;
        revision++;
    }

    int _revision() {
        return revision;
    }
}
