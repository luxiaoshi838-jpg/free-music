package com.jianglab.babywife;

import org.json.JSONObject;

/** Detects cached files that are materially shorter than catalog metadata. */
final class PlaybackDurationGuard {
    private PlaybackDurationGuard() {
    }

    static boolean clearlyShort(String catalogJson, String playbackUri,
                                boolean networkCatalog, long actualDurationMs) {
        if (!networkCatalog || playbackUri == null
            || playbackUri.startsWith("http://") || playbackUri.startsWith("https://")) {
            return false;
        }
        long expected = expectedDurationMs(catalogJson);
        if (expected <= 0L || actualDurationMs <= 0L) return false;
        long shortBy = expected - actualDurationMs;
        return shortBy >= 15000L && actualDurationMs * 100L < expected * 90L;
    }

    static long expectedDurationMs(String catalogJson) {
        if (catalogJson == null || catalogJson.trim().isEmpty()) return -1L;
        try {
            JSONObject object = new JSONObject(catalogJson);
            String[] millisecondKeys = {"duration_ms", "durationMs", "dt"};
            for (String key : millisecondKeys) {
                long value = object.optLong(key, -1L);
                if (valid(value)) return value;
            }
            String[] flexibleKeys = {"duration", "interval", "time", "length"};
            for (String key : flexibleKeys) {
                double raw = object.optDouble(key, -1.0);
                if (raw <= 0.0) continue;
                long value = raw <= 10000.0 ? Math.round(raw * 1000.0) : Math.round(raw);
                if (valid(value)) return value;
            }
        } catch (Exception ignored) {
        }
        return -1L;
    }

    private static boolean valid(long value) {
        return value > 1000L && value < 4L * 60L * 60L * 1000L;
    }
}
