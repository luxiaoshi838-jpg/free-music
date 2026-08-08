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
        if replacement in text:
            return text
        raise SystemExit("method not found: " + signature)
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit("method brace not found: " + signature)
    depth = 0
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement + text[i + 1:]
    raise SystemExit("unterminated method: " + signature)

main_path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = main_path.read_text(encoding="utf-8")

# Persist large playlists off the UI thread. Only a lightweight object copy is made
# synchronously; JSON building and SharedPreferences writes are serialized in background.
field_anchor = '''    private final ExecutorService playlistCacheScanExecutor = Executors.newSingleThreadExecutor();\n    private volatile int playlistCacheScanSerial = 0;'''
field_new = '''    private final ExecutorService playlistCacheScanExecutor = Executors.newSingleThreadExecutor();\n    private volatile int playlistCacheScanSerial = 0;\n    private final ExecutorService playlistPersistenceExecutor = Executors.newSingleThreadExecutor();\n    private volatile int playlistPersistenceSerial = 0;'''
if "playlistPersistenceExecutor" not in text:
    if field_anchor not in text:
        raise SystemExit("playlist persistence field anchor missing")
    text = text.replace(field_anchor, field_new, 1)

save_method = '''    private void savePlaylists() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            runOnUiThread(this::savePlaylists);
            return;
        }
        final List<Playlist> snapshot = new ArrayList<>();
        for (Playlist playlist : playlists) {
            if (playlist == null) continue;
            Playlist playlistCopy = new Playlist(playlist.name);
            for (Song song : playlist.songs) {
                if (song != null) playlistCopy.songs.add(copySongForPersistence(song));
            }
            snapshot.add(playlistCopy);
        }
        final int selectedIndex = currentPlaylistIndex;
        final int serial = ++playlistPersistenceSerial;
        try {
            playlistPersistenceExecutor.execute(() -> {
                if (serial != playlistPersistenceSerial) return;
                JSONArray array = new JSONArray();
                for (Playlist playlist : snapshot) array.put(playlist.toJson());
                if (serial != playlistPersistenceSerial) return;
                getApplicationContext().getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                    .edit()
                    .putString(KEY_PLAYLISTS, array.toString())
                    .putInt(KEY_CURRENT_PLAYLIST, selectedIndex)
                    .apply();
            });
        } catch (java.util.concurrent.RejectedExecutionException ignored) {
        }
    }

    private Song copySongForPersistence(Song song) {
        Song copy = new Song(song.title, song.artist, song.source, song.lyric,
            song.uri, song.catalogJson, song.cachedUri);
        copy.lyricLabel = song.lyricLabel;
        copy.artworkUrl = song.artworkUrl;
        copy.addedAt = song.addedAt;
        copy.unavailable = song.unavailable;
        copy.autoUnavailable = song.autoUnavailable;
        copy.manualUnavailable = song.manualUnavailable;
        copy.manualAttempt = song.manualAttempt;
        copy.cacheFailed = song.cacheFailed;
        return copy;
    }'''
text = replace_method(text, "    private void savePlaylists()", save_method)

# Media3 index recovery must never trigger one full-playlist save per song during a
# UI cache-state scan. State remains in memory and is persisted by the next coalesced save.
old_recover = '''        if (!indexedUri.isEmpty()) {\n            boolean changed = recoverCachedSongState(song, indexedUri);\n            if (changed) savePlaylists();\n            return true;\n        }'''
new_recover = '''        if (!indexedUri.isEmpty()) {\n            recoverCachedSongState(song, indexedUri);\n            return true;\n        }'''
text = replace_once(text, old_recover, new_recover, "remove per-song playlist save")

# Failed one-click cache entries must be visually red even when playback availability
# itself has not yet been declared unavailable.
text = replace_once(
    text,
    '            int color = song.unavailable ? Color.rgb(255, 96, 96) : TEXT_MAIN;',
    '            int color = (song.unavailable || song.cacheFailed) ? Color.rgb(255, 96, 96) : TEXT_MAIN;',
    "cache failure red marker",
)

# Never read lyric files through SAF synchronously on the UI thread.
hydrate_method = '''    private void hydrateLyricFromCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return;
        if (song.lyric != null && !song.lyric.trim().isEmpty()) return;
        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        if (key.isEmpty()) return;
        if (Looper.myLooper() == Looper.getMainLooper()) {
            try {
                searchCacheExecutor.submit(() -> {
                    String cachedLyric = CacheStorage.readLyricForSong(
                        this, key, song.title, song.artist);
                    if (cachedLyric == null || cachedLyric.trim().isEmpty()) return;
                    runOnUiThread(() -> {
                        if (activityDestroyed || song.lyric != null && !song.lyric.trim().isEmpty()) return;
                        song.lyric = cachedLyric;
                        if (song.lyricLabel == null || song.lyricLabel.trim().isEmpty()) {
                            song.lyricLabel = song.title + " / " + song.artist + " / " + song.source;
                        }
                        if (currentSong == song && lyricView != null) applyLyricText(cachedLyric);
                        if (isSongInAnyPlaylist(song)) savePlaylists();
                    });
                });
            } catch (java.util.concurrent.RejectedExecutionException ignored) {
            }
            return;
        }
        String cachedLyric = CacheStorage.readLyricForSong(this, key, song.title, song.artist);
        if (cachedLyric != null && !cachedLyric.trim().isEmpty()) {
            song.lyric = cachedLyric;
            if (song.lyricLabel == null || song.lyricLabel.trim().isEmpty()) {
                song.lyricLabel = song.title + " / " + song.artist + " / " + song.source;
            }
        }
    }'''
text = replace_method(text, "    private void hydrateLyricFromCache(Song song)", hydrate_method)

# Let already queued persistence work finish after Activity teardown instead of killing
# the last playlist state write.
destroy_anchor = '''        ++playlistCacheScanSerial;\n        playlistCacheScanExecutor.shutdownNow();'''
destroy_new = '''        ++playlistCacheScanSerial;\n        playlistCacheScanExecutor.shutdownNow();\n        playlistPersistenceExecutor.shutdown();'''
text = replace_once(text, destroy_anchor, destroy_new, "persistence executor shutdown")

main_path.write_text(text, encoding="utf-8")

# Cache validity has exactly two requirements: Android can really prepare it, and
# the measured duration is strictly greater than 60 seconds. No format/bitrate/source
# preference is introduced.
resolver_path = Path("app/src/main/java/com/jianglab/babywife/PlayableAudioResolver.java")
r = resolver_path.read_text(encoding="utf-8")
probe_anchor = '''                        AudioPlaybackVerifier.Probe probe = AudioPlaybackVerifier.probeFile(decodedSource);\n                        String actualExtension = detectAudioExtension(decodedSource,'''
probe_new = '''                        AudioPlaybackVerifier.Probe probe = AudioPlaybackVerifier.probeFile(decodedSource);\n                        if (probe.durationMs <= 60_000L) {\n                            throw new IllegalStateException("候选实际时长不超过60秒");\n                        }\n                        String actualExtension = detectAudioExtension(decodedSource,'''
r = replace_once(r, probe_anchor, probe_new, "minimum real duration")
resolver_path.write_text(r, encoding="utf-8")
