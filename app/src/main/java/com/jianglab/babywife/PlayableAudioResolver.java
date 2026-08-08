package com.jianglab.babywife;

import android.content.Context;

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
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import bridge.Bridge;

/** Resolves sources with no format priority and stops at the first candidate that passes real playback validation. */
final class PlayableAudioResolver {
    private static final String[] REQUEST_FORMATS = {""};
    private static final int MAX_CATALOG_CANDIDATES = 8;
    private static final int CONNECT_TIMEOUT_MS = 12000;
    private static final int READ_TIMEOUT_MS = 30000;
    private static final long MAX_AUDIO_BYTES = 512L * 1024L * 1024L;

    private PlayableAudioResolver() {
    }

    static final class Result {
        final String catalogJson;
        final String audioUri;
        final boolean fromCache;

        Result(String catalogJson, String audioUri, boolean fromCache) {
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.audioUri = audioUri == null ? "" : audioUri;
            this.fromCache = fromCache;
        }
    }

    private static final class Candidate {
        final JSONObject catalog;
        final String extension;
        final String mimeType;

        Candidate(JSONObject catalog, String extension, String mimeType) {
            this.catalog = catalog;
            this.extension = extension;
            this.mimeType = mimeType == null ? "" : mimeType;
        }
    }

    private static final class Address {
        final String url;
        final String playAuth;

        Address(String url, String playAuth) {
            this.url = url == null ? "" : url.trim();
            this.playAuth = playAuth == null ? "" : playAuth.trim();
        }

        static Address parse(String rawUrl, String explicitAuth) {
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
            return new Address(raw, auth);
        }
    }

    static Result prepare(Context context, JSONObject requestedCatalog,
                          NetworkMediaCache.StatusCallback callback) throws Exception {
        if (context == null || requestedCatalog == null) {
            throw new IllegalArgumentException("歌曲解析参数无效");
        }
        List<JSONObject> catalogs = candidateCatalogs(requestedCatalog);
        File tempRoot = new File(context.getCacheDir(), "network_download");
        if (!tempRoot.exists() && !tempRoot.mkdirs()) {
            throw new IllegalStateException("无法创建下载临时目录");
        }

        String requestedKey = cacheKey(requestedCatalog);
        File bestFile = new File(tempRoot, requestedKey + ".best.ready");
        File mp3Ready = new File(tempRoot, requestedKey + ".mp3.ready");
        Candidate best = null;
        Set<String> attemptedAddresses = new HashSet<>();
        Exception lastError = null;
        int attempt = 0;

        try {
            outer:
            for (String requestedFormat : REQUEST_FORMATS) {
                String formatLabel = "自动格式";
                status(callback, "正在按来源顺序寻找第一个可播放资源...");

                for (JSONObject catalog : catalogs) {
                    String source = source(catalog);
                    String id = catalog.optString("id", "").trim();
                    if (source.isEmpty() || id.isEmpty()) continue;
                    JSONObject resolved;
                    try {
                        resolved = resolveForFormat(catalog, requestedFormat);
                    } catch (Exception error) {
                        lastError = error;
                        continue;
                    }

                    Address address = Address.parse(resolved.optString("url", ""),
                        firstNonEmpty(resolved.optString("play_auth"),
                            resolved.optString("playAuth"), resolved.optString("PlayAuth")));
                    if (address.url.isEmpty()) continue;
                    if (!attemptedAddresses.add(address.url + "#auth=" + address.playAuth)) continue;

                    attempt++;
                    String hintedExtension = sanitizeExtension(firstNonEmpty(
                        resolved.optString("ext"), extensionFromUrl(address.url),
                        requestedFormat, "audio"));
                    File partial = new File(tempRoot, requestedKey + ".try" + attempt + ".part");
                    File decrypted = new File(tempRoot, requestedKey + ".try" + attempt + ".decrypted");
                    try {
                        status(callback, "正在下载候选：" + CatalogSearch.labelForSource(source)
                            + " / " + formatLabel + "（尚未写入正式缓存）");
                        download(address.url, source, partial, callback);
                        if (partial.length() <= 0) {
                            throw new IllegalStateException("歌曲候选文件为空");
                        }

                        File decodedSource = partial;
                        if (SodaM4aDecryptor.isEncryptedM4a(partial)) {
                            if (address.playAuth.isEmpty()) {
                                throw new IllegalStateException("加密 M4A 缺少 PlayAuth");
                            }
                            status(callback, "正在解密 M4A 音频...");
                            SodaM4aDecryptor.decrypt(partial, decrypted, address.playAuth);
                            decodedSource = decrypted;
                        }

                        AudioPlaybackVerifier.Probe probe = AudioPlaybackVerifier.probeFile(decodedSource);
                        if (probe.durationMs <= 60_000L) {
                            throw new IllegalStateException("候选实际时长不超过60秒");
                        }
                        String actualExtension = detectAudioExtension(decodedSource,
                            hintedExtension, probe.mimeType);
                        status(callback, "候选可播放：" + displayFormat(actualExtension)
                            + "（" + Math.max(0L, probe.durationMs / 1000L) + " 秒），立即使用");

                        if (bestFile.exists() && !bestFile.delete()) {
                            throw new IllegalStateException("无法保存已通过校验的候选");
                        }
                        copyFile(decodedSource, bestFile);
                        best = new Candidate(new JSONObject(catalog.toString()),
                            actualExtension, probe.mimeType);
                        break outer;
                    } catch (Exception error) {
                        lastError = error;
                        status(callback, "候选不可播放，临时文件已删除；继续下一格式或来源");
                    } finally {
                        if (partial.exists()) partial.delete();
                        if (decrypted.exists()) decrypted.delete();
                    }
                }
            }

            if (best == null || !bestFile.isFile() || bestFile.length() <= 0) {
                String detail = lastError == null || lastError.getMessage() == null
                    ? "没有返回可用音频" : lastError.getMessage();
                throw new IllegalStateException("未找到能实际播放的音频文件：" + detail);
            }

            JSONObject catalog = canonicalCatalog(best.catalog.toString());
            String source = source(catalog);
            String id = catalog.optString("id", "").trim();
            String key = sha256(source + "|" + id);
            String title = title(requestedCatalog);
            String artist = artist(requestedCatalog);
            String album = firstNonEmpty(album(requestedCatalog), album(catalog));
            File cacheSource = bestFile;

            if ("mp3".equals(best.extension)) {
                AudioTranscoder.ensureMp3(bestFile, mp3Ready);
                AudioMetadataWriter.applyAndVerify(mp3Ready, title, artist, album);
                AudioPlaybackVerifier.probeFile(mp3Ready);
                cacheSource = mp3Ready;
            }

            status(callback, "已找到第一个可播放资源：" + displayFormat(best.extension)
                + "，正在写入唯一正式缓存");
            String storedUri = CacheStorage.storeAudio(context, key, best.extension, cacheSource,
                title, artist, album, catalog.toString());
            if (!CacheStorage.exists(context, storedUri)
                || SodaM4aDecryptor.isEncryptedM4a(context, storedUri)) {
                CacheStorage.deleteKey(context, key);
                throw new IllegalStateException("文件写入缓存后不存在或仍为加密内容，已自动删除");
            }
            status(callback, "唯一正式缓存写入完成，所有临时候选已清理");
            return new Result(catalog.toString(), storedUri, false);
        } finally {
            if (bestFile.exists()) bestFile.delete();
            if (mp3Ready.exists()) mp3Ready.delete();
        }
    }

    static boolean cachedAudioExists(Context context, String uriText) {
        // Cache completion is a storage-state check. The bytes were already decrypted
        // and probed before CacheStorage.storeAudio(). Re-preparing a content:// URI
        // here causes false negatives on document providers that still play the file.
        return CacheStorage.exists(context, uriText)
            && !SodaM4aDecryptor.isEncryptedM4a(context, uriText);
    }

    private static List<JSONObject> candidateCatalogs(JSONObject requestedCatalog) {
        List<JSONObject> catalogs = new ArrayList<>();
        Set<String> identities = new HashSet<>();
        addCatalog(catalogs, identities, requestedCatalog);
        try {
            for (CatalogSearch.Track alternative :
                CatalogSearch.findExactAlternatives(requestedCatalog.toString())) {
                if (catalogs.size() >= MAX_CATALOG_CANDIDATES) break;
                addCatalog(catalogs, identities, canonicalCatalog(alternative.rawJson));
            }
        } catch (Exception ignored) {
        }
        return catalogs;
    }

    private static void addCatalog(List<JSONObject> catalogs, Set<String> identities,
                                   JSONObject catalog) {
        if (catalog == null) return;
        String source = source(catalog);
        String id = catalog.optString("id", "").trim();
        if (source.isEmpty() || id.isEmpty() || !identities.add(source + "|" + id)) return;
        try {
            catalogs.add(new JSONObject(catalog.toString()));
        } catch (Exception ignored) {
        }
    }

    private static JSONObject resolveForFormat(JSONObject catalog, String format) throws Exception {
        JSONObject request = new JSONObject(catalog.toString());
        String wanted = format == null ? "" : format.trim().toLowerCase(Locale.ROOT);
        if (!wanted.isEmpty()) {
            request.put("format", wanted);
            request.put("ext", wanted);
            if ("mp3".equals(wanted)) {
                request.put("quality", "320k");
                request.put("br", 320000);
            } else if ("flac".equals(wanted)) {
                request.put("quality", "lossless");
            } else if ("m4a".equals(wanted)) {
                request.put("quality", "high");
            }
        }
        JSONObject response = new JSONObject(Bridge.resolve(request.toString()));
        if (!response.optBoolean("ok", false)) {
            throw new IllegalStateException(response.optString("error", "歌曲解析失败"));
        }
        JSONObject data = response.optJSONObject("data");
        if (data == null || data.optString("url", "").trim().isEmpty()) {
            throw new IllegalStateException("歌曲解析结果没有音频地址");
        }
        return data;
    }

    private static JSONObject canonicalCatalog(String raw) throws Exception {
        JSONObject catalog = new JSONObject(raw == null ? "{}" : raw);
        catalog.put("source", source(catalog));
        return catalog;
    }

    private static String cacheKey(JSONObject catalog) throws Exception {
        return sha256(source(catalog) + "|" + catalog.optString("id", "").trim());
    }

    private static String source(JSONObject catalog) {
        return catalog == null ? "" : catalog.optString("source", "")
            .trim().toLowerCase(Locale.ROOT);
    }

    private static String title(JSONObject catalog) {
        return firstNonEmpty(catalog.optString("name"), catalog.optString("title"), "未知歌曲");
    }

    private static String artist(JSONObject catalog) {
        return firstNonEmpty(catalog.optString("artist"), catalog.optString("singer"), "未知歌手");
    }

    private static String album(JSONObject catalog) {
        return firstNonEmpty(catalog.optString("album"), catalog.optString("albumName"), "未知专辑");
    }

    private static String displayFormat(String extension) {
        String value = sanitizeExtension(extension);
        return value.isEmpty() ? "其他格式" : value.toUpperCase(Locale.ROOT);
    }

    private static String extensionFromUrl(String url) {
        if (url == null) return "";
        String clean = url;
        int query = clean.indexOf('?');
        if (query >= 0) clean = clean.substring(0, query);
        int fragment = clean.indexOf('#');
        if (fragment >= 0) clean = clean.substring(0, fragment);
        int slash = clean.lastIndexOf('/');
        int dot = clean.lastIndexOf('.');
        return dot > slash ? clean.substring(dot + 1) : "";
    }

    private static String sanitizeExtension(String value) {
        String extension = value == null ? "" : value.toLowerCase(Locale.ROOT)
            .replaceAll("[^a-z0-9]", "");
        if (extension.isEmpty()) return "audio";
        return extension.length() > 12 ? extension.substring(0, 12) : extension;
    }

    private static String detectAudioExtension(File file, String fallback, String mimeType) {
        if (AudioTranscoder.isMp3(file)) return "mp3";
        byte[] header = new byte[96];
        try (InputStream input = new BufferedInputStream(new FileInputStream(file))) {
            int count = input.read(header);
            if (count >= 4) {
                String first4 = new String(header, 0, 4, StandardCharsets.ISO_8859_1);
                if ("fLaC".equals(first4)) return "flac";
                if ("OggS".equals(first4)) {
                    String probe = new String(header, 0, count, StandardCharsets.ISO_8859_1);
                    return probe.contains("OpusHead") ? "opus" : "ogg";
                }
                if ("RIFF".equals(first4) && count >= 12
                    && "WAVE".equals(new String(header, 8, 4, StandardCharsets.ISO_8859_1))) return "wav";
                if ("MThd".equals(first4)) return "mid";
                if ("FORM".equals(first4) && count >= 12) return "aiff";
            }
            if (count >= 8 && "ftyp".equals(
                new String(header, 4, 4, StandardCharsets.ISO_8859_1))) return "m4a";
            if (count >= 4 && (header[0] & 0xff) == 0x1a && (header[1] & 0xff) == 0x45
                && (header[2] & 0xff) == 0xdf && (header[3] & 0xff) == 0xa3) return "webm";
            if (count >= 6 && new String(header, 0, 6,
                StandardCharsets.ISO_8859_1).startsWith("#!AMR")) return "amr";
            if (count >= 2 && (header[0] & 0xff) == 0xff
                && ((header[1] & 0xf6) == 0xf0)) return "aac";
            if (count >= 4 && (header[0] & 0xff) == 0x30 && (header[1] & 0xff) == 0x26
                && (header[2] & 0xff) == 0xb2 && (header[3] & 0xff) == 0x75) return "wma";
        } catch (Exception ignored) {
        }
        String mimeExtension = extensionForMime(mimeType);
        return mimeExtension.isEmpty() ? sanitizeExtension(fallback) : mimeExtension;
    }

    private static String extensionForMime(String mimeType) {
        String mime = mimeType == null ? "" : mimeType.toLowerCase(Locale.ROOT);
        if (mime.contains("flac")) return "flac";
        if (mime.contains("mpeg")) return "mp3";
        if (mime.contains("mp4") || mime.contains("alac")) return "m4a";
        if (mime.contains("opus")) return "opus";
        if (mime.contains("ogg") || mime.contains("vorbis")) return "ogg";
        if (mime.contains("wav")) return "wav";
        if (mime.contains("webm")) return "webm";
        if (mime.contains("aac")) return "aac";
        if (mime.contains("amr")) return "amr";
        if (mime.contains("midi")) return "mid";
        if (mime.contains("wma")) return "wma";
        if (mime.contains("eac3")) return "eac3";
        if (mime.contains("ac3")) return "ac3";
        return "";
    }

    private static void download(String urlText, String source, File partial,
                                 NetworkMediaCache.StatusCallback callback) throws Exception {
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
            long written = 0;
            int lastPercent = -1;
            try (InputStream input = new BufferedInputStream(connection.getInputStream());
                 BufferedOutputStream output = new BufferedOutputStream(new FileOutputStream(partial))) {
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = input.read(buffer)) >= 0) {
                    if (count == 0) continue;
                    written += count;
                    if (written > MAX_AUDIO_BYTES) {
                        throw new IllegalStateException("歌曲文件超过缓存上限");
                    }
                    output.write(buffer, 0, count);
                    if (total > 0) {
                        int percent = (int) Math.min(100, written * 100 / total);
                        if (percent >= lastPercent + 10) {
                            lastPercent = percent;
                            status(callback, "候选下载进度：" + percent + "%");
                        }
                    }
                }
            }
            if (written <= 0) throw new IllegalStateException("没有下载到音频内容");
        } finally {
            connection.disconnect();
        }
    }

    private static void copyFile(File source, File target) throws Exception {
        try (InputStream input = new BufferedInputStream(new FileInputStream(source));
             BufferedOutputStream output = new BufferedOutputStream(new FileOutputStream(target))) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) >= 0) {
                if (count > 0) output.write(buffer, 0, count);
            }
        }
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
        for (byte item : bytes) {
            builder.append(String.format(Locale.ROOT, "%02x", item & 0xff));
        }
        return builder.toString();
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) return value.trim();
        }
        return "";
    }

    private static void status(NetworkMediaCache.StatusCallback callback, String message) {
        if (callback != null) callback.onStatus(message);
    }
}
