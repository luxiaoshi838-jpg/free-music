from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/src/main/java/com/jianglab/babywife/MainActivity.java"
STORE = ROOT / "app/src/main/java/com/jianglab/babywife/Media3CacheStore.java"
EXPORTER = ROOT / "app/src/main/java/com/jianglab/babywife/Media3FriendlyCacheExporter.java"
GRADLE = ROOT / "app/build.gradle"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def replace_method(text: str, marker: str, replacement: str, label: str) -> str:
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"{label}: marker missing")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"{label}: opening brace missing")
    depth = 0
    in_string = False
    in_char = False
    escape = False
    line_comment = False
    block_comment = False
    i = brace
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if ch == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_string or in_char:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif in_string and ch == '"':
                in_string = False
            elif in_char and ch == "'":
                in_char = False
            i += 1
            continue
        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch == '"':
            in_string = True
        elif ch == "'":
            in_char = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement.rstrip() + "\n\n" + text[i + 1:]
        i += 1
    raise SystemExit(f"{label}: closing brace missing")


main = MAIN.read_text(encoding="utf-8")
main = replace_once(
    main,
    "import java.util.concurrent.Callable;\n",
    "import java.util.concurrent.Callable;\nimport java.util.concurrent.ConcurrentHashMap;\n",
    "ConcurrentHashMap import",
)
main = replace_once(
    main,
    "    private Future<?> searchCacheFuture;\n",
    "    private final ConcurrentHashMap<String, Future<?>> searchCacheTasks = new ConcurrentHashMap<>();\n",
    "search cache task map",
)

play_search = r'''    private void playSearchSongFast(Song song, int playToken) {
        attachExistingFriendlyCache(song);
        Song playlistMatch = findPlaylistSongMatch(song);
        boolean exactPlaylistCatalog = playlistMatch != null
            && sameCatalogIdentity(playlistMatch.catalogJson, song.catalogJson);
        String playlistCache = !exactPlaylistCatalog || playlistMatch.cachedUri == null
            ? "" : playlistMatch.cachedUri.trim();
        if (!playlistCache.isEmpty()) {
            song.cachedUri = playlistCache;
            song.uri = playlistCache;
            statusView.setText("已使用同一来源歌曲缓存，正在启动播放...");
            startLocalPlayback(song, playToken, null, () -> {
                song.cachedUri = "";
                song.uri = "";
                playlistMatch.cachedUri = "";
                playlistMatch.uri = "";
                savePlaylists();
                statusView.setText("同一来源缓存无法播放，正在重新解析所选来源...");
                trySearchPlaybackCandidate(song, playToken, 0, false);
            });
            return;
        }

        String sessionCache = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (!sessionCache.isEmpty()) {
            song.uri = sessionCache;
            statusView.setText("已读取所选来源缓存，正在启动播放...");
            startLocalPlayback(song, playToken, null, () -> {
                song.cachedUri = "";
                song.uri = "";
                statusView.setText("所选来源缓存无法播放，正在重新解析...");
                trySearchPlaybackCandidate(song, playToken, 0, false);
            });
            return;
        }
        trySearchPlaybackCandidate(song, playToken, 0, false);
    }'''
main = replace_method(main, "    private void playSearchSongFast(", play_search,
                      "playSearchSongFast")

try_candidate = r'''    private void trySearchPlaybackCandidate(Song song, int playToken, int stage) {
        trySearchPlaybackCandidate(song, playToken, stage, !playingSearchQueue);
    }

    private void trySearchPlaybackCandidate(Song song, int playToken, int stage,
                                            boolean allowCrossSourceFallback) {
        if (song == null || currentSong != song || playToken != playbackRequestSerial) return;
        int maxStage = allowCrossSourceFallback ? 2 : 0;
        if (stage > maxStage) {
            stopPlayback();
            playButton.setText("▶");
            lyricView.setText("音频未开始播放，未启动在线歌词匹配");
            String selectedLabel = sourceLabelFromCatalog(song.catalogJson);
            statusView.setText(allowCrossSourceFallback
                ? "没有找到可播放的同名资源"
                : selectedLabel + "结果没有返回可播放地址，请选择其他来源结果");
            toast("暂时没有找到可播放资源");
            return;
        }

        String stageLabel = stage == 0
            ? sourceLabelFromCatalog(song.catalogJson)
            : (stage == 1 ? "酷我（歌单自动替代）" : "网易云（歌单自动替代）");
        statusView.setText("正在解析" + stageLabel + "的真实播放地址...");
        final String requestedSource = sourceCodeFromCatalog(song.catalogJson);
        new Thread(() -> {
            SearchQuickPlayback.Candidate candidate = null;
            try {
                candidate = SearchQuickPlayback.resolveStage(song.catalogJson, stage);
            } catch (Exception ignored) {
            }
            SearchQuickPlayback.Candidate resolved = candidate;
            runOnUiThread(() -> {
                if (currentSong != song || playToken != playbackRequestSerial) return;
                if (resolved == null || resolved.playbackUrl.isEmpty()) {
                    trySearchPlaybackCandidate(song, playToken, stage + 1,
                        allowCrossSourceFallback);
                    return;
                }
                if (stage == 0 && !requestedSource.isEmpty()
                    && !requestedSource.equals(resolved.sourceCode)) {
                    statusView.setText("来源校验失败：选择的是"
                        + CatalogSearch.labelForSource(requestedSource) + "，解析结果却是"
                        + resolved.sourceLabel);
                    trySearchPlaybackCandidate(song, playToken, stage + 1,
                        allowCrossSourceFallback);
                    return;
                }

                // The resolved catalog must be installed before Media3 opens the
                // URL. Playback headers, internal cache key and friendly export
                // therefore always describe the same source and song ID.
                song.catalogJson = resolved.catalogJson;
                song.source = resolved.sourceLabel;
                song.uri = resolved.playbackUrl;
                String resolvedArtwork = PlaybackArtworkLoader.extractArtworkUrl(
                    resolved.catalogJson);
                if (!resolvedArtwork.isEmpty()) song.artworkUrl = resolvedArtwork;
                artistView.setText(song.artist + " · " + song.source);

                statusView.setText("已找到" + resolved.sourceLabel
                    + "真实地址，正在在线播放；播放后自动生成本地缓存文件...");
                startLocalPlayback(song, playToken, () -> {
                    saveLastSong(0);
                    statusView.setText("正在在线播放，同时后台生成“"
                        + song.title + " - " + song.artist + "”缓存文件...");
                    cacheSearchPlaybackAsync(song, resolved, playToken);
                }, () -> {
                    song.uri = "";
                    if (allowCrossSourceFallback) {
                        statusView.setText(resolved.sourceLabel
                            + "地址无法播放，继续寻找歌单替代来源...");
                        trySearchPlaybackCandidate(song, playToken, stage + 1, true);
                    } else {
                        statusView.setText(resolved.sourceLabel
                            + "地址无法播放，请选择其他来源结果");
                        stopPlayback();
                        playButton.setText("▶");
                    }
                });
            });
        }, "search-address-resolver").start();
    }

    private String sourceCodeFromCatalog(String catalogJson) {
        try {
            return new JSONObject(catalogJson == null ? "{}" : catalogJson)
                .optString("source", "").trim().toLowerCase(Locale.ROOT);
        } catch (Exception ignored) {
            return "";
        }
    }

    private String sourceLabelFromCatalog(String catalogJson) {
        String source = sourceCodeFromCatalog(catalogJson);
        return source.isEmpty() ? "所选来源" : CatalogSearch.labelForSource(source);
    }

    private String catalogIdentity(String catalogJson) {
        try {
            JSONObject object = new JSONObject(catalogJson == null ? "{}" : catalogJson);
            String source = object.optString("source", "").trim().toLowerCase(Locale.ROOT);
            String id = object.optString("id", "").trim();
            return source.isEmpty() || id.isEmpty() ? "" : source + "|" + id;
        } catch (Exception ignored) {
            return "";
        }
    }

    private boolean sameCatalogIdentity(String leftCatalog, String rightCatalog) {
        String left = catalogIdentity(leftCatalog);
        return !left.isEmpty() && left.equals(catalogIdentity(rightCatalog));
    }'''
main = replace_method(main, "    private void trySearchPlaybackCandidate(", try_candidate,
                      "trySearchPlaybackCandidate")

cache_async = r'''    private void cacheSearchPlaybackAsync(Song song,
                                          SearchQuickPlayback.Candidate candidate,
                                          int playToken) {
        if (song == null || candidate == null) return;
        final String media3Key = Media3CacheStore.keyFor(
            song.title, song.artist, candidate.catalogJson);
        if (media3Key.isEmpty()) return;
        if (song.artworkUrl.isEmpty()) {
            song.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(candidate.catalogJson);
        }
        Media3PlaybackCacheIndex.record(this, media3Key, song.title, song.artist,
            candidate.catalogJson, song.artworkUrl);

        attachExistingFriendlyCache(song);
        if (song.cachedUri != null && !song.cachedUri.trim().isEmpty()
            && CacheFileState.exists(this, song.cachedUri)) {
            Media3PlaybackCacheIndex.markExported(this, media3Key, song.cachedUri);
            return;
        }

        synchronized (searchCacheTasks) {
            Future<?> existingTask = searchCacheTasks.get(media3Key);
            if (existingTask != null && !existingTask.isDone()) return;
            Future<?> submitted = searchCacheExecutor.submit(() -> {
                SearchQuickPlayback.Candidate exportCandidate = candidate;
                Exception lastError = null;
                try {
                    for (int attempt = 0; attempt < 2; attempt++) {
                        try {
                            final int currentAttempt = attempt;
                            final java.util.concurrent.atomic.AtomicInteger lastPercent =
                                new java.util.concurrent.atomic.AtomicInteger(-1);
                            String storedUri = Media3FriendlyCacheExporter.cacheAndExport(
                                this,
                                exportCandidate,
                                song.title,
                                song.artist,
                                "",
                                (totalBytes, cachedBytes) -> {
                                    Media3PlaybackCacheIndex.updateProgress(
                                        this, media3Key, cachedBytes, totalBytes);
                                    if (activityDestroyed || currentSong != song
                                        || totalBytes <= 0L) return;
                                    int percent = (int) Math.max(0L, Math.min(100L,
                                        cachedBytes * 100L / totalBytes));
                                    int previous = lastPercent.getAndSet(percent);
                                    if (percent != 100 && previous >= 0
                                        && percent - previous < 5) return;
                                    runOnUiThread(() -> {
                                        if (!activityDestroyed && currentSong == song
                                            && statusView != null) {
                                            statusView.setText("正在在线播放并生成缓存文件："
                                                + percent + "%"
                                                + (currentAttempt > 0 ? "（续传）" : ""));
                                        }
                                    });
                                }
                            );
                            Media3PlaybackCacheIndex.markExported(
                                this, media3Key, storedUri);
                            SearchQuickPlayback.Candidate completedCandidate = exportCandidate;
                            runOnUiThread(() -> {
                                if (activityDestroyed) return;
                                song.cachedUri = storedUri;
                                persistSearchCacheToPlaylistCopies(
                                    song, completedCandidate, storedUri);
                                savePlaylists();
                                if (currentSong == song) {
                                    int position = 0;
                                    try {
                                        if (mediaPlayer != null) {
                                            position = mediaPlayer.getCurrentPosition();
                                        }
                                    } catch (Exception ignored) {
                                    }
                                    saveLastSong(position);
                                    statusView.setText("当前播放：" + song.title
                                        + "（缓存文件已生成：“" + song.title
                                        + " - " + song.artist + "”）");
                                    publishPlaybackControlState(true);
                                }
                                updatePlaylistCacheButtonVisibility();
                            });
                            return;
                        } catch (Exception error) {
                            lastError = error;
                            if (Thread.currentThread().isInterrupted()) return;
                            if (attempt == 0) {
                                try {
                                    SearchQuickPlayback.Candidate refreshed =
                                        SearchQuickPlayback.resolveStage(
                                            exportCandidate.catalogJson, 0);
                                    if (refreshed != null
                                        && !refreshed.playbackUrl.isEmpty()
                                        && refreshed.sourceCode.equals(
                                            exportCandidate.sourceCode)) {
                                        exportCandidate = refreshed;
                                        continue;
                                    }
                                } catch (Exception ignored) {
                                }
                            }
                            break;
                        }
                    }
                    Exception failure = lastError;
                    runOnUiThread(() -> {
                        if (!activityDestroyed && currentSong == song) {
                            String detail = failure == null
                                || failure.getMessage() == null
                                ? "未知错误" : failure.getMessage();
                            statusView.setText("播放正常，但缓存文件生成失败：" + detail);
                        }
                    });
                } finally {
                    searchCacheTasks.remove(media3Key);
                }
            });
            searchCacheTasks.put(media3Key, submitted);
        }
    }'''
main = replace_method(main, "    private void cacheSearchPlaybackAsync(", cache_async,
                      "cacheSearchPlaybackAsync")

persist_method = r'''    private void persistSearchCacheToPlaylistCopies(
                                                     Song song,
                                                     SearchQuickPlayback.Candidate candidate,
                                                     String storedUri) {
        String candidateIdentity = catalogIdentity(candidate.catalogJson);
        boolean changed = false;
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item != song && (candidateIdentity.isEmpty()
                    || !candidateIdentity.equals(catalogIdentity(item.catalogJson)))) {
                    continue;
                }
                item.source = candidate.sourceLabel;
                item.catalogJson = candidate.catalogJson;
                item.artworkUrl = !song.artworkUrl.isEmpty()
                    ? song.artworkUrl
                    : PlaybackArtworkLoader.extractArtworkUrl(candidate.catalogJson);
                item.cachedUri = storedUri;
                item.uri = storedUri;
                item.cacheFailed = false;
                item.autoUnavailable = false;
                item.unavailable = false;
                changed = true;
            }
        }
        if (changed) {
            savePlaylists();
            renderCurrentPlaylist();
        }
    }'''
main = replace_method(main, "    private void persistSearchCacheToPlaylistCopies(",
                      persist_method, "persistSearchCacheToPlaylistCopies")

cancel_method = r'''    private void cancelSearchCacheTask() {
        // Playback-created cache jobs survive ordinary song switches. They are
        // cancelled only when the Activity is actually destroyed.
        if (!activityDestroyed) return;
        synchronized (searchCacheTasks) {
            for (Future<?> task : searchCacheTasks.values()) {
                if (task != null) task.cancel(true);
            }
            searchCacheTasks.clear();
        }
    }'''
main = replace_method(main, "    private void cancelSearchCacheTask(", cancel_method,
                      "cancelSearchCacheTask")

if "searchCacheFuture" in main:
    raise SystemExit("old searchCacheFuture remains")
if "搜索结果、酷我和网易云均没有可播放地址" in main:
    raise SystemExit("old forced cross-source fallback remains")
if "trySearchPlaybackCandidate(song, playToken, 0, false)" not in main:
    raise SystemExit("search source fidelity route missing")
if "searchCacheTasks.remove(media3Key)" not in main:
    raise SystemExit("cache task cleanup missing")
MAIN.write_text(main, encoding="utf-8")

store = STORE.read_text(encoding="utf-8")
old_key = '''    static String keyFor(String title, String artist, String catalogJson) {
        String logical = CacheStorage.logicalIdentity(title, artist);
        if (logical != null && !logical.trim().isEmpty()) {
            return "media3|" + logical.trim();
        }
        String catalogKey = NetworkMediaCache.cacheKeyForCatalog(catalogJson);
        return catalogKey == null || catalogKey.trim().isEmpty()
            ? "" : "media3|" + catalogKey.trim();
    }
'''
new_key = '''    static String keyFor(String title, String artist, String catalogJson) {
        String catalogKey = NetworkMediaCache.cacheKeyForCatalog(catalogJson);
        if (catalogKey != null && !catalogKey.trim().isEmpty()) {
            return "media3|catalog|" + catalogKey.trim();
        }
        String logical = CacheStorage.logicalIdentity(title, artist);
        return logical == null || logical.trim().isEmpty()
            ? "" : "media3|logical|" + logical.trim();
    }

    static long contiguousCachedBytesFromZero(Context context, String key) {
        if (context == null || key == null || key.trim().isEmpty()) return 0L;
        try {
            long end = 0L;
            for (androidx.media3.datasource.cache.CacheSpan span
                : get(context).getCachedSpans(key.trim())) {
                if (!span.isCached || span.length <= 0L) continue;
                if (span.position > end) break;
                end = Math.max(end, span.position + span.length);
            }
            return end;
        } catch (Exception ignored) {
            return 0L;
        }
    }
'''
store = replace_once(store, old_key, new_key, "source-aware Media3 key")
STORE.write_text(store, encoding="utf-8")

exporter = EXPORTER.read_text(encoding="utf-8")
exporter = replace_once(
    exporter,
    '''        if (media3Key.isEmpty() || storageKey.isEmpty()) {
            throw new IllegalStateException("歌曲缓存键无效");
        }

        Map<String, String> headers = UnifiedMediaPlayer.requestHeadersFor(candidate.catalogJson);
''',
    '''        if (media3Key.isEmpty() || storageKey.isEmpty()) {
            throw new IllegalStateException("歌曲缓存键无效");
        }
        String existingUri = CacheStorage.findAudioUri(context, storageKey);
        if (!existingUri.isEmpty() && CacheFileState.exists(context, existingUri)
            && !SodaM4aDecryptor.isEncryptedM4a(context, existingUri)) {
            Media3PlaybackCacheIndex.markExported(context, media3Key, existingUri);
            return existingUri;
        }

        Map<String, String> headers = UnifiedMediaPlayer.requestHeadersFor(candidate.catalogJson);
''',
    "existing friendly cache reuse",
)
exporter = replace_once(
    exporter,
    '''        if (contentLength <= 0L) contentLength = observedLength.get();
        if (contentLength <= 0L) {
            throw new IllegalStateException("Media3没有得到音频总长度");
        }
        if (!Media3CacheStore.get(context).isCached(media3Key, 0L, contentLength)) {
            throw new IllegalStateException("Media3缓存尚未覆盖完整歌曲");
        }

        File tempRoot = new File(context.getCacheDir(), "media3_friendly_export");
''',
    '''        if (contentLength <= 0L) contentLength = observedLength.get();
        // CacheWriter returning normally means it reached the resource EOF. Some
        // music CDNs omit a usable Content-Length, so derive the exact contiguous
        // byte count from the cache instead of discarding a completed download.
        if (contentLength <= 0L) {
            contentLength = Media3CacheStore.contiguousCachedBytesFromZero(
                context, media3Key);
        }
        if (contentLength <= 0L) {
            throw new IllegalStateException("Media3缓存完成后仍无法确定音频长度");
        }
        if (!Media3CacheStore.get(context).isCached(media3Key, 0L, contentLength)) {
            throw new IllegalStateException("Media3缓存尚未覆盖完整歌曲");
        }
        DataSpec exportSpec = new DataSpec.Builder()
            .setUri(Uri.parse(candidate.playbackUrl))
            .setKey(media3Key)
            .setLength(contentLength)
            .build();

        File tempRoot = new File(context.getCacheDir(), "media3_friendly_export");
''',
    "unknown-length completed cache export",
)
exporter = replace_once(
    exporter,
    "            copyCachedResource(cacheFactory, dataSpec, raw, contentLength);\n",
    "            copyCachedResource(cacheFactory, exportSpec, raw, contentLength);\n",
    "bounded cached export",
)
EXPORTER.write_text(exporter, encoding="utf-8")

gradle = GRADLE.read_text(encoding="utf-8")
gradle = replace_once(gradle, "versionCode 2026080656", "versionCode 2026080757",
                      "v157 versionCode")
gradle = replace_once(
    gradle,
    'versionName "2026.08.06.v156-upgrade-compatible"',
    'versionName "2026.08.06.v157-source-faithful-cache-export"',
    "v157 versionName",
)
GRADLE.write_text(gradle, encoding="utf-8")
