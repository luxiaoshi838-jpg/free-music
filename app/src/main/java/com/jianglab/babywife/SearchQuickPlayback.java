package com.jianglab.babywife;

import android.content.Context;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

import bridge.Bridge;

/**
 * Lightweight search-result playback path.
 *
 * It resolves only one address at a time, starts streaming before caching, and
 * stores the exact address that actually started playback. Playlist one-click
 * caching continues to use NetworkMediaCache and PlayableAudioResolver.
 */
final class SearchQuickPlayback {
    private static final int CONNECT_TIMEOUT_MS = 12000;
    private static final int READ_TIMEOUT_MS = 30000;
    private static final long MAX_AUDIO_BYTES = 512L * 1024L * 1024L;

    private SearchQuickPlayback() {
    }

    static final class Candidate {
        final String catalogJson;
        final String sourceCode;
        final String sourceLabel;
        final String playbackUrl;
        final String playAuth;
        final String extension;

        Candidate(String catalogJson, String sourceCode, String playbackUrl,
                  String playAuth, String extension) {
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.sourceCode = sourceCode == null ? "" : sourceCode;
            this.sourceLabel = CatalogSearch.labelForSource(this.sourceCode);
            this.playbackUrl = playbackUrl == null ? "" : playbackUrl;
            this.playAuth = playAuth == null ? "" : playAuth;
            this.extension = sanitizeExtension(extension);
        }
    }

    static Candidate resolveStage(String requestedCatalogJson, int stage) throws Exception {
        JSONObject requested = new JSONObject(requestedCatalogJson == null ? "{}" : requestedCatalogJson);
        if (stage == 0) return resolveCatalog(requested);

        String fallbackSource = stage == 1 ? "kuwo" : (stage == 2 ? "netease" : "");
        if (fallbackSource.isEmpty()) return null;
        String currentSource = requested.optString("source", "").trim().toLowerCase(Locale.ROOT);
        if (fallbackSource.equals(currentSource)) return null;

        CatalogSearch.Track alternative = CatalogSearch.findBestExactOnSource(
            fallbackSource,
            requested.optString("name", requested.optString("title", "")),
            requested.optString("artist", requested.optString("singer", ""))
        );
        if (alternative == null) return null;
        return resolveCatalog(new JSONObject(alternative.rawJson));
    }

    private static Candidate resolveCatalog(JSONObject catalog) throws Exception {
        String source = catalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String id = catalog.optString("id", "").trim();
        if (source.isEmpty() || id.isEmpty()) return null;

        JSONObject response = new JSONObject(Bridge.resolve(catalog.toString()));
        if (!response.optBoolean("ok", false)) return null;
        JSONObject data = response.optJSONObject("data");
        if (data == null) return null;
        String rawUrl = data.optString("url", "").trim();
        if (rawUrl.isEmpty()) return null;

        String playAuth = firstNonEmpty(data.optString("play_auth"),
            data.optString("playAuth"), data.optString("PlayAuth"));
        int authMarker = rawUrl.indexOf("#auth=");
        if (authMarker >= 0) {
            if (playAuth.isEmpty()) {
                try {
                    playAuth = java.net.URLDecoder.decode(rawUrl.substring(authMarker + 6), "UTF-8");
                } catch (Exception ignored) {
                    playAuth = rawUrl.substring(authMarker + 6);
                }
            }
            rawUrl = rawUrl.substring(0, authMarker);
        }

        data.put("source", source);
        if (data.optString("id", "").trim().isEmpty()) data.put("id", id);
        copyIfMissing(data, catalog, "name");
        copyIfMissing(data, catalog, "artist");
        copyIfMissing(data, catalog, "album");
        String extension = firstNonEmpty(data.optString("ext"), extensionFromUrl(rawUrl), "audio");
        return new Candidate(data.toString(), source, rawUrl, playAuth, extension);
    }

    static String cache(Context context, Candidate candidate, String title,
                        String artist, String album) throws Exception {
        if (context == null || candidate == null || candidate.playbackUrl.isEmpty()) {
            throw new IllegalArgumentException("搜索歌曲缓存参数无效");
        }
        String key = NetworkMediaCache.cacheKeyForCatalog(candidate.catalogJson);
        if (key.isEmpty()) throw new IllegalStateException("搜索歌曲缓存键无效");

        File tempRoot = new File(context.getCacheDir(), "search_stream_cache");
        if (!tempRoot.exists() && !tempRoot.mkdirs()) {
            throw new IllegalStateException("无法创建搜索歌曲临时缓存目录");
        }
        File partial = new File(tempRoot, key + ".part");
        File decrypted = new File(tempRoot, key + ".decrypted");
        try {
            download(candidate, partial);
            if (!partial.isFile() || partial.length() <= 0) {
                throw new IllegalStateException("搜索歌曲下载文件为空");
            }

            File source = partial;
            if (SodaM4aDecryptor.isEncryptedM4a(partial)) {
                if (candidate.playAuth.isEmpty()) {
                    throw new IllegalStateException("加密 M4A 缺少 PlayAuth");
                }
                SodaM4aDecryptor.decrypt(partial, decrypted, candidate.playAuth);
                source = decrypted;
            }

            AudioPlaybackVerifier.Probe probe = AudioPlaybackVerifier.probeFile(source);
            String extension = detectExtension(source, candidate.extension, probe.mimeType);
            String savedAlbum = album == null ? "" : album.trim();
            if (savedAlbum.isEmpty()) {
                try {
                    savedAlbum = new JSONObject(candidate.catalogJson)
                        .optString("album", "").trim();
                } catch (Exception ignored) {
                }
            }
            String storedUri = CacheStorage.storeAudio(context, key, extension, source,
                title, artist, savedAlbum, candidate.catalogJson);
            if (!CacheStorage.exists(context, storedUri)) {
                CacheStorage.deleteKey(context, key);
                throw new IllegalStateException("搜索歌曲缓存写入后不存在");
            }
            CacheStorage.deleteOtherSongCaches(context, title, artist, key);
            return storedUri;
        } finally {
            if (partial.exists()) partial.delete();
            if (decrypted.exists()) decrypted.delete();
        }
    }

    private static void download(Candidate candidate, File output) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(candidate.playbackUrl).openConnection();
        connection.setInstanceFollowRedirects(true);
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setRequestProperty("User-Agent", "Mozilla/5.0");
        if ("netease".equals(candidate.sourceCode)) {
            connection.setRequestProperty("Referer", "https://music.163.com/");
        } else if ("kuwo".equals(candidate.sourceCode)) {
            connection.setRequestProperty("Referer", "https://www.kuwo.cn/");
        }
        int code = connection.getResponseCode();
        if (code < 200 || code >= 400) {
            connection.disconnect();
            throw new IllegalStateException("音频下载响应异常：HTTP " + code);
        }
        long total = 0L;
        try (InputStream input = new BufferedInputStream(connection.getInputStream());
             OutputStream stream = new BufferedOutputStream(new FileOutputStream(output))) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = input.read(buffer)) >= 0) {
                if (read == 0) continue;
                total += read;
                if (total > MAX_AUDIO_BYTES) {
                    throw new IllegalStateException("音频文件超过缓存大小限制");
                }
                stream.write(buffer, 0, read);
            }
        } finally {
            connection.disconnect();
        }
    }

    private static String detectExtension(File file, String fallback, String mimeType) {
        if (AudioTranscoder.isMp3(file)) return "mp3";
        byte[] header = new byte[96];
        try (InputStream input = new BufferedInputStream(new FileInputStream(file))) {
            int count = input.read(header);
            if (count >= 4) {
                String first4 = new String(header, 0, 4, StandardCharsets.ISO_8859_1);
                if ("fLaC".equals(first4)) return "flac";
                if ("OggS".equals(first4)) return "ogg";
                if ("RIFF".equals(first4) && count >= 12
                    && "WAVE".equals(new String(header, 8, 4, StandardCharsets.ISO_8859_1))) return "wav";
            }
            if (count >= 8 && "ftyp".equals(
                new String(header, 4, 4, StandardCharsets.ISO_8859_1))) return "m4a";
        } catch (Exception ignored) {
        }
        String mime = mimeType == null ? "" : mimeType.toLowerCase(Locale.ROOT);
        if (mime.contains("flac")) return "flac";
        if (mime.contains("mpeg")) return "mp3";
        if (mime.contains("mp4") || mime.contains("m4a")) return "m4a";
        if (mime.contains("ogg")) return "ogg";
        if (mime.contains("wav")) return "wav";
        return sanitizeExtension(fallback);
    }

    private static String extensionFromUrl(String url) {
        if (url == null) return "";
        String clean = url;
        int query = clean.indexOf('?');
        if (query >= 0) clean = clean.substring(0, query);
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

    private static void copyIfMissing(JSONObject target, JSONObject source, String key) {
        if (!target.optString(key, "").trim().isEmpty()) return;
        String value = source.optString(key, "").trim();
        if (!value.isEmpty()) {
            try {
                target.put(key, value);
            } catch (Exception ignored) {
            }
        }
    }

    private static String firstNonEmpty(String... values) {
        if (values == null) return "";
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) return value.trim();
        }
        return "";
    }
}
