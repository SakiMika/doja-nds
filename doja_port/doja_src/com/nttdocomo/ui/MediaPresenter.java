package com.nttdocomo.ui;

public class MediaPresenter {
    protected MediaListener listener;
    protected MediaResource resource;

    public void setMediaListener(MediaListener value) {
        listener = value;
    }

    public MediaResource getMediaResource() {
        return resource;
    }
}
