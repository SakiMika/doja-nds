package com.nttdocomo.ui;

public final class AudioPresenter extends MediaPresenter {
    public static final int AUDIO_PLAYING = 1;
    public static final int AUDIO_STOPPED = 2;
    public static final int AUDIO_COMPLETE = 3;
    public static final int AUDIO_SYNC = 4;
    public static final int AUDIO_PAUSED = 5;
    public static final int AUDIO_RESTARTED = 6;
    public static final int AUDIO_LOOPED = 7;

    public static final int ATTR_PRIORITY = 1;
    public static final int ATTR_SYNC_MODE = 2;
    public static final int ATTR_TRANSPOSE_KEY = 3;
    public static final int ATTR_SET_VOLUME = 4;
    public static final int ATTR_CHANGE_TEMPO = 5;
    public static final int ATTR_LOOP_COUNT = 6;

    private static final AudioPresenter[] PRESENTERS = new AudioPresenter[] {
        new AudioPresenter(), new AudioPresenter(), new AudioPresenter(), new AudioPresenter()
    };
    private int generation;

    private AudioPresenter() {
    }

    public static AudioPresenter getAudioPresenter(int index) {
        if (index < 0 || index >= PRESENTERS.length) {
            index = 0;
        }
        return PRESENTERS[index];
    }

    public void setSound(MediaSound sound) {
        resource = sound;
    }

    public void setAttribute(int attribute, int value) {
    }

    public void play() {
        final int token = ++generation;
        notifyListener(AUDIO_PLAYING);
        new Thread() {
            public void run() {
                try {
                    Thread.sleep(900);
                } catch (Exception ignored) {
                }
                if (generation == token) {
                    notifyListener(AUDIO_COMPLETE);
                }
            }
        }.start();
    }

    public void stop() {
        generation++;
        notifyListener(AUDIO_STOPPED);
    }

    private void notifyListener(int event) {
        if (listener != null) {
            listener.mediaAction(this, event, 0);
        }
    }
}
