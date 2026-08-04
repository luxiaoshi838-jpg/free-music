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
    'versionCode 2026080137\n        versionName "2026.08.04.no-playback-cache-scan"',
    'v137 version',
)

# Network lyrics must not start before audio playback starts.
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
    'defer network lyrics',
)

# Route playlist/search through recorded URI only; never scan cache folders before playback.
start = main_path.read_text(encoding='utf-8').index('    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {')
end = main_path.read_text(encoding='utf-8').index('    private void cacheAndPlay(Song song, int playToken) {', start)
text = main_path.read_text(encoding='utf-8')
replacement = '''    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {
        String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (recorded.isEmpty()) {
            statusView.setText("歌单没有记录缓存，立即获取音频...");
            cacheAndPlay(song, playToken);
            return;
        }
        song.uri = recorded;
        statusView.setText("已读取歌单记录缓存，正在启动播放...");
        startLocalPlayback(song, playToken, null, () -> {
            song.cachedUri = "";
            song.uri = "";
            statusView.setText("歌单记录缓存无法播放，立即重新获取音频...");
            cacheAndPlay(song, playToken);
        });
    }

'''
main_path.write_text(text[:start] + replacement + text[end:], encoding='utf-8')

# Search replay in the same session uses its recorded URI directly.
replace_once(
    main_path,
    '            if (!playingSearchQueue && isSongInAnyPlaylist(song)) {\n'
    '                playPlaylistSongFromCacheFirst(song, playToken);\n'
    '            } else {\n'
    '                cacheAndPlay(song, playToken);\n'
    '            }',
    '            if (!playingSearchQueue && isSongInAnyPlaylist(song)) {\n'
    '                playPlaylistSongFromCacheFirst(song, playToken);\n'
    '            } else if (song.cachedUri != null && !song.cachedUri.trim().isEmpty()) {\n'
    '                song.uri = song.cachedUri;\n'
    '                statusView.setText("已读取本次搜索缓存，正在启动播放...");\n'
    '                startLocalPlayback(song, playToken, null, () -> {\n'
    '                    song.cachedUri = "";\n'
    '                    song.uri = "";\n'
    '                    statusView.setText("本次搜索缓存无法播放，立即重新获取音频...");\n'
    '                    cacheAndPlay(song, playToken);\n'
    '                });\n'
    '            } else {\n'
    '                statusView.setText("未记录缓存，立即获取音频...");\n'
    '                cacheAndPlay(song, playToken);\n'
    '            }',
    'search recorded cache route',
)

# Lyrics start only after MediaPlayer has actually started.
replace_once(
    main_path,
    '        statusView.setText("当前播放：" + song.title);\n'
    '        if (onStarted != null) onStarted.run();\n'
    '        publishPlaybackControlState(true);',
    '        statusView.setText("当前播放：" + song.title);\n'
    '        if (song.isNetworkCatalog()) showSongLyrics(song);\n'
    '        if (onStarted != null) onStarted.run();\n'
    '        publishPlaybackControlState(true);',
    'lyrics after playback start',
)

# Remove every pre-play cache-folder lookup from NetworkMediaCache.cacheLocked.
network = network_path.read_text(encoding='utf-8')
scan_start = network.index('        status(callback, "正在检查这首歌是否已有可播放缓存...");')
prepare_start = network.index('        PlayableAudioResolver.Result prepared =', scan_start)
network = network[:scan_start] + '        status(callback, "未使用播放前缓存扫描，立即获取可播放音频...");\n' + network[prepare_start:]
network_path.write_text(network, encoding='utf-8')

# Cached playback failure retries once without scanning.
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
    '                                statusView.setText("记录缓存无法播放，立即重新获取音频...");\n'
    '                                cacheAndPlay(song, playToken);\n'
    '                            } else {\n'
    '                                markPlaybackFailure(song, true);\n'
    '                            }\n'
    '                        });',
    'retry failed recorded cache',
)

check = check_path.read_text(encoding='utf-8')
check = check.replace(
    "'version bumped': 'versionCode 2026080135' in gradle,",
    "'no cache-folder scan in playback path': (\n"
    "        'playPlaylistSongFromCacheFirst' in main\n"
    "        and 'playPlaylistSongFromExactCache' not in main\n"
    "        and '歌单没有记录缓存，立即获取音频' in main\n"
    "        and '本次搜索缓存' in main\n"
    "        and '正在准备音频，播放开始后再匹配歌词' in main\n"
    "        and 'if (song.isNetworkCatalog()) showSongLyrics(song);' in main\n"
    "        and '未使用播放前缓存扫描，立即获取可播放音频' in network\n"
    "        and 'findAudioMatches(context, requestedTitle, requestedArtist)' not in network[network.find('private static CacheResult cacheLocked'):network.find('private static Object[] createCacheLocks')]\n"
    "        and 'CacheStorage.findAudioUri(context, requestedKey)' not in network[network.find('private static CacheResult cacheLocked'):network.find('private static Object[] createCacheLocks')]\n"
    "        and 'CacheStorage.findAudioUri(this, exactKey)' not in main\n"
    "    ),\n"
    "    'version bumped': 'versionCode 2026080137' in gradle,"
)
check_path.write_text(check, encoding='utf-8')

append_once(
    project_log_path,
    'Remove all cache-folder scans from playback',
    '''## 2026-08-04 - Remove all cache-folder scans from playback

- Removed the v135 same-title scan and the proposed exact-key document-tree lookup from the playback path.
- Playlist playback now uses only the URI already stored in the playlist record; a missing record immediately starts retrieval.
- Search replay uses only the URI held by the current search result; otherwise retrieval starts immediately.
- No `findAudioUri`, `findAudioMatches`, or metadata directory enumeration is allowed before playback.
- Lyrics start only after MediaPlayer has actually started audio.''',
)
append_once(
    changelog_path,
    'no-playback-cache-scan',
    '''## 2026.08.04.no-playback-cache-scan

- Removed all cache-folder scanning from the click-to-play path.
- Playlist and search playback now use only their already-recorded cache URI.
- Missing or stale recorded URIs fall back immediately to audio retrieval.
- Lyrics no longer run before audio playback begins.''',
)

print('v137 no playback cache scan patch applied')
