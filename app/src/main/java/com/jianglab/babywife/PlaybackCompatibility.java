package com.jianglab.babywife;

import android.content.Context;
import android.media.MediaCodecList;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.net.Uri;

import java.io.File;
import java.nio.ByteBuffer;
import java.util.Locale;

/** Checks whether this Android device can decode and seek a cached audio file. */
final class PlaybackCompatibility {
    private static final long MIN_DURATION_US = 60_000_000L;
    private static final long SEEK_PROBE_LIMIT_US = 30_000_000L;
    private static final int SAMPLE_PROBE_BYTES = 256 * 1024;

    private PlaybackCompatibility() {
    }

    static boolean isPlayable(File file) {
        if (file == null || !file.isFile() || file.length() <= 0L) return false;
        MediaExtractor extractor = new MediaExtractor();
        try {
            extractor.setDataSource(file.getAbsolutePath());
            return inspect(extractor);
        } catch (Throwable ignored) {
            return false;
        } finally {
            try { extractor.release(); } catch (Throwable ignored) { }
        }
    }

    static boolean isPlayable(Context context, String uriText) {
        if (context == null || uriText == null || uriText.trim().isEmpty()) return false;
        MediaExtractor extractor = new MediaExtractor();
        try {
            Uri uri = Uri.parse(uriText);
            if ("file".equalsIgnoreCase(uri.getScheme())) {
                String path = uri.getPath();
                if (path == null || path.isEmpty()) return false;
                extractor.setDataSource(path);
            } else {
                extractor.setDataSource(context, uri, null);
            }
            return inspect(extractor);
        } catch (Throwable ignored) {
            return false;
        } finally {
            try { extractor.release(); } catch (Throwable ignored) { }
        }
    }

    private static boolean inspect(MediaExtractor extractor) {
        int audioTrack = -1;
        MediaFormat audioFormat = null;
        for (int index = 0; index < extractor.getTrackCount(); index++) {
            MediaFormat format = extractor.getTrackFormat(index);
            String mime = format.getString(MediaFormat.KEY_MIME);
            if (mime != null && mime.toLowerCase(Locale.ROOT).startsWith("audio/")) {
                audioTrack = index;
                audioFormat = format;
                break;
            }
        }
        if (audioTrack < 0 || audioFormat == null) return false;

        long durationUs = audioFormat.containsKey(MediaFormat.KEY_DURATION)
            ? audioFormat.getLong(MediaFormat.KEY_DURATION) : 0L;
        if (durationUs < MIN_DURATION_US) return false;

        String mime = audioFormat.getString(MediaFormat.KEY_MIME);
        if (mime == null || mime.trim().isEmpty()) return false;
        if (!"audio/raw".equalsIgnoreCase(mime)) {
            try {
                String decoder = new MediaCodecList(MediaCodecList.REGULAR_CODECS)
                    .findDecoderForFormat(audioFormat);
                if (decoder == null || decoder.trim().isEmpty()) return false;
            } catch (Throwable ignored) {
                return false;
            }
        }

        extractor.selectTrack(audioTrack);
        if (!hasReadableSample(extractor)) return false;

        long seekTargetUs = Math.min(durationUs / 2L, SEEK_PROBE_LIMIT_US);
        if (seekTargetUs >= 5_000_000L) {
            extractor.seekTo(seekTargetUs, MediaExtractor.SEEK_TO_CLOSEST_SYNC);
            long sampleTimeUs = extractor.getSampleTime();
            if (sampleTimeUs < 0L || !hasReadableSample(extractor)) return false;
            if (seekTargetUs >= 10_000_000L && sampleTimeUs < 2_000_000L) return false;
        }
        return true;
    }

    private static boolean hasReadableSample(MediaExtractor extractor) {
        ByteBuffer buffer = ByteBuffer.allocate(SAMPLE_PROBE_BYTES);
        return extractor.readSampleData(buffer, 0) > 0;
    }
}
