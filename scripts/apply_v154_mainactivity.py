from pathlib import Path
import re

path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    text = text.replace(old, new, 1)


def replace_method(start_marker: str, next_marker: str, replacement: str, label: str) -> None:
    global text
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"{label}: start marker missing")
    end = text.find(next_marker, start + len(start_marker))
    if end < 0:
        raise SystemExit(f"{label}: end marker missing")
    text = text[:start] + replacement.rstrip() + "\n\n" + text[end:]


replace_once(
    "import android.media.MediaPlayer;\n",
    "import androidx.media3.common.util.UnstableApi;\n",
    "replace MediaPlayer import",
)
replace_once(
    "public class MainActivity extends Activity {",
    "@UnstableApi\npublic class MainActivity extends Activity {",
    "annotate MainActivity",
)
text, type_count = re.subn(r"\bMediaPlayer\b", "UnifiedMediaPlayer", text)
if type_count < 10:
    raise SystemExit(f"expected multiple MediaPlayer type replacements, found {type_count}")
replace_once(
    "UnifiedMediaPlayer player = new UnifiedMediaPlayer();",
    "UnifiedMediaPlayer player = new UnifiedMediaPlayer(this);",
    "construct unified player",
)

replace_method(
    "    private void addSongToCurrentPlaylist(Song song) {",
    "    private void addSongToCurrentPlaylistReady(Song song) {",
    '''    private void addSongToCurrentPlaylist(Song song) {
        if (song == null) return;
        // Adding a song is a metadata operation. It must never wait for a full
        // audio download; the shared Media3 cache continues in the background.
        addSongToCurrentPlaylistReady(song);
    }''',
    "immediate playlist add",
)
replace_once(
    "        Song playlistSong = copySongForPlaylist(song);",
    "        Song playlistSong = currentSong == song ? song : copySongForPlaylist(song);",
    "preserve active song identity when adding",
)

replace_method(
    "    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {",
    "    private void cacheAndPlay(Song song, int playToken) {",
    '''    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {
        String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (recorded.isEmpty()) {
            statusView.setText("歌单没有完整友好缓存，正在在线播放并复用Media3缓存...");
            trySearchPlaybackCandidate(song, playToken, 0);
            return;
        }
        song.uri = recorded;
        statusView.setText("已读取歌单记录缓存，正在启动播放...");
        startLocalPlayback(song, playToken, null, () -> {
            song.cachedUri = "";
            song.uri = "";
            statusView.setText("歌单记录缓存无法播放，正在在线播放并重新补齐缓存...");
            trySearchPlaybackCandidate(song, playToken, 0);
        });
    }''',
    "stream playlist songs before full cache",
)

replace_method(
    "    private void cacheSearchPlaybackAsync(Song song, SearchQuickPlayback.Candidate candidate,",
    "    private void persistSearchCacheToPlaylistCopies(Song song,",
    '''    private void cacheSearchPlaybackAsync(Song song, SearchQuickPlayback.Candidate candidate,
                                          int playToken) {
        cancelSearchCacheTask();
        searchCacheFuture = searchCacheExecutor.submit(() -> {
            SearchQuickPlayback.Candidate exportCandidate = candidate;
            Exception lastError = null;
            for (int attempt = 0; attempt < 2; attempt++) {
                try {
                    if (Thread.currentThread().isInterrupted()
                        || activityDestroyed || playToken != foregroundPlaybackSerial) return;
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
                            if (Thread.currentThread().isInterrupted()
                                || playToken != foregroundPlaybackSerial) {
                                throw new IllegalStateException("后台缓存已取消");
                            }
                            if (totalBytes <= 0L) return;
                            int percent = (int) Math.max(0L, Math.min(100L,
                                cachedBytes * 100L / totalBytes));
                            int previous = lastPercent.getAndSet(percent);
                            if (percent != 100 && previous >= 0 && percent - previous < 5) return;
                            runOnUiThread(() -> {
                                if (!activityDestroyed && currentSong == song
                                    && playToken == playbackRequestSerial && statusView != null) {
                                    statusView.setText("正在在线播放并补齐缓存：" + percent + "%"
                                        + (currentAttempt > 0 ? "（续传）" : ""));
                                }
                            });
                        }
                    );
                    if (Thread.currentThread().isInterrupted()
                        || activityDestroyed || playToken != foregroundPlaybackSerial) return;
                    SearchQuickPlayback.Candidate completedCandidate = exportCandidate;
                    runOnUiThread(() -> {
                        if (activityDestroyed || currentSong != song
                            || playToken != playbackRequestSerial) return;
                        song.cachedUri = storedUri;
                        song.uri = storedUri;
                        persistSearchCacheToPlaylistCopies(
                            song, completedCandidate, storedUri);
                        int position = 0;
                        try {
                            if (mediaPlayer != null) position = mediaPlayer.getCurrentPosition();
                        } catch (Exception ignored) {
                        }
                        saveLastSong(position);
                        statusView.setText("当前播放：" + song.title
                            + "（缓存已保存为“" + song.title + " - " + song.artist + "”）");
                        publishPlaybackControlState(true);
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
                if (!activityDestroyed && currentSong == song
                    && playToken == playbackRequestSerial) {
                    String detail = failure == null || failure.getMessage() == null
                        ? "未知错误" : failure.getMessage();
                    statusView.setText("当前播放正常，但后台缓存失败：" + detail);
                }
            });
        });
    }''',
    "Media3 friendly cache export",
)

replace_once(
    "                preparedPlayer.setDataSource(this, Uri.parse(playbackUri));",
    '''                if (online && song.isNetworkCatalog()) {
                    String media3Key = Media3CacheStore.keyFor(
                        song.title, song.artist, song.catalogJson);
                    preparedPlayer.setDataSource(
                        this,
                        Uri.parse(playbackUri),
                        media3Key,
                        UnifiedMediaPlayer.requestHeadersFor(song.catalogJson)
                    );
                } else {
                    preparedPlayer.setDataSource(this, Uri.parse(playbackUri));
                }''',
    "shared Media3 data source",
)

replace_once(
    '''        PlaybackControlService.publishState(
            this,
            title,
            artist,
            isPlaying,
            duration,
            position
        );''',
    '''        String notificationCatalog = currentSong == null ? "" : currentSong.catalogJson;
        String notificationUri = currentSong == null ? "" : firstNonEmpty(
            currentSong.cachedUri, currentSong.uri);
        PlaybackControlService.publishState(
            this,
            title,
            artist,
            isPlaying,
            duration,
            position,
            notificationCatalog,
            notificationUri
        );''',
    "publish cover metadata",
)

replace_once(
    '''        try {
            NetworkMediaCache.deleteCatalogCache(this, song.catalogJson);
        } catch (Exception ignored) {
        }
        song.cachedUri = "";''',
    '''        try {
            NetworkMediaCache.deleteCatalogCache(this, song.catalogJson);
        } catch (Exception ignored) {
        }
        try {
            Media3CacheStore.remove(this,
                Media3CacheStore.keyFor(song.title, song.artist, song.catalogJson));
        } catch (Exception ignored) {
        }
        song.cachedUri = "";''',
    "remove incomplete Media3 cache",
)

replace_method(
    "    private void clearTransientCache() {",
    "    private void cacheCurrentPlaylistOneClick() {",
    '''    private void clearTransientCache() {
        Set<String> keepKeys = new HashSet<>();
        Set<String> keepMedia3Keys = new HashSet<>();
        for (Playlist playlist : playlists) {
            for (Song song : playlist.songs) {
                if (song != null && song.isNetworkCatalog()) {
                    String cacheKey = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
                    if (!cacheKey.isEmpty()) keepKeys.add(cacheKey);
                    String media3Key = Media3CacheStore.keyFor(
                        song.title, song.artist, song.catalogJson);
                    if (!media3Key.isEmpty()) keepMedia3Keys.add(media3Key);
                }
            }
        }
        Song activeSong = currentSong;
        if (activeSong != null && activeSong.isNetworkCatalog()) {
            String activeKey = Media3CacheStore.keyFor(
                activeSong.title, activeSong.artist, activeSong.catalogJson);
            if (!activeKey.isEmpty()) keepMedia3Keys.add(activeKey);
        }
        new Thread(() -> {
            int removed = NetworkMediaCache.clearExcept(this, keepKeys);
            int removedMedia3 = Media3CacheStore.removeExcept(this, keepMedia3Keys);
            getSharedPreferences("lyric_version_picker_cache", MODE_PRIVATE).edit().clear().apply();
            int totalRemoved = removed + removedMedia3;
            runOnUiThread(() -> toast("已清理非歌单缓存：" + totalRemoved + " 个文件/资源"));
        }).start();
    }''',
    "clear transient Media3 cache",
)

# Guard against accidental UI edits by this patch.
if "android.media.MediaPlayer" in text or re.search(r"\bMediaPlayer\b", text):
    raise SystemExit("MediaPlayer type remains after migration")
if text.count("@UnstableApi\npublic class MainActivity") != 1:
    raise SystemExit("MainActivity annotation missing")
if "歌曲还在缓存，完成后再加入歌单" in text:
    raise SystemExit("old playlist cache gate remains")
if "Media3FriendlyCacheExporter.cacheAndExport" not in text:
    raise SystemExit("Media3 friendly exporter not connected")
if "PlaybackControlService.publishState(" not in text or "notificationCatalog" not in text:
    raise SystemExit("notification artwork metadata not connected")

path.write_text(text, encoding="utf-8")
