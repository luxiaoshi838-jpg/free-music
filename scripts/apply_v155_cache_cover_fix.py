from pathlib import Path
import re

ROOT = Path('.')


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1, found {count}')
    return text.replace(old, new, 1)


def replace_method(text, start_marker, next_marker, replacement, label):
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f'{label}: start missing')
    end = text.find(next_marker, start + len(start_marker))
    if end < 0:
        raise SystemExit(f'{label}: end missing')
    return text[:start] + replacement.rstrip() + '\n\n' + text[end:]

# MainActivity
path = ROOT / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
text = path.read_text(encoding='utf-8')
text = replace_once(text,
    'private final ExecutorService searchCacheExecutor = Executors.newSingleThreadExecutor();',
    'private final ExecutorService searchCacheExecutor = Executors.newFixedThreadPool(2);',
    'cache executor')

text = replace_method(text,
    '    private void cancelSearchCacheTask() {',
    '    private void releaseMediaPlayer(',
    '''    private void cancelSearchCacheTask() {
        // Playback cache completion is intentionally not cancelled by song switches.
        // All queued tasks are stopped only when the Activity is destroyed and the
        // executor is shut down. This prevents "playable but never exported" songs.
        if (!activityDestroyed) return;
        Future<?> task = searchCacheFuture;
        searchCacheFuture = null;
        if (task != null) task.cancel(true);
    }''',
    'cancel cache task')

text = replace_method(text,
    '    private void cacheSearchPlaybackAsync(Song song, SearchQuickPlayback.Candidate candidate,',
    '    private void persistSearchCacheToPlaylistCopies(Song song,',
    '''    private void cacheSearchPlaybackAsync(Song song, SearchQuickPlayback.Candidate candidate,
                                          int playToken) {
        if (song == null || candidate == null) return;
        String media3Key = Media3CacheStore.keyFor(song.title, song.artist, candidate.catalogJson);
        if (song.artworkUrl.isEmpty()) {
            song.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(candidate.catalogJson);
        }
        Media3PlaybackCacheIndex.record(this, media3Key, song.title, song.artist,
            candidate.catalogJson, song.artworkUrl);
        searchCacheExecutor.submit(() -> {
            SearchQuickPlayback.Candidate exportCandidate = candidate;
            Exception lastError = null;
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
                            if (activityDestroyed || currentSong != song) return;
                            if (totalBytes <= 0L) return;
                            int percent = (int) Math.max(0L, Math.min(100L,
                                cachedBytes * 100L / totalBytes));
                            int previous = lastPercent.getAndSet(percent);
                            if (percent != 100 && previous >= 0 && percent - previous < 5) return;
                            runOnUiThread(() -> {
                                if (!activityDestroyed && currentSong == song && statusView != null) {
                                    statusView.setText("正在在线播放并补齐缓存：" + percent + "%"
                                        + (currentAttempt > 0 ? "（续传）" : ""));
                                }
                            });
                        }
                    );
                    Media3PlaybackCacheIndex.markExported(this, media3Key, storedUri);
                    SearchQuickPlayback.Candidate completedCandidate = exportCandidate;
                    runOnUiThread(() -> {
                        if (activityDestroyed) return;
                        song.cachedUri = storedUri;
                        persistSearchCacheToPlaylistCopies(song, completedCandidate, storedUri);
                        savePlaylists();
                        if (currentSong == song) {
                            int position = 0;
                            try {
                                if (mediaPlayer != null) position = mediaPlayer.getCurrentPosition();
                            } catch (Exception ignored) {
                            }
                            saveLastSong(position);
                            statusView.setText("当前播放：" + song.title
                                + "（缓存已保存为“" + song.title + " - " + song.artist + "”）");
                            publishPlaybackControlState(true);
                        }
                    });
                    return;
                } catch (Exception error) {
                    lastError = error;
                    if (Thread.currentThread().isInterrupted()) return;
                    if (attempt == 0) {
                        try {
                            SearchQuickPlayback.Candidate refreshed =
                                SearchQuickPlayback.resolveStage(exportCandidate.catalogJson, 0);
                            if (refreshed != null && !refreshed.playbackUrl.isEmpty()) {
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
                    String detail = failure == null || failure.getMessage() == null
                        ? "未知错误" : failure.getMessage();
                    statusView.setText("当前播放正常，但后台缓存失败：" + detail);
                }
            });
        });
    }

    private void attachExistingFriendlyCache(Song song) {
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
    }''',
    'cache method')

text = replace_once(text,
    '    private void addSongToCurrentPlaylist(Song song) {\n        if (song == null) return;',
    '    private void addSongToCurrentPlaylist(Song song) {\n        if (song == null) return;\n        attachExistingFriendlyCache(song);',
    'attach cache before add')

text = replace_once(text,
    '                    song.source = resolved.sourceLabel;\n                    artistView.setText(song.artist + " · " + song.source);',
    '                    song.source = resolved.sourceLabel;\n                    if (song.artworkUrl.isEmpty()) {\n                        song.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(resolved.catalogJson);\n                    }\n                    artistView.setText(song.artist + " · " + song.source);',
    'resolved artwork')

text = replace_once(text,
    '                    String media3Key = Media3CacheStore.keyFor(\n                        song.title, song.artist, song.catalogJson);',
    '                    String media3Key = Media3CacheStore.keyFor(\n                        song.title, song.artist, song.catalogJson);\n                    Media3PlaybackCacheIndex.record(this, media3Key, song.title,\n                        song.artist, song.catalogJson, song.artworkUrl);',
    'record playback cache')

text = replace_once(text,
    '            notificationCatalog,\n            notificationUri\n        );',
    '            notificationCatalog,\n            currentSong == null ? "" : currentSong.artworkUrl,\n            notificationUri\n        );',
    'publish artwork url')

text = replace_once(text,
    '        Song copy = new Song(song.title, song.artist, song.source, song.lyric,\n            song.uri, song.catalogJson, song.cachedUri);\n        copy.lyricLabel = song.lyricLabel;',
    '        Song copy = new Song(song.title, song.artist, song.source, song.lyric,\n            song.uri, song.catalogJson, song.cachedUri);\n        copy.artworkUrl = song.artworkUrl;\n        copy.lyricLabel = song.lyricLabel;',
    'copy artwork')

text = replace_once(text,
    '        if (empty(keeper.catalogJson) && !empty(candidate.catalogJson)) keeper.catalogJson = candidate.catalogJson;\n        if (empty(keeper.cachedUri) && !empty(candidate.cachedUri)) keeper.cachedUri = candidate.cachedUri;',
    '        if (empty(keeper.catalogJson) && !empty(candidate.catalogJson)) keeper.catalogJson = candidate.catalogJson;\n        if (empty(keeper.artworkUrl) && !empty(candidate.artworkUrl)) keeper.artworkUrl = candidate.artworkUrl;\n        if (empty(keeper.cachedUri) && !empty(candidate.cachedUri)) keeper.cachedUri = candidate.cachedUri;',
    'merge artwork')

text = replace_once(text,
    '        String catalogJson;\n        String cachedUri;',
    '        String catalogJson;\n        String artworkUrl;\n        String cachedUri;',
    'song field')

text = replace_once(text,
    '            this.catalogJson = catalogJson == null ? "" : catalogJson;\n            this.cachedUri = cachedUri == null ? "" : cachedUri;',
    '            this.catalogJson = catalogJson == null ? "" : catalogJson;\n            this.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(this.catalogJson);\n            this.cachedUri = cachedUri == null ? "" : cachedUri;',
    'song constructor artwork')

text = replace_once(text,
    '        static Song fromCatalog(CatalogSearch.Track track) {\n            return new Song(',
    '        static Song fromCatalog(CatalogSearch.Track track) {\n            Song song = new Song(',
    'from catalog return start')
text = replace_once(text,
    '                track.rawJson,\n                ""\n            );\n        }',
    '                track.rawJson,\n                ""\n            );\n            song.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(track.rawJson);\n            return song;\n        }',
    'from catalog return end')

text = replace_once(text,
    '                object.put("catalogJson", catalogJson);\n                object.put("cachedUri", cachedUri);',
    '                object.put("catalogJson", catalogJson);\n                object.put("artworkUrl", artworkUrl);\n                object.put("cachedUri", cachedUri);',
    'serialize artwork')

text = replace_once(text,
    '            song.lyricLabel = object.optString("lyricLabel", "");',
    '            song.artworkUrl = object.optString("artworkUrl",\n                PlaybackArtworkLoader.extractArtworkUrl(song.catalogJson));\n            song.lyricLabel = object.optString("lyricLabel", "");',
    'deserialize artwork')

# In broom, only preserve Media3 spans for playlist songs lacking a friendly file.
old = '''                    String media3Key = Media3CacheStore.keyFor(
                        song.title, song.artist, song.catalogJson);
                    if (!media3Key.isEmpty()) keepMedia3Keys.add(media3Key);'''
new = '''                    String media3Key = Media3CacheStore.keyFor(
                        song.title, song.artist, song.catalogJson);
                    attachExistingFriendlyCache(song);
                    boolean hasFriendly = !song.cachedUri.isEmpty()
                        && CacheFileState.exists(this, song.cachedUri);
                    if (!media3Key.isEmpty() && !hasFriendly) keepMedia3Keys.add(media3Key);'''
text = replace_once(text, old, new, 'broom keep logic')

path.write_text(text, encoding='utf-8')

# PlaybackArtworkLoader
path = ROOT / 'app/src/main/java/com/jianglab/babywife/PlaybackArtworkLoader.java'
text = path.read_text(encoding='utf-8')
text = replace_once(text,
    '''    static Bitmap load(Context context, String title, String artist,
                       String catalogJson, String mediaUri) {
        if (context == null) return null;''',
    '''    static Bitmap load(Context context, String title, String artist,
                       String catalogJson, String mediaUri) {
        return load(context, title, artist, catalogJson, "", mediaUri);
    }

    static Bitmap load(Context context, String title, String artist,
                       String catalogJson, String explicitArtworkUrl,
                       String mediaUri) {
        if (context == null) return null;''',
    'loader overload')
text = replace_once(text,
    '''        bitmap = embeddedArtwork(context, mediaUri);
        if (bitmap == null) {
            String url = findArtworkUrl(catalogJson);
            if (!url.isEmpty()) bitmap = downloadArtwork(url);
        }''',
    '''        bitmap = embeddedArtwork(context, mediaUri);
        if (bitmap == null) {
            String url = explicitArtworkUrl == null ? "" : explicitArtworkUrl.trim();
            if (url.isEmpty()) url = findArtworkUrl(catalogJson);
            if (!url.isEmpty()) bitmap = downloadArtwork(url);
        }''',
    'explicit artwork priority')
text = replace_once(text,
    '    private static String findArtworkUrl(String catalogJson) {',
    '    static String extractArtworkUrl(String catalogJson) {\n        return findArtworkUrl(catalogJson);\n    }\n\n    private static String findArtworkUrl(String catalogJson) {',
    'extract artwork method')
path.write_text(text, encoding='utf-8')

# PlaybackControlService
path = ROOT / 'app/src/main/java/com/jianglab/babywife/PlaybackControlService.java'
text = path.read_text(encoding='utf-8')
text = replace_once(text,
    '    private static final String EXTRA_CATALOG_JSON = "catalog_json";\n    private static final String EXTRA_MEDIA_URI = "media_uri";',
    '    private static final String EXTRA_CATALOG_JSON = "catalog_json";\n    private static final String EXTRA_ARTWORK_URL = "artwork_url";\n    private static final String EXTRA_MEDIA_URI = "media_uri";',
    'service extra')
text = replace_once(text,
    '    private String catalogJson = "";\n    private String mediaUri = "";',
    '    private String catalogJson = "";\n    private String artworkUrl = "";\n    private String mediaUri = "";',
    'service field')
text = replace_once(text,
    '''        publishState(context, title, artist, playing, duration, position, "", "");
    }

    static void publishState(Context context, String title, String artist,
                             boolean playing, long duration, long position,
                             String catalogJson, String mediaUri) {''',
    '''        publishState(context, title, artist, playing, duration, position, "", "", "");
    }

    static void publishState(Context context, String title, String artist,
                             boolean playing, long duration, long position,
                             String catalogJson, String mediaUri) {
        publishState(context, title, artist, playing, duration, position,
            catalogJson, "", mediaUri);
    }

    static void publishState(Context context, String title, String artist,
                             boolean playing, long duration, long position,
                             String catalogJson, String artworkUrl, String mediaUri) {''',
    'service overload')
text = replace_once(text,
    '            .putExtra(EXTRA_CATALOG_JSON, catalogJson == null ? "" : catalogJson)\n            .putExtra(EXTRA_MEDIA_URI, mediaUri == null ? "" : mediaUri);',
    '            .putExtra(EXTRA_CATALOG_JSON, catalogJson == null ? "" : catalogJson)\n            .putExtra(EXTRA_ARTWORK_URL, artworkUrl == null ? "" : artworkUrl)\n            .putExtra(EXTRA_MEDIA_URI, mediaUri == null ? "" : mediaUri);',
    'service intent artwork')
text = replace_once(text,
    '            catalogJson = safe(intent.getStringExtra(EXTRA_CATALOG_JSON));\n            mediaUri = safe(intent.getStringExtra(EXTRA_MEDIA_URI));',
    '            catalogJson = safe(intent.getStringExtra(EXTRA_CATALOG_JSON));\n            artworkUrl = safe(intent.getStringExtra(EXTRA_ARTWORK_URL));\n            mediaUri = safe(intent.getStringExtra(EXTRA_MEDIA_URI));',
    'service read artwork')
text = replace_once(text,
    '        final String requestCatalog = catalogJson;\n        final String requestUri = mediaUri;',
    '        final String requestCatalog = catalogJson;\n        final String requestArtworkUrl = artworkUrl;\n        final String requestUri = mediaUri;',
    'service request field')
text = replace_once(text,
    '                this, requestTitle, requestArtist, requestCatalog, requestUri);',
    '                this, requestTitle, requestArtist, requestCatalog,\n                requestArtworkUrl, requestUri);',
    'service load artwork')
path.write_text(text, encoding='utf-8')

# CacheStorage details shows real internal playback cache.
path = ROOT / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java'
text = path.read_text(encoding='utf-8')
text = replace_once(text,
    '        text.append("\\n\\n删除歌单或歌曲只移除歌单记录，不删除歌曲和歌词文件；")',
    '        text.append("\\n\\n")\n            .append(Media3PlaybackCacheIndex.summary(context).displayText())\n            .append("\\n")\n            .append("删除歌单或歌曲只移除歌单记录，不删除歌曲和歌词文件；")',
    'cache details summary')
path.write_text(text, encoding='utf-8')

# Media3CacheStore removes index entries with spans.
path = ROOT / 'app/src/main/java/com/jianglab/babywife/Media3CacheStore.java'
text = path.read_text(encoding='utf-8')
text = replace_once(text,
    '            get(context).removeResource(key.trim());\n        } catch (Exception ignored) {',
    '            get(context).removeResource(key.trim());\n            Media3PlaybackCacheIndex.remove(context, key.trim());\n        } catch (Exception ignored) {',
    'remove index')
text = replace_once(text,
    '                    local.removeResource(key);\n                    removed++;',
    '                    local.removeResource(key);\n                    Media3PlaybackCacheIndex.remove(context, key);\n                    removed++;',
    'removeExcept index')
text = replace_once(text,
    '        } catch (Exception ignored) {\n        }\n        return removed;\n    }',
    '        } catch (Exception ignored) {\n        }\n        try {\n            Media3PlaybackCacheIndex.pruneToKeys(context, get(context).getKeys());\n        } catch (Exception ignored) {\n        }\n        return removed;\n    }',
    'prune index')
path.write_text(text, encoding='utf-8')

# Exporter records actual cache progress and friendly export.
path = ROOT / 'app/src/main/java/com/jianglab/babywife/Media3FriendlyCacheExporter.java'
text = path.read_text(encoding='utf-8')
text = replace_once(text,
    '        String storageKey = NetworkMediaCache.cacheKeyForCatalog(candidate.catalogJson);',
    '        String storageKey = NetworkMediaCache.cacheKeyForCatalog(candidate.catalogJson);\n        String artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(candidate.catalogJson);\n        Media3PlaybackCacheIndex.record(context, media3Key, title, artist,\n            candidate.catalogJson, artworkUrl);',
    'exporter record')
text = replace_once(text,
    '                if (requestLength > 0L) observedLength.set(requestLength);\n                if (callback != null) callback.onProgress(requestLength, bytesCached);',
    '                if (requestLength > 0L) observedLength.set(requestLength);\n                Media3PlaybackCacheIndex.updateProgress(\n                    context, media3Key, bytesCached, requestLength);\n                if (callback != null) callback.onProgress(requestLength, bytesCached);',
    'exporter progress')
text = replace_once(text,
    '            CacheStorage.deleteOtherSongCaches(context, title, artist, storageKey);\n            return storedUri;',
    '            CacheStorage.deleteOtherSongCaches(context, title, artist, storageKey);\n            Media3PlaybackCacheIndex.markExported(context, media3Key, storedUri);\n            return storedUri;',
    'exporter exported')
path.write_text(text, encoding='utf-8')

print('v155 combined cache/cover patch applied')
