package nds.pstros.audio;

import java.util.Vector;

import javax.microedition.media.Control;
import javax.microedition.media.MediaException;
import javax.microedition.media.Player;
import javax.microedition.media.PlayerListener;
import javax.microedition.media.control.VolumeControl;

import nds.Video;

/**
 * Small MIDP Player implementation for Nintendo DS PCM WAV audio.
 *
 * Diamond Rush keeps its original compact MIDI resources in the Java heap.
 * The NDS native bridge recognizes each MIDI track and plays a pre-rendered
 * signed PCM copy linked outside the JAR, avoiding a large Java allocation.
 * AMR remains a silent compatibility player.
 */
final class NdsAudioPlayer implements Player {
    private static final int AUDIO_PLAY = -1000000;
    private static final int AUDIO_STOP = -2000000;
    private static final int AUDIO_STOP_CHANNEL = -2100000;
    private static final int AUDIO_VOLUME = -3000000;
    private static final int AUDIO_VOLUME_CHANNEL = -3100000;

    private final byte[] data;
    private final String contentType;
    private final Vector listeners = new Vector(2);
    private final Volume volumeControl = new Volume();

    private int state = UNREALIZED;
    private int level = 100;
    private int loopCount = 1;
    private long mediaTime;
    private long startedAt;
    private long duration;
    private boolean nativeStarted;
    private int nativeChannel = -1;
    private int playGeneration;

    NdsAudioPlayer(byte[] data, String contentType) {
        this.data = data == null ? new byte[0] : data;
        this.contentType = contentType == null ? "" : contentType;
        this.duration = wavDurationMillis(this.data);
    }

    public void realize() throws MediaException {
        ensureOpen();
        if (state < REALIZED) {
            state = REALIZED;
        }
    }

    public void prefetch() throws MediaException {
        ensureOpen();
        if (state < REALIZED) {
            realize();
        }
        state = PREFETCHED;
    }

    public void start() throws MediaException {
        ensureOpen();
        if (state < PREFETCHED) {
            prefetch();
        }

        nativeStarted = false;
        if (data.length > 0) {
            int loop = loopCount == -1 ? 1 : 0;
            int result = Video.decodePngImage(data, AUDIO_PLAY - loop, null, null);
            nativeChannel = result;
            nativeStarted = result >= 0;
        }

        state = STARTED;
        startedAt = System.currentTimeMillis() - mediaTime;
        int generation = ++playGeneration;
        report(PlayerListener.STARTED, new Long(mediaTime));
        if (duration > 0 && loopCount != -1) {
            long total = duration * (long)loopCount;
            Thread watcher = new Thread(new EndWatcher(this, generation, total));
            watcher.start();
        }
    }

    public void stop() throws MediaException {
        ensureOpen();
        playGeneration++;
        stopNativeChannel();
        if (state == STARTED) {
            mediaTime = System.currentTimeMillis() - startedAt;
        }
        state = PREFETCHED;
        report(PlayerListener.STOPPED, new Long(mediaTime));
    }

    public void deallocate() throws IllegalStateException {
        if (state == CLOSED) {
            throw new IllegalStateException();
        }
        try {
            if (state == STARTED) {
                stop();
            }
        } catch (MediaException ignored) {
        }
        state = REALIZED;
    }

    public void close() {
        if (state == CLOSED) {
            return;
        }
        playGeneration++;
        stopNativeChannel();
        state = CLOSED;
        report(PlayerListener.CLOSED, null);
        listeners.removeAllElements();
    }

    public long setMediaTime(long now) throws MediaException {
        ensureOpen();
        if (now < 0) {
            now = 0;
        }
        mediaTime = now;
        return mediaTime;
    }

    public long getMediaTime() {
        ensureOpen();
        if (state == STARTED) {
            return System.currentTimeMillis() - startedAt;
        }
        return mediaTime;
    }

    public int getState() {
        return state;
    }

    public long getDuration() throws IllegalStateException {
        ensureOpen();
        return duration > 0 ? duration : TIME_UNKNOWN;
    }

    public String getContentType() throws IllegalStateException {
        ensureOpen();
        return contentType;
    }

    public void setLoopCount(int count) throws Exception {
        ensureOpen();
        if (count == 0) {
            throw new IllegalArgumentException("loop count is zero");
        }
        if (state == STARTED) {
            throw new IllegalStateException();
        }
        loopCount = count;
    }

    public void addPlayerListener(PlayerListener listener) throws IllegalStateException {
        ensureOpen();
        if (listener != null && !listeners.contains(listener)) {
            listeners.addElement(listener);
        }
    }

    public void removePlayerListener(PlayerListener listener) throws IllegalStateException {
        ensureOpen();
        listeners.removeElement(listener);
    }

    public Control getControl(String controlType) {
        if ("VolumeControl".equals(controlType)
                || "javax.microedition.media.control.VolumeControl".equals(controlType)) {
            return volumeControl;
        }
        return null;
    }

    public Control[] getControls() {
        return new Control[] { volumeControl };
    }

    public void emuUpdatePlayer() {
        // Completion is reported by EndWatcher because players created by the
        // bridge are not stored in the ROMized Manager player vector.
    }

    private synchronized void finishIfCurrent(int generation, long total) {
        if (generation != playGeneration || state != STARTED) {
            return;
        }
        stopNativeChannel();
        mediaTime = total;
        state = PREFETCHED;
        report(PlayerListener.END_OF_MEDIA, new Long(mediaTime));
    }

    public int emuGetVolumeLevel() {
        return level;
    }

    public int emuSetVolumeLevel(int newLevel) {
        if (newLevel < 0) {
            newLevel = 0;
        } else if (newLevel > 100) {
            newLevel = 100;
        }
        level = newLevel;
        if (nativeStarted && nativeChannel >= 0) {
            int command = AUDIO_VOLUME_CHANNEL - nativeChannel * 101 - level;
            Video.decodePngImage(null, command, null, null);
        }
        report(PlayerListener.VOLUME_CHANGED, volumeControl);
        return level;
    }

    private void stopNativeChannel() {
        if (nativeStarted && nativeChannel >= 0) {
            Video.decodePngImage(null, AUDIO_STOP_CHANNEL - nativeChannel, null, null);
        }
        nativeStarted = false;
        nativeChannel = -1;
    }

    private boolean isWav() {
        return data.length >= 12
                && data[0] == 'R' && data[1] == 'I'
                && data[2] == 'F' && data[3] == 'F'
                && data[8] == 'W' && data[9] == 'A'
                && data[10] == 'V' && data[11] == 'E';
    }

    private void ensureOpen() {
        if (state == CLOSED) {
            throw new IllegalStateException("player is closed");
        }
    }

    private void report(String event, Object value) {
        int count = listeners.size();
        for (int i = 0; i < count; i++) {
            ((PlayerListener)listeners.elementAt(i)).playerUpdate(this, event, value);
        }
    }

    private static int readLe16(byte[] src, int pos) {
        return (src[pos] & 255) | ((src[pos + 1] & 255) << 8);
    }

    private static int readLe32(byte[] src, int pos) {
        return (src[pos] & 255)
                | ((src[pos + 1] & 255) << 8)
                | ((src[pos + 2] & 255) << 16)
                | ((src[pos + 3] & 255) << 24);
    }

    private static long wavDurationMillis(byte[] src) {
        if (src == null || src.length < 44
                || src[0] != 'R' || src[1] != 'I' || src[2] != 'F' || src[3] != 'F') {
            return 0;
        }
        int byteRate = readLe32(src, 28);
        if (byteRate <= 0) {
            return 0;
        }
        int pos = 12;
        while (pos + 8 <= src.length) {
            int size = readLe32(src, pos + 4);
            if (src[pos] == 'd' && src[pos + 1] == 'a'
                    && src[pos + 2] == 't' && src[pos + 3] == 'a') {
                if (size < 0 || pos + 8 + size > src.length) {
                    size = src.length - pos - 8;
                }
                return ((long)size * 1000L) / (long)byteRate;
            }
            if (size < 0) {
                return 0;
            }
            pos += 8 + size + (size & 1);
        }
        return 0;
    }

    private static final class EndWatcher implements Runnable {
        private final NdsAudioPlayer player;
        private final int generation;
        private final long delay;

        EndWatcher(NdsAudioPlayer player, int generation, long delay) {
            this.player = player;
            this.generation = generation;
            this.delay = delay;
        }

        public void run() {
            try {
                Thread.sleep(delay);
                player.finishIfCurrent(generation, delay);
            } catch (InterruptedException ignored) {
            }
        }
    }

    private final class Volume implements VolumeControl {
        private boolean muted;

        public int getLevel() {
            return level;
        }

        public int setLevel(int value) {
            return emuSetVolumeLevel(value);
        }

        public boolean isMuted() {
            return muted;
        }

        public void setMute(boolean value) {
            muted = value;
            emuSetVolumeLevel(value ? 0 : level);
        }
    }
}
