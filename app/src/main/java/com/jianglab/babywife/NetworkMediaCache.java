package com.jianglab.babywife;

import android.content.Context;
import android.media.MediaMetadataRetriever;
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
import java.util.concurrent.atomic.AtomicInteger;

import bridge.Bridge;

/** Downloads only tracks the user actually selects and keeps their source metadata. */
final class NetworkMediaCache {
    private static final int CONNECT_TIMEOUT_MS = 12000;
    private static final int READ_TIMEOUT_MS = 30000;
    private static final long MAX_AUDIO_BYTES = 512L * 1024L * 1024L;
    private static final long MIN_AUTOMATIC_DURATION_MS = 60_000L;
    private static final int MAX_FALLBACK_ATTEMPTS = 4;
    private static final String PRIORITY_FOLDER = "network_cache_priority";
    private static final String FOREGROUND_LEASE_NAME = "foreground.lease";
    private static final long FOREGROUND_LEASE_VALID_MS = 8000L;
    private static final long FOREGROUND_LEASE_REFRESH_MS = 1500L;
    private static final AtomicInteger FOREGROUND_LEASE_COUNT = new AtomicInteger(0);
    private static final Object FOREGROUND_LEASE_GUARD = new Object();
    private static volatile boolean foregroundLeaseRefresherRunning;

    private NetworkMediaCache() {
    }

    interface StatusCallback {
        void onStatus(String message);
    }

    static final class ForegroundPriorityException extends InterruptedException {
        ForegroundPriorityException() {
            super("前台播放优先，后台缓存稍后继续");
        }
    }

    static final class ForegroundLease implements AutoCloseable {
        private final Context appContext;
        private boolean closed;

        ForegroundLease(Context context) {
            appContext = context.getApplicationContext();
        }

        @Override
        public void close() {
            synchronized (FOREGROUND_LEASE_GUARD) {
                if (closed) return;
                closed = true;
                int remaining = FOREGROUND_LEASE_COUNT.decrementAndGet();
                if (remaining <= 0) {
                    FOREGROUND_LEASE_COUNT.set(0);
                    File lease = foregroundLeaseFile(appContext);
                    if (lease.isFile() && !lease.delete()) lease.deleteOnExit();
                }
            }
        }
    }

    static ForegroundLease beginForegroundWork(Context context) {
        if (context == null) throw new IllegalArgumentException("context is required");
        Context app = context.getApplicationContext();
        synchronized (FOREGROUND_LEASE_GUARD) {
            FOREGROUND_LEASE_COUNT.incrementAndGet();
            touchForegroundLease(app);
            startForegroundLeaseRefresher(app);
        }
        return new ForegroundLease(app);
    }

    static boolean foregroundWorkActive(Context context) {
        if (context == null) return false;
        File lease = foregroundLeaseFile(context.getApplicationContext());
        if (!lease.isFile()) return false;
        long age = System.currentTimeMillis() - lease.lastModified();
        if (age >= 0L && age <= FOREGROUND_LEASE_VALID_MS) return true;
        if (!lease.delete()) lease.deleteOnExit();
        return false;
    }

    static void awaitForegroundIdle(Context context) throws InterruptedException {
        while (foregroundWorkActive(context)) {
            checkInterrupted();
            Thread.sleep(200L);
        }
    }

    private static void awaitBackgroundTurn(Context context) throws InterruptedException {
        if (!isBatchCacheThread()) return;
        try {
            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
        } catch (Exception ignored) {
        }
        awaitForegroundIdle(context);
    }

    private static void yieldIfForegroundRequested(Context context)
        throws ForegroundPriorityException, InterruptedException {
        checkInterrupted();
        if (isBatchCacheThread() && foregroundWorkActive(context)) {
            throw new ForegroundPriorityException();
        }
    }

    private static boolean isBatchCacheThread() {
        String name = Thread.currentThread().getName();
        return name != null && name.startsWith("PlaylistBatchCache");
    }

    private static File foregroundLeaseFile(Context context) {
        File root = new File(context.getFilesDir(), PRIORITY_FOLDER);
        if (!root.exists()) root.mkdirs();
        return new File(root, FOREGROUND_LEASE_NAME);
    }

    private static void touchForegroundLease(Context context) {
        try {
            File lease = foregroundLeaseFile(context);
            try (FileOutputStream output = new FileOutputStream(lease, false)) {
                output.write(String.valueOf(System.currentTimeMillis())
                    .getBytes(StandardCharsets.UTF_8));
                output.flush();
            }
        } catch (Exception ignored) {
        }
    }

    private static void startForegroundLeaseRefresher(Context context) {
        if (foregroundLeaseRefresherRunning) return;
        foregroundLeaseRefresherRunning = true;
        Thread refresher = new Thread(() -> {
            try {
                while (true) {
                    synchronized (FOREGROUND_LEASE_GUARD) {
                        if (FOREGROUND_LEASE_COUNT.get() <= 0) break;
                        touchForegroundLease(context);
                    }
                    Thread.sleep(FOREGROUND_LEASE_REFRESH_MS);
                }
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            } finally {
                synchronized (FOREGROUND_LEASE_GUARD) {
                    foregroundLeaseRefresherRunning = false;
                    if (FOREGROUND_LEASE_COUNT.get() > 0) {
                        startForegroundLeaseRefresher(context);
                    }
                }
            }
        }, "ForegroundCachePriorityLease");
        refresher.setDaemon(true);
        refresher.start();
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

    static final class ImmediatePlaybackResult {
        final String audioUri;
        final String catalogJson;
        final String sourceCode;
        final boolean sourceChanged;
        final boolean fromCache;

        ImmediatePlaybackResult(String audioUri, String catalogJson, String sourceCode,
                                boolean sourceChanged, boolean fromCache) {
            this.audioUri = audioUri == null ? "" : audioUri;
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.sourceCode = sourceCode == null ? "" : sourceCode;
            this.sourceChanged = sourceChanged;
            this.fromCache = fromCache;
        }
    }

    /** Compatibility overload used by the final player source.
     * The boolean requests persistent caching; this implementation always persists selected tracks.
     */
    static CacheResult cache(Context context, String catalogJson, boolean persist,
                             StatusCallback callback) throws Exception {
        return cacheForAutomatic(context, catalogJson, callback);
    }

    static CacheResult cache(Context context, String catalogJson,
                             StatusCallback callback) throws Exception {
        return cacheForAutomatic(context, catalogJson, callback);
    }

    static CacheResult cacheForAutomatic(Context context, String catalogJson,
                                         StatusCallback callback) throws Exception {
        return cacheInternal(context, catalogJson, true, true, callback);
    }

    static CacheResult cacheForPlayback(Context context, String catalogJson,
                                        StatusCallback callback) throws Exception {
        return cachePrivateStylePlayback(context, catalogJson, callback);
    }

    /**
     * Resolve only enough information to start playback. No audio download,
     * duration check, format coercion or decoder probe is performed here.
     * Existing managed cache is preferred; otherwise the raw resolved URL is
     * returned immediately to MediaPlayer.prepareAsync().
     */
    static ImmediatePlaybackResult resolveForImmediatePlayback(Context context,
                                                               String catalogJson,
                                                               StatusCallback callback) throws Exception {
        checkInterrupted();
        if (context == null) throw new IllegalArgumentException("context is required");
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
        String requestedSource = requestedCatalog.optString("source", "")
            .trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        if (requestedSource.isEmpty() || requestedId.isEmpty()) {
            throw new IllegalArgumentException("歌曲目录缺少来源或 ID");
        }

        String requestedKey = sha256(requestedSource + "|" + requestedId);
        String requestedCached = CacheStorage.findAudioUri(context, requestedKey);
        if (!requestedCached.isEmpty() && CacheStorage.exists(context, requestedCached)) {
            status(callback, "已读取歌曲缓存");
            return new ImmediatePlaybackResult(requestedCached, requestedCatalog.toString(),
                requestedSource, false, true);
        }

        ResolvedChoice choice = null;
        status(callback, "正在连接原来源...");
        try {
            choice = new ResolvedChoice(requestedCatalog,
                resolvePrivateStyle(requestedCatalog.toString()));
        } catch (Exception ignored) {
        }
        if (choice == null || choice.audioUrl().isEmpty()) {
            status(callback, "原来源不可用，正在按歌名和歌手切换来源...");
            choice = findPrivateStyleFallback(context, requestedCatalog, callback);
        }
        if (choice == null || choice.audioUrl().isEmpty()) {
            throw new IllegalStateException("未找到同歌手同名的可播放版本，请手动使用替换歌曲");
        }

        JSONObject actualCatalog = canonicalCatalog(choice.catalog.toString());
        String actualSource = actualCatalog.optString("source", "")
            .trim().toLowerCase(Locale.ROOT);
        String actualId = actualCatalog.optString("id", "").trim();
        if (actualSource.isEmpty() || actualId.isEmpty()) {
            throw new IllegalStateException("歌曲目录不完整");
        }
        boolean sourceChanged = !requestedSource.equals(actualSource)
            || !requestedId.equals(actualId);
        String actualKey = sha256(actualSource + "|" + actualId);
        String actualCached = CacheStorage.findAudioUri(context, actualKey);
        boolean fromCache = !actualCached.isEmpty()
            && CacheStorage.exists(context, actualCached);
        String audioUri = fromCache ? actualCached : choice.audioUrl();
        return new ImmediatePlaybackResult(audioUri, actualCatalog.toString(),
            actualSource, sourceChanged, fromCache);
    }

    /**
     * Lightweight playback path matching the original private repository:
     * show catalog results immediately, resolve only after selection, try the
     * original source first, then exact normalized title+artist alternatives.
     * It intentionally skips one-minute, forced-format and decoder validation;
     * those remain exclusive to cacheForAutomatic / one-click caching.
     */
    private static CacheResult cachePrivateStylePlayback(Context context, String catalogJson,
                                                         StatusCallback callback) throws Exception {
        checkInterrupted();
        if (context == null) throw new IllegalArgumentException("context is required");
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        if (requestedSource.isEmpty() || requestedId.isEmpty()) {
            throw new IllegalArgumentException("歌曲目录缺少来源或 ID");
        }

        String requestedKey = sha256(requestedSource + "|" + requestedId);
        String requestedTitle = catalogTitle(requestedCatalog);
        String requestedArtist = catalogArtist(requestedCatalog);
        String requestedAlbum = catalogAlbum(requestedCatalog);
        CacheStorage.ensureFriendlyNames(context, requestedKey, requestedTitle, requestedArtist,
            requestedAlbum, requestedCatalog.toString());
        String requestedAudio = CacheStorage.findAudioUri(context, requestedKey);
        String requestedLyric = CacheStorage.readLyric(context, requestedKey);
        if (!requestedAudio.isEmpty() && CacheStorage.exists(context, requestedAudio)) {
            status(callback, "已读取歌曲缓存");
            return new CacheResult(requestedAudio, requestedLyric, true,
                !requestedLyric.trim().isEmpty(), requestedCatalog.toString(), requestedSource, false);
        }

        status(callback, "正在按原平台解析歌曲地址...");
        ResolvedChoice choice = null;
        try {
            choice = new ResolvedChoice(requestedCatalog,
                resolvePrivateStyle(requestedCatalog.toString()));
        } catch (Exception ignored) {
        }
        if (choice == null || choice.audioUrl().isEmpty()) {
            status(callback, "原来源不可用，正在查找同歌手同名的其他平台版本...");
            choice = findPrivateStyleFallback(context, requestedCatalog, callback);
        }
        if (choice == null || choice.audioUrl().isEmpty()) {
            throw new IllegalStateException("未找到同歌手同名的可播放版本，请手动使用替换歌曲");
        }
        return storePrivateStyleChoice(context, requestedCatalog, choice, callback);
    }

    private static ResolvedChoice findPrivateStyleFallback(Context context,
                                                            JSONObject requestedCatalog,
                                                            StatusCallback callback) {
        String requestedSource = requestedCatalog.optString("source", "")
            .trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        for (String sourceToSearch : CatalogSearch.exactAlternativeSourceOrder(
                 requestedCatalog.toString())) {
            try {
                checkInterrupted();
                status(callback, "正在尝试"
                    + CatalogSearch.labelForSource(sourceToSearch) + "版本...");
                List<CatalogSearch.Track> alternatives =
                    CatalogSearch.findExactAlternativesInSource(
                        context, requestedCatalog.toString(), sourceToSearch, true);
                for (CatalogSearch.Track alternative : alternatives) {
                    JSONObject catalog = canonicalCatalog(alternative.rawJson);
                    String source = catalog.optString("source", "")
                        .trim().toLowerCase(Locale.ROOT);
                    String id = catalog.optString("id", "").trim();
                    if (source.isEmpty() || id.isEmpty()) continue;
                    if (requestedSource.equals(source) && requestedId.equals(id)) continue;
                    try {
                        JSONObject resolved = resolvePrivateStyle(catalog.toString());
                        ResolvedChoice choice = new ResolvedChoice(catalog, resolved);
                        if (!choice.audioUrl().isEmpty()) {
                            status(callback, "已切换到"
                                + CatalogSearch.labelForSource(source) + "版本");
                            return choice;
                        }
                    } catch (Exception ignored) {
                    }
                }
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                return null;
            } catch (Exception ignored) {
            }
        }
        return null;
    }

    private static CacheResult storePrivateStyleChoice(Context context,
                                                       JSONObject requestedCatalog,
                                                       ResolvedChoice choice,
                                                       StatusCallback callback) throws Exception {
        checkInterrupted();
        JSONObject actualCatalog = canonicalCatalog(choice.catalog.toString());
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        String actualSource = actualCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String actualId = actualCatalog.optString("id", "").trim();
        if (actualSource.isEmpty() || actualId.isEmpty()) {
            throw new IllegalStateException("替换歌曲目录不完整");
        }
        boolean sourceChanged = !requestedSource.equals(actualSource) || !requestedId.equals(actualId);
        String key = sha256(actualSource + "|" + actualId);
        try (CacheKeyLock ignored = CacheKeyLock.acquire(context, key)) {
            String title = catalogTitle(actualCatalog);
            String artist = catalogArtist(actualCatalog);
            String album = catalogAlbum(actualCatalog);
            CacheStorage.ensureFriendlyNames(context, key, title, artist, album,
                actualCatalog.toString());
            String lyric = CacheStorage.readLyric(context, key);
            String existingAudio = CacheStorage.findAudioUri(context, key);
            if (!existingAudio.isEmpty() && CacheStorage.exists(context, existingAudio)) {
                status(callback, sourceChanged ? "已切换并读取其他平台缓存" : "歌曲缓存已存在");
                return new CacheResult(existingAudio, lyric, true, !lyric.trim().isEmpty(),
                    actualCatalog.toString(), actualSource, sourceChanged);
            }

            File tempRoot = new File(context.getCacheDir(), "network_download");
            if (!tempRoot.exists() && !tempRoot.mkdirs()) {
                throw new IllegalStateException("无法创建下载临时目录");
            }
            String hintedExtension = choiceExtension(choice);
            File partial = new File(tempRoot, key + "." + hintedExtension + "."
                + android.os.Process.myPid() + "." + Thread.currentThread().getId() + ".part");
            if (partial.exists()) partial.delete();
            status(callback, sourceChanged
                ? "原来源不可用，正在从" + CatalogSearch.labelForSource(actualSource) + "缓存歌曲..."
                : "正在缓存歌曲...");
            try {
                download(context, choice.audioUrl(), actualSource, partial, callback);
                checkInterrupted();
                if (partial.length() <= 0L) throw new IllegalStateException("歌曲缓存为空");
                String actualExtension = detectAudioExtension(partial, hintedExtension);
                String storedUri = CacheStorage.storeAudio(context, key, actualExtension, partial,
                    title, artist, album, actualCatalog.toString());
                status(callback, "歌曲缓存完成");
                return new CacheResult(storedUri, lyric, false, !lyric.trim().isEmpty(),
                    actualCatalog.toString(), actualSource, sourceChanged);
            } finally {
                if (partial.exists()) partial.delete();
            }
        }
    }

    private static JSONObject resolvePrivateStyle(String catalogJson) throws Exception {
        JSONObject response = new JSONObject(Bridge.resolve(catalogJson));
        if (!response.optBoolean("ok", false)) {
            throw new IllegalStateException(response.optString("error", "歌曲解析失败"));
        }
        JSONObject data = response.optJSONObject("data");
        if (data == null) throw new IllegalStateException("歌曲解析结果为空");
        return data;
    }

    private static CacheResult cacheInternal(Context context, String catalogJson,
                                             boolean enforceRequestedMinimum,
                                             boolean eagerLyrics,
                                             StatusCallback callback) throws Exception {
        checkInterrupted();
        if (context == null) throw new IllegalArgumentException("context is required");
        awaitBackgroundTurn(context);
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        if (requestedSource.isEmpty() || requestedId.isEmpty()) throw new IllegalArgumentException("歌曲目录缺少来源或 ID");

        String requestedKey = sha256(requestedSource + "|" + requestedId);
        String requestedTitle = catalogTitle(requestedCatalog);
        String requestedArtist = catalogArtist(requestedCatalog);
        String requestedAlbum = catalogAlbum(requestedCatalog);
        CacheStorage.ensureFriendlyNames(context, requestedKey, requestedTitle, requestedArtist,
            requestedAlbum, requestedCatalog.toString());
        String requestedAudioUri = CacheStorage.findAudioUri(context, requestedKey);
        String requestedLyric = CacheStorage.readLyric(context, requestedKey);
        if (!requestedAudioUri.isEmpty() && isAcceptableCachedAudio(context, requestedAudioUri)) {
            boolean lyricFromCache = !requestedLyric.trim().isEmpty();
            if (eagerLyrics && !lyricFromCache) {
                status(callback, "正在按原平台读取歌词...");
                yieldIfForegroundRequested(context);
                requestedLyric = fetchLyrics(requestedCatalog.toString());
                if (!requestedLyric.trim().isEmpty()) {
                    CacheStorage.writeLyric(context, requestedKey, requestedLyric, requestedTitle,
                        requestedArtist, requestedAlbum, requestedCatalog.toString());
                }
            }
            status(callback, "已读取原来源歌曲缓存");
            return new CacheResult(requestedAudioUri, requestedLyric, true, lyricFromCache,
                requestedCatalog.toString(), requestedSource, false);
        }
        if (!requestedAudioUri.isEmpty() && CacheStorage.exists(context, requestedAudioUri)) {
            status(callback, "旧缓存无法稳定播放，正在重新匹配...");
            CacheStorage.deleteKey(context, requestedKey);
        }

        Exception primaryError = null;
        status(callback, "正在使用歌单原来源解析歌曲...");
        try {
            if (enforceRequestedMinimum) {
                long duration = catalogDurationMs(requestedCatalog);
                if (duration > 0L && duration < MIN_AUTOMATIC_DURATION_MS) {
                    throw new IllegalStateException("原来源歌曲时长不足1分钟");
                }
            }
            awaitBackgroundTurn(context);
            ResolvedChoice original = new ResolvedChoice(requestedCatalog,
                resolve(requestedCatalog.toString()));
            CacheResult result = cacheChoice(context, requestedCatalog, original,
                enforceRequestedMinimum, eagerLyrics, callback);
            if (result != null) return result;
        } catch (InterruptedException interrupted) {
            throw interrupted;
        } catch (Exception error) {
            primaryError = error;
        }

        status(callback, "原来源不可用，才开始查找其他平台版本...");
        return cacheFirstUsableAlternative(context, requestedCatalog, callback,
            primaryError, eagerLyrics);
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

    private static CacheResult cacheFirstUsableAlternative(Context context,
                                                               JSONObject requestedCatalog,
                                                               StatusCallback callback,
                                                               Exception primaryError,
                                                               boolean eagerLyrics) throws Exception {
        awaitBackgroundTurn(context);
        List<CatalogSearch.Track> alternatives = CatalogSearch.findExactAlternatives(
            context, requestedCatalog.toString());
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        Exception lastError = primaryError;
        int attempted = 0;

        for (CatalogSearch.Track alternative : alternatives) {
            checkInterrupted();
            awaitBackgroundTurn(context);
            if (attempted >= MAX_FALLBACK_ATTEMPTS) break;
            try {
                JSONObject catalog = canonicalCatalog(alternative.rawJson);
                String source = catalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
                String id = catalog.optString("id", "").trim();
                if (source.isEmpty() || id.isEmpty()) continue;
                if (requestedSource.equals(source) && requestedId.equals(id)) continue;
                long duration = catalogDurationMs(catalog);
                if (duration > 0L && duration < MIN_AUTOMATIC_DURATION_MS) continue;

                attempted++;
                status(callback, "正在尝试其他平台候选 " + attempted + "/" + MAX_FALLBACK_ATTEMPTS
                    + "：" + CatalogSearch.labelForSource(source));
                ResolvedChoice choice = new ResolvedChoice(catalog, resolve(catalog.toString()));
                CacheResult result = cacheChoice(context, requestedCatalog, choice, true, eagerLyrics, callback);
                if (result != null) return result;
            } catch (InterruptedException interrupted) {
                throw interrupted;
            } catch (Exception error) {
                lastError = error;
            }
        }

        String detail = lastError == null || lastError.getMessage() == null
            ? "" : "：" + lastError.getMessage();
        throw new IllegalStateException("未找到时长不低于1分钟的可播放音频，请手动使用替换歌曲" + detail);
    }



    private static CacheResult cacheChoice(Context context, JSONObject requestedCatalog,
                                           ResolvedChoice choice, boolean enforceMinimumDuration,
                                           boolean eagerLyrics, StatusCallback callback) throws Exception {
        checkInterrupted();
        awaitBackgroundTurn(context);
        if (choice == null || choice.audioUrl().isEmpty()) return null;
        JSONObject actualCatalog = canonicalCatalog(choice.catalog.toString());
        if (enforceMinimumDuration) {
            long catalogDuration = catalogDurationMs(actualCatalog);
            if (catalogDuration > 0L && catalogDuration < MIN_AUTOMATIC_DURATION_MS) {
                throw new IllegalStateException("候选歌曲时长不足1分钟");
            }
        }

        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        String actualSource = actualCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String actualId = actualCatalog.optString("id", "").trim();
        if (actualSource.isEmpty() || actualId.isEmpty()) return null;
        boolean sourceChanged = !requestedSource.equals(actualSource) || !requestedId.equals(actualId);
        String key = sha256(actualSource + "|" + actualId);
        try (CacheKeyLock cacheKeyLock = CacheKeyLock.acquire(context, key)) {
        yieldIfForegroundRequested(context);
        String actualTitle = catalogTitle(actualCatalog);
        String actualArtist = catalogArtist(actualCatalog);
        String actualAlbum = catalogAlbum(actualCatalog);
        CacheStorage.ensureFriendlyNames(context, key, actualTitle, actualArtist,
            actualAlbum, actualCatalog.toString());

        String lyric = CacheStorage.readLyric(context, key);
        boolean lyricFromCache = !lyric.trim().isEmpty();
        String existingAudioUri = CacheStorage.findAudioUri(context, key);
        if (!existingAudioUri.isEmpty() && isAcceptableCachedAudio(context, existingAudioUri)) {
            if (eagerLyrics && !lyricFromCache) {
                yieldIfForegroundRequested(context);
                lyric = fetchLyrics(actualCatalog.toString());
                if (!lyric.trim().isEmpty()) {
                    CacheStorage.writeLyric(context, key, lyric, actualTitle, actualArtist,
                        actualAlbum, actualCatalog.toString());
                }
            }
            status(callback, sourceChanged ? "已切换并读取其他平台缓存" : "歌曲缓存已存在");
            return new CacheResult(existingAudioUri, lyric, true, lyricFromCache,
                actualCatalog.toString(), actualSource, sourceChanged);
        }
        if (!existingAudioUri.isEmpty() && CacheStorage.exists(context, existingAudioUri)) {
            status(callback, "已有缓存无法稳定播放，正在重新下载...");
            CacheStorage.deleteKey(context, key);
            lyric = "";
            lyricFromCache = false;
        }

        File tempRoot = new File(context.getCacheDir(), "network_download");
        if (!tempRoot.exists() && !tempRoot.mkdirs()) throw new IllegalStateException("无法创建下载临时目录");
        String hintedExtension = choiceExtension(choice);
        File partial = new File(tempRoot, key + "." + hintedExtension + "."
            + android.os.Process.myPid() + "." + Thread.currentThread().getId() + ".part");
        if (partial.exists()) partial.delete();
        status(callback, sourceChanged
            ? "正在从" + CatalogSearch.labelForSource(actualSource) + "缓存候选音频..."
            : "正在缓存候选音频...");
        try {
            download(context, choice.audioUrl(), actualSource, partial, callback);
            checkInterrupted();
            if (partial.length() <= 0L) throw new IllegalStateException("歌曲缓存为空");
            String actualExtension = detectAudioExtension(partial, hintedExtension);
            if (enforceMinimumDuration) {
                long actualDuration = mediaDurationMs(partial);
                if (actualDuration < MIN_AUTOMATIC_DURATION_MS) {
                    if (actualDuration <= 0L) throw new IllegalStateException("设备无法识别候选音频或确认时长");
                    throw new IllegalStateException("候选音频只有" + Math.max(1L, actualDuration / 1000L) + "秒");
                }
            }
            yieldIfForegroundRequested(context);
            if (!PlaybackCompatibility.isPlayable(partial)) {
                throw new IllegalStateException("当前设备无法稳定解码或拖动该音频格式");
            }

            // 不向音频文件写入歌名、歌手、专辑或其他标签；歌曲信息由歌单保存。
            String storedUri = CacheStorage.storeAudio(context, key, actualExtension, partial,
                actualTitle, actualArtist, actualAlbum, actualCatalog.toString());
            if (eagerLyrics && !lyricFromCache) {
                yieldIfForegroundRequested(context);
                lyric = fetchLyrics(actualCatalog.toString());
                if (!lyric.trim().isEmpty()) {
                    CacheStorage.writeLyric(context, key, lyric, actualTitle, actualArtist,
                        actualAlbum, actualCatalog.toString());
                }
            }
            status(callback, "歌曲缓存完成：" + formatLabel(actualExtension));
            return new CacheResult(storedUri, lyric, false, lyricFromCache,
                actualCatalog.toString(), actualSource, sourceChanged);
        } finally {
            if (partial.exists()) partial.delete();
        }
        }
    }

    private static int choiceFormatRank(ResolvedChoice choice) {
        String extension = choiceExtension(choice);
        if ("mp3".equals(extension)) return 0;
        if ("flac".equals(extension)) return 1;
        return 2;
    }

    private static String choiceExtension(ResolvedChoice choice) {
        if (choice == null || choice.resolved == null) return "audio";
        String explicit = firstNonEmpty(
            choice.resolved.optString("ext"),
            choice.resolved.optString("format"),
            choice.resolved.optString("type")
        );
        String extension = sanitizeExtension(explicit);
        if (!"audio".equals(extension)) return extension;
        extension = sanitizeExtension(extensionFromUrl(choice.audioUrl()));
        if (!"audio".equals(extension)) return extension;
        return choice.resolved.optBoolean("_requested_mp3", false) ? "mp3" : "audio";
    }

    private static long catalogDurationMs(JSONObject catalog) {
        if (catalog == null) return 0L;
        Object raw = catalog.has("durationMs") ? catalog.opt("durationMs")
            : catalog.has("duration_ms") ? catalog.opt("duration_ms")
            : catalog.has("duration") ? catalog.opt("duration")
            : catalog.has("dt") ? catalog.opt("dt")
            : catalog.opt("length");
        if (raw == null || raw == JSONObject.NULL) return 0L;
        String value = String.valueOf(raw).trim();
        if (value.isEmpty()) return 0L;
        try {
            if (value.contains(":")) {
                String[] parts = value.split(":");
                double seconds = 0.0;
                for (String part : parts) seconds = seconds * 60.0 + Double.parseDouble(part.trim());
                return Math.max(0L, Math.round(seconds * 1000.0));
            }
            double numeric = Double.parseDouble(value);
            if (numeric <= 0.0) return 0L;
            return Math.round(numeric < 10000.0 ? numeric * 1000.0 : numeric);
        } catch (Exception ignored) {
            return 0L;
        }
    }

    private static boolean isAcceptableCachedAudio(Context context, String uriText) {
        return context != null
            && uriText != null
            && !uriText.trim().isEmpty()
            && CacheStorage.exists(context, uriText)
            && PlaybackCompatibility.isPlayable(context, uriText);
    }

    private static long mediaDurationMs(File file) {
        if (file == null || !file.isFile() || file.length() <= 0L) return 0L;
        MediaMetadataRetriever retriever = new MediaMetadataRetriever();
        try {
            retriever.setDataSource(file.getAbsolutePath());
            String raw = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
            return raw == null ? 0L : Long.parseLong(raw);
        } catch (Exception ignored) {
            return 0L;
        } finally {
            try { retriever.release(); } catch (Exception ignored) { }
        }
    }

    private static String formatLabel(String extension) {
        if (extension == null || extension.trim().isEmpty() || "audio".equals(extension)) return "原始音频格式";
        return extension.toUpperCase(Locale.ROOT);
    }

    private static void checkInterrupted() throws InterruptedException {
        if (Thread.currentThread().isInterrupted()) throw new InterruptedException("歌曲资源匹配已取消");
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
        return CacheStorage.exists(context, uriText);
    }

    static boolean validateCatalogCache(Context context, String catalogJson) {
        String key = cacheKeyForCatalog(catalogJson);
        if (key.isEmpty()) return false;
        String uri = CacheStorage.findAudioUri(context, key);
        if (uri.isEmpty()) return false;
        if (isAcceptableCachedAudio(context, uri)) return true;
        CacheStorage.deleteKey(context, key);
        return false;
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
        boolean requestedMp3Resolved = response.optBoolean("ok", false);
        if (!requestedMp3Resolved) {
            response = new JSONObject(Bridge.resolve(catalogJson));
        }
        if (!response.optBoolean("ok", false)) {
            throw new IllegalStateException(response.optString("error", "歌曲解析失败"));
        }
        JSONObject data = response.optJSONObject("data");
        if (data == null) throw new IllegalStateException("歌曲解析结果为空");
        data.put("_requested_mp3", requestedMp3Resolved);
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

    private static void download(Context context, String urlText, String source,
                                 File partial, StatusCallback callback) throws Exception {
        checkInterrupted();
        yieldIfForegroundRequested(context);
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
            String contentType = connection.getContentType();
            String normalizedType = contentType == null ? "" : contentType.toLowerCase(Locale.ROOT);
            if (normalizedType.startsWith("text/") || normalizedType.contains("json")
                || normalizedType.contains("html") || normalizedType.contains("xml")) {
                throw new IllegalStateException("下载地址返回的不是音频：" + normalizedType);
            }
            long total = connection.getContentLengthLong();
            if (total > MAX_AUDIO_BYTES) throw new IllegalStateException("歌曲文件超过缓存上限");

            long written = 0L;
            int lastPercent = -1;
            long lastStatusAt = System.currentTimeMillis();
            try (InputStream input = new BufferedInputStream(connection.getInputStream());
                 BufferedOutputStream output = new BufferedOutputStream(new FileOutputStream(partial))) {
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = input.read(buffer)) >= 0) {
                    checkInterrupted();
                    yieldIfForegroundRequested(context);
                    if (count == 0) continue;
                    written += count;
                    if (written > MAX_AUDIO_BYTES) throw new IllegalStateException("歌曲文件超过缓存上限");
                    output.write(buffer, 0, count);
                    long now = System.currentTimeMillis();
                    if (total > 0) {
                        int percent = (int) Math.min(100, written * 100 / total);
                        if (percent >= lastPercent + 5 || now - lastStatusAt >= 5000L) {
                            lastPercent = percent;
                            lastStatusAt = now;
                            status(callback, "正在缓存歌曲：" + percent + "%");
                        }
                    } else if (now - lastStatusAt >= 5000L) {
                        lastStatusAt = now;
                        status(callback, "正在缓存歌曲：" + Math.max(1L, written / 1024L / 1024L) + "MB");
                    }
                }
            }
            if (written <= 0L) throw new IllegalStateException("没有下载到音频内容");
        } finally {
            connection.disconnect();
            if (Thread.currentThread().isInterrupted() && partial.exists()) partial.delete();
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
        if (url == null || url.trim().isEmpty()) return "audio";
        String clean = url;
        int query = clean.indexOf('?');
        if (query >= 0) clean = clean.substring(0, query);
        int fragment = clean.indexOf('#');
        if (fragment >= 0) clean = clean.substring(0, fragment);
        int slash = Math.max(clean.lastIndexOf('/'), clean.lastIndexOf('\\'));
        int dot = clean.lastIndexOf('.');
        return dot <= slash || dot + 1 >= clean.length() ? "audio" : clean.substring(dot + 1);
    }

    private static String sanitizeExtension(String value) {
        String extension = value == null ? "" : value.toLowerCase(Locale.ROOT).trim();
        int semicolon = extension.indexOf(';');
        if (semicolon >= 0) extension = extension.substring(0, semicolon);
        int slash = extension.lastIndexOf('/');
        if (slash >= 0) extension = extension.substring(slash + 1);
        if (extension.startsWith(".")) extension = extension.substring(1);
        if (extension.startsWith("x-")) extension = extension.substring(2);
        extension = extension.replaceAll("[^a-z0-9]", "");
        if ("mpeg".equals(extension) || "mpeg3".equals(extension)
            || "mpga".equals(extension)) return "mp3";
        if ("mp4".equals(extension)) return "m4a";
        if ("oga".equals(extension)) return "ogg";
        if ("wave".equals(extension)) return "wav";
        if ("mswma".equals(extension)) return "wma";
        if (extension.isEmpty() || extension.length() > 10) return "audio";
        return extension;
    }

    private static String detectAudioExtension(File file, String fallback) {
        if (AudioTranscoder.isMp3(file)) return "mp3";
        byte[] header = new byte[64];
        try (InputStream input = new BufferedInputStream(new FileInputStream(file))) {
            int count = input.read(header);
            if (count >= 4) {
                String first4 = new String(header, 0, 4, StandardCharsets.ISO_8859_1);
                if ("fLaC".equals(first4)) return "flac";
                if ("OggS".equals(first4)) {
                    String probe = new String(header, 0, count, StandardCharsets.ISO_8859_1);
                    return probe.contains("OpusHead") ? "opus" : "ogg";
                }
                if ("RIFF".equals(first4) && count >= 12) return "wav";
                int b0 = header[0] & 0xff;
                int b1 = header[1] & 0xff;
                if (b0 == 0xff && (b1 & 0xf6) == 0xf0) return "aac";
                if (b0 == 0x1a && b1 == 0x45 && (header[2] & 0xff) == 0xdf
                    && (header[3] & 0xff) == 0xa3) return "webm";
            }
            if (count >= 8) {
                String ftyp = new String(header, 4, 4, StandardCharsets.ISO_8859_1);
                if ("ftyp".equals(ftyp)) return "m4a";
            }
            if (count >= 16
                && (header[0] & 0xff) == 0x30 && (header[1] & 0xff) == 0x26
                && (header[2] & 0xff) == 0xb2 && (header[3] & 0xff) == 0x75) {
                return "wma";
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
