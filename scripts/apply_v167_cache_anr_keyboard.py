from pathlib import Path

gradle = Path('app/build.gradle')
text = gradle.read_text(encoding='utf-8')
text = text.replace('versionCode 2026080866', 'versionCode 2026080867')
text = text.replace('versionName "2026.08.08.v166-call-voip-audio-focus"', 'versionName "2026.08.08.v167-cache-anr-keyboard-transition"')
gradle.write_text(text, encoding='utf-8')

main = Path('app/src/main/java/com/jianglab/babywife/MainActivity.java')
text = main.read_text(encoding='utf-8')

anchor = '    private volatile boolean playlistCacheRunning = false;\n'
if 'transientCacheCleanupRunning' not in text:
    if anchor not in text:
        raise SystemExit('field anchor missing')
    text = text.replace(anchor, anchor + '    private volatile boolean transientCacheCleanupRunning = false;\n', 1)

for name in ('showPlayerPage', 'showSearchPage', 'showPlaylistPage'):
    old = f'    private void {name}() {{\n'
    new = old + '        hideKeyboardAndClearFocus(null);\n'
    if new not in text:
        if old not in text:
            raise SystemExit(f'{name} missing')
        text = text.replace(old, new, 1)

start = text.find('    private void clearTransientCache() {')
end = text.find('\n    private void cacheCurrentPlaylistOneClick()', start)
if start < 0 or end < 0:
    raise SystemExit('clearTransientCache block missing')

replacement = '''    private void clearTransientCache() {
        if (transientCacheCleanupRunning) {
            toast("缓存正在后台清理，请稍候");
            return;
        }

        final List<Song> songSnapshot = new ArrayList<>();
        for (Playlist playlist : playlists) {
            if (playlist != null && playlist.songs != null) {
                songSnapshot.addAll(new ArrayList<>(playlist.songs));
            }
        }
        final Song activeSong = currentSong;
        transientCacheCleanupRunning = true;
        if (statusView != null) statusView.setText("正在后台清理非歌单缓存…");

        new Thread(() -> {
            try {
                Set<String> keepKeys = new HashSet<>();
                Set<String> keepMedia3Keys = new HashSet<>();
                for (Song song : songSnapshot) {
                    if (song == null || !song.isNetworkCatalog()) continue;
                    String cacheKey = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
                    if (!cacheKey.isEmpty()) keepKeys.add(cacheKey);
                    String media3Key = Media3CacheStore.keyFor(song.title, song.artist, song.catalogJson);
                    String friendlyUri = cacheKey.isEmpty() ? "" : CacheStorage.findAudioUri(this, cacheKey);
                    if (friendlyUri.isEmpty() && !media3Key.isEmpty()) {
                        friendlyUri = Media3PlaybackCacheIndex.friendlyUri(this, media3Key);
                    }
                    boolean hasFriendly = !friendlyUri.isEmpty() && CacheFileState.exists(this, friendlyUri);
                    if (!media3Key.isEmpty() && !hasFriendly) keepMedia3Keys.add(media3Key);
                }

                if (activeSong != null && activeSong.isNetworkCatalog()) {
                    String activeNetworkKey = NetworkMediaCache.cacheKeyForCatalog(activeSong.catalogJson);
                    if (!activeNetworkKey.isEmpty()) keepKeys.add(activeNetworkKey);
                    String activeMedia3Key = Media3CacheStore.keyFor(activeSong.title, activeSong.artist, activeSong.catalogJson);
                    if (!activeMedia3Key.isEmpty()) keepMedia3Keys.add(activeMedia3Key);
                }

                int removed = NetworkMediaCache.clearExcept(this, keepKeys);
                int removedMedia3 = Media3CacheStore.removeExcept(this, keepMedia3Keys);
                getSharedPreferences("lyric_version_picker_cache", MODE_PRIVATE).edit().clear().apply();
                int totalRemoved = removed + removedMedia3;
                runOnUiThread(() -> {
                    transientCacheCleanupRunning = false;
                    if (statusView != null) statusView.setText("缓存清理完成");
                    toast("已清理非歌单缓存：" + totalRemoved + " 个文件/资源");
                });
            } catch (Throwable error) {
                runOnUiThread(() -> {
                    transientCacheCleanupRunning = false;
                    if (statusView != null) statusView.setText("缓存清理失败");
                    String message = error.getMessage();
                    toast("缓存清理失败：" + (message == null ? error.getClass().getSimpleName() : message));
                });
            }
        }, "transient-cache-cleaner").start();
    }
'''

text = text[:start] + replacement + text[end:]
main.write_text(text, encoding='utf-8')
