package com.jianglab.babywife;

import android.content.Context;
import android.net.Uri;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import bridge.Bridge;

/** Downloads only tracks the user actually selects and keeps their source metadata. */
final class NetworkMediaCache {
    private static final int CONNECT_TIMEOUT_MS = 12000;
    private static final int READ_TIMEOUT_MS = 30000;
    private static final long MAX_AUDIO_BYTES = 512L * 1024L * 1024L;
    private static final Object[] CACHE_LOCKS = createCacheLocks();

    private NetworkMediaCache() {
    }

    interface StatusCallback {
        void onStatus(String message);
    }

    static final class CacheResult {
        final String audioUri;
        final String lyric;
        final boolean audioFromCache;
        final boolean lyricFromCache;
        final String catalogJson;
        final String sourceCode;
        final boolean sourceChanged;

        CacheResult(String audioUri, String lyric, boolean audioFromCache, boolean lyricFromCache,
                    String catalogJson, String sourceCode, boolean sourceChanged) {
            this.audioUri = audioUri == null ? "" : audioUri;
            this.lyric = lyric == null ? "" : lyric;
            this.audioFromCache = audioFromCache;
            this.lyricFromCache = lyricFromCache;
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.sourceCode = sourceCode == null ? "" : sourceCode;
            this.sourceChanged = sourceChanged;
        }
    }

    /** Compatibility overload used by the final player source.
     * The boolean requests persistent caching; this implementation always persists selected tracks.
     */
    static CacheResult cache(Context context, String catalogJson, boolean persist,
                             StatusCallback callback) throws Exception {
        return cache(context, catalogJson, callback);
    }

    static CacheResult cache(Context context, String catalogJson, StatusCallback callback) throws Exception {
        if (context == null) throw new IllegalArgumentException("context is required");
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
        String identity = CacheStorage.logicalIdentity(catalogTitle(requestedCatalog), catalogArtist(requestedCatalog));
        Object lock = CACHE_LOCKS[Math.floorMod(identity.hashCode(), CACHE_LOCKS.length)];
        synchronized (lock) {
            return cacheLocked(context, requestedCatalog, callback);
        }
    }

    private static CacheResult cacheLocked(Context context, JSONObject requestedCatalog,
                                           StatusCallback callback) throws Exception {
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        if (requestedSource.isEmpty() || requestedId.isEmpty()) {
            throw new IllegalArgumentException("歌曲目录缺少来源或 ID");
        }

        String requestedKey = sha256(requestedSource + "|" + requestedId);
        String requestedTitle = catalogTitle(requestedCatalog);
        String requestedArtist = catalogArtist(requestedCatalog);
        String requestedAlbum = catalogAlbum(requestedCatalog);

        status(callback, "正在检查这首歌是否已有可播放缓存...");
        for (CacheStorage.AudioMatch match :
            CacheStorage.findAudioMatches(context, requestedTitle, requestedArtist)) {
            if (!PlayableAudioResolver.cachedAudioExists(context, match.audioUri)) {
                CacheStorage.deleteKey(context, match.key);
                continue;
            }
            JSONObject matchedCatalog;
            try {
                matchedCatalog = canonicalCatalog(match.catalogJson);
            } catch (Exception ignored) {
                matchedCatalog = requestedCatalog;
            }
            String matchedSource = matchedCatalog.optString("source", "")
                .trim().toLowerCase(Locale.ROOT);
            String matchedId = matchedCatalog.optString("id", "").trim();
            if (matchedSource.isEmpty() || matchedId.isEmpty()) {
                matchedCatalog = requestedCatalog;
                matchedSource = requestedSource;
                matchedId = requestedId;
            }
            String lyric = CacheStorage.readLyric(context, match.key);
            boolean lyricFromCache = !lyric.trim().isEmpty();
            cleanupDuplicateSongCachesAsync(context, requestedTitle, requestedArtist, match.key);
            boolean sourceChanged = !requestedSource.equals(matchedSource)
                || !requestedId.equals(matchedId);
            status(callback, "已找到同歌名和歌手的现有缓存，直接播放");
            return new CacheResult(match.audioUri, lyric, true, lyricFromCache,
                matchedCatalog.toString(), matchedSource, sourceChanged);
        }

        CacheStorage.ensureFriendlyNames(context, requestedKey, requestedTitle, requestedArtist,
            requestedAlbum, requestedCatalog.toString());
        String requestedAudioUri = CacheStorage.findAudioUri(context, requestedKey);
        if (!requestedAudioUri.isEmpty()) {
            if (PlayableAudioResolver.cachedAudioExists(context, requestedAudioUri)) {
                String requestedLyric = CacheStorage.readLyric(context, requestedKey);
                boolean lyricFromCache = !requestedLyric.trim().isEmpty();
                status(callback, "已找到原来源缓存，直接播放");
                return new CacheResult(requestedAudioUri, requestedLyric, true, lyricFromCache,
                    requestedCatalog.toString(), requestedSource, false);
            }
            CacheStorage.deleteKey(context, requestedKey);
            status(callback, "原有缓存不可播放，已清理；开始寻找唯一可用版本...");
        }

        PlayableAudioResolver.Result prepared =
            PlayableAudioResolver.prepare(context, requestedCatalog, callback);
        JSONObject actualCatalog = canonicalCatalog(prepared.catalogJson);
        String actualSource = actualCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String actualId = actualCatalog.optString("id", "").trim();
        boolean sourceChanged = !requestedSource.equals(actualSource) || !requestedId.equals(actualId);
        String actualKey = sha256(actualSource + "|" + actualId);
        String actualTitle = catalogTitle(actualCatalog);
        String actualArtist = catalogArtist(actualCatalog);
        String actualAlbum = catalogAlbum(actualCatalog);

        CacheStorage.ensureFriendlyNames(context, actualKey, actualTitle, actualArtist,
            actualAlbum, actualCatalog.toString());
        String lyric = CacheStorage.readLyric(context, actualKey);
        boolean lyricFromCache = !lyric.trim().isEmpty();
        cleanupDuplicateSongCachesAsync(context, requestedTitle, requestedArtist, actualKey);
        if (!CacheStorage.logicalIdentity(requestedTitle, requestedArtist).equals(
            CacheStorage.logicalIdentity(actualTitle, actualArtist))) {
            cleanupDuplicateSongCachesAsync(context, actualTitle, actualArtist, actualKey);
        }
        status(callback, prepared.fromCache
            ? "已读取唯一可播放缓存" : "唯一正式缓存已完成，其他来源候选已清理");
        return new CacheResult(prepared.audioUri, lyric, prepared.fromCache, lyricFromCache,
            actualCatalog.toString(), actualSource, sourceChanged);
    }

    static void cleanupDuplicateSongCachesAsync(Context context, String title,
                                                     String artist, String keepKey) {
        if (context == null) return;
        new Thread(() -> CacheStorage.deleteOtherSongCaches(context, title, artist, keepKey),
            "duplicate-cache-cleanup").start();
    }

    private static Object[] createCacheLocks() {
        Object[] locks = new Object[32];
        for (int index = 0; index < locks.length; index++) locks[index] = new Object();
        return locks;
    }

    private static final class ResolvedAudioAddress {
        final String url;
        final String playAuth;

        ResolvedAudioAddress(String url, String playAuth) {
            this.url = url == null ? "" : url.trim();
            this.playAuth = playAuth == null ? "" : playAuth.trim();
        }

        static ResolvedAudioAddress parse(String rawUrl, String explicitAuth) {
            String raw = rawUrl == null ? "" : rawUrl.trim();
            String auth = explicitAuth == null ? "" : explicitAuth.trim();
            int marker = raw.indexOf("#auth=");
            if (marker >= 0) {
                if (auth.isEmpty()) {
                    try {
                        auth = java.net.URLDecoder.decode(raw.substring(marker + 6), "UTF-8");
                    } catch (Exception ignored) {
                        auth = raw.substring(marker + 6);
                    }
                }
                raw = raw.substring(0, marker);
            }
            return new ResolvedAudioAddress(raw, auth);
        }
    }

    private static final class ResolvedChoice {
        final JSONObject catalog;
        final JSONObject resolved;

        ResolvedChoice(JSONObject catalog, JSONObject resolved) {
            this.catalog = catalog;
            this.resolved = resolved;
        }

        String audioUrl() {
            return resolved == null ? "" : resolved.optString("url", "").trim();
        }
    }

    private static JSONObject canonicalCatalog(String raw) throws Exception {
        JSONObject catalog = new JSONObject(raw == null ? "{}" : raw);
        String source = catalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        catalog.put("source", source);
        return catalog;
    }

    private static ResolvedChoice findFallback(JSONObject requestedCatalog, StatusCallback callback) {
        List<CatalogSearch.Track> alternatives = CatalogSearch.findExactAlternatives(requestedCatalog.toString());
        for (CatalogSearch.Track alternative : alternatives) {
            try {
                JSONObject catalog = canonicalCatalog(alternative.rawJson);
                JSONObject resolved = resolve(catalog.toString());
                ResolvedChoice choice = new ResolvedChoice(catalog, resolved);
                if (!choice.audioUrl().isEmpty()) {
                    status(callback, "已匹配到同歌手同名的" + CatalogSearch.labelForSource(alternative.sourceCode) + "版本");
                    return choice;
                }
            } catch (Exception ignored) {
            }
        }
        return null;
    }

    static String cacheKeyForCatalog(String catalogJson) {
        try {
            JSONObject catalog = canonicalCatalog(catalogJson);
            String source = catalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
            String id = catalog.optString("id", "").trim();
            if (source.isEmpty() || id.isEmpty()) return "";
            return sha256(source + "|" + id);
        } catch (Exception ignored) {
            return "";
        }
    }

    static void normalizeCacheFiles(Context context, String catalogJson) {
        try {
            JSONObject catalog = canonicalCatalog(catalogJson);
            String key = cacheKeyForCatalog(catalog.toString());
            if (key.isEmpty()) return;
            CacheStorage.ensureFriendlyNames(context, key, catalogTitle(catalog), catalogArtist(catalog),
                catalogAlbum(catalog), catalog.toString());
        } catch (Exception ignored) {
        }
    }

    static int clearExcept(Context context, Set<String> keepKeys) {
        return CacheStorage.clearExcept(context, keepKeys);
    }

    static int deleteCatalogCache(Context context, String catalogJson) {
        String key = cacheKeyForCatalog(catalogJson);
        return key.isEmpty() ? 0 : CacheStorage.deleteKey(context, key);
    }

    static boolean cachedAudioExists(Context context, String uriText) {
        return PlayableAudioResolver.cachedAudioExists(context, uriText);
    }

    private static String catalogTitle(JSONObject catalog) {
        if (catalog == null) return "未知歌曲";
        return firstNonEmpty(catalog.optString("name"), catalog.optString("title"), "未知歌曲");
    }

    private static String catalogArtist(JSONObject catalog) {
        if (catalog == null) return "未知歌手";
        return firstNonEmpty(catalog.optString("artist"), catalog.optString("singer"), "未知歌手");
    }

    private static String catalogAlbum(JSONObject catalog) {
        return catalog == null ? "未知专辑" : firstNonEmpty(catalog.optString("album"), catalog.optString("albumName"), "未知专辑");
    }

    private static JSONObject resolve(String catalogJson) throws Exception {
        JSONObject catalog = new JSONObject(catalogJson == null ? "{}" : catalogJson);
        catalog.put("format", "mp3");
        catalog.put("ext", "mp3");
        catalog.put("quality", "320k");
        catalog.put("br", 320000);
        JSONObject response = new JSONObject(Bridge.resolve(catalog.toString()));
        if (!response.optBoolean("ok", false)) {
            response = new JSONObject(Bridge.resolve(catalogJson));
        }
        if (!response.optBoolean("ok", false)) {
            throw new IllegalStateException(response.optString("error", "歌曲解析失败"));
        }
        JSONObject data = response.optJSONObject("data");
        if (data == null) throw new IllegalStateException("歌曲解析结果为空");
        return data;
    }

    private static String fetchLyrics(String catalogJson) {
        try {
            JSONObject response = new JSONObject(Bridge.lyrics(catalogJson));
            if (!response.optBoolean("ok", false)) return "";
            Object value = response.opt("data");
            return value instanceof String ? ((String) value).trim() : "";
        } catch (Exception ignored) {
            return "";
        }
    }

    private static void download(String urlText, String source, File partial, StatusCallback callback) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(urlText).openConnection();
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setInstanceFollowRedirects(true);
        connection.setUseCaches(false);
        connection.setRequestProperty("User-Agent", userAgent(source));
        connection.setRequestProperty("Accept", "audio/*,application/octet-stream;q=0.9,*/*;q=0.1");
        connection.setRequestProperty("Accept-Encoding", "identity");
        String referer = referer(source);
        if (!referer.isEmpty()) connection.setRequestProperty("Referer", referer);

        try {
            int statusCode = connection.getResponseCode();
            if (statusCode < 200 || statusCode >= 400) throw new IllegalStateException("音频下载失败：HTTP " + statusCode);
            long total = connection.getContentLengthLong();
            if (total > MAX_AUDIO_BYTES) throw new IllegalStateException("歌曲文件超过缓存上限");

            long written = 0;
            int lastPercent = -1;
            try (InputStream input = new BufferedInputStream(connection.getInputStream());
                 BufferedOutputStream output = new BufferedOutputStream(new FileOutputStream(partial))) {
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = input.read(buffer)) >= 0) {
                    if (count == 0) continue;
                    written += count;
                    if (written > MAX_AUDIO_BYTES) throw new IllegalStateException("歌曲文件超过缓存上限");
                    output.write(buffer, 0, count);
                    if (total > 0) {
                        int percent = (int) Math.min(100, written * 100 / total);
                        if (percent >= lastPercent + 10) {
                            lastPercent = percent;
                            status(callback, "正在缓存歌曲：" + percent + "%");
                        }
                    }
                }
            }
            if (written <= 0) throw new IllegalStateException("没有下载到音频内容");
        } finally {
            connection.disconnect();
        }
    }

    private static File findExistingAudio(File root, String key) {
        File[] files = root.listFiles();
        if (files == null) return null;
        String prefix = key + ".";
        for (File file : files) {
            if (!file.isFile() || !file.getName().startsWith(prefix) || file.getName().endsWith(".part")
                || file.getName().endsWith(".lrc")) continue;
            if (file.length() > 0) return file;
        }
        return null;
    }

    private static String readText(File file) {
        if (file == null || !file.exists() || file.length() <= 0) return "";
        try (FileInputStream input = new FileInputStream(file)) {
            byte[] data = new byte[(int) Math.min(file.length(), 4L * 1024L * 1024L)];
            int count = input.read(data);
            return count <= 0 ? "" : new String(data, 0, count, StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            return "";
        }
    }

    private static void writeTextAtomically(File output, String text) throws Exception {
        File partial = new File(output.getParentFile(), output.getName() + ".part");
        try (FileOutputStream stream = new FileOutputStream(partial)) {
            stream.write(text.getBytes(StandardCharsets.UTF_8));
        }
        if (output.exists() && !output.delete()) throw new IllegalStateException("无法更新歌词缓存");
        if (!partial.renameTo(output)) {
            copyFile(partial, output);
            if (!partial.delete()) partial.deleteOnExit();
        }
    }

    private static void copyFile(File source, File target) throws Exception {
        try (FileInputStream input = new FileInputStream(source);
             FileOutputStream output = new FileOutputStream(target)) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) >= 0) {
                if (count > 0) output.write(buffer, 0, count);
            }
        }
    }

    private static String extensionFromUrl(String url) {
        if (url == null) return "mp3";
        String clean = url;
        int query = clean.indexOf('?');
        if (query >= 0) clean = clean.substring(0, query);
        int dot = clean.lastIndexOf('.');
        return dot < 0 ? "mp3" : clean.substring(dot + 1);
    }

    private static String sanitizeExtension(String value) {
        String extension = value == null ? "" : value.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
        if (extension.equals("flac") || extension.equals("m4a") || extension.equals("aac")
            || extension.equals("ogg") || extension.equals("opus") || extension.equals("wav")
            || extension.equals("wma") || extension.equals("mp3")) return extension;
        return "mp3";
    }

    private static String detectAudioExtension(File file, String fallback) {
        if (AudioTranscoder.isMp3(file)) return "mp3";
        byte[] header = new byte[16];
        try (InputStream input = new BufferedInputStream(new FileInputStream(file))) {
            int count = input.read(header);
            if (count >= 4) {
                String first4 = new String(header, 0, 4, StandardCharsets.ISO_8859_1);
                if ("fLaC".equals(first4)) return "flac";
                if ("OggS".equals(first4)) return "ogg";
                if ("RIFF".equals(first4) && count >= 12) return "wav";
            }
            if (count >= 8) {
                String ftyp = new String(header, 4, 4, StandardCharsets.ISO_8859_1);
                if ("ftyp".equals(ftyp)) return "m4a";
            }
        } catch (Exception ignored) {
        }
        return sanitizeExtension(fallback);
    }

    private static String userAgent(String source) {
        if ("kugou".equals(source) || "migu".equals(source) || "soda".equals(source)) {
            return "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36";
        }
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134 Safari/537.36";
    }

    private static String referer(String source) {
        if ("netease".equals(source)) return "https://music.163.com/";
        if ("qq".equals(source)) return "https://y.qq.com/";
        if ("kugou".equals(source)) return "https://www.kugou.com/";
        if ("kuwo".equals(source)) return "http://www.kuwo.cn/";
        if ("migu".equals(source)) return "https://music.migu.cn/";
        if ("bilibili".equals(source)) return "https://www.bilibili.com/";
        return "";
    }

    private static String sha256(String value) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] bytes = digest.digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder builder = new StringBuilder();
        for (byte item : bytes) builder.append(String.format(Locale.ROOT, "%02x", item & 0xff));
        return builder.toString();
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) return value.trim();
        }
        return "";
    }

    private static void status(StatusCallback callback, String message) {
        if (callback != null) callback.onStatus(message);
    }
}
