package com.jianglab.babywife;

import android.content.Context;
import android.media.MediaCodec;
import android.media.MediaCodecList;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.net.Uri;

import java.io.File;
import java.nio.ByteBuffer;
import java.util.Locale;

/** Checks whether this Android device can actually decode and seek a cached audio file. */
final class PlaybackCompatibility {
    private static final long MIN_DURATION_US = 60_000_000L;
    private static final long SEEK_PROBE_LIMIT_US = 30_000_000L;
    private static final long DECODE_PROBE_TIMEOUT_NS = 1_800_000_000L;
    private static final int MAX_INPUT_PACKETS = 64;

    private PlaybackCompatibility() {
    }

    static boolean isPlayable(File file) {
        if (file == null || !file.isFile() || file.length() <= 0L) return false;
        MediaExtractor extractor = new MediaExtractor();
        try {
            extractor.setDataSource(file.getAbsolutePath());
            return inspectAndDecode(extractor);
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
            return inspectAndDecode(extractor);
        } catch (Throwable ignored) {
            return false;
        } finally {
            try { extractor.release(); } catch (Throwable ignored) { }
        }
    }

    private static boolean inspectAndDecode(MediaExtractor extractor) {
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

        if ("audio/raw".equalsIgnoreCase(mime)) {
            extractor.selectTrack(audioTrack);
            return hasReadableRawSample(extractor, 0L)
                && hasReadableRawSample(extractor, Math.min(durationUs / 2L, SEEK_PROBE_LIMIT_US));
        }

        String decoderName;
        try {
            decoderName = new MediaCodecList(MediaCodecList.REGULAR_CODECS)
                .findDecoderForFormat(audioFormat);
        } catch (Throwable ignored) {
            return false;
        }
        if (decoderName == null || decoderName.trim().isEmpty()) return false;

        extractor.selectTrack(audioTrack);
        if (!decodeProbe(extractor, audioFormat, decoderName, 0L)) return false;

        long seekTargetUs = Math.min(durationUs / 2L, SEEK_PROBE_LIMIT_US);
        return seekTargetUs < 5_000_000L
            || decodeProbe(extractor, audioFormat, decoderName, seekTargetUs);
    }

    private static boolean hasReadableRawSample(MediaExtractor extractor, long seekUs) {
        try {
            extractor.seekTo(Math.max(0L, seekUs), MediaExtractor.SEEK_TO_CLOSEST_SYNC);
            ByteBuffer buffer = ByteBuffer.allocate(256 * 1024);
            return extractor.getSampleTime() >= 0L && extractor.readSampleData(buffer, 0) > 0;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static boolean decodeProbe(MediaExtractor extractor, MediaFormat format,
                                       String decoderName, long seekUs) {
        MediaCodec codec = null;
        try {
            extractor.seekTo(Math.max(0L, seekUs), MediaExtractor.SEEK_TO_CLOSEST_SYNC);
            if (extractor.getSampleTime() < 0L) return false;

            codec = MediaCodec.createByCodecName(decoderName);
            codec.configure(format, null, null, 0);
            codec.start();

            MediaCodec.BufferInfo outputInfo = new MediaCodec.BufferInfo();
            long deadline = System.nanoTime() + DECODE_PROBE_TIMEOUT_NS;
            int queuedPackets = 0;
            boolean inputEnded = false;

            while (System.nanoTime() < deadline) {
                if (!inputEnded && queuedPackets < MAX_INPUT_PACKETS) {
                    int inputIndex = codec.dequeueInputBuffer(10_000L);
                    if (inputIndex >= 0) {
                        ByteBuffer input = codec.getInputBuffer(inputIndex);
                        if (input == null) return false;
                        input.clear();
                        int sampleSize = extractor.readSampleData(input, 0);
                        long sampleTimeUs = extractor.getSampleTime();
                        if (sampleSize < 0 || sampleTimeUs < 0L) {
                            codec.queueInputBuffer(inputIndex, 0, 0, 0L,
                                MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputEnded = true;
                        } else {
                            codec.queueInputBuffer(inputIndex, 0, sampleSize,
                                Math.max(0L, sampleTimeUs), 0);
                            extractor.advance();
                            queuedPackets++;
                        }
                    }
                }

                int outputIndex = codec.dequeueOutputBuffer(outputInfo, 10_000L);
                if (outputIndex >= 0) {
                    boolean decodedAudio = outputInfo.size > 0;
                    boolean outputEnded = (outputInfo.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
                    codec.releaseOutputBuffer(outputIndex, false);
                    if (decodedAudio) return true;
                    if (outputEnded) return false;
                }

                if (queuedPackets >= MAX_INPUT_PACKETS && !inputEnded) {
                    int inputIndex = codec.dequeueInputBuffer(10_000L);
                    if (inputIndex >= 0) {
                        codec.queueInputBuffer(inputIndex, 0, 0, 0L,
                            MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                        inputEnded = true;
                    }
                }
            }
            return false;
        } catch (Throwable ignored) {
            return false;
        } finally {
            if (codec != null) {
                try { codec.stop(); } catch (Throwable ignored) { }
                try { codec.release(); } catch (Throwable ignored) { }
            }
        }
    }
}
