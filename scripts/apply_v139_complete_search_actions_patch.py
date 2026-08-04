from pathlib import Path

root = Path(__file__).resolve().parents[1]
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'
project_log_path = root / 'PROJECT_LOG.md'
changelog_path = root / 'docs/CHANGELOG.md'


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'Cannot find {label} in {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def replace_method(path: Path, start_marker: str, end_marker: str, replacement: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise SystemExit(f'Cannot find {label} in {path}')
    path.write_text(text[:start] + replacement.rstrip() + '\n\n' + text[end:], encoding='utf-8')


def append_once(path: Path, marker: str, body: str) -> None:
    text = path.read_text(encoding='utf-8')
    if marker in text:
        return
    path.write_text(text.rstrip() + '\n\n' + body.rstrip() + '\n', encoding='utf-8')

replace_once(
    gradle_path,
    'versionCode 2026080138\n        versionName "2026.08.04.restore-search-add-playlist"',
    'versionCode 2026080139\n        versionName "2026.08.04.complete-search-song-actions"',
    'v139 version',
)

replace_once(
    main_path,
    '''    private int indexOfSong(Playlist playlist, Song song) {
        if (playlist == null || song == null) return -1;
        String key = song.key();
        for (int i = 0; i < playlist.songs.size(); i++) {
            Song item = playlist.songs.get(i);
            if (item == song || item.key().equals(key)) return i;
        }
        return -1;
    }

    private void switchPlaybackToPlaylist(Playlist playlist, int songIndex) {
        if (playlist == null || songIndex < 0 || songIndex >= playlist.songs.size()) return;
        int playlistIndex = playlists.indexOf(playlist);
        if (playlistIndex < 0) return;
        currentPlaylistIndex = playlistIndex;
        currentSongIndex = songIndex;
        playingSearchQueue = false;
        searchSongIndex = -1;
        renderCurrentPlaylist();
        updateLyricActionVisibility(currentSong);
        saveLastSong(0);
    }
''',
    '''    private int indexOfSong(Playlist playlist, Song song) {
        if (playlist == null || song == null) return -1;
        String identity = dedupeKey(song);
        for (int i = 0; i < playlist.songs.size(); i++) {
            Song item = playlist.songs.get(i);
            if (item == song || dedupeKey(item).equals(identity)) return i;
        }
        return -1;
    }

    private void switchPlaybackToPlaylist(Playlist playlist, int songIndex) {
        if (playlist == null || songIndex < 0 || songIndex >= playlist.songs.size()) return;
        int playlistIndex = playlists.indexOf(playlist);
        if (playlistIndex < 0) return;
        currentPlaylistIndex = playlistIndex;
        currentSongIndex = songIndex;
        currentSong = playlist.songs.get(songIndex);
        playingSearchQueue = false;
        searchSongIndex = -1;
        renderCurrentPlaylist();
        updateLyricActionVisibility(currentSong);
        saveLastSong(0);
    }

    private Song findPlaylistSongMatch(Song song) {
        if (song == null) return null;
        String identity = dedupeKey(song);
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item == song || dedupeKey(item).equals(identity)) return item;
            }
        }
        return null;
    }

    private boolean isPlaylistSongObject(Song song) {
        if (song == null) return false;
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item == song) return true;
            }
        }
        return false;
    }

    private boolean switchPlaybackToPlaylistSong(Song song) {
        if (song == null) return false;
        for (Playlist playlist : playlists) {
            for (int index = 0; index < playlist.songs.size(); index++) {
                if (playlist.songs.get(index) == song) {
                    switchPlaybackToPlaylist(playlist, index);
                    return true;
                }
            }
        }
        return false;
    }
''',
    'playlist identity and context helpers',
)

replace_method(
    main_path,
    '    private void showSongVersionPicker() {',
    '    private void confirmPendingReplacement() {',
    '''    private void showSongVersionPicker() {
        Song selected = currentSong;
        if (selected == null) {
            toast("请先选择歌曲");
            return;
        }
        Song target = findPlaylistSongMatch(selected);
        if (target == null) {
            toast("替换歌曲只对歌单内歌曲生效");
            return;
        }
        SongVersionPicker.show(this, selected.title, selected.artist, new SongVersionPicker.Callback() {
            @Override
            public void onStatus(String message) {
                runOnUiThread(() -> {
                    if (currentSong == selected && statusView != null) statusView.setText(message);
                });
            }

            @Override
            public void onPreview(String title, String artist, String sourceLabel, String catalogJson) {
                runOnUiThread(() -> {
                    if (currentSong != selected || catalogJson == null || catalogJson.trim().isEmpty()) return;
                    clearPendingLyricPreview();
                    pendingSongTarget = target;
                    pendingSongOriginalKey = target.key();
                    pendingSongTitle = title == null ? target.title : title;
                    pendingSongArtist = artist == null ? target.artist : artist;
                    pendingSongSource = sourceLabel == null ? target.source : sourceLabel;
                    pendingSongCatalogJson = catalogJson;
                    pendingReplacementType = REPLACEMENT_SONG;
                    titleView.setText(pendingSongTitle);
                    artistView.setText(pendingSongArtist + " · " + pendingSongSource);
                    if (confirmLyricButton != null) {
                        confirmLyricButton.setText("确认替换歌曲");
                        confirmLyricButton.setVisibility(View.VISIBLE);
                        confirmLyricButton.bringToFront();
                    }
                    statusView.setText("正在预览替换版本；点击右下角确认后才会写入歌单");
                });
            }

            @Override
            public void onUnavailable() {
                runOnUiThread(() -> {
                    if (currentSong != selected || !isPlaylistSongObject(target)) return;
                    target.manualUnavailable = true;
                    markSongUnavailable(target, target.autoUnavailable && target.manualUnavailable);
                    savePlaylists();
                    renderCurrentPlaylist();
                    statusView.setText("手动搜索全部来源后仍未找到相近版本");
                });
            }
        });
    }''',
    'song replacement picker',
)

replace_method(
    main_path,
    '    private void confirmPendingSong() {',
    '    private void persistResolvedCatalogToPlaylistCopies(',
    '''    private void confirmPendingSong() {
        Song target = pendingSongTarget;
        if (target == null || pendingSongCatalogJson == null || pendingSongCatalogJson.trim().isEmpty()) return;
        if (!isPlaylistSongObject(target)) {
            clearPendingLyricPreview();
            toast("目标歌曲已不在歌单中");
            return;
        }
        String originalKey = pendingSongOriginalKey;
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item == target || item.key().equals(originalKey)) {
                    item.title = pendingSongTitle;
                    item.artist = pendingSongArtist;
                    item.source = pendingSongSource;
                    item.catalogJson = pendingSongCatalogJson;
                    item.uri = "";
                    item.cachedUri = "";
                    item.lyric = "";
                    item.lyricLabel = "";
                    item.manualAttempt = true;
                    item.manualUnavailable = false;
                    item.unavailable = false;
                    item.cacheFailed = false;
                }
            }
        }
        target.title = pendingSongTitle;
        target.artist = pendingSongArtist;
        target.source = pendingSongSource;
        target.catalogJson = pendingSongCatalogJson;
        target.uri = "";
        target.cachedUri = "";
        target.lyric = "";
        target.lyricLabel = "";
        target.manualAttempt = true;
        target.manualUnavailable = false;
        target.unavailable = false;
        target.cacheFailed = false;
        clearPendingLyricPreview();
        savePlaylists();
        renderCurrentPlaylist();
        switchPlaybackToPlaylistSong(target);
        titleView.setText(target.title);
        artistView.setText(target.artist + " · " + target.source);
        statusView.setText("歌曲版本已替换，正在按新版本缓存播放");
        toast("已替换歌单中的歌曲版本");
        playSong(target);
    }''',
    'song replacement confirmation',
)

replace_method(
    main_path,
    '    private void showLyricVersionPicker() {',
    '    private void confirmPendingLyric() {',
    '''    private void showLyricVersionPicker() {
        Song selected = currentSong;
        if (selected == null) {
            toast("请先选择歌曲");
            return;
        }
        Song target = findPlaylistSongMatch(selected);
        if (target == null) {
            toast("替换歌词只对歌单内歌曲生效");
            return;
        }
        LyricVersionPicker.show(this, selected.title, selected.artist, new LyricVersionPicker.Callback() {
            @Override
            public void onStatus(String message) {
                runOnUiThread(() -> {
                    if (currentSong == selected && statusView != null) statusView.setText(message);
                });
            }

            @Override
            public void onPreview(String lyric, String lyricTitle, String lyricArtist, String sourceLabel) {
                runOnUiThread(() -> {
                    if (currentSong != selected || lyric == null || lyric.trim().isEmpty()) return;
                    clearPendingLyricPreview();
                    pendingLyricSong = target;
                    pendingLyric = lyric;
                    pendingLyricLabel = lyricTitle + " · " + lyricArtist + " · " + sourceLabel;
                    pendingReplacementType = REPLACEMENT_LYRIC;
                    applyLyricText(lyric);
                    if (confirmLyricButton != null) {
                        confirmLyricButton.setText("确认替换歌词");
                        confirmLyricButton.setVisibility(View.VISIBLE);
                        confirmLyricButton.bringToFront();
                    }
                    statusView.setText("正在预览：" + pendingLyricLabel + "；点击右下角确认替换");
                });
            }
        });
    }''',
    'lyric replacement picker',
)

replace_method(
    main_path,
    '    private void confirmPendingLyric() {',
    '    private void clearPendingLyricPreview() {',
    '''    private void confirmPendingLyric() {
        if (pendingLyricSong == null || pendingLyric == null || pendingLyric.trim().isEmpty()) return;
        Song target = pendingLyricSong;
        if (!isPlaylistSongObject(target)) {
            clearPendingLyricPreview();
            toast("目标歌曲已不在歌单中");
            return;
        }
        String lyric = pendingLyric;
        String label = pendingLyricLabel;
        bindLyricToPlaylistCopies(target, lyric, label);
        if (currentSong != null && dedupeKey(currentSong).equals(dedupeKey(target))) {
            currentSong.lyric = lyric;
            currentSong.lyricLabel = label;
        }
        clearPendingLyricPreview();
        savePlaylists();
        showSongLyrics(currentSong);
        statusView.setText("已绑定歌词：" + label);
        toast("歌词已与歌单歌曲绑定");
    }''',
    'lyric replacement confirmation',
)

replace_method(
    main_path,
    '    private void updateLyricActionVisibility(Song song) {',
    '    private boolean isSongInAnyPlaylist(Song song) {',
    '''    private void updateLyricActionVisibility(Song song) {
        Song playlistMatch = findPlaylistSongMatch(song);
        boolean existsInPlaylist = playlistMatch != null;
        boolean fromSearch = song != null && playingSearchQueue;
        boolean unmatchedSearch = fromSearch && !existsInPlaylist;
        if (addCurrentButton != null) {
            addCurrentButton.setText("加入当前歌单");
            addCurrentButton.setVisibility(unmatchedSearch ? View.VISIBLE : View.GONE);
        }
        if (songVersionButton != null) {
            songVersionButton.setVisibility(existsInPlaylist ? View.VISIBLE : View.GONE);
        }
        if (lyricVersionButton != null) {
            lyricVersionButton.setVisibility(existsInPlaylist ? View.VISIBLE : View.GONE);
        }
        if (!existsInPlaylist && (pendingLyricSong != null || pendingSongTarget != null)) {
            clearPendingLyricPreview();
        }
    }''',
    'complete search action visibility',
)

check = check_path.read_text(encoding='utf-8')
old_check = '''    'search result always exposes add-to-playlist action': (
        'boolean fromSearch = song != null && playingSearchQueue;' in main
        and 'addCurrentButton.setText("加入当前歌单");' in main
        and 'addCurrentButton.setVisibility(fromSearch ? View.VISIBLE : View.GONE);' in main
        and 'fromSearchOnly' not in main
        and 'searchResultsList.setOnItemLongClickListener' in main
    ),
    'version bumped': 'versionCode 2026080138' in gradle,'''
new_check = '''    'search result exposes complete context actions': (
        'Song playlistMatch = findPlaylistSongMatch(song);' in main
        and 'boolean unmatchedSearch = fromSearch && !existsInPlaylist;' in main
        and 'addCurrentButton.setVisibility(unmatchedSearch ? View.VISIBLE : View.GONE);' in main
        and 'songVersionButton.setVisibility(existsInPlaylist ? View.VISIBLE : View.GONE);' in main
        and 'lyricVersionButton.setVisibility(existsInPlaylist ? View.VISIBLE : View.GONE);' in main
        and 'Song target = findPlaylistSongMatch(selected);' in main
        and 'pendingSongTarget = target;' in main
        and 'pendingLyricSong = target;' in main
        and 'isPlaylistSongObject(target)' in main
        and 'switchPlaybackToPlaylistSong(target);' in main
        and 'addCurrentButton.setVisibility(fromSearch ? View.VISIBLE : View.GONE);' not in main
    ),
    'version bumped': 'versionCode 2026080139' in gradle,'''
if old_check not in check:
    raise SystemExit('Cannot find obsolete v138 check')
check_path.write_text(check.replace(old_check, new_check, 1), encoding='utf-8')

append_once(
    project_log_path,
    'Complete search-result action state machine',
    '''## 2026-08-04 - Complete search-result action state machine

- Corrected the v138 assumption that every search result should expose `加入当前歌单`.
- Search-only songs show `加入当前歌单`.
- A search result matching an existing playlist song by normalized title and artist hides the add action and shows `替换歌曲` plus `替换歌词`.
- Replacement previews and confirmations bind to the real playlist song object rather than the temporary search-result object.
- Confirmed song replacement switches playback to the updated playlist entry.''',
)
append_once(
    changelog_path,
    'complete-search-song-actions',
    '''## 2026.08.04.complete-search-song-actions

- Restored the full search-result action logic instead of forcing the add-to-playlist button.
- Unmatched search results show `加入当前歌单`.
- Matching playlist songs show `替换歌曲` and `替换歌词`.
- Replacement actions now update the actual playlist entry and no longer fail because the search result is a separate object.''',
)

print('v139 complete search action logic patch applied')
