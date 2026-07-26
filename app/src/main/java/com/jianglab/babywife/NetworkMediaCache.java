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
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        if (requestedSource.isEmpty() || requestedId.isEmpty()) throw new IllegalArgumentException("歌曲目录缺少来源或 ID");

        File root = new File(context.getFilesDir(), "network_music");
        if (!root.exists() && !root.mkdirs()) throw new IllegalStateException("无法创建歌曲缓存目录");

        String requestedKey = sha256(requestedSource + "|" + requestedId);
        File requestedAudio = findExistingAudio(root, requestedKey);
        File requestedLyricFile = new File(root, requestedKey + ".lrc");
        String requestedLyric = readText(requestedLyricFile);
        if (requestedAudio != null && requestedAudio.length() > 0) {
            boolean lyricFromCache = !requestedLyric.trim().isEmpty();
            if (!lyricFromCache) {
                status(callback, "正在按原平台读取歌词...");
                requestedLyric = fetchLyrics(requestedCatalog.toString());
                if (!requestedLyric.trim().isEmpty()) writeTextAtomically(requestedLyricFile, requestedLyric);
            }
            status(callback, "已读取歌曲缓存");
            return new CacheResult(Uri.fromFile(requestedAudio).toString(), requestedLyric, true, lyricFromCache,
                requestedCatalog.toString(), requestedSource, false);
        }

        status(callback, "正在按原平台解析歌曲地址...");
        ResolvedChoice choice;
        Exception primaryError;
        try {
            choice = new ResolvedChoice(requestedCatalog, resolve(requestedCatalog.toString()));
            primaryError = null;
        } catch (Exception error) {
            primaryError = error;
            choice = null;
        }

        if (choice == null || choice.audioUrl().isEmpty()) {
            status(callback, "原来源不可用，正在查找同歌手同名的其他平台版本...");
            choice = findFallback(requestedCatalog, callback);
        }
        if (choice == null || choice.audioUrl().isEmpty()) {
            throw new IllegalStateException("未找到同歌手同名的可播放版本，请手动使用替换歌曲");
        }

        JSONObject actualCatalog = canonicalCatalog(choice.catalog.toString());
        String actualSource = actualCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String actualId = actualCatalog.optString("id", "").trim();
        boolean sourceChanged = !requestedSource.equals(actualSource) || !requestedId.equals(actualId);
        String key = sha256(actualSource + "|" + actualId);
        File lyricFile = new File(root, key + ".lrc");
        String lyric = readText(lyricFile);
        boolean lyricFromCache = !lyric.trim().isEmpty();
        if (!lyricFromCache) {
            status(callback, sourceChanged ? "正在从实际平台读取匹配歌词..." : "正在按原平台读取歌词...");
            lyric = fetchLyrics(actualCatalog.toString());
            if (!lyric.trim().isEmpty()) writeTextAtomically(lyricFile, lyric);
        }

        File existingAudio = findExistingAudio(root, key);
        if (existingAudio != null && existingAudio.length() > 0) {
            status(callback, sourceChanged ? "已切换并读取其他平台缓存" : "歌曲缓存已存在");
            return new CacheResult(Uri.fromFile(existingAudio).toString(), lyric, true, lyricFromCache,
                actualCatalog.toString(), actualSource, sourceChanged);
        }

        String audioUrl = choice.audioUrl();
        String extension = sanitizeExtension(firstNonEmpty(choice.resolved.optString("ext"), extensionFromUrl(audioUrl)));
        File output = new File(root, key + "." + extension);
        File partial = new File(root, key + "." + extension + ".part");
        status(callback, sourceChanged
            ? "原来源不可用，正在从" + CatalogSearch.labelForSource(actualSource) + "缓存歌曲..."
            : "正在缓存歌曲...");
        download(audioUrl, actualSource, partial, callback);
        if (output.exists() && !output.delete()) throw new IllegalStateException("无法替换旧缓存");
        if (!partial.renameTo(output)) {
            copyFile(partial, output);
            if (!partial.delete()) partial.deleteOnExit();
        }
        if (output.length() <= 0) throw new IllegalStateException("歌曲缓存为空");
        status(callback, "歌曲与歌词缓存完成");
        return new CacheResult(Uri.fromFile(output).toString(), lyric, false, lyricFromCache,
            actualCatalog.toString(), actualSource, sourceChanged);
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

    static int clearExcept(Context context, Set<String> keepKeys) {
        if (context == null) return 0;
        File root = new File(context.getFilesDir(), "network_music");
        File[] files = root.listFiles();
        if (files == null) return 0;
        int removed = 0;
        for (File file : files) {
            if (file == null || !file.isFile()) continue;
            String name = file.getName();
            int dot = name.indexOf('.');
            String key = dot > 0 ? name.substring(0, dot) : name;
            if (keepKeys != null && keepKeys.contains(key)) continue;
            if (file.delete()) removed++;
        }
        return removed;
    }

    static boolean cachedAudioExists(Context context, String uriText) {
        if (uriText == null || uriText.trim().isEmpty()) return false;
        try {
            Uri uri = Uri.parse(uriText);
            if (!"file".equalsIgnoreCase(uri.getScheme())) return false;
            File file = new File(uri.getPath());
            return file.exists() && file.length() > 0;
        } catch (Exception ignored) {
            return false;
        }
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
