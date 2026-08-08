from pathlib import Path


def replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise SystemExit("method not found: " + signature)
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit("method brace not found: " + signature)
    depth = 0
    in_string = False
    escape = False
    in_char = False
    for i in range(brace, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if in_char:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                in_char = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "'":
            in_char = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement + text[i + 1:]
    raise SystemExit("unterminated method: " + signature)


gradle = Path("app/build.gradle")
g = gradle.read_text(encoding="utf-8")
g = g.replace("versionCode 2026080874", "versionCode 2026080875", 1)
g = g.replace(
    'versionName "2026.08.08.v174-search-mode-centered"',
    'versionName "2026.08.08.v175-playback-cache-format-crashlog"',
    1,
)
if "versionCode 2026080875" not in g or 'versionName "2026.08.08.v175-playback-cache-format-crashlog"' not in g:
    raise SystemExit("v175 version patch failed")
gradle.write_text(g, encoding="utf-8")

main_path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = main_path.read_text(encoding="utf-8")

cache_method = r'''    private void cacheSearchPlaybackAsync(Song song,
                                          SearchQuickPlayback.Candidate candidate,
                                          int playToken) {
        if (song == null || candidate == null || !song.isNetworkCatalog()) return;
        final String media3Key = Media3CacheStore.keyFor(
            song.title, song.artist, candidate.catalogJson);
        if (media3Key.isEmpty()) return;

        final String originalKey = song.key();
        if (song.artworkUrl == null || song.artworkUrl.trim().isEmpty()) {
            song.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(candidate.catalogJson);
        }

        synchronized (searchCacheTasks) {
            Future<?> existingTask = searchCacheTasks.get(media3Key);
            if (existingTask != null && !existingTask.isDone()) return;

            Future<?> submitted = searchCacheExecutor.submit(() -> {
                try {
                    // Search playback and one-click caching deliberately share the
                    // exact same format-agnostic real-playback validation path.
                    // This prevents a song that already played from being downloaded
                    // a second time merely because its source is not MP3/FLAC.
                    NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
                        this,
                        candidate.catalogJson,
                        true,
                        message -> {
                            if (activityDestroyed) {
                                throw new IllegalStateException("页面已关闭，停止后台缓存");
                            }
                            runOnUiThread(() -> {
                                if (!activityDestroyed && currentSong == song && statusView != null) {
                                    statusView.setText(message);
                                }
                            });
                        }
                    );

                    runOnUiThread(() -> {
                        if (activityDestroyed) return;
                        if (cached.catalogJson != null && !cached.catalogJson.trim().isEmpty()) {
                            song.catalogJson = cached.catalogJson;
                        }
                        if (cached.sourceCode != null && !cached.sourceCode.trim().isEmpty()) {
                            song.source = CatalogSearch.labelForSource(cached.sourceCode);
                        }
                        if (cached.audioUri != null && !cached.audioUri.trim().isEmpty()) {
                            song.cachedUri = cached.audioUri;
                            song.uri = cached.audioUri;
                        }
                        if ((song.lyric == null || song.lyric.trim().isEmpty())
                            && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                            song.lyric = cached.lyric;
                        }
                        String artwork = PlaybackArtworkLoader.extractArtworkUrl(song.catalogJson);
                        if (artwork != null && !artwork.trim().isEmpty()) song.artworkUrl = artwork;
                        song.cacheFailed = false;
                        song.unavailable = false;
                        song.manualUnavailable = false;
                        song.manualAttempt = false;

                        // If the user added this search result to a playlist while the
                        // background cache was running, update that same playlist entry
                        // instead of requiring a later one-click cache pass.
                        persistResolvedCatalogToPlaylistCopies(song, originalKey);
                        savePlaylists();
                        renderCurrentPlaylist();
                        if (resultAdapter != null) resultAdapter.notifyDataSetChanged();
                        if (playlistAdapter != null) playlistAdapter.notifyDataSetChanged();
                        if (currentSong == song && statusView != null) {
                            statusView.setText("已完成当前播放歌曲缓存：" + song.title);
                        }
                    });
                } catch (Exception error) {
                    runOnUiThread(() -> {
                        if (activityDestroyed) return;
                        // Playback itself remains valid even when a background cache
                        // attempt fails. Do not mark the song unavailable or prevent it
                        // from being added to a playlist because of its container format.
                        song.cacheFailed = false;
                        if (currentSong == song && statusView != null) {
                            String detail = error.getMessage() == null ? "后台缓存暂未完成" : error.getMessage();
                            statusView.setText("歌曲仍可正常播放；" + detail);
                        }
                    });
                } finally {
                    synchronized (searchCacheTasks) {
                        searchCacheTasks.remove(media3Key);
                    }
                }
            });
            searchCacheTasks.put(media3Key, submitted);
        }
    }'''
text = replace_method(text, "    private void cacheSearchPlaybackAsync(Song song,", cache_method)

# Make playlist insertion explicitly metadata-only and format-agnostic. The current
# playback/cache object is reused when the selected search result is the current song.
add_method = r'''    private void addSongToCurrentPlaylist(Song song) {
        if (song == null) return;
        // Joining a playlist is a metadata operation. Never reject a network song
        // because its playable resource is not MP3/FLAC (M4A/AAC/OGG/OPUS/WAV/etc.
        // are all valid as long as Android can actually play the resource).
        attachExistingFriendlyCache(song);
        addSongToCurrentPlaylistReady(song);
    }'''
text = replace_method(text, "    private void addSongToCurrentPlaylist(Song song)", add_method)

crash_method = r'''    private void persistCrashReport(Thread thread, Throwable throwable) {
        StringWriter stack = new StringWriter();
        if (throwable != null) throwable.printStackTrace(new PrintWriter(stack));
        StringBuilder report = new StringBuilder();
        report.append("Crash report\n");
        appendReportContext(report, thread == null ? "" : thread.getName());
        report.append("\nstack:\n").append(stack);
        // An uncaught exception can terminate the process immediately. Use a
        // synchronous SharedPreferences commit here so the real Java stack trace
        // is durable before Android records the process-exit reason.
        storeProblemReportSync(report.toString());
    }'''
text = replace_method(text, "    private void persistCrashReport(Thread thread, Throwable throwable)", crash_method)

sync_method = r'''
    private void storeProblemReportSync(String reportText) {
        String report = trimForReport(reportText, 60000);
        long now = System.currentTimeMillis();
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        try {
            JSONArray old = readProblemReportHistory();
            JSONArray next = new JSONArray();
            JSONObject newest = new JSONObject();
            newest.put("name", problemReportName(now));
            newest.put("time", now);
            newest.put("text", report);
            next.put(newest);
            for (int i = 0; i < old.length() && next.length() < MAX_PROBLEM_REPORT_HISTORY; i++) {
                JSONObject item = old.optJSONObject(i);
                if (item == null) continue;
                long oldTime = item.optLong("time", 0L);
                String oldText = item.optString("text", "");
                if (oldTime == now && oldText.equals(report)) continue;
                next.put(item);
            }
            prefs.edit()
                .putString(KEY_PROBLEM_REPORT_HISTORY, next.toString())
                .putString(KEY_CRASH_REPORT, report)
                .putLong(KEY_CRASH_REPORT_TIME, now)
                .putBoolean(KEY_CRASH_REPORT_DISMISSED, false)
                .commit();
        } catch (Throwable ignored) {
            try {
                prefs.edit()
                    .putString(KEY_CRASH_REPORT, report)
                    .putLong(KEY_CRASH_REPORT_TIME, now)
                    .putBoolean(KEY_CRASH_REPORT_DISMISSED, false)
                    .commit();
            } catch (Throwable ignoredAgain) {
            }
        }
    }
'''
if "private void storeProblemReportSync(String reportText)" not in text:
    marker = "    private void openSavedCrashReport() {"
    if marker not in text:
        raise SystemExit("sync crash-log insertion marker missing")
    text = text.replace(marker, sync_method + "\n" + marker, 1)

main_path.write_text(text, encoding="utf-8")

network_path = Path("app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java")
network = network_path.read_text(encoding="utf-8")
resolve_method = r'''    private static JSONObject resolve(String catalogJson) throws Exception {
        // No container/codec preference is injected here. Let each provider return
        // its natural playable resource; validation, not MP3/FLAC priority, decides.
        JSONObject response = new JSONObject(Bridge.resolve(catalogJson));
        if (!response.optBoolean("ok", false)) {
            throw new IllegalStateException(response.optString("error", "歌曲解析失败"));
        }
        JSONObject data = response.optJSONObject("data");
        if (data == null) throw new IllegalStateException("歌曲解析结果为空");
        return data;
    }'''
network = replace_method(network, "    private static JSONObject resolve(String catalogJson)", resolve_method)
network_path.write_text(network, encoding="utf-8")

resolver_path = Path("app/src/main/java/com/jianglab/babywife/PlayableAudioResolver.java")
resolver = resolver_path.read_text(encoding="utf-8")
if 'private static final String[] REQUEST_FORMATS = {""};' not in resolver:
    raise SystemExit("format-agnostic resolver invariant missing")
# Keep the empty format request as the sole mode: there is no MP3/FLAC priority.
resolver = resolver.replace(
    '/** Resolves sources in order and stops at the first candidate that passes real playback validation. */',
    '/** Resolves sources with no format priority and stops at the first candidate that passes real playback validation. */',
    1,
)
resolver_path.write_text(resolver, encoding="utf-8")
