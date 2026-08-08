from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


def replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise SystemExit("method not found: " + signature)
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit("method brace not found: " + signature)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement + text[i + 1:]
    raise SystemExit("unterminated method: " + signature)

path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = path.read_text(encoding="utf-8")

field_anchor = '''    private volatile boolean playlistCacheRunning = false;\n    private volatile boolean transientCacheCleanupRunning = false;'''
field_new = '''    private volatile boolean playlistCacheRunning = false;\n    private volatile boolean transientCacheCleanupRunning = false;\n    // Built when the playlist cache button is refreshed. One-click caching consumes\n    // this exact list instead of scanning the full playlist a second time.\n    private final List<Song> playlistOneClickTargets = new ArrayList<>();\n    private Playlist playlistOneClickTargetPlaylist = null;\n    private int playlistOneClickManualOnlyCount = 0;'''
if "playlistOneClickTargets" not in text:
    if field_anchor not in text:
        raise SystemExit("one-click target field anchor missing")
    text = text.replace(field_anchor, field_new, 1)

update_method = '''    private void updatePlaylistCacheButtonVisibility() {
        if (playlistCacheButton == null) return;
        if (playlistCacheRunning) {
            playlistCacheButton.setVisibility(View.VISIBLE);
            playlistCacheButton.setEnabled(false);
            return;
        }

        // This is the single classification pass for the current playlist. The
        // resulting target list is retained and consumed directly by one-click cache.
        Playlist playlist = currentPlaylist();
        playlistOneClickTargetPlaylist = playlist;
        playlistOneClickTargets.clear();
        playlistOneClickManualOnlyCount = 0;
        for (Song song : new ArrayList<>(playlist.songs)) {
            if (song == null || !song.isNetworkCatalog()) continue;
            if (isManualOnlyCacheSong(song)) {
                playlistOneClickManualOnlyCount++;
                continue;
            }
            if (!songHasRecordedCache(song)) playlistOneClickTargets.add(song);
        }

        int missing = playlistOneClickTargets.size();
        playlistCacheButton.setEnabled(missing > 0);
        playlistCacheButton.setVisibility(missing > 0 ? View.VISIBLE : View.GONE);
        playlistCacheButton.setText("一键缓存未缓存歌曲（" + missing + "）");
    }

    private boolean isManualOnlyCacheSong(Song song) {
        return song != null && (song.unavailable || song.cacheFailed);
    }

    private boolean songHasRecordedCacheQuick(Song song) {
        if (song == null || !song.isNetworkCatalog()) return true;
        String cached = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (!cached.isEmpty()) return true;
        String direct = song.uri == null ? "" : song.uri.trim();
        return direct.startsWith("file:") || direct.startsWith("content:");
    }'''
text = replace_method(text, "    private void updatePlaylistCacheButtonVisibility()", update_method)

cache_method = '''    private void cacheCurrentPlaylistOneClick() {
        final Playlist playlist = currentPlaylist();
        if (playlist == null || playlist.songs.isEmpty()) {
            toast("当前歌单为空");
            return;
        }
        if (playlistCacheRunning) {
            toast("当前歌单正在缓存");
            return;
        }

        // updatePlaylistCacheButtonVisibility() already identified the missing songs.
        // Never rescan the complete playlist when the user presses one-click cache.
        if (playlistOneClickTargetPlaylist != playlist) {
            updatePlaylistCacheButtonVisibility();
            toast("缓存状态已刷新，请再次点击一键缓存");
            return;
        }
        final List<Song> targets = new ArrayList<>(playlistOneClickTargets);
        final int manualOnlyAtStart = playlistOneClickManualOnlyCount;
        if (targets.isEmpty()) {
            if (manualOnlyAtStart > 0) {
                toast("没有可自动缓存歌曲；红色歌曲需手动处理");
            } else {
                toast("当前歌单都已缓存");
            }
            return;
        }

        final int cacheStartSerial = foregroundPlaybackSerial;
        playlistCacheRunning = true;
        ++playlistCacheScanSerial;
        if (playlistCacheButton != null) {
            playlistCacheButton.setVisibility(View.VISIBLE);
            playlistCacheButton.setEnabled(false);
            playlistCacheButton.setText("缓存 0/" + targets.size());
        }
        if (statusView != null) {
            statusView.setText("开始缓存：" + playlist.name + "，共 " + targets.size() + " 首");
        }

        new Thread(() -> {
            int done = 0;
            int skipped = 0;
            int waitingExisting = 0;
            int failed = 0;
            int manualSkipped = manualOnlyAtStart;
            boolean pausedForPlayback = false;
            for (int i = 0; i < targets.size(); i++) {
                if (foregroundPlaybackSerial != cacheStartSerial) {
                    pausedForPlayback = true;
                    break;
                }
                Song song = targets.get(i);
                if (song == null || !song.isNetworkCatalog()) {
                    skipped++;
                    continue;
                }
                // A song can turn red after the target list was built (for example,
                // another playback attempt failed). Red songs are manual-only forever
                // until the user explicitly operates/replaces them.
                if (isManualOnlyCacheSong(song)) {
                    manualSkipped++;
                    continue;
                }
                // Only check the in-memory URI fields for this already-classified target.
                // Do not perform another full playlist/index scan.
                if (songHasRecordedCacheQuick(song)) {
                    done++;
                    continue;
                }

                final String operationKey = cacheOperationKey(song);
                if (!beginSongCacheTask(operationKey)) {
                    waitingExisting++;
                    final int index = i + 1;
                    runOnUiThread(() -> {
                        String progress = playlistCacheProgressText(song, index, targets.size());
                        if (statusView != null) statusView.setText(progress + " · 复用已有缓存任务");
                        if (playlistCacheButton != null) playlistCacheButton.setText("缓存 " + index + "/" + targets.size());
                    });
                    continue;
                }

                final int index = i + 1;
                runOnUiThread(() -> {
                    String progress = playlistCacheProgressText(song, index, targets.size());
                    if (statusView != null) statusView.setText(progress);
                    if (playlistCacheButton != null) playlistCacheButton.setText("缓存 " + index + "/" + targets.size());
                });
                try {
                    NetworkMediaCache.CacheResult cached = cachePlaylistSongWithTimeout(
                        song, cacheStartSerial, index, targets.size());
                    if (foregroundPlaybackSerial != cacheStartSerial) {
                        pausedForPlayback = true;
                        break;
                    }
                    String originalKey = song.key();
                    song.cachedUri = cached.audioUri;
                    song.uri = cached.audioUri;
                    if (cached.catalogJson != null && !cached.catalogJson.trim().isEmpty()) {
                        song.catalogJson = cached.catalogJson;
                    }
                    if (cached.sourceCode != null && !cached.sourceCode.trim().isEmpty()) {
                        song.source = CatalogSearch.labelForSource(cached.sourceCode);
                    }
                    if ((song.lyric == null || song.lyric.trim().isEmpty())
                        && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                        song.lyric = cached.lyric;
                    }
                    song.cacheFailed = false;
                    song.unavailable = false;
                    song.autoUnavailable = false;
                    song.manualUnavailable = false;
                    song.manualAttempt = false;
                    recoverCachedSongState(song, cached.audioUri);
                    persistResolvedCatalogToPlaylistCopies(song, originalKey);
                    done++;
                } catch (Exception error) {
                    if (foregroundPlaybackSerial != cacheStartSerial) {
                        pausedForPlayback = true;
                        break;
                    }
                    // Failure becomes red/manual-only. Future one-click runs skip it.
                    song.cacheFailed = true;
                    failed++;
                } finally {
                    endSongCacheTask(operationKey);
                }
            }
            int finalDone = done;
            int finalSkipped = skipped;
            int finalWaitingExisting = waitingExisting;
            int finalFailed = failed;
            int finalManualSkipped = manualSkipped;
            boolean finalPausedForPlayback = pausedForPlayback;
            runOnUiThread(() -> {
                playlistCacheRunning = false;
                savePlaylists();
                renderCurrentPlaylist();
                if (statusView == null) return;
                if (finalPausedForPlayback) {
                    statusView.setText("已因前台播放切换而暂停一键缓存");
                } else {
                    statusView.setText("一键缓存完成：成功 " + finalDone
                        + "，复用已有任务 " + finalWaitingExisting
                        + "，普通跳过 " + finalSkipped
                        + "，失败标红 " + finalFailed
                        + "，红色手动处理 " + finalManualSkipped);
                }
            });
        }, "playlist-one-click-cache").start();
    }'''
text = replace_method(text, "    private void cacheCurrentPlaylistOneClick()", cache_method)

path.write_text(text, encoding="utf-8")
