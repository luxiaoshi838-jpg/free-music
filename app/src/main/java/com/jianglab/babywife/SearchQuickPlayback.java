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
 * stores the exact song after resolving a separate address for background
 * download. The background downloader uses HTTP byte ranges, matching the way
 * Android's MediaPlayer reads many signed CDN audio URLs.
 */
final class SearchQuickPlayback {
    private static final int CONNECT_TIMEOUT_MS = 12000;
    private static final int READ_TIMEOUT_MS = 30000;
    private static final int DOWNLOAD_ATTEMPTS = 3;
    private static final int MAX_REDIRECTS = 8;
    private static final long DOWNLOAD_RETRY_DELAY_MS = 320L;
    private static final long RANGE_CHUNK_BYTES = 4L * 1024L * 1024L;
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

    private static final class RangeResponse {
        final HttpURLConnection connection;
        final URL finalUrl;
        final int statusCode;
        final long contentLength;
        final String contentRange;

        RangeResponse(HttpURLConnection connection, URL finalUrl, int statusCode,
                      long contentLength, String contentRange) {
            this.connection = connection;
            this.finalUrl = finalUrl;
            this.statusCode = statusCode;
            this.contentLength = contentLength;
            this.contentRange = contentRange == null ? "" : contentRange.trim();
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

    static String cache(Context context, Candidate playbackCandidate, String title,
                        String artist, String album) throws Exception {
        if (context == null || playbackCandidate == null || playbackCandidate.playbackUrl.isEmpty()) {
            throw new IllegalArgumentException("搜索歌曲缓存参数无效");
        }
        String key = NetworkMediaCache.cacheKeyForCatalog(playbackCandidate.catalogJson);
        if (key.isEmpty()) throw new IllegalStateException("搜索歌曲缓存键无效");

        File tempRoot = new File(context.getCacheDir(), "search_stream_cache");
        if (!tempRoot.exists() && !tempRoot.mkdirs()) {
            throw new IllegalStateException("无法创建搜索歌曲临时缓存目录");
        }
        File partial = new File(tempRoot, key + ".part");
        File decrypted = new File(tempRoot, key + ".decrypted");
        try {
            throwIfInterrupted();
            Candidate downloadCandidate = downloadWithFreshAddress(playbackCandidate, partial);
            throwIfInterrupted();

            File source = partial;
            if (SodaM4aDecryptor.isEncryptedM4a(partial)) {
                if (downloadCandidate.playAuth.isEmpty()) {
                    throw new IllegalStateException("加密 M4A 缺少 PlayAuth");
                }
                SodaM4aDecryptor.decrypt(partial, decrypted, downloadCandidate.playAuth);
                source = decrypted;
            }

            throwIfInterrupted();
            AudioPlaybackVerifier.Probe probe = AudioPlaybackVerifier.probeFile(source);
            String extension = detectExtension(source, downloadCandidate.extension, probe.mimeType);
            String savedAlbum = album == null ? "" : album.trim();
            if (savedAlbum.isEmpty()) {
                try {
                    savedAlbum = new JSONObject(downloadCandidate.catalogJson)
                        .optString("album", "").trim();
                } catch (Exception ignored) {
                }
            }
            throwIfInterrupted();
            String storedUri = CacheStorage.storeAudio(context, key, extension, source,
                title, artist, savedAlbum, downloadCandidate.catalogJson);
            if (!CacheFileState.exists(context, storedUri)) {
                CacheFileState.deleteDirect(context, storedUri);
                CacheStorage.deleteKey(context, key);
                throw new IllegalStateException("搜索歌曲缓存写入后无法读取");
            }
            if (SodaM4aDecryptor.isEncryptedM4a(context, storedUri)) {
                CacheFileState.deleteDirect(context, storedUri);
                CacheStorage.deleteKey(context, key);
                throw new IllegalStateException("搜索歌曲缓存写入后仍为加密内容");
            }
            CacheStorage.deleteOtherSongCaches(context, title, artist, key);
            return storedUri;
        } finally {
            if (partial.exists()) partial.delete();
            if (decrypted.exists()) decrypted.delete();
        }
    }

    private static Candidate downloadWithFreshAddress(Candidate playbackCandidate,
                                                       File output) throws Exception {
        Exception lastError = null;
        for (int attempt = 0; attempt < DOWNLOAD_ATTEMPTS; attempt++) {
            throwIfInterrupted();
            Candidate downloadCandidate;
            try {
                downloadCandidate = resolveFreshCandidate(playbackCandidate);
            } catch (Exception resolveError) {
                lastError = resolveError;
                downloadCandidate = playbackCandidate;
            }
            if (output.exists() && !output.delete()) {
                throw new IllegalStateException("无法重置搜索歌曲临时文件");
            }
            try {
                downloadByRanges(downloadCandidate, output);
                if (output.isFile() && output.length() > 0) return downloadCandidate;
                lastError = new IllegalStateException("Range 下载完成但临时文件仍为空");
            } catch (Exception error) {
                lastError = error;
            }
            if (output.exists()) output.delete();
            if (attempt + 1 < DOWNLOAD_ATTEMPTS) {
                try {
                    Thread.sleep(DOWNLOAD_RETRY_DELAY_MS);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("搜索歌曲后台缓存已中断", interrupted);
                }
            }
        }
        String detail = lastError == null || lastError.getMessage() == null
            ? "Range 分段下载没有收到音频内容" : lastError.getMessage();
        throw new IllegalStateException("搜索歌曲后台下载失败：" + detail, lastError);
    }

    private static Candidate resolveFreshCandidate(Candidate playbackCandidate) throws Exception {
        Candidate refreshed = resolveCatalog(new JSONObject(playbackCandidate.catalogJson));
        if (refreshed == null || refreshed.playbackUrl.isEmpty()) {
            throw new IllegalStateException("重新解析没有返回下载地址");
        }
        return refreshed;
    }

    private static void downloadByRanges(Candidate candidate, File output) throws Exception {
        long writtenTotal = 0L;
        long expectedTotal = -1L;
        boolean complete = false;
        int segment = 0;

        try (OutputStream stream = new BufferedOutputStream(new FileOutputStream(output, false))) {
            while (!complete) {
                throwIfInterrupted();
                if (writtenTotal >= MAX_AUDIO_BYTES) {
                    throw new IllegalStateException("音频文件超过缓存大小限制");
                }
                long rangeEnd = Math.min(MAX_AUDIO_BYTES - 1L,
                    writtenTotal + RANGE_CHUNK_BYTES - 1L);
                RangeResponse response = openRange(candidate, writtenTotal, rangeEnd);
                long segmentBytes = 0L;
                try {
                    if (response.statusCode != HttpURLConnection.HTTP_OK
                        && response.statusCode != HttpURLConnection.HTTP_PARTIAL) {
                        throw new IllegalStateException(downloadDiagnostic(response, writtenTotal,
                            "HTTP 状态不可下载"));
                    }
                    if (response.statusCode == HttpURLConnection.HTTP_OK && writtenTotal > 0L) {
                        throw new IllegalStateException(downloadDiagnostic(response, writtenTotal,
                            "后续分段被服务器改为完整响应"));
                    }
                    long rangeTotal = parseContentRangeTotal(response.contentRange);
                    if (rangeTotal > 0L) expectedTotal = rangeTotal;
                    if (expectedTotal > MAX_AUDIO_BYTES) {
                        throw new IllegalStateException("音频文件超过缓存大小限制");
                    }

                    try (InputStream input = new BufferedInputStream(
                        response.connection.getInputStream())) {
                        byte[] buffer = new byte[64 * 1024];
                        int read;
                        while ((read = input.read(buffer)) >= 0) {
                            throwIfInterrupted();
                            if (read == 0) continue;
                            segmentBytes += read;
                            writtenTotal += read;
                            if (writtenTotal > MAX_AUDIO_BYTES) {
                                throw new IllegalStateException("音频文件超过缓存大小限制");
                            }
                            stream.write(buffer, 0, read);
                        }
                    }

                    if (segmentBytes <= 0L) {
                        throw new IllegalStateException(downloadDiagnostic(response, writtenTotal,
                            "Range 响应正文为 0 字节"));
                    }
                    segment++;
                    if (response.statusCode == HttpURLConnection.HTTP_OK) {
                        complete = true;
                    } else if (expectedTotal > 0L && writtenTotal >= expectedTotal) {
                        complete = true;
                    } else if (segmentBytes < RANGE_CHUNK_BYTES) {
                        complete = true;
                    } else if (segment > 160) {
                        throw new IllegalStateException("Range 分段数量异常，已停止下载");
                    }
                } finally {
                    response.connection.disconnect();
                }
            }
            stream.flush();
        }

        if (!complete || writtenTotal <= 0L || !output.isFile() || output.length() <= 0L) {
            throw new IllegalStateException("Range 分段下载未生成音频文件");
        }
    }

    private static RangeResponse openRange(Candidate candidate, long start,
                                           long end) throws Exception {
        URL current = new URL(candidate.playbackUrl);
        for (int redirect = 0; redirect <= MAX_REDIRECTS; redirect++) {
            throwIfInterrupted();
            HttpURLConnection connection = (HttpURLConnection) current.openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setUseCaches(false);
            connection.setRequestMethod("GET");
            connection.setRequestProperty("User-Agent", userAgent(candidate.sourceCode));
            connection.setRequestProperty("Accept", "audio/*,application/octet-stream;q=0.9,*/*;q=0.1");
            connection.setRequestProperty("Accept-Encoding", "identity");
            connection.setRequestProperty("Connection", "keep-alive");
            connection.setRequestProperty("Range", "bytes=" + start + "-" + end);
            String referer = referer(candidate.sourceCode);
            if (!referer.isEmpty()) connection.setRequestProperty("Referer", referer);

            int code = connection.getResponseCode();
            if (code >= 300 && code < 400) {
                String location = connection.getHeaderField("Location");
                connection.disconnect();
                if (location == null || location.trim().isEmpty()) {
                    throw new IllegalStateException("音频重定向没有 Location");
                }
                current = new URL(current, location.trim());
                continue;
            }
            return new RangeResponse(connection, current, code,
                connection.getContentLengthLong(), connection.getHeaderField("Content-Range"));
        }
        throw new IllegalStateException("音频重定向次数过多");
    }

    private static void throwIfInterrupted() {
        if (Thread.currentThread().isInterrupted()) {
            throw new IllegalStateException("搜索歌曲后台缓存已取消");
        }
    }

    private static long parseContentRangeTotal(String value) {
        if (value == null) return -1L;
        int slash = value.lastIndexOf('/');
        if (slash < 0 || slash + 1 >= value.length()) return -1L;
        String total = value.substring(slash + 1).trim();
        if (total.isEmpty() || "*".equals(total)) return -1L;
        try {
            return Long.parseLong(total);
        } catch (Exception ignored) {
            return -1L;
        }
    }

    private static String downloadDiagnostic(RangeResponse response, long written,
                                             String reason) {
        String range = response.contentRange.isEmpty() ? "无" : response.contentRange;
        return reason + "：HTTP " + response.statusCode
            + "，Content-Length=" + response.contentLength
            + "，Content-Range=" + range
            + "，已写入=" + written + " 字节";
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
