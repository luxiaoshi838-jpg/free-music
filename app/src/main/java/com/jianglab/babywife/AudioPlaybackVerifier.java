package com.jianglab.babywife;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.media.MediaPlayer;
import android.net.Uri;

import java.io.File;
import java.util.Locale;

/** Verifies that the app's actual Android playback stack can prepare an audio file. */
final class AudioPlaybackVerifier {
    private AudioPlaybackVerifier() {
    }

    static final class Probe {
        final String mimeType;
        final long durationMs;

        Probe(String mimeType, long durationMs) {
            this.mimeType = mimeType == null ? "" : mimeType;
            this.durationMs = durationMs;
        }
    }

    static Probe probeFile(File file) throws Exception {
        if (file == null || !file.isFile() || file.length() <= 0) {
            throw new IllegalArgumentException("待校验音频文件无效");
        }
        MediaExtractor extractor = new MediaExtractor();
        MediaPlayer player = new MediaPlayer();
        try {
            extractor.setDataSource(file.getAbsolutePath());
            Probe track = audioTrack(extractor);
            configure(player);
            player.setDataSource(file.getAbsolutePath());
            player.prepare();
            long duration = player.getDuration();
            return new Probe(track.mimeType, duration >= 0 ? duration : track.durationMs);
        } finally {
            try {
                extractor.release();
            } catch (Exception ignored) {
            }
            try {
                player.release();
            } catch (Exception ignored) {
            }
        }
    }

    static boolean isPlayableUri(Context context, String uriText) {
        if (context == null || uriText == null || uriText.trim().isEmpty()) return false;
        MediaExtractor extractor = new MediaExtractor();
        MediaPlayer player = new MediaPlayer();
        try {
            Uri uri = Uri.parse(uriText);
            extractor.setDataSource(context, uri, null);
            audioTrack(extractor);
            configure(player);
            player.setDataSource(context, uri);
            player.prepare();
            return true;
        } catch (Exception ignored) {
            return false;
        } finally {
            try {
                extractor.release();
            } catch (Exception ignored) {
            }
            try {
                player.release();
            } catch (Exception ignored) {
            }
        }
    }

    private static Probe audioTrack(MediaExtractor extractor) {
        for (int index = 0; index < extractor.getTrackCount(); index++) {
            MediaFormat format = extractor.getTrackFormat(index);
            String mime = format.containsKey(MediaFormat.KEY_MIME)
                ? format.getString(MediaFormat.KEY_MIME) : "";
            if (mime == null || !mime.toLowerCase(Locale.ROOT).startsWith("audio/")) continue;
            long durationMs = format.containsKey(MediaFormat.KEY_DURATION)
                ? Math.max(0L, format.getLong(MediaFormat.KEY_DURATION) / 1000L) : 0L;
            return new Probe(mime, durationMs);
        }
        throw new IllegalStateException("文件中没有可播放的音频轨道");
    }

    private static void configure(MediaPlayer player) {
        player.setAudioAttributes(new AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
            .build());
        player.setVolume(0f, 0f);
    }
}
