package nds.pstros.audio;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;

import javax.microedition.media.MediaException;
import javax.microedition.media.Player;

/**
 * Replacement for Manager.createPlayer() used by the embedded Diamond Rush
 * JAR. It keeps the MIDP Player contract while forwarding PCM WAV playback to
 * the existing nds.Video native bridge.
 */
public final class AudioBridge {
    private AudioBridge() {
    }

    public static Player createPlayer(InputStream stream, String contentType)
            throws IOException, MediaException {
        if (stream == null) {
            throw new IllegalArgumentException("stream is null");
        }

        ByteArrayOutputStream out = new ByteArrayOutputStream(4096);
        byte[] chunk = new byte[1024];
        int read;
        while ((read = stream.read(chunk, 0, chunk.length)) > 0) {
            out.write(chunk, 0, read);
        }
        return new NdsAudioPlayer(out.toByteArray(), contentType);
    }
}
