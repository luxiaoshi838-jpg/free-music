package com.jianglab.babywife;

import android.content.Context;

import androidx.media3.common.util.UnstableApi;
import androidx.media3.database.StandaloneDatabaseProvider;
import androidx.media3.datasource.DataSource;
import androidx.media3.datasource.cache.Cache;
import androidx.media3.datasource.cache.CacheDataSource;
import androidx.media3.datasource.cache.ContentMetadata;
import androidx.media3.datasource.cache.LeastRecentlyUsedCacheEvictor;
import androidx.media3.datasource.cache.SimpleCache;

import java.io.File;
import java.util.HashSet;
import java.util.Set;

/**
 * Process-wide Media3 cache used by both streaming playback and later resumes.
 *
 * This cache is intentionally separate from the user-selected friendly export
 * folder. It stores Media3 spans while a song is being played, so reopening the
 * same logical song reuses already downloaded bytes instead of starting a second
 * full-file download.
 */
@UnstableApi
final class Media3CacheStore {
    private static final long MAX_CACHE_BYTES = 1024L * 1024L * 1024L;
    private static SimpleCache cache;
    private static StandaloneDatabaseProvider databaseProvider;

    private Media3CacheStore() {
    }

    static String keyFor(String title, String artist, String catalogJson) {
        String logical = CacheStorage.logicalIdentity(title, artist);
        if (logical != null && !logical.trim().isEmpty()) {
            return "media3|" + logical.trim();
        }
        String catalogKey = NetworkMediaCache.cacheKeyForCatalog(catalogJson);
        return catalogKey == null || catalogKey.trim().isEmpty()
            ? "" : "media3|" + catalogKey.trim();
    }

    static synchronized SimpleCache get(Context context) {
        if (cache != null) return cache;
        Context app = context.getApplicationContext();
        File directory = new File(app.getFilesDir(), "media3_shared_audio_cache");
        if (!directory.exists()) directory.mkdirs();
        databaseProvider = new StandaloneDatabaseProvider(app);
        cache = new SimpleCache(
            directory,
            new LeastRecentlyUsedCacheEvictor(MAX_CACHE_BYTES),
            databaseProvider
        );
        return cache;
    }

    static DataSource.Factory dataSourceFactory(Context context,
                                                DataSource.Factory upstream) {
        return new CacheDataSource.Factory()
            .setCache(get(context))
            .setUpstreamDataSourceFactory(upstream)
            .setFlags(CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR);
    }

    static boolean hasAny(Context context, String key) {
        if (key == null || key.trim().isEmpty()) return false;
        try {
            return !get(context).getCachedSpans(key.trim()).isEmpty();
        } catch (Exception ignored) {
            return false;
        }
    }

    static boolean isFullyCached(Context context, String key) {
        if (key == null || key.trim().isEmpty()) return false;
        try {
            SimpleCache local = get(context);
            long length = ContentMetadata.getContentLength(
                local.getContentMetadata(key.trim()));
            return length > 0L && local.isCached(key.trim(), 0L, length);
        } catch (Exception ignored) {
            return false;
        }
    }

    static long cachedBytes(Context context, String key) {
        if (key == null || key.trim().isEmpty()) return 0L;
        try {
            long total = 0L;
            for (androidx.media3.datasource.cache.CacheSpan span
                : get(context).getCachedSpans(key.trim())) {
                if (span.isCached && span.length > 0L) total += span.length;
            }
            return total;
        } catch (Exception ignored) {
            return 0L;
        }
    }

    static void remove(Context context, String key) {
        if (key == null || key.trim().isEmpty()) return;
        try {
            get(context).removeResource(key.trim());
        } catch (Exception ignored) {
        }
    }

    static int removeExcept(Context context, Set<String> keepKeys) {
        int removed = 0;
        Set<String> keep = keepKeys == null
            ? new HashSet<>() : new HashSet<>(keepKeys);
        try {
            SimpleCache local = get(context);
            Set<String> keys = new HashSet<>(local.getKeys());
            for (String key : keys) {
                if (keep.contains(key)) continue;
                try {
                    local.removeResource(key);
                    removed++;
                } catch (Cache.CacheException ignored) {
                }
            }
        } catch (Exception ignored) {
        }
        return removed;
    }
}
