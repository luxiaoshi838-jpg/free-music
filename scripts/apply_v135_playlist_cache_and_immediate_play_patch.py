from pathlib import Path

root = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'Cannot find {label} in {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def append_once(path: Path, marker: str, block: str) -> None:
    text = path.read_text(encoding='utf-8')
    if marker in text:
        return
    path.write_text(text.rstrip() + '\n\n' + block.rstrip() + '\n', encoding='utf-8')

main = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
network = root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java'
gradle = root / 'app/build.gradle'
checks = root / 'scripts/check_feature_requirements.py'
project_log = root / 'PROJECT_LOG.md'
changelog = root / 'docs/CHANGELOG.md'

replace_once(
    gradle,
    'versionCode 2026080134\n        versionName "2026.08.04.single-cache-search-flow"',
    'versionCode 2026080135\n        versionName "2026.08.04.playlist-cache-immediate-play"',
    'v135 version',
)

# 1) Playlist playback has its own cache-first path, separate from search playback.
replace_once(
    main,
    '''        if (song.isNetworkCatalog()) {
            if (song.cachedUri != null && !song.cachedUri.trim().isEmpty()) {
                song.uri = song.cachedUri;
                startLocalPlayback(song, playToken, null, () -> {
                    song.cachedUri = "";
                    song.uri = "";
                    cacheAndPlay(song, playToken);
                });
                return;
            }
            stopPlayback();
            playButton.setText("▶");
            cacheAndPlay(song, playToken);
            return;
        }
''',
    '''        if (song.isNetworkCatalog()) {
            stopPlayback();
            playButton.setText("▶");
            if (!playingSearchQueue && isSongInAnyPlaylist(song)) {
                playPlaylistSongFromCacheFirst(song, playToken);
            } else {
                cacheAndPlay(song, playToken);
            }
            return;
        }
''',
    'separate playlist cache path',
)

playlist_method = '''    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {
        statusView.setText("正在读取歌单已有缓存...");
        new Thread(() -> {
            String playableUri = "";
            String matchedKey = "";
            String matchedCatalog = "";

            String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();
            if (NetworkMediaCache.cachedAudioExists(this, recorded)) {
                playableUri = recorded;
                matchedKey = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
                matchedCatalog = song.catalogJson;
            }

            if (playableUri.isEmpty()) {
                String exactKey = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
                String exactUri = exactKey.isEmpty() ? "" : CacheStorage.findAudioUri(this, exactKey);
                if (NetworkMediaCache.cachedAudioExists(this, exactUri)) {
                    playableUri = exactUri;
                    matchedKey = exactKey;
                    matchedCatalog = song.catalogJson;
                }
            }

            if (playableUri.isEmpty()) {
                for (CacheStorage.AudioMatch match :
                    CacheStorage.findAudioMatches(this, song.title, song.artist)) {
                    if (!NetworkMediaCache.cachedAudioExists(this, match.audioUri)) {
                        CacheStorage.deleteKey(this, match.key);
                        continue;
                    }
                    playableUri = match.audioUri;
                    matchedKey = match.key;
                    matchedCatalog = match.catalogJson;
                    break;
                }
            }

            String finalPlayableUri = playableUri;
            String finalMatchedKey = matchedKey;
            String finalMatchedCatalog = matchedCatalog;
            runOnUiThread(() -> {
                if (currentSong != song || playToken != playbackRequestSerial) return;
                if (finalPlayableUri.isEmpty()) {
                    song.cachedUri = "";
                    song.uri = "";
                    statusView.setText("歌单没有可播放缓存，开始寻找可用来源...");
                    cacheAndPlay(song, playToken);
                    return;
                }

                String originalKey = song.key();
                song.cachedUri = finalPlayableUri;
                song.uri = finalPlayableUri;
                if (finalMatchedCatalog != null && !finalMatchedCatalog.trim().isEmpty()) {
                    try {
                        JSONObject catalog = new JSONObject(finalMatchedCatalog);
                        String sourceCode = catalog.optString("source", "").trim();
                        if (!sourceCode.isEmpty()) song.source = CatalogSearch.labelForSource(sourceCode);
                        song.catalogJson = finalMatchedCatalog;
                    } catch (Exception ignored) {
                    }
                }
                persistResolvedCatalogToPlaylistCopies(song, originalKey);
                song.cacheFailed = false;
                song.unavailable = false;
                song.autoUnavailable = false;
                savePlaylists();
                renderCurrentPlaylist();
                statusView.setText("已读取歌单缓存，正在启动播放...");
                NetworkMediaCache.cleanupDuplicateSongCachesAsync(
                    this, song.title, song.artist, finalMatchedKey);
                startLocalPlayback(song, playToken, null, () -> {
                    song.cachedUri = "";
                    song.uri = "";
                    statusView.setText("歌单缓存无法播放，开始寻找可用来源...");
                    cacheAndPlay(song, playToken);
                });
            });
        }, "playlist-cache-lookup").start();
    }

'''
replace_once(
    main,
    '    private void cacheAndPlay(Song song, int playToken) {',
    playlist_method + '    private void cacheAndPlay(Song song, int playToken) {',
    'playlist cache lookup method',
)

# 2) Local/content playback also prepares asynchronously, so playback start never blocks the main thread.
replace_once(
    main,
    '''            if (song.uri.startsWith("http://") || song.uri.startsWith("https://")) {
                statusView.setText("正在打开在线音频...");
                mediaPlayer.setOnPreparedListener(player -> {
                    try {
                        if (currentSong != song || playToken != playbackRequestSerial) return;
                        player.start();
                        onPlaybackStarted(song, onStarted);
                    } catch (Exception error) {
                        stopPlayback();
                        playButton.setText("▶");
                        statusView.setText("播放失败：" + error.getMessage());
                        if (onFailed != null) onFailed.run();
                    }
                });
                mediaPlayer.prepareAsync();
            } else {
                mediaPlayer.prepare();
                mediaPlayer.start();
                onPlaybackStarted(song, onStarted);
            }
''',
    '''            boolean online = song.uri.startsWith("http://") || song.uri.startsWith("https://");
            statusView.setText(online ? "正在打开在线音频..." : "缓存已就绪，正在启动播放...");
            mediaPlayer.setOnPreparedListener(player -> {
                try {
                    if (currentSong != song || playToken != playbackRequestSerial) return;
                    player.start();
                    onPlaybackStarted(song, onStarted);
                } catch (Exception error) {
                    stopPlayback();
                    playButton.setText("▶");
                    statusView.setText("播放失败：" + error.getMessage());
                    if (onFailed != null) onFailed.run();
                }
            });
            mediaPlayer.prepareAsync();
''',
    'async prepare for cached audio',
)

# 3) Audio cache completion no longer waits for lyric network requests or duplicate cleanup.
replace_once(
    network,
    '''            String lyric = CacheStorage.readLyric(context, match.key);
            boolean lyricFromCache = !lyric.trim().isEmpty();
            if (!lyricFromCache) {
                status(callback, "已有音频缓存，正在补充歌词...");
                lyric = fetchLyrics(matchedCatalog.toString());
                if (!lyric.trim().isEmpty()) {
                    CacheStorage.writeLyric(context, match.key, lyric,
                        requestedTitle, requestedArtist, requestedAlbum, matchedCatalog.toString());
                }
            }
            CacheStorage.deleteOtherSongCaches(context, requestedTitle, requestedArtist, match.key);
''',
    '''            String lyric = CacheStorage.readLyric(context, match.key);
            boolean lyricFromCache = !lyric.trim().isEmpty();
            cleanupDuplicateSongCachesAsync(context, requestedTitle, requestedArtist, match.key);
''',
    'existing cache returns before lyric fetch',
)

replace_once(
    network,
    '''        String lyric = CacheStorage.readLyric(context, actualKey);
        boolean lyricFromCache = !lyric.trim().isEmpty();
        if (!lyricFromCache) {
            status(callback, sourceChanged
                ? "正在从实际平台读取匹配歌词..." : "正在按原平台读取歌词...");
            lyric = fetchLyrics(actualCatalog.toString());
            if (!lyric.trim().isEmpty()) {
                CacheStorage.writeLyric(context, actualKey, lyric, actualTitle, actualArtist,
                    actualAlbum, actualCatalog.toString());
            }
        }
        CacheStorage.deleteOtherSongCaches(context, requestedTitle, requestedArtist, actualKey);
        if (!CacheStorage.logicalIdentity(requestedTitle, requestedArtist).equals(
            CacheStorage.logicalIdentity(actualTitle, actualArtist))) {
            CacheStorage.deleteOtherSongCaches(context, actualTitle, actualArtist, actualKey);
        }
''',
    '''        String lyric = CacheStorage.readLyric(context, actualKey);
        boolean lyricFromCache = !lyric.trim().isEmpty();
        cleanupDuplicateSongCachesAsync(context, requestedTitle, requestedArtist, actualKey);
        if (!CacheStorage.logicalIdentity(requestedTitle, requestedArtist).equals(
            CacheStorage.logicalIdentity(actualTitle, actualArtist))) {
            cleanupDuplicateSongCachesAsync(context, actualTitle, actualArtist, actualKey);
        }
''',
    'new cache returns before lyric and cleanup',
)

replace_once(
    network,
    '''    private static Object[] createCacheLocks() {
        Object[] locks = new Object[32];
        for (int index = 0; index < locks.length; index++) locks[index] = new Object();
        return locks;
    }
''',
    '''    static void cleanupDuplicateSongCachesAsync(Context context, String title,
                                                     String artist, String keepKey) {
        if (context == null) return;
        new Thread(() -> CacheStorage.deleteOtherSongCaches(context, title, artist, keepKey),
            "duplicate-cache-cleanup").start();
    }

    private static Object[] createCacheLocks() {
        Object[] locks = new Object[32];
        for (int index = 0; index < locks.length; index++) locks[index] = new Object();
        return locks;
    }
''',
    'background duplicate cleanup method',
)

# Split checks into independent requirements and assert lyric/cleanup do not block audio return.
replace_once(
    checks,
    '''    'single logical cache per song and clear search flow': (
        'static final class AudioMatch' in cache
        and 'logicalIdentity(String title, String artist)' in cache
        and 'findAudioMatches(Context context, String title, String artist)' in cache
        and 'deleteOtherSongCaches' in cache
        and 'CACHE_LOCKS = createCacheLocks()' in network
        and 'cacheLocked(context, requestedCatalog, callback)' in network
        and '已找到同歌名和歌手的现有缓存，直接播放' in network
        and '唯一正式缓存已完成，其他来源候选已清理' in network
        and '尚未写入正式缓存' in playable_resolver
        and '候选下载进度' in playable_resolver
        and '唯一正式缓存写入完成' in playable_resolver
        and 'CacheStorage.findAudioUri(context, key)' not in playable_resolver[playable_resolver.find('for (JSONObject catalog : catalogs)'):playable_resolver.find('if (best == null')]
        and '播放请求已切换，停止旧候选下载' in main
    ),
    'version bumped': 'versionCode 2026080134' in gradle,
''',
    '''    'playlist playback reads existing cache before network search': (
        'playPlaylistSongFromCacheFirst(song, playToken)' in main
        and '正在读取歌单已有缓存' in main
        and 'CacheStorage.findAudioUri(this, exactKey)' in main
        and 'CacheStorage.findAudioMatches(this, song.title, song.artist)' in main
        and '已读取歌单缓存，正在启动播放' in main
        and '歌单没有可播放缓存，开始寻找可用来源' in main
        and '"playlist-cache-lookup"' in main
    ),
    'search candidates write only one formal cache': (
        'static final class AudioMatch' in cache
        and 'logicalIdentity(String title, String artist)' in cache
        and 'findAudioMatches(Context context, String title, String artist)' in cache
        and 'CACHE_LOCKS = createCacheLocks()' in network
        and 'cacheLocked(context, requestedCatalog, callback)' in network
        and '唯一正式缓存已完成，其他来源候选已清理' in network
        and '尚未写入正式缓存' in playable_resolver
        and '候选下载进度' in playable_resolver
        and '唯一正式缓存写入完成' in playable_resolver
        and 'CacheStorage.findAudioUri(context, key)' not in playable_resolver[playable_resolver.find('for (JSONObject catalog : catalogs)'):playable_resolver.find('if (best == null')]
        and '播放请求已切换，停止旧候选下载' in main
    ),
    'cached audio starts without waiting for lyrics or cleanup': (
        'cleanupDuplicateSongCachesAsync' in network
        and '"duplicate-cache-cleanup"' in network
        and '缓存已就绪，正在启动播放' in main
        and 'mediaPlayer.prepareAsync();' in main
        and 'mediaPlayer.prepare();' not in main[main.find('private void startLocalPlayback'):main.find('private void onPlaybackStarted')]
        and 'fetchLyrics(matchedCatalog.toString())' not in network
        and 'fetchLyrics(actualCatalog.toString())' not in network
    ),
    'version bumped': 'versionCode 2026080135' in gradle,
''',
    'separate v135 checks',
)

append_once(
    project_log,
    'Playlist cache lookup and immediate playback are independent',
    '''## 2026-08-04 - Playlist cache lookup and immediate playback are independent

- Playlist playback now has a dedicated cache-first path: recorded URI, exact source key, then normalized title+artist cache.
- Network source search starts only when all three playlist cache checks fail.
- Search result format/source trials remain temporary and still produce only one formal cache.
- Audio cache completion no longer waits for lyric network requests or duplicate cache cleanup.
- File/content MediaPlayer preparation now uses prepareAsync so a completed cache starts without blocking the main thread.''',
)
append_once(
    changelog,
    'playlist-cache-immediate-play',
    '''## 2026.08.04.playlist-cache-immediate-play

- Fixed playlist songs searching for a source even though a playable cache already existed.
- Kept search candidate deduplication as a separate flow from playlist cache lookup.
- Started cached audio immediately after final verification; lyrics continue asynchronously.
- Moved duplicate same-song cache cleanup to a background thread.
- Changed local/content playback from synchronous prepare to prepareAsync.''',
)

print('v135 playlist cache and immediate playback patch applied')
