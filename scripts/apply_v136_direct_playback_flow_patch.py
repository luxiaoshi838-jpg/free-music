from pathlib import Path

root = Path(__file__).resolve().parents[1]
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
network_path = root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'
project_log_path = root / 'PROJECT_LOG.md'
changelog_path = root / 'docs/CHANGELOG.md'


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'Cannot find {label} in {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def append_once(path: Path, marker: str, body: str) -> None:
    text = path.read_text(encoding='utf-8')
    if marker in text:
        return
    path.write_text(text.rstrip() + '\n\n' + body.rstrip() + '\n', encoding='utf-8')

replace_once(
    gradle_path,
    'versionCode 2026080135\n        versionName "2026.08.04.playlist-cache-immediate-play"',
    'versionCode 2026080136\n        versionName "2026.08.04.direct-playback-before-lyrics"',
    'v136 version',
)

# Do not start lyric matching before network playback is ready.
replace_once(
    main_path,
    '        statusView.setText("当前选择：" + song.title);\n'
    '        showSongLyrics(song);\n'
    '        publishPlaybackControlState(true);\n\n'
    '        if (song.isNetworkCatalog()) {',
    '        statusView.setText("当前选择：" + song.title);\n'
    '        if (song.isNetworkCatalog()) {\n'
    '            lyricLines.clear();\n'
    '            highlightedLyricIndex = -1;\n'
    '            if (song.lyric != null && !song.lyric.trim().isEmpty()) {\n'
    '                applyLyricText(song.lyric);\n'
    '            } else {\n'
    '                lyricView.setText("正在准备音频，播放开始后再匹配歌词...");\n'
    '            }\n'
    '        } else {\n'
    '            showSongLyrics(song);\n'
    '        }\n'
    '        publishPlaybackControlState(true);\n\n'
    '        if (song.isNetworkCatalog()) {',
    'defer lyric matching until playback',
)

# Replace complex playlist cache lookup with direct recorded-uri -> exact-key -> network flow.
start = main_path.read_text(encoding='utf-8').index('    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {')
end = main_path.read_text(encoding='utf-8').index('    private void cacheAndPlay(Song song, int playToken) {', start)
text = main_path.read_text(encoding='utf-8')
new_method = '''    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {
        String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (!recorded.isEmpty()) {
            song.uri = recorded;
            statusView.setText("已读取歌单记录缓存，正在启动播放...");
            startLocalPlayback(song, playToken, null, () -> {
                song.cachedUri = "";
                song.uri = "";
                playPlaylistSongFromExactCache(song, playToken);
            });
            return;
        }
        playPlaylistSongFromExactCache(song, playToken);
    }

    private void playPlaylistSongFromExactCache(Song song, int playToken) {
        statusView.setText("正在读取歌单精确缓存...");
        new Thread(() -> {
            String exactKey = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
            String exactUri = exactKey.isEmpty() ? "" : CacheStorage.findAudioUri(this, exactKey);
            runOnUiThread(() -> {
                if (currentSong != song || playToken != playbackRequestSerial) return;
                if (exactUri == null || exactUri.trim().isEmpty()) {
                    statusView.setText("歌单没有精确缓存，开始获取音频...");
                    cacheAndPlay(song, playToken);
                    return;
                }
                song.cachedUri = exactUri;
                song.uri = exactUri;
                song.cacheFailed = false;
                statusView.setText("已找到歌单精确缓存，正在启动播放...");
                startLocalPlayback(song, playToken, null, () -> {
                    CacheStorage.deleteKey(this, exactKey);
                    song.cachedUri = "";
                    song.uri = "";
                    statusView.setText("精确缓存无法播放，开始重新获取音频...");
                    cacheAndPlay(song, playToken);
                });
            });
        }, "playlist-exact-cache-lookup").start();
    }

'''
main_path.write_text(text[:start] + new_method + text[end:], encoding='utf-8')

# On playback start, only then start lyric display/matching.
replace_once(
    main_path,
    '        statusView.setText("当前播放：" + song.title);\n'
    '        if (onStarted != null) onStarted.run();\n'
    '        publishPlaybackControlState(true);',
    '        statusView.setText("当前播放：" + song.title);\n'
    '        if (song.isNetworkCatalog()) showSongLyrics(song);\n'
    '        if (onStarted != null) onStarted.run();\n'
    '        publishPlaybackControlState(true);',
    'lyric matching after playback starts',
)

# If a cached result fails at the actual player, delete it and retry once via network.
replace_once(
    main_path,
    '                    startLocalPlayback(song, playToken,\n'
    '                        () -> commitResolvedPlayback(song, commit, playToken),\n'
    '                        () -> markPlaybackFailure(song, true));',
    '                    startLocalPlayback(song, playToken,\n'
    '                        () -> commitResolvedPlayback(song, commit, playToken),\n'
    '                        () -> {\n'
    '                            if (cached.audioFromCache) {\n'
    '                                NetworkMediaCache.deleteCatalogCache(this, cached.catalogJson);\n'
    '                                song.cachedUri = "";\n'
    '                                song.uri = "";\n'
    '                                statusView.setText("已有缓存无法播放，正在重新获取音频...");\n'
    '                                cacheAndPlay(song, playToken);\n'
    '                            } else {\n'
    '                                markPlaybackFailure(song, true);\n'
    '                            }\n'
    '                        });',
    'retry failed cached result',
)

# Network search must not scan all same-title caches before starting.
network = network_path.read_text(encoding='utf-8')
block_start = network.index('        status(callback, "正在检查这首歌是否已有可播放缓存...");')
block_end = network.index('        CacheStorage.ensureFriendlyNames(context, requestedKey, requestedTitle, requestedArtist,', block_start)
replacement = '''        status(callback, "正在检查当前搜索结果的精确缓存...");
'''
network = network[:block_start] + replacement + network[block_end:]
network_path.write_text(network, encoding='utf-8')

# Use a cheap existence check; actual MediaPlayer async prepare decides playability.
replace_once(
    network_path,
    '            if (PlayableAudioResolver.cachedAudioExists(context, requestedAudioUri)) {',
    '            if (CacheStorage.exists(context, requestedAudioUri)) {',
    'cheap exact cache existence check',
)
replace_once(
    network_path,
    '                status(callback, "已找到原来源缓存，直接播放");',
    '                status(callback, "已找到当前搜索结果的精确缓存，立即启动播放");',
    'exact cache status',
)

# Requirements.
check = check_path.read_text(encoding='utf-8')
check = check.replace("'version bumped': 'versionCode 2026080135' in gradle,", "'direct playback before lyrics and no global cache scan': (\n        'playPlaylistSongFromExactCache' in main\n        and 'playlist-exact-cache-lookup' in main\n        and '正在准备音频，播放开始后再匹配歌词' in main\n        and 'if (song.isNetworkCatalog()) showSongLyrics(song);' in main\n        and 'CacheStorage.findAudioMatches(this, song.title, song.artist)' not in main[main.find('private void playPlaylistSongFromCacheFirst'):main.find('private void cacheAndPlay')]\n        and '正在检查当前搜索结果的精确缓存' in network\n        and 'findAudioMatches(context, requestedTitle, requestedArtist)' not in network[network.find('private static CacheResult cacheLocked'):network.find('CacheStorage.ensureFriendlyNames')]\n        and 'CacheStorage.exists(context, requestedAudioUri)' in network\n        and 'NetworkMediaCache.deleteCatalogCache(this, cached.catalogJson)' in main\n    ),\n    'version bumped': 'versionCode 2026080136' in gradle,")
check_path.write_text(check, encoding='utf-8')

append_once(
    project_log_path,
    'Direct playback before lyrics and remove global cache scan',
    '''## 2026-08-04 - Direct playback before lyrics and remove global cache scan

- Reverted the v135 broad same-title cache scan from the playback critical path.
- Playlist playback now tries the recorded URI directly, then the exact catalog key, then network retrieval.
- Search playback checks only the current result's exact cache key and never scans the whole cache folder first.
- Lyrics begin only after MediaPlayer reports that audio playback has started.
- A stale exact cache is deleted and reacquired only after the actual player rejects it.''',
)
append_once(
    changelog_path,
    'direct-playback-before-lyrics',
    '''## 2026.08.04.direct-playback-before-lyrics

- Removed the slow global cache lookup introduced in v135.
- Playlist tracks now start from their recorded URI or exact catalog cache without pre-scanning the folder.
- Search tracks no longer run lyric matching before audio is ready.
- Playback starts first; lyrics and duplicate cleanup remain background work.''',
)

print('v136 direct playback flow patch applied')
