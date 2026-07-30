package com.nttdocomo.ui;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;

public final class MediaManager {
    private MediaManager() {
    }

    public static MediaImage getImage(String url) {
        try {
            return new ImageResource(readResource(url));
        } catch (Exception e) {
            return new ImageResource(null);
        }
    }

    public static MediaImage getImage(byte[] data) {
        return new ImageResource(data);
    }

    public static MediaSound getSound(String url) {
        try {
            return new SoundResource(readResource(url));
        } catch (Exception e) {
            return new SoundResource(null);
        }
    }

    public static MediaSound getSound(byte[] data) {
        return new SoundResource(data);
    }

    private static byte[] readResource(String url) throws Exception {
        String name = url;
        if (name.startsWith("resource:///")) {
            name = name.substring(12);
        }
        while (name.startsWith("/")) {
            name = name.substring(1);
        }
        InputStream in = new com.sun.cldc.io.ResourceInputStream(name);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[1024];
        int count;
        while ((count = in.read(buffer)) > 0) {
            out.write(buffer, 0, count);
        }
        in.close();
        return out.toByteArray();
    }

    private static final class ImageResource implements MediaImage {
        private byte[] data;
        private Image image;

        ImageResource(byte[] value) {
            data = value;
        }

        public void use() {
            getImage();
        }

        public void unuse() {
        }

        public void dispose() {
            image = null;
            data = null;
        }

        public Image getImage() {
            if (image == null && data != null) {
                try {
                    javax.microedition.lcdui.Image decoded;
                    if (nds.doja.image.GifDecoder.isGif(data)) {
                        decoded = nds.doja.image.GifDecoder.decode(data);
                    } else {
                        decoded = javax.microedition.lcdui.Image.createImage(data, 0, data.length);
                    }
                    image = new Image(decoded);
                } catch (Exception e) {
                    image = null;
                }
            }
            return image;
        }
    }

    static final class SoundResource implements MediaSound {
        byte[] data;

        SoundResource(byte[] value) {
            data = value;
        }

        public void use() {
        }

        public void unuse() {
        }

        public void dispose() {
            data = null;
        }
    }
}
