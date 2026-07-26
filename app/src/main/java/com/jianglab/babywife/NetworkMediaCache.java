package com.jianglab.babywife;

import android.content.Context;
import android.net.Uri;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import java.util.Locale;

import bridge.Bridge;

/** Downloads selected tracks and routes persistent or transient files through CacheStorage. */
final class NetworkMediaCache {
    private static final int CONNECT_TIMEOUT_MS = 12000;
    private static final int READ_TIMEOUT_MS = 30000;
    private static final long MAX_AUDIO_BYTES = 512L * 1024L * 1024L;

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
        final String cacheFolder;

        CacheResult(String audioUri, String lyric, boolean audioFromCache, boolean lyricFromCache,
                    String catalogJson, String sourceCode, boolean sourceChanged, String cacheFolder) {
            this.audioUri = audioUri == null ? "" : audioUri;
            this.lyric = lyric == null ? "" : lyric;
            this.audioFromCache = audioFromCache;
            this.lyricFromCache = lyricFromCache;
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.sourceCode = sourceCode == null ? "" : sourceCode;
            this.sourceChanged = sourceChanged;
            this.cacheFolder = cacheFolder == null ? CacheStorage.TRANSIENT_FOLDER : cacheFolder;
        }
    }

    static CacheResult cache(Context context, String catalogJson, boolean persist,
                             StatusCallback callback) throws Exception {
        return cache(context, catalogJson, CacheStorage.TRANSIENT_FOLDER, false, callback);
    }

    static CacheResult cache(Context context, String catalogJson, StatusCallback callback) throws Exception {
        return cache(context, catalogJson, CacheStorage.TRANSIENT_FOLDER, false, callback);
    }

    /**
     * @param preferredFolder playlist folder or 缓存
     * @param fallbackToTransient when the original source fails, place the replacement in 缓存
     */
    static CacheResult cache(Context context, String catalogJson, String preferredFolder,
                             boolean fallbackToTransient, StatusCallback callback) throws Exception {
        if (context == null) throw new IllegalArgumentException("context is required");
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        if (requestedSource.isEmpty() || requestedId.isEmpty()) throw new IllegalArgumentException("歌曲目录缺少来源或 ID");

        String requestedFolder = CacheStorage.sanitizeFolderName(preferredFolder);
        String requestedKey = sha256(requestedSource + "|" + requestedId);
        CacheStorage.Entry requestedAudio = CacheStorage.findAudio(context, requestedFolder, requestedKey);
        String requestedLyric = CacheStorage.readText(context, requestedFolder, requestedKey + ".lrc");
        if (requestedAudio != null && requestedAudio.size > 0) {
            boolean lyricFromCache = !requestedLyric.trim().isEmpty();
            if (!lyricFromCache) {
                status(callback, "正在按原平台读取歌词...");
                requestedLyric = fetchLyrics(requestedCatalog.toString());
                if (!requestedLyric.trim().isEmpty()) {
                    CacheStorage.writeText(context, requestedFolder, requestedKey + ".lrc", requestedLyric);
                }
            }
            status(callback, "已读取歌曲缓存");
            return new CacheResult(requestedAudio.uri.toString(), requestedLyric, true, lyricFromCache,
                requestedCatalog.toString(), requestedSource, false, requestedFolder);
        }

        status(callback, "正在按原平台解析歌曲地址...");
        ResolvedChoice choice;
        try {
            choice = new ResolvedChoice(requestedCatalog, resolve(requestedCatalog.toString()));
        } catch (Exception error) {
            choice = null;
        }

        if (choice == null || choice.audioUrl().isEmpty()) {
            status(callback, "原来源不可用，正在查找相似的可播放版本...");
            choice = findFallback(requestedCatalog, callback);
        }
        if (choice == null || choice.audioUrl().isEmpty()) {
            throw new IllegalStateException("未找到可播放版本，请手动使用替换歌曲");
        }

        JSONObject actualCatalog = canonicalCatalog(choice.catalog.toString());
        String actualSource = actualCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String actualId = actualCatalog.optString("id", "").trim();
        boolean sourceChanged = !requestedSource.equals(actualSource) || !requestedId.equals(actualId);
        String actualFolder = sourceChanged && fallbackToTransient
            ? CacheStorage.TRANSIENT_FOLDER : requestedFolder;
        String key = sha256(actualSource + "|" + actualId);
        String lyric = CacheStorage.readText(context, actualFolder, key + ".lrc");
        boolean lyricFromCache = !lyric.trim().isEmpty();
        if (!lyricFromCache) {
            status(callback, sourceChanged ? "正在从实际平台读取匹配歌词..." : "正在按原平台读取歌词...");
            lyric = fetchLyrics(actualCatalog.toString());
            if (!lyric.trim().isEmpty()) {
                CacheStorage.writeText(context, actualFolder, key + ".lrc", lyric);
            }
        }

        CacheStorage.Entry existingAudio = CacheStorage.findAudio(context, actualFolder, key);
        if (existingAudio != null && existingAudio.size > 0) {
            status(callback, sourceChanged ? "已切换并读取其他平台缓存" : "歌曲缓存已存在");
            return new CacheResult(existingAudio.uri.toString(), lyric, true, lyricFromCache,
                actualCatalog.toString(), actualSource, sourceChanged, actualFolder);
        }

        String audioUrl = choice.audioUrl();
        String extension = sanitizeExtension(firstNonEmpty(choice.resolved.optString("ext"), extensionFromUrl(audioUrl)));
        status(callback, sourceChanged
            ? "原来源不可用，正在从" + CatalogSearch.labelForSource(actualSource) + "缓存歌曲..."
            : "正在缓存歌曲...");
        Uri output = download(context, audioUrl, actualSource, actualFolder, key, extension, callback);
        if (output == null || !CacheStorage.uriExists(context, output.toString())) {
            throw new IllegalStateException("歌曲缓存为空");
        }
        status(callback, "歌曲与歌词缓存完成");
        return new CacheResult(output.toString(), lyric, false, lyricFromCache,
            actualCatalog.toString(), actualSource, sourceChanged, actualFolder);
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
        List<CatalogSearch.Track> alternatives = CatalogSearch.findPlayableAlternatives(requestedCatalog.toString());
        for (CatalogSearch.Track alternative : alternatives) {
            try {
                JSONObject catalog = canonicalCatalog(alternative.rawJson);
                JSONObject resolved = resolve(catalog.toString());
                ResolvedChoice choice = new ResolvedChoice(catalog, resolved);
                if (!choice.audioUrl().isEmpty() && probeAudio(choice.audioUrl(), alternative.sourceCode)) {
                    status(callback, "已匹配到" + CatalogSearch.labelForSource(alternative.sourceCode) + "的可播放版本");
                    return choice;
                }
            } catch (Exception ignored) {
            }
        }
        return null;
    }

    static boolean canResolveCatalog(String catalogJson) {
        try {
            JSONObject catalog = canonicalCatalog(catalogJson);
            JSONObject resolved = resolve(catalog.toString());
            String url = resolved.optString("url", "").trim();
            return !url.isEmpty() && probeAudio(url, catalog.optString("source", ""));
        } catch (Exception ignored) {
            return false;
        }
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

    static String promoteToPlaylist(Context context, String catalogJson, String playlistName) {
        String key = cacheKeyForCatalog(catalogJson);
        if (key.isEmpty()) return "";
        return CacheStorage.promoteFromTransient(context, key, playlistName);
    }

    static int clearTransient(Context context) {
        return CacheStorage.clearFolder(context, CacheStorage.TRANSIENT_FOLDER);
    }

    static boolean cachedAudioExists(Context context, String uriText) {
        return CacheStorage.uriExists(context, uriText);
    }

    private static JSONObject resolve(String catalogJson) throws Exception {
        JSONObject response = new JSONObject(Bridge.resolve(catalogJson));
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

    private static Uri download(Context context, String urlText, String source, String folder,
                                String key, String extension, StatusCallback callback) throws Exception {
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
            if (statusCode < 200 || statusCode >= 400) {
                throw new IllegalStateException("音频下载失败：HTTP " + statusCode);
            }
            long total = connection.getContentLengthLong();
            if (total > MAX_AUDIO_BYTES) throw new IllegalStateException("歌曲文件超过缓存上限");
            final int[] lastPercent = {-1};
            try (InputStream input = new BufferedInputStream(connection.getInputStream())) {
                return CacheStorage.writeAudio(context, folder, key, extension, input, total, MAX_AUDIO_BYTES,
                    (written, expected) -> {
                        if (expected <= 0) return;
                        int percent = (int) Math.min(100, written * 100 / expected);
                        if (percent >= lastPercent[0] + 10) {
                            lastPercent[0] = percent;
                            status(callback, "正在缓存歌曲：" + percent + "%");
                        }
                    });
            }
        } finally {
            connection.disconnect();
        }
    }

    private static boolean probeAudio(String urlText, String source) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(urlText).openConnection();
            connection.setConnectTimeout(8000);
            connection.setReadTimeout(8000);
            connection.setInstanceFollowRedirects(true);
            connection.setRequestProperty("User-Agent", userAgent(source));
            connection.setRequestProperty("Range", "bytes=0-1023");
            connection.setRequestProperty("Accept-Encoding", "identity");
            String referer = referer(source);
            if (!referer.isEmpty()) connection.setRequestProperty("Referer", referer);
            int code = connection.getResponseCode();
            if (code < 200 || code >= 400) return false;
            String type = connection.getContentType();
            if (type != null) {
                String lower = type.toLowerCase(Locale.ROOT);
                if (lower.contains("json") || lower.contains("html") || lower.contains("text/plain")) return false;
            }
            try (InputStream input = connection.getInputStream()) {
                byte[] head = new byte[32];
                int count = input.read(head);
                if (count <= 0) return false;
                String prefix = new String(head, 0, Math.min(count, 16), StandardCharsets.UTF_8).trim();
                return !(prefix.startsWith("{") || prefix.startsWith("[") || prefix.startsWith("<"));
            }
        } catch (Exception ignored) {
            return false;
        } finally {
            if (connection != null) connection.disconnect();
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
