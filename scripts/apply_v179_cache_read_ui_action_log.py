from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


def replace_block(text: str, start_marker: str, end_marker: str, new_block: str, label: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0:
        raise SystemExit(f"anchor missing: {label}")
    return text[:start] + new_block + text[end:]


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
p = Path("app/build.gradle")
g = p.read_text(encoding="utf-8")
g = g.replace("versionCode 2026080878", "versionCode 2026080879", 1)
g = g.replace(
    'versionName "2026.08.10.v178-playlist-open-rapid-next-stability"',
    'versionName "2026.08.10.v179-cache-read-ui-action-log"',
    1,
)
if "versionCode 2026080879" not in g:
    raise SystemExit("v179 version patch failed")
p.write_text(g, encoding="utf-8")


# ---------------------------------------------------------------------------
# MainActivity
# ---------------------------------------------------------------------------
p = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = p.read_text(encoding="utf-8")

# Catch a blocked UI before Android's ~5s input-dispatch ANR and keep a recent
# action ring that survives a process kill.
text = text.replace("private static final long NO_RESPONSE_THRESHOLD_MS = 12000L;",
                    "private static final long NO_RESPONSE_THRESHOLD_MS = 4500L;", 1)
text = text.replace("private static final long NO_RESPONSE_CHECK_INTERVAL_MS = 3000L;",
                    "private static final long NO_RESPONSE_CHECK_INTERVAL_MS = 1000L;", 1)
text = replace_once(
    text,
    '''    private static final String KEY_PLAYBACK_TRANSITION_TIME = "playback_transition_time";''',
    '''    private static final String KEY_PLAYBACK_TRANSITION_TIME = "playback_transition_time";\n    private static final String KEY_RECENT_ACTIONS = "recent_actions_v1";\n    private static final int MAX_RECENT_ACTIONS = 50;''',
    "recent action constants",
)

text = replace_once(
    text,
    '''    private final ExecutorService playlistPersistenceExecutor = Executors.newSingleThreadExecutor();\n    private volatile int playlistPersistenceSerial = 0;\n    private boolean playlistUiDirty = false;''',
    '''    private final ExecutorService playlistPersistenceExecutor = Executors.newSingleThreadExecutor();\n    private final ExecutorService cacheLookupExecutor = Executors.newFixedThreadPool(2);\n    private volatile int playlistPersistenceSerial = 0;\n    private boolean playlistUiDirty = false;\n    private final java.util.ArrayDeque<String> recentActions = new java.util.ArrayDeque<>();''',
    "cache lookup executor and recent action ring",
)

# Load previous-session actions before ApplicationExitInfo is converted to a log.
text = replace_once(
    text,
    '''        loadPlaylists();\n        migrateLegacyProblemReportIfNeeded();''',
    '''        loadPlaylists();\n        restoreRecentActions();\n        migrateLegacyProblemReportIfNeeded();''',
    "restore recent actions before exit report",
)
text = replace_once(
    text,
    '''        setContentView(buildContentView());\n        attachPressFeedbackTree(shellView);''',
    '''        setContentView(buildContentView());\n        recordRecentAction("软件启动完成");\n        attachPressFeedbackTree(shellView);''',
    "record startup action",
)

# Clear the action trail on a normal APK version change so the next real failure
# never gets attributed to operations from the previous installed version.
old = '''                editor.putLong(KEY_LAST_HANDLED_EXIT_TIME, System.currentTimeMillis())\n                    .putBoolean(KEY_CRASH_REPORT_DISMISSED, true)\n                    .putBoolean(KEY_PLAYBACK_TRANSITION_PENDING, false)\n                    .remove(KEY_PLAYBACK_TRANSITION_DETAIL)\n                    .remove(KEY_PLAYBACK_TRANSITION_TIME);'''
new = '''                editor.putLong(KEY_LAST_HANDLED_EXIT_TIME, System.currentTimeMillis())\n                    .putBoolean(KEY_CRASH_REPORT_DISMISSED, true)\n                    .putBoolean(KEY_PLAYBACK_TRANSITION_PENDING, false)\n                    .remove(KEY_PLAYBACK_TRANSITION_DETAIL)\n                    .remove(KEY_PLAYBACK_TRANSITION_TIME)\n                    .remove(KEY_RECENT_ACTIONS);\n                synchronized (recentActions) {\n                    recentActions.clear();\n                }'''
text = replace_once(text, old, new, "clear action trail after normal update")

# Recent action helpers. Meaningful operations only; progress ticks are deliberately
# excluded so the ring remains useful when diagnosing a crash/ANR.
anchor = '''    private void installCrashReporter() {'''
helpers = '''    private void restoreRecentActions() {\n        String raw = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)\n            .getString(KEY_RECENT_ACTIONS, "");\n        if (raw == null || raw.trim().isEmpty()) return;\n        synchronized (recentActions) {\n            recentActions.clear();\n            for (String line : raw.split("\\n")) {\n                String safe = line == null ? "" : line.trim();\n                if (safe.isEmpty()) continue;\n                recentActions.addLast(safe);\n                while (recentActions.size() > MAX_RECENT_ACTIONS) recentActions.removeFirst();\n            }\n        }\n    }\n\n    private void recordRecentAction(String action) {\n        String safeAction = action == null ? "" : action.replace('\\n', ' ').replace('\\r', ' ').trim();\n        if (safeAction.isEmpty()) return;\n        String timestamp = new java.text.SimpleDateFormat(\n            "HH:mm:ss.SSS", java.util.Locale.ROOT).format(new java.util.Date());\n        String page = currentPageForLog();\n        Song song = currentSong;\n        String songText = song == null ? ""\n            : trimForReport(song.title + " / " + song.artist, 100);\n        String line = timestamp\n            + " page=" + page\n            + " action=" + trimForReport(safeAction, 180)\n            + " playlistIndex=" + currentPlaylistIndex\n            + " songIndex=" + currentSongIndex\n            + (songText.isEmpty() ? "" : " song=" + songText);\n        String snapshot;\n        synchronized (recentActions) {\n            recentActions.addLast(line);\n            while (recentActions.size() > MAX_RECENT_ACTIONS) recentActions.removeFirst();\n            snapshot = recentActionsTextLocked();\n        }\n        getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit()\n            .putString(KEY_RECENT_ACTIONS, snapshot)\n            .apply();\n    }\n\n    private String currentPageForLog() {\n        if (playlistPanel != null && playlistPanel.getVisibility() == View.VISIBLE) return "playlist";\n        if (searchPanel != null && searchPanel.getVisibility() == View.VISIBLE) return "search";\n        if (playerPanel != null && playerPanel.getVisibility() == View.VISIBLE) return "player";\n        return "startup";\n    }\n\n    private String recentActionsTextLocked() {\n        StringBuilder out = new StringBuilder();\n        for (String line : recentActions) {\n            if (out.length() > 0) out.append('\\n');\n            out.append(line);\n        }\n        return out.toString();\n    }\n\n    private String recentActionsText() {\n        synchronized (recentActions) {\n            return recentActionsTextLocked();\n        }\n    }\n\n    private void appendRecentActions(StringBuilder report) {\n        if (report == null) return;\n        String actions = recentActionsText();\n        if (actions.trim().isEmpty()) {\n            actions = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)\n                .getString(KEY_RECENT_ACTIONS, "");\n        }\n        if (actions == null || actions.trim().isEmpty()) return;\n        report.append("\\nRecent actions (oldest -> newest):\\n")\n            .append(trimForReport(actions, 14000)).append('\\n');\n    }\n\n''' + anchor
text = replace_once(text, anchor, helpers, "recent action helpers")

# All crash, ANR and no-response reports now include the operation trail.
old = '''            report.append("catalog=").append(trimForReport(snapshotSong.catalogJson, 1200)).append('\\n');\n        }\n    }'''
new = '''            report.append("catalog=").append(trimForReport(snapshotSong.catalogJson, 1200)).append('\\n');\n        }\n        appendRecentActions(report);\n    }'''
text = replace_once(text, old, new, "append recent actions to report context")

# Playback interruption reports use the same operation trail.
old = '''            playbackPreparing,\n            playbackExpectedPlaying,\n            playbackUserPaused\n        );'''
new = '''            playbackPreparing,\n            playbackExpectedPlaying,\n            playbackUserPaused,\n            recentActionsText()\n        );'''
text = replace_once(text, old, new, "recent actions in playback problem report")

# Invalid/short cache cleanup must never delete SAF/Media3 content from the UI thread.
start_marker = '''    private void deleteIncompletePlaybackCache(Song song, String playbackUri) {'''
end_marker = '''    private void persistCrashReport(Thread thread, Throwable throwable) {'''
new_block = '''    private void deleteIncompletePlaybackCache(Song song, String playbackUri) {\n        if (song == null) return;\n        final String oldCatalog = song.catalogJson;\n        final String oldTitle = song.title;\n        final String oldArtist = song.artist;\n        song.cachedUri = "";\n        song.uri = "";\n        savePlaylists();\n        recordRecentAction("无效缓存已从播放状态摘除，后台删除文件");\n        try {\n            cacheLookupExecutor.execute(() -> {\n                try {\n                    CacheFileState.deleteDirect(this, playbackUri);\n                } catch (Exception ignored) {\n                }\n                try {\n                    NetworkMediaCache.deleteCatalogCache(this, oldCatalog);\n                } catch (Exception ignored) {\n                }\n                try {\n                    Media3CacheStore.remove(this,\n                        Media3CacheStore.keyFor(oldTitle, oldArtist, oldCatalog));\n                } catch (Exception ignored) {\n                }\n            });\n        } catch (java.util.concurrent.RejectedExecutionException ignored) {\n        }\n    }\n\n'''
text = replace_block(text, start_marker, end_marker, new_block, "async incomplete cache deletion")

# Page switches are performed before any IME work. A stuck IME/provider must not
# delay the playlist Back button or any other page navigation.
old = '''    private void showPlayerPage() {\n        hideKeyboardAndClearFocus(null);\n        if (headerBar != null) headerBar.setVisibility(View.VISIBLE);\n        if (statusView != null) statusView.setVisibility(View.VISIBLE);\n        if (playerPanel != null) playerPanel.setVisibility(View.VISIBLE);\n        if (searchPanel != null) searchPanel.setVisibility(View.GONE);\n        if (playlistPanel != null) playlistPanel.setVisibility(View.GONE);\n    }'''
new = '''    private void showPlayerPage() {\n        recordRecentAction("打开播放页/从子页面返回");\n        View focused = getCurrentFocus();\n        if (headerBar != null) headerBar.setVisibility(View.VISIBLE);\n        if (statusView != null) statusView.setVisibility(View.VISIBLE);\n        if (playerPanel != null) playerPanel.setVisibility(View.VISIBLE);\n        if (searchPanel != null) searchPanel.setVisibility(View.GONE);\n        if (playlistPanel != null) playlistPanel.setVisibility(View.GONE);\n        if (focused instanceof EditText) {\n            focused.clearFocus();\n            focused.post(() -> hideKeyboardAndClearFocus(focused));\n        }\n    }'''
text = replace_once(text, old, new, "instant player page return")

old = '''    private void showPlaylistPage() {\n        // Page switching must stay a pure UI operation. Cache verification and\n        // persistence are never started from this click path.\n        View focused = getCurrentFocus();'''
new = '''    private void showPlaylistPage() {\n        // Page switching must stay a pure UI operation. Cache verification and\n        // persistence are never started from this click path.\n        recordRecentAction("打开当前歌单");\n        View focused = getCurrentFocus();'''
text = replace_once(text, old, new, "record playlist open")

old = '''    private void showSearchPage() {\n        hideKeyboardAndClearFocus(null);'''
new = '''    private void showSearchPage() {\n        recordRecentAction("打开搜索页");\n        hideKeyboardAndClearFocus(null);'''
text = replace_once(text, old, new, "record search page open")

# Record playback/navigation operations useful for reproducing a crash.
old = '''    private void playSongFromPlaylist(int index) {\n        if (index < 0 || index >= currentPlaylist().songs.size()) return;'''
new = '''    private void playSongFromPlaylist(int index) {\n        if (index < 0 || index >= currentPlaylist().songs.size()) return;\n        recordRecentAction("点击/切换歌单歌曲 index=" + index);'''
text = replace_once(text, old, new, "record playlist song selection")

old = '''    private void playPlaylistOffset(int offset) {\n        if (offset == 0) {'''
new = '''    private void playPlaylistOffset(int offset) {\n        if (offset != 0) recordRecentAction(offset > 0 ? "点击下一首" : "点击上一首");\n        if (offset == 0) {'''
text = replace_once(text, old, new, "record next previous")

old = '''    private void togglePlayback() {\n        if (mediaPlayer == null) {'''
new = '''    private void togglePlayback() {\n        recordRecentAction(mediaPlayer == null ? "点击播放"\n            : (mediaPlayer.isPlaying() ? "点击暂停" : "点击继续播放"));\n        if (mediaPlayer == null) {'''
text = replace_once(text, old, new, "record play pause")

old = '''    @Override\n    public void onBackPressed() {\n        if (drawerPanel != null && drawerPanel.getVisibility() == View.VISIBLE) {'''
new = '''    @Override\n    public void onBackPressed() {\n        recordRecentAction("系统返回键");\n        if (drawerPanel != null && drawerPanel.getVisibility() == View.VISIBLE) {'''
text = replace_once(text, old, new, "record back press")

# Starting a local/content cache must do zero storage/index work on the UI thread.
# Main-thread callers now only trust an already-attached URI. Missing URI recovery
# is handled by playPlaylistSongFromCacheFirst on cacheLookupExecutor.
start_marker = '''    private void attachExistingFriendlyCache(Song song) {'''
end_marker = '''    private void persistSearchCacheToPlaylistCopies('''
new_block = '''    private void attachExistingFriendlyCache(Song song) {\n        if (song == null || !song.isNetworkCatalog()) return;\n        if (Looper.myLooper() == Looper.getMainLooper()) return;\n\n        String uri = findExistingFriendlyCacheUriBackground(song);\n        if (!uri.isEmpty()) {\n            boolean changed = applyRecoveredCacheState(song, uri);\n            if (changed) savePlaylists();\n        }\n    }\n\n    private String findExistingFriendlyCacheUriBackground(Song song) {\n        if (song == null || !song.isNetworkCatalog()) return "";\n        String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();\n        if (!recorded.isEmpty() && CacheFileState.exists(this, recorded)) return recorded;\n        String direct = song.uri == null ? "" : song.uri.trim();\n        if ((direct.startsWith("file:") || direct.startsWith("content:"))\n            && CacheFileState.exists(this, direct)) return direct;\n\n        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);\n        String uri = key.isEmpty() ? "" : CacheStorage.findAudioUri(this, key);\n        if (!uri.isEmpty() && CacheFileState.exists(this, uri)) return uri;\n\n        String media3Key = Media3CacheStore.keyFor(song.title, song.artist, song.catalogJson);\n        String indexed = Media3PlaybackCacheIndex.friendlyUri(this, media3Key);\n        if (!indexed.isEmpty() && CacheFileState.exists(this, indexed)) return indexed;\n        return "";\n    }\n\n'''
text = replace_block(text, start_marker, end_marker, new_block, "off-main friendly cache lookup")

# Playlist cache-first playback: no SharedPreferences/SAF/cache-provider lookup on
# the click thread. The user can open playlist/back/next while lookup is in flight.
start_marker = '''    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {'''
end_marker = '''    private void cacheAndPlay(Song song, int playToken) {'''
new_block = '''    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {\n        String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();\n        if (!recorded.isEmpty()) {\n            song.uri = recorded;\n            recordRecentAction("使用已记录本地缓存，异步交给播放器读取");\n            statusView.setText("已读取歌单记录缓存，正在后台启动播放...");\n            startLocalPlayback(song, playToken, null, () -> {\n                song.cachedUri = "";\n                song.uri = "";\n                recordRecentAction("记录缓存播放失败，转在线资源");\n                statusView.setText("歌单记录缓存无法播放，正在在线播放并重新补齐缓存...");\n                trySearchPlaybackCandidate(song, playToken, 0);\n            });\n            return;\n        }\n\n        recordRecentAction("后台查找本地缓存开始");\n        statusView.setText("正在后台查找本地缓存；界面可继续操作...");\n        try {\n            cacheLookupExecutor.execute(() -> {\n                String found = findExistingFriendlyCacheUriBackground(song);\n                runOnUiThread(() -> {\n                    if (activityDestroyed || currentSong != song\n                        || playToken != playbackRequestSerial) return;\n                    if (!found.isEmpty()) {\n                        applyRecoveredCacheState(song, found);\n                        song.uri = found;\n                        savePlaylists();\n                        notifyPlaylistAdapterStateChanged();\n                        recordRecentAction("后台找到本地缓存，交给播放器读取");\n                        statusView.setText("已找到本地缓存，正在后台启动播放...");\n                        startLocalPlayback(song, playToken, null, () -> {\n                            song.cachedUri = "";\n                            song.uri = "";\n                            recordRecentAction("找到的缓存无法播放，转在线资源");\n                            statusView.setText("本地缓存无法播放，正在在线播放并重新补齐缓存...");\n                            trySearchPlaybackCandidate(song, playToken, 0);\n                        });\n                    } else {\n                        recordRecentAction("未找到本地缓存，转在线资源");\n                        statusView.setText("未找到完整本地缓存，正在在线播放并复用Media3缓存...");\n                        trySearchPlaybackCandidate(song, playToken, 0);\n                    }\n                });\n            });\n        } catch (java.util.concurrent.RejectedExecutionException ignored) {\n            trySearchPlaybackCandidate(song, playToken, 0);\n        }\n    }\n\n'''
text = replace_block(text, start_marker, end_marker, new_block, "fully async playlist cache lookup")

# Cache-open lifecycle markers.
old = '''    private void startLocalPlayback(Song song, int playToken, Runnable onStarted, Runnable onFailed) {\n        stopPlayback();'''
new = '''    private void startLocalPlayback(Song song, int playToken, Runnable onStarted, Runnable onFailed) {\n        String sourceForLog = song == null || song.uri == null ? "" : song.uri.trim();\n        recordRecentAction(sourceForLog.startsWith("content:") || sourceForLog.startsWith("file:")\n            ? "本地缓存读取交给后台播放器" : "在线音频读取交给后台播放器");\n        stopPlayback();'''
text = replace_once(text, old, new, "record async media open")

old = '''        statusView.setText("当前播放：" + song.title);\n        // Successful playback is the strongest cache-state signal.'''
new = '''        statusView.setText("当前播放：" + song.title);\n        recordRecentAction("播放开始成功");\n        // Successful playback is the strongest cache-state signal.'''
text = replace_once(text, old, new, "record playback started")

# Lyric cache writes are SAF/file I/O and therefore never execute from a Media3
# prepared callback on the main thread.
old = '''    private void writeNetworkLyricCache(Song song, String lyric) {\n        if (song == null || !song.isNetworkCatalog() || lyric == null || lyric.trim().isEmpty()) return;\n        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);\n        if (key.isEmpty()) return;\n        try {\n            CacheStorage.writeLyric(this, key, lyric, song.title, song.artist, "", song.catalogJson);\n        } catch (Exception error) {\n            android.util.Log.w("BabywifePlaylist", "write lyric cache failed: " + error.getMessage());\n        }\n    }'''
new = '''    private void writeNetworkLyricCache(Song song, String lyric) {\n        if (song == null || !song.isNetworkCatalog() || lyric == null || lyric.trim().isEmpty()) return;\n        if (Looper.myLooper() == Looper.getMainLooper()) {\n            try {\n                cacheLookupExecutor.execute(() -> writeNetworkLyricCache(song, lyric));\n            } catch (java.util.concurrent.RejectedExecutionException ignored) {\n            }\n            return;\n        }\n        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);\n        if (key.isEmpty()) return;\n        try {\n            CacheStorage.writeLyric(this, key, lyric, song.title, song.artist, "", song.catalogJson);\n        } catch (Exception error) {\n            android.util.Log.w("BabywifePlaylist", "write lyric cache failed: " + error.getMessage());\n        }\n    }'''
text = replace_once(text, old, new, "async lyric cache write")

# savePlaylists previously deep-copied every Song (including lyric/catalog strings)
# on the UI thread. Keep only tiny shallow list snapshots on UI; deep copy + JSON
# serialization happen on playlistPersistenceExecutor.
start_marker = '''    private void savePlaylists() {'''
end_marker = '''    private Song copySongForPersistence(Song song) {'''
new_block = '''    private void savePlaylists() {\n        if (Looper.myLooper() != Looper.getMainLooper()) {\n            runOnUiThread(this::savePlaylists);\n            return;\n        }\n        final List<String> playlistNames = new ArrayList<>();\n        final List<List<Song>> songRefs = new ArrayList<>();\n        for (Playlist playlist : playlists) {\n            if (playlist == null) continue;\n            playlistNames.add(playlist.name);\n            songRefs.add(new ArrayList<>(playlist.songs));\n        }\n        final int selectedIndex = currentPlaylistIndex;\n        final int serial = ++playlistPersistenceSerial;\n        try {\n            playlistPersistenceExecutor.execute(() -> {\n                if (serial != playlistPersistenceSerial) return;\n                JSONArray array = new JSONArray();\n                for (int i = 0; i < songRefs.size(); i++) {\n                    Playlist copy = new Playlist(playlistNames.get(i));\n                    for (Song song : songRefs.get(i)) {\n                        if (song != null) copy.songs.add(copySongForPersistence(song));\n                    }\n                    array.put(copy.toJson());\n                }\n                if (serial != playlistPersistenceSerial) return;\n                getApplicationContext().getSharedPreferences(PREFS_NAME, MODE_PRIVATE)\n                    .edit()\n                    .putString(KEY_PLAYLISTS, array.toString())\n                    .putInt(KEY_CURRENT_PLAYLIST, selectedIndex)\n                    .apply();\n            });\n        } catch (java.util.concurrent.RejectedExecutionException ignored) {\n        }\n    }\n\n'''
text = replace_block(text, start_marker, end_marker, new_block, "off-main playlist deep snapshot")

# Dedicated cache lookup/delete executor lifecycle.
old = '''        playlistCacheScanExecutor.shutdownNow();\n        playlistPersistenceExecutor.shutdown();'''
new = '''        playlistCacheScanExecutor.shutdownNow();\n        cacheLookupExecutor.shutdownNow();\n        playlistPersistenceExecutor.shutdown();'''
text = replace_once(text, old, new, "shutdown cache lookup executor")

p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# PlaybackProblemReporter: include operation trail and keep playback reports in
# the same 10-entry history used by crash/ANR reports.
# ---------------------------------------------------------------------------
p = Path("app/src/main/java/com/jianglab/babywife/PlaybackProblemReporter.java")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    private static final String KEY_REPORT_DISMISSED = "last_crash_report_dismissed";''',
    '''    private static final String KEY_REPORT_DISMISSED = "last_crash_report_dismissed";\n    private static final String KEY_HISTORY = "problem_report_history_v1";\n    private static final int MAX_HISTORY = 10;''',
    "playback report history constants",
)

old = '''                      boolean deviceInteractive, boolean preparing,\n                      boolean expectedPlaying, boolean userPaused) {'''
new = '''                      boolean deviceInteractive, boolean preparing,\n                      boolean expectedPlaying, boolean userPaused,\n                      String recentActions) {'''
text = replace_once(text, old, new, "playback reporter action argument")

old = '''            report.append("catalog=").append(trim(catalogJson, 1800)).append('\\n');\n\n            String text = trim(report.toString(), 60000);\n            SharedPreferences preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);\n            preferences.edit()\n                .putString(KEY_REPORT, text)\n                .putLong(KEY_REPORT_TIME, System.currentTimeMillis())\n                .putBoolean(KEY_REPORT_DISMISSED, false)\n                .commit();'''
new = '''            report.append("catalog=").append(trim(catalogJson, 1800)).append('\\n');\n            if (recentActions != null && !recentActions.trim().isEmpty()) {\n                report.append("\\nRecent actions (oldest -> newest):\\n")\n                    .append(trim(recentActions, 14000)).append('\\n');\n            }\n\n            String text = trim(report.toString(), 60000);\n            long now = System.currentTimeMillis();\n            SharedPreferences preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);\n            org.json.JSONArray oldHistory;\n            try {\n                oldHistory = new org.json.JSONArray(preferences.getString(KEY_HISTORY, "[]"));\n            } catch (Throwable ignored) {\n                oldHistory = new org.json.JSONArray();\n            }\n            org.json.JSONArray next = new org.json.JSONArray();\n            try {\n                org.json.JSONObject newest = new org.json.JSONObject();\n                newest.put("name", new java.text.SimpleDateFormat(\n                    "yyyyMMdd_HHmmss", java.util.Locale.ROOT).format(new java.util.Date(now)));\n                newest.put("time", now);\n                newest.put("text", text);\n                next.put(newest);\n                for (int i = 0; i < oldHistory.length() && next.length() < MAX_HISTORY; i++) {\n                    org.json.JSONObject item = oldHistory.optJSONObject(i);\n                    if (item != null) next.put(item);\n                }\n            } catch (Throwable ignored) {\n            }\n            preferences.edit()\n                .putString(KEY_HISTORY, next.toString())\n                .putString(KEY_REPORT, text)\n                .putLong(KEY_REPORT_TIME, now)\n                .putBoolean(KEY_REPORT_DISMISSED, false)\n                .commit();'''
text = replace_once(text, old, new, "playback report recent actions and history")
p.write_text(text, encoding="utf-8")
