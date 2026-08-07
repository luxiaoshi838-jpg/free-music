package com.jianglab.babywife;

import android.content.Context;
import android.net.Uri;

import androidx.media3.common.C;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.datasource.DataSource;
import androidx.media3.datasource.DataSpec;
import androidx.media3.datasource.DefaultDataSource;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.datasource.cache.CacheDataSource;
import androidx.media3.datasource.cache.ContentMetadata;

import org.json.JSONObject;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.util.Map;

/**
 * Exports the active online resource to the user's friendly cache file.
 *
 * Playback and export share the same Media3 cache key, but the export side is
 * deliberately read-only. It reuses spans that playback has already cached and
 * reads only missing bytes from upstream. It never waits for playback's cache
 * write lock, so pausing or continuing playback cannot leave export stuck at 0%.
 */
@UnstableApi
final class Media3FriendlyCacheExporter {
    interface ProgressCallback {
        void onProgress(long totalBytes, long completedBytes);
    }

    private Media3FriendlyCacheExporter() {
    }

    static String cacheAndExport(Context context,
                                 SearchQuickPlayback.Candidate candidate,
                                 String title,
                                 String artist,
                                 String album,
                                 ProgressCallback callback) throws Exception {
        if (context == null || candidate == null || candidate.playbackUrl.isEmpty()) {
            throw new IllegalArgumentException("Media3缓存参数无效");
        }
        String media3Key = Media3CacheStore.keyFor(title, artist, candidate.catalogJson);
        String storageKey = NetworkMediaCache.cacheKeyForCatalog(candidate.catalogJson);
        String artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(candidate.catalogJson);
        Media3PlaybackCacheIndex.record(context, media3Key, title, artist,
            candidate.catalogJson, artworkUrl);
        if (media3Key.isEmpty() || storageKey.isEmpty()) {
            throw new IllegalStateException("歌曲缓存键无效");
        }

        String existingUri = CacheStorage.findAudioUri(context, storageKey);
        if (!existingUri.isEmpty() && CacheFileState.exists(context, existingUri)
            && !SodaM4aDecryptor.isEncryptedM4a(context, existingUri)) {
            Media3PlaybackCacheIndex.markExported(context, media3Key, existingUri);
            return existingUri;
        }

        Map<String, String> headers = UnifiedMediaPlayer.requestHeadersFor(candidate.catalogJson);
        DefaultHttpDataSource.Factory httpFactory = new DefaultHttpDataSource.Factory()
            .setConnectTimeoutMs(12000)
            .setReadTimeoutMs(30000)
            .setAllowCrossProtocolRedirects(true)
            .setUserAgent(headers.containsKey("User-Agent")
                ? headers.get("User-Agent")
                : "Mozilla/5.0 (Android)");
        if (!headers.isEmpty()) httpFactory.setDefaultRequestProperties(headers);
        DefaultDataSource.Factory upstream = new DefaultDataSource.Factory(context, httpFactory);

        // Important: this factory is READ-ONLY for the Media3 cache. The player
        // may currently own a writable cache hole for the same key. A blocking
        // CacheWriter would wait for that hole and can stay at 0% for the whole
        // playback session (pause does not close the player's data source).
        CacheDataSource.Factory exportFactory = new CacheDataSource.Factory()
            .setCache(Media3CacheStore.get(context))
            .setUpstreamDataSourceFactory(upstream)
            .setCacheWriteDataSinkFactory(null)
            .setFlags(CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR);

        DataSpec dataSpec = new DataSpec.Builder()
            .setUri(Uri.parse(candidate.playbackUrl))
            .setKey(media3Key)
            .build();

        File tempRoot = new File(context.getCacheDir(), "media3_friendly_export");
        if (!tempRoot.exists() && !tempRoot.mkdirs()) {
            throw new IllegalStateException("无法创建Media3导出目录");
        }
        File raw = new File(tempRoot, storageKey + ".raw");
        File decrypted = new File(tempRoot, storageKey + ".decrypted");
        try {
            long written = copyReadThroughResource(
                context, exportFactory, dataSpec, raw, media3Key, callback);
            if (written <= 0L) {
                throw new IllegalStateException("缓存文件导出为空");
            }

            File source = raw;
            if (SodaM4aDecryptor.isEncryptedM4a(raw)) {
                if (candidate.playAuth.isEmpty()) {
                    throw new IllegalStateException("加密M4A缺少PlayAuth");
                }
                SodaM4aDecryptor.decrypt(raw, decrypted, candidate.playAuth);
                source = decrypted;
            }

            AudioPlaybackVerifier.Probe probe = AudioPlaybackVerifier.probeFile(source);
            String extension = extensionFor(candidate.extension, probe.mimeType);
            String savedAlbum = album == null ? "" : album.trim();
            if (savedAlbum.isEmpty()) {
                try {
                    savedAlbum = new JSONObject(candidate.catalogJson)
                        .optString("album", "").trim();
                } catch (Exception ignored) {
                }
            }
            String storedUri = CacheStorage.storeAudio(
                context, storageKey, extension, source,
                title, artist, savedAlbum, candidate.catalogJson);
            if (!CacheFileState.exists(context, storedUri)) {
                CacheFileState.deleteDirect(context, storedUri);
                CacheStorage.deleteKey(context, storageKey);
                throw new IllegalStateException("友好名称缓存写入后无法读取");
            }
            if (SodaM4aDecryptor.isEncryptedM4a(context, storedUri)) {
                CacheFileState.deleteDirect(context, storedUri);
                CacheStorage.deleteKey(context, storageKey);
                throw new IllegalStateException("友好名称缓存写入后仍为加密内容");
            }
            CacheStorage.deleteOtherSongCaches(context, title, artist, storageKey);
            Media3PlaybackCacheIndex.markExported(context, media3Key, storedUri);
            return storedUri;
        } finally {
            if (raw.exists()) raw.delete();
            if (decrypted.exists()) decrypted.delete();
        }
    }

    private static long copyReadThroughResource(Context context,
                                                CacheDataSource.Factory factory,
                                                DataSpec dataSpec,
                                                File output,
                                                String media3Key,
                                                ProgressCallback callback) throws Exception {
        DataSource source = factory.createDataSource();
        long written = 0L;
        long expectedLength = C.LENGTH_UNSET;
        try (OutputStream stream = new BufferedOutputStream(
            new FileOutputStream(output, false))) {
            long openedLength = source.open(dataSpec);
            if (openedLength > 0L) expectedLength = openedLength;
            if (expectedLength <= 0L) {
                long metadataLength = ContentMetadata.getContentLength(
                    Media3CacheStore.get(context).getContentMetadata(media3Key));
                if (metadataLength > 0L) expectedLength = metadataLength;
            }

            byte[] buffer = new byte[128 * 1024];
            while (true) {
                if (Thread.currentThread().isInterrupted()) {
                    throw new IllegalStateException("后台缓存导出已取消");
                }
                int read = source.read(buffer, 0, buffer.length);
                if (read == C.RESULT_END_OF_INPUT) break;
                if (read <= 0) continue;
                stream.write(buffer, 0, read);
                written += read;

                long actualCached = Media3CacheStore.cachedBytes(context, media3Key);
                Media3PlaybackCacheIndex.updateProgress(
                    context, media3Key, actualCached, expectedLength);
                if (callback != null) callback.onProgress(expectedLength, written);
            }
            stream.flush();
        } finally {
            try {
                source.close();
            } catch (Exception ignored) {
            }
        }

        if (written <= 0L || output.length() != written) {
            throw new IllegalStateException("缓存文件导出为空");
        }
        if (expectedLength > 0L && written != expectedLength) {
            throw new IllegalStateException("缓存文件长度不完整：期望 "
                + expectedLength + "，实际 " + written);
        }
        if (callback != null) callback.onProgress(
            expectedLength > 0L ? expectedLength : written, written);
        return written;
    }

    private static String extensionFor(String hint, String mimeType) {
        String mime = mimeType == null ? "" : mimeType.toLowerCase();
        if (mime.contains("flac")) return "flac";
        if (mime.contains("mpeg") || mime.contains("mp3")) return "mp3";
        if (mime.contains("mp4") || mime.contains("m4a")) return "m4a";
        if (mime.contains("wav")) return "wav";
        if (mime.contains("ogg")) return "ogg";
        if (mime.contains("aac")) return "aac";
        String safe = hint == null ? "" : hint.trim().toLowerCase()
            .replaceAll("[^a-z0-9]", "");
        if (safe.equals("mpeg")) return "mp3";
        if (safe.equals("mp4")) return "m4a";
        return safe.isEmpty() || safe.equals("audio") ? "m4a" : safe;
    }
}
