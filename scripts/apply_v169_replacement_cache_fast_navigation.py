from pathlib import Path


gradle = Path("app/build.gradle")
text = gradle.read_text(encoding="utf-8")
text = text.replace("versionCode 2026080868", "versionCode 2026080869")
text = text.replace(
    'versionName "2026.08.08.v168-fast-transient-cache-cleanup"',
    'versionName "2026.08.08.v169-replacement-cache-fast-navigation"',
)
gradle.write_text(text, encoding="utf-8")

main = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = main.read_text(encoding="utf-8")

field_anchor = "    private volatile int playlistCacheScanSerial = 0;\n"
if "replacementCacheSerial" not in text:
    if field_anchor not in text:
        raise SystemExit("replacement field anchor missing")
    text = text.replace(
        field_anchor,
        field_anchor + "    private volatile int replacementCacheSerial = 0;\n",
        1,
    )

old_search = """        searchResultsList.setOnItemClickListener((parent, view, position, id) -> {
            if (position < 0 || position >= searchResults.size()) return;
            playSongFromSearch(position);
            showPlayerPage();
        });"""
new_search = """        searchResultsList.setOnItemClickListener((parent, view, position, id) -> {
            if (position < 0 || position >= searchResults.size()) return;
            final int selectedPosition = position;
            showPlayerPage();
            if (playerPanel != null) {
                playerPanel.postDelayed(() -> playSongFromSearch(selectedPosition), 20L);
            } else {
                playSongFromSearch(selectedPosition);
            }
        });"""
if old_search in text:
    text = text.replace(old_search, new_search, 1)
elif new_search not in text:
    raise SystemExit("search click block missing")

old_playlist = """            if (actualIndex < 0) return;
            playSongFromPlaylist(actualIndex);
            showPlayerPage();"""
new_playlist = """            if (actualIndex < 0) return;
            final int selectedIndex = actualIndex;
            showPlayerPage();
            if (playerPanel != null) {
                playerPanel.postDelayed(() -> playSongFromPlaylist(selectedIndex), 20L);
            } else {
                playSongFromPlaylist(selectedIndex);
            }"""
if old_playlist in text:
    text = text.replace(old_playlist, new_playlist, 1)
elif new_playlist not in text:
    raise SystemExit("playlist click block missing")

method_start = text.find("    private void attachExistingFriendlyCache(Song song) {")
if method_start < 0:
    raise SystemExit("attachExistingFriendlyCache missing")
method_end = text.find("\n    private ", method_start + 20)
if method_end < 0:
    raise SystemExit("attachExistingFriendlyCache end missing")
fast_method = '''    private void attachExistingFriendlyCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return;

        // Click-to-play must never walk SAF/filesystem on the UI thread. Trust
        // recorded state and the SharedPreferences-backed Media3 export index;
        // a stale URI is cleared by the normal asynchronous playback failure path.
        if (Looper.myLooper() == Looper.getMainLooper()) {
            String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();
            if (!recorded.isEmpty()) return;
            String media3Key = Media3CacheStore.keyFor(
                song.title, song.artist, song.catalogJson);
            String indexedUri = Media3PlaybackCacheIndex.friendlyUri(this, media3Key);
            if (!indexedUri.isEmpty()) {
                recoverCachedSongState(song, indexedUri);
            }
            return;
        }

        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        String uri = CacheStorage.findAudioUri(this, key);
        if (uri.isEmpty()) {
            String media3Key = Media3CacheStore.keyFor(song.title, song.artist, song.catalogJson);
            uri = Media3PlaybackCacheIndex.friendlyUri(this, media3Key);
        }
        if (!uri.isEmpty() && CacheFileState.exists(this, uri)) {
            boolean changed = recoverCachedSongState(song, uri);
            if (changed) savePlaylists();
        }
    }
'''
text = text[:method_start] + fast_method + text[method_end:]

replace_anchor = """        statusView.setText("歌曲版本已替换，正在按新版本缓存播放");
        toast("已替换歌单中的歌曲版本");
        playSong(target);
    }

    private void persistResolvedCatalogToPlaylistCopies(Song song, String originalKey) {"""
replacement = '''        statusView.setText("歌曲版本已替换，正在按新版本缓存播放");
        toast("已替换歌单中的歌曲版本");
        int cacheSerial = ++replacementCacheSerial;
        playSong(target);
        cacheReplacedPlaylistSongAsync(target, cacheSerial);
    }

    private void cacheReplacedPlaylistSongAsync(Song song, int cacheSerial) {
        if (song == null || !song.isNetworkCatalog()) return;
        final String requestedCatalog = song.catalogJson == null ? "" : song.catalogJson.trim();
        final String originalKey = song.key();
        if (requestedCatalog.isEmpty()) return;

        searchCacheExecutor.submit(() -> {
            try {
                NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
                    this,
                    requestedCatalog,
                    true,
                    message -> {
                        if (message == null || message.trim().isEmpty()) return;
                        runOnUiThread(() -> {
                            if (activityDestroyed || cacheSerial != replacementCacheSerial) return;
                            if (currentSong == song && statusView != null) {
                                statusView.setText("替换版本正在后台缓存：" + message);
                            }
                        });
                    }
                );
                runOnUiThread(() -> {
                    if (activityDestroyed || cacheSerial != replacementCacheSerial) return;
                    if (cached.catalogJson != null && !cached.catalogJson.trim().isEmpty()) {
                        song.catalogJson = cached.catalogJson;
                    }
                    if (cached.sourceCode != null && !cached.sourceCode.trim().isEmpty()) {
                        song.source = CatalogSearch.labelForSource(cached.sourceCode);
                    }
                    if (song.artworkUrl == null || song.artworkUrl.trim().isEmpty()) {
                        song.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(song.catalogJson);
                    }
                    song.cachedUri = cached.audioUri;
                    song.uri = cached.audioUri;
                    song.cacheFailed = false;
                    song.unavailable = false;
                    song.autoUnavailable = false;
                    song.manualUnavailable = false;
                    if ((song.lyric == null || song.lyric.trim().isEmpty())
                        && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                        song.lyric = cached.lyric;
                        song.lyricLabel = song.title + " · " + song.artist + " · " + song.source;
                    }
                    persistResolvedCatalogToPlaylistCopies(song, originalKey);
                    savePlaylists();
                    renderCurrentPlaylist();
                    updatePlaylistCacheButtonVisibility();
                    if (currentSong == song && statusView != null) {
                        statusView.setText("替换歌曲版本缓存已完成");
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (activityDestroyed || cacheSerial != replacementCacheSerial) return;
                    updatePlaylistCacheButtonVisibility();
                    if (currentSong == song && statusView != null) {
                        statusView.setText("替换版本可继续播放；自动缓存未完成，可稍后一键缓存");
                    }
                });
            }
        });
    }

    private void persistResolvedCatalogToPlaylistCopies(Song song, String originalKey) {'''
if replace_anchor in text:
    text = text.replace(replace_anchor, replacement, 1)
elif "cacheReplacedPlaylistSongAsync" not in text:
    raise SystemExit("replacement cache anchor missing")

main.write_text(text, encoding="utf-8")
