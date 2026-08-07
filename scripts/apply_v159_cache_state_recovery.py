from pathlib import Path

root = Path(__file__).resolve().parents[1]
main_path = root / "app/src/main/java/com/jianglab/babywife/MainActivity.java"
gradle_path = root / "app/build.gradle"
main = main_path.read_text(encoding="utf-8")
gradle = gradle_path.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)

# Playlist cache scans run on background executors, so they can verify the real
# file instead of trusting a stale cachedUri flag.
main = replace_once(
    main,
    "            if (songHasRecordedCache(song)) continue;\n            result.add(song);",
    "            if (songHasPlayableCache(song)) continue;\n            result.add(song);",
    "uncached network classification",
)
main = replace_once(
    main,
    "                if (songHasRecordedCache(song)) {\n                    done++;\n                    continue;\n                }",
    "                if (songHasPlayableCache(song)) {\n                    done++;\n                    continue;\n                }",
    "one-click cache existing-file verification",
)

old_playable = '''    private boolean songHasPlayableCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return true;
        if (NetworkMediaCache.cachedAudioExists(this, song.cachedUri)) return true;
        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        String existingUri = key.isEmpty() ? "" : CacheStorage.findAudioUri(this, key);
        if (NetworkMediaCache.cachedAudioExists(this, existingUri)) {
            song.cachedUri = existingUri;
            song.uri = existingUri;
            song.cacheFailed = false;
            return true;
        }
        return false;
    }'''
new_playable = '''    private boolean songHasPlayableCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return true;
        String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (NetworkMediaCache.cachedAudioExists(this, recorded)) {
            boolean changed = recoverCachedSongState(song, recorded);
            if (changed) savePlaylists();
            return true;
        }
        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        String existingUri = key.isEmpty() ? "" : CacheStorage.findAudioUri(this, key);
        if (!NetworkMediaCache.cachedAudioExists(this, existingUri)) {
            String media3Key = Media3CacheStore.keyFor(
                song.title, song.artist, song.catalogJson);
            existingUri = Media3PlaybackCacheIndex.friendlyUri(this, media3Key);
        }
        if (NetworkMediaCache.cachedAudioExists(this, existingUri)) {
            boolean changed = recoverCachedSongState(song, existingUri);
            if (changed) savePlaylists();
            return true;
        }
        return false;
    }

    /**
     * A verified friendly cache is authoritative: once Android can really read
     * the file, every stale red/failure flag for the same logical playlist song
     * must be cleared and all playlist copies must point at the playable file.
     */
    private boolean recoverCachedSongState(Song song, String playableUri) {
        if (song == null || playableUri == null || playableUri.trim().isEmpty()) return false;
        String uri = playableUri.trim();
        String logicalKey = dedupeKey(song);
        String catalogId = catalogIdentity(song.catalogJson);
        boolean changed = applyRecoveredCacheState(song, uri);
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item == null || item == song) continue;
                boolean sameLogicalSong = dedupeKey(item).equals(logicalKey);
                boolean sameCatalog = !catalogId.isEmpty()
                    && catalogId.equals(catalogIdentity(item.catalogJson));
                if (!sameLogicalSong && !sameCatalog) continue;
                changed |= applyRecoveredCacheState(item, uri);
            }
        }
        return changed;
    }

    private boolean applyRecoveredCacheState(Song song, String uri) {
        if (song == null) return false;
        boolean changed = !uri.equals(song.cachedUri)
            || !uri.equals(song.uri)
            || song.unavailable
            || song.autoUnavailable
            || song.manualUnavailable
            || song.manualAttempt
            || song.cacheFailed;
        song.cachedUri = uri;
        song.uri = uri;
        song.unavailable = false;
        song.autoUnavailable = false;
        song.manualUnavailable = false;
        song.manualAttempt = false;
        song.cacheFailed = false;
        return changed;
    }'''
main = replace_once(main, old_playable, new_playable, "playable cache recovery")

old_attach = '''    private void attachExistingFriendlyCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return;
        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        String uri = CacheStorage.findAudioUri(this, key);
        if (uri.isEmpty()) {
            String media3Key = Media3CacheStore.keyFor(song.title, song.artist, song.catalogJson);
            uri = Media3PlaybackCacheIndex.friendlyUri(this, media3Key);
        }
        if (!uri.isEmpty() && CacheFileState.exists(this, uri)) {
            song.cachedUri = uri;
        }
    }'''
new_attach = '''    private void attachExistingFriendlyCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return;
        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        String uri = CacheStorage.findAudioUri(this, key);
        if (uri.isEmpty()) {
            String media3Key = Media3CacheStore.keyFor(song.title, song.artist, song.catalogJson);
            uri = Media3PlaybackCacheIndex.friendlyUri(this, media3Key);
        }
        if (!uri.isEmpty() && CacheFileState.exists(this, uri)) {
            boolean changed = recoverCachedSongState(song, uri);
            if (changed) {
                savePlaylists();
                if (Looper.myLooper() == Looper.getMainLooper()) {
                    if (playlistAdapter != null) playlistAdapter.notifyDataSetChanged();
                    if (resultAdapter != null) resultAdapter.notifyDataSetChanged();
                    updatePlaylistCacheButtonVisibility();
                }
            }
        }
    }'''
main = replace_once(main, old_attach, new_attach, "attach existing friendly cache")

old_refresh = '''        song.cachedUri = CacheFileState.exists(this, uri) ? uri : "";
        if (!song.cachedUri.isEmpty()) song.uri = song.cachedUri;'''
new_refresh = '''        if (CacheFileState.exists(this, uri)) {
            recoverCachedSongState(song, uri);
        } else {
            song.cachedUri = "";
        }'''
main = replace_once(main, old_refresh, new_refresh, "migration cache refresh")

# A completed playback export must clear every failure marker, including the
# manual-unavailable flag that v158 left behind.
main = replace_once(
    main,
    '''                item.cacheFailed = false;
                item.autoUnavailable = false;
                item.unavailable = false;
                changed = true;''',
    '''                item.cacheFailed = false;
                item.autoUnavailable = false;
                item.manualUnavailable = false;
                item.manualAttempt = false;
                item.unavailable = false;
                changed = true;''',
    "search export state clear",
)

# One-click cache success also updates any same-song copies across playlists.
main = replace_once(
    main,
    '''                    song.cacheFailed = false;
                    song.unavailable = false;
                    song.autoUnavailable = false;
                    song.manualUnavailable = false;
                    done++;''',
    '''                    song.cacheFailed = false;
                    song.unavailable = false;
                    song.autoUnavailable = false;
                    song.manualUnavailable = false;
                    song.manualAttempt = false;
                    recoverCachedSongState(song, cached.audioUri);
                    done++;''',
    "one-click cache success state clear",
)

# Version bump only; no UI resources are touched.
gradle = replace_once(
    gradle,
    "        versionCode 2026080758\n        versionName \"2026.08.07.v158-active-playback-cache-export\"",
    "        versionCode 2026080759\n        versionName \"2026.08.07.v159-cache-state-recovery\"",
    "v159 version",
)

required = [
    "recoverCachedSongState(song, recorded)",
    "song.manualUnavailable = false;",
    "playlistAdapter.notifyDataSetChanged()",
    "if (songHasPlayableCache(song)) continue;",
    "versionCode 2026080759",
]
combined = main + "\n" + gradle
for token in required:
    if token not in combined:
        raise SystemExit("missing required v159 token: " + token)

main_path.write_text(main, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")
