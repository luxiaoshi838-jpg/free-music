package com.jianglab.babywife;

import android.content.Context;
import android.content.SharedPreferences;

import androidx.media3.common.util.UnstableApi;

import org.json.JSONObject;

import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Persistent metadata index for the real Media3 span cache.
 *
 * Media3 stores binary spans under internal names. This index maps those spans
 * back to a song, records partial/full progress and remembers the friendly
 * exported URI. It lets the existing cache dialog and broom recognise and
 * clean playback cache even before a user-visible audio file is exported.
 */
@UnstableApi
final class Media3PlaybackCacheIndex {
    private static final String PREFS = "media3_playback_cache_index";
    private static final String ENTRY_PREFIX = "entry|";

    static final class Summary {
        final int resources;
        final int partialResources;
        final int completeResources;
        final long cachedBytes;

        Summary(int resources, int partialResources, int completeResources,
                long cachedBytes) {
            this.resources = resources;
            this.partialResources = partialResources;
            this.completeResources = completeResources;
            this.cachedBytes = Math.max(0L, cachedBytes);
        }

        String displayText() {
            return "播放缓存：" + resources + " 首（完整 " + completeResources
                + "，片段 " + partialResources + "），共 " + formatBytes(cachedBytes);
        }
    }

    private Media3PlaybackCacheIndex() {
    }

    static synchronized void record(Context context, String key,
                                    String title, String artist,
                                    String catalogJson, String artworkUrl) {
        if (context == null || empty(key)) return;
        JSONObject object = read(context, key);
        try {
            object.put("key", key.trim());
            object.put("title", safe(title));
            object.put("artist", safe(artist));
            if (!empty(catalogJson)) object.put("catalogJson", catalogJson);
            if (!empty(artworkUrl)) object.put("artworkUrl", artworkUrl);
            object.put("lastAccess", System.currentTimeMillis());
            write(context, key, object);
        } catch (Exception ignored) {
        }
    }

    static synchronized void updateProgress(Context context, String key,
                                            long cachedBytes, long totalBytes) {
        if (context == null || empty(key)) return;
        JSONObject object = read(context, key);
        try {
            object.put("key", key.trim());
            object.put("cachedBytes", Math.max(0L, cachedBytes));
            if (totalBytes > 0L) object.put("totalBytes", totalBytes);
            object.put("complete", totalBytes > 0L && cachedBytes >= totalBytes);
            object.put("lastAccess", System.currentTimeMillis());
            write(context, key, object);
        } catch (Exception ignored) {
        }
    }

    static synchronized void markExported(Context context, String key,
                                          String friendlyUri) {
        if (context == null || empty(key)) return;
        JSONObject object = read(context, key);
        try {
            object.put("key", key.trim());
            object.put("friendlyUri", safe(friendlyUri));
            object.put("exported", !empty(friendlyUri));
            object.put("lastAccess", System.currentTimeMillis());
            write(context, key, object);
        } catch (Exception ignored) {
        }
    }

    static synchronized String friendlyUri(Context context, String key) {
        if (context == null || empty(key)) return "";
        return read(context, key).optString("friendlyUri", "").trim();
    }

    static synchronized String artworkUrl(Context context, String key) {
        if (context == null || empty(key)) return "";
        return read(context, key).optString("artworkUrl", "").trim();
    }

    static synchronized void remove(Context context, String key) {
        if (context == null || empty(key)) return;
        preferences(context).edit().remove(prefKey(key)).apply();
    }

    static synchronized void pruneToKeys(Context context, Set<String> existingKeys) {
        if (context == null) return;
        Set<String> existing = existingKeys == null
            ? new HashSet<>() : new HashSet<>(existingKeys);
        SharedPreferences prefs = preferences(context);
        SharedPreferences.Editor editor = prefs.edit();
        boolean changed = false;
        for (Map.Entry<String, ?> entry : prefs.getAll().entrySet()) {
            if (!entry.getKey().startsWith(ENTRY_PREFIX)) continue;
            try {
                JSONObject object = new JSONObject(String.valueOf(entry.getValue()));
                String key = object.optString("key", "");
                if (!existing.contains(key)) {
                    editor.remove(entry.getKey());
                    changed = true;
                }
            } catch (Exception ignored) {
                editor.remove(entry.getKey());
                changed = true;
            }
        }
        if (changed) editor.apply();
    }

    static synchronized Summary summary(Context context) {
        if (context == null) return new Summary(0, 0, 0, 0L);
        Set<String> keys;
        try {
            keys = new HashSet<>(Media3CacheStore.get(context).getKeys());
        } catch (Exception ignored) {
            keys = new HashSet<>();
        }
        int partial = 0;
        int complete = 0;
        long bytes = 0L;
        for (String key : keys) {
            long cached = Media3CacheStore.cachedBytes(context, key);
            bytes += Math.max(0L, cached);
            boolean full = Media3CacheStore.isFullyCached(context, key);
            if (full) complete++;
            else if (cached > 0L) partial++;
            updateProgress(context, key, cached, full ? cached : -1L);
        }
        pruneToKeys(context, keys);
        return new Summary(keys.size(), partial, complete, bytes);
    }

    static synchronized List<String> knownKeys(Context context) {
        List<String> keys = new ArrayList<>();
        if (context == null) return keys;
        for (Object value : preferences(context).getAll().values()) {
            try {
                String key = new JSONObject(String.valueOf(value))
                    .optString("key", "").trim();
                if (!key.isEmpty()) keys.add(key);
            } catch (Exception ignored) {
            }
        }
        return keys;
    }

    private static JSONObject read(Context context, String key) {
        try {
            String raw = preferences(context).getString(prefKey(key), "");
            if (raw != null && !raw.trim().isEmpty()) return new JSONObject(raw);
        } catch (Exception ignored) {
        }
        return new JSONObject();
    }

    private static void write(Context context, String key, JSONObject object) {
        preferences(context).edit().putString(prefKey(key), object.toString()).apply();
    }

    private static SharedPreferences preferences(Context context) {
        return context.getApplicationContext()
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static String prefKey(String key) {
        return ENTRY_PREFIX + sha256(safe(key).trim());
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(value.getBytes("UTF-8"));
            StringBuilder out = new StringBuilder();
            for (byte item : bytes) out.append(String.format(Locale.ROOT, "%02x", item));
            return out.toString();
        } catch (Exception ignored) {
            return Integer.toHexString(value.hashCode());
        }
    }

    private static String formatBytes(long bytes) {
        if (bytes < 1024L) return bytes + " B";
        double kb = bytes / 1024.0;
        if (kb < 1024.0) return String.format(Locale.ROOT, "%.1f KB", kb);
        double mb = kb / 1024.0;
        if (mb < 1024.0) return String.format(Locale.ROOT, "%.1f MB", mb);
        return String.format(Locale.ROOT, "%.2f GB", mb / 1024.0);
    }

    private static boolean empty(String value) {
        return value == null || value.trim().isEmpty();
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }
}
