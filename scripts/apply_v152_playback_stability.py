from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
main_path = root / "app/src/main/java/com/jianglab/babywife/MainActivity.java"
search_path = root / "app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java"

main = main_path.read_text(encoding="utf-8")
search = search_path.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{label}: expected one regex match, found {count}")
    return updated


main = replace_once(
    main,
    "import android.app.Activity;\nimport android.app.AlertDialog;",
    "import android.app.Activity;\nimport android.app.ActivityManager;\nimport android.app.AlertDialog;\nimport android.app.ApplicationExitInfo;",
    "android exit-info imports",
)

main = replace_once(
    main,
    "    private static final long UI_HEARTBEAT_INTERVAL_MS = 1000L;",
    "    private static final long UI_HEARTBEAT_INTERVAL_MS = 1000L;\n"
    "    private static final long PLAYBACK_NAVIGATION_DEBOUNCE_MS = 220L;\n"
    "    private static final String KEY_LAST_HANDLED_EXIT_TIME = \"last_handled_exit_time\";\n"
    "    private static final String KEY_PLAYBACK_TRANSITION_PENDING = \"playback_transition_pending\";\n"
    "    private static final String KEY_PLAYBACK_TRANSITION_DETAIL = \"playback_transition_detail\";\n"
    "    private static final String KEY_PLAYBACK_TRANSITION_TIME = \"playback_transition_time\";",
    "v152 constants",
)

main = replace_once(
    main,
    "    private volatile int foregroundPlaybackSerial = 0;",
    "    private volatile int foregroundPlaybackSerial = 0;\n"
    "    private final Handler playbackNavigationHandler = new Handler(Looper.getMainLooper());\n"
    "    private int pendingNavigationOffset = 0;\n"
    "    private final Runnable playbackNavigationRunnable = () -> {\n"
    "        int offset = pendingNavigationOffset;\n"
    "        pendingNavigationOffset = 0;\n"
    "        if (offset != 0) performPlaylistOffset(offset);\n"
    "    };\n"
    "    private final ExecutorService mediaSourceExecutor = Executors.newSingleThreadExecutor();\n"
    "    private final ExecutorService searchCacheExecutor = Executors.newSingleThreadExecutor();\n"
    "    private Future<?> mediaSourceOpenFuture;\n"
    "    private Future<?> searchCacheFuture;\n"
    "    private int mediaOpenSerial = 0;\n"
    "    private volatile boolean activityDestroyed = false;",
    "v152 playback fields",
)

main = replace_once(
    main,
    "        installCrashReporter();\n        normalStatusBarColor",
    "        installCrashReporter();\n        captureLastProcessExitReport();\n        normalStatusBarColor",
    "capture process exit at startup",
)

main = replace_once(
    main,
    "    @Override\n    protected void onPause() {\n        activityResumed = false;\n        windowFocused = false;\n        lastUiHeartbeatMs = System.currentTimeMillis();\n        noResponseReportWritten = false;\n        responsivenessHandler.removeCallbacks(responsivenessHeartbeat);\n        super.onPause();\n    }",
    "    @Override\n    protected void onPause() {\n        activityResumed = false;\n        windowFocused = false;\n        lastUiHeartbeatMs = System.currentTimeMillis();\n        noResponseReportWritten = false;\n        responsivenessHandler.removeCallbacks(responsivenessHeartbeat);\n        super.onPause();\n    }\n\n"
    "    @Override\n    protected void onDestroy() {\n        activityDestroyed = true;\n        clearPendingPlaybackNavigation();\n        cancelMediaSourceOpenTask();\n        cancelSearchCacheTask();\n        mediaSourceExecutor.shutdownNow();\n        searchCacheExecutor.shutdownNow();\n        stopPlayback();\n        super.onDestroy();\n    }",
    "activity destruction cleanup",
)

exit_methods = r'''
    private void captureLastProcessExitReport() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return;
        try {
            SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
            String existing = prefs.getString(KEY_CRASH_REPORT, "");
            long handledTime = prefs.getLong(KEY_LAST_HANDLED_EXIT_TIME, 0L);
            ActivityManager manager = (ActivityManager) getSystemService(ACTIVITY_SERVICE);
            if (manager == null) return;
            List<ApplicationExitInfo> exits = manager.getHistoricalProcessExitReasons(
                getPackageName(), 0, 8);
            if (exits == null || exits.isEmpty()) return;

            ApplicationExitInfo latest = null;
            for (ApplicationExitInfo info : exits) {
                if (info == null || info.getTimestamp() <= handledTime) continue;
                if (latest == null || info.getTimestamp() > latest.getTimestamp()) latest = info;
            }
            if (latest == null) return;
            prefs.edit().putLong(KEY_LAST_HANDLED_EXIT_TIME, latest.getTimestamp()).apply();
            if (existing != null && !existing.trim().isEmpty()) return;
            if (!isDiagnosticExitReason(latest.getReason())) return;

            StringBuilder report = new StringBuilder();
            report.append("Process exit report\n");
            appendReportContext(report, "system-exit-history");
            report.append("exitTime=").append(latest.getTimestamp()).append('\n');
            report.append("reason=").append(exitReasonText(latest.getReason()))
                .append(" (").append(latest.getReason()).append(")\n");
            report.append("status=").append(latest.getStatus()).append('\n');
            report.append("importance=").append(latest.getImportance()).append('\n');
            report.append("pssKb=").append(latest.getPss()).append('\n');
            report.append("rssKb=").append(latest.getRss()).append('\n');
            String description = latest.getDescription();
            if (description != null && !description.trim().isEmpty()) {
                report.append("description=").append(description.trim()).append('\n');
            }
            if (prefs.getBoolean(KEY_PLAYBACK_TRANSITION_PENDING, false)) {
                report.append("pendingPlaybackTransition=")
                    .append(prefs.getString(KEY_PLAYBACK_TRANSITION_DETAIL, ""))
                    .append('\n');
                report.append("pendingPlaybackTransitionTime=")
                    .append(prefs.getLong(KEY_PLAYBACK_TRANSITION_TIME, 0L)).append('\n');
            }
            storeProblemReport(report.toString());
        } catch (Throwable ignored) {
        }
    }

    private boolean isDiagnosticExitReason(int reason) {
        return reason == ApplicationExitInfo.REASON_CRASH
            || reason == ApplicationExitInfo.REASON_CRASH_NATIVE
            || reason == ApplicationExitInfo.REASON_ANR
            || reason == ApplicationExitInfo.REASON_LOW_MEMORY
            || reason == ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE
            || reason == ApplicationExitInfo.REASON_INITIALIZATION_FAILURE
            || reason == ApplicationExitInfo.REASON_SIGNALED;
    }

    private String exitReasonText(int reason) {
        if (reason == ApplicationExitInfo.REASON_CRASH) return "Java crash";
        if (reason == ApplicationExitInfo.REASON_CRASH_NATIVE) return "Native crash";
        if (reason == ApplicationExitInfo.REASON_ANR) return "ANR";
        if (reason == ApplicationExitInfo.REASON_LOW_MEMORY) return "Low memory";
        if (reason == ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE) return "Excessive resource usage";
        if (reason == ApplicationExitInfo.REASON_INITIALIZATION_FAILURE) return "Initialization failure";
        if (reason == ApplicationExitInfo.REASON_SIGNALED) return "Killed by signal";
        return "Other";
    }

    private void recordPlaybackTransition(Song song, int playToken) {
        if (song == null) return;
        String detail = "token=" + playToken
            + ", queue=" + (playingSearchQueue ? "search" : "playlist")
            + ", title=" + song.title
            + ", artist=" + song.artist;
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit()
            .putBoolean(KEY_PLAYBACK_TRANSITION_PENDING, true)
            .putString(KEY_PLAYBACK_TRANSITION_DETAIL, detail)
            .putLong(KEY_PLAYBACK_TRANSITION_TIME, System.currentTimeMillis())
            .apply();
    }

    private void clearPlaybackTransition() {
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit()
            .putBoolean(KEY_PLAYBACK_TRANSITION_PENDING, false)
            .apply();
    }
'''

main = replace_once(
    main,
    "    private void persistCrashReport(Thread thread, Throwable throwable) {",
    exit_methods + "\n    private void persistCrashReport(Thread thread, Throwable throwable) {",
    "system exit reporting methods",
)

main = replace_once(
    main,
    "    private void playSong(Song song) {\n        if (song == null) return;\n        int playToken = ++playbackRequestSerial;\n        foregroundPlaybackSerial = playToken;",
    "    private void playSong(Song song) {\n        if (song == null) return;\n        clearPendingPlaybackNavigation();\n        cancelMediaSourceOpenTask();\n        cancelSearchCacheTask();\n        int playToken = ++playbackRequestSerial;\n        foregroundPlaybackSerial = playToken;\n        recordPlaybackTransition(song, playToken);",
    "play request cancellation and breadcrumb",
)

cache_method = r'''    private void cacheSearchPlaybackAsync(Song song, SearchQuickPlayback.Candidate candidate,
                                          int playToken) {
        cancelSearchCacheTask();
        searchCacheFuture = searchCacheExecutor.submit(() -> {
            try {
                if (Thread.currentThread().isInterrupted()
                    || activityDestroyed || playToken != foregroundPlaybackSerial) return;
                String storedUri = SearchQuickPlayback.cache(
                    this, candidate, song.title, song.artist, "");
                if (Thread.currentThread().isInterrupted()
                    || activityDestroyed || playToken != foregroundPlaybackSerial) return;
                runOnUiThread(() -> {
                    if (activityDestroyed || currentSong != song
                        || playToken != playbackRequestSerial) return;
                    song.cachedUri = storedUri;
                    persistSearchCacheToPlaylistCopies(song, candidate, storedUri);
                    int position = 0;
                    try {
                        if (mediaPlayer != null) position = mediaPlayer.getCurrentPosition();
                    } catch (Exception ignored) {
                    }
                    saveLastSong(position);
                    statusView.setText("当前播放：" + song.title
                        + "（缓存已保存为“" + song.title + " - " + song.artist + "”）");
                });
            } catch (Exception error) {
                if (Thread.currentThread().isInterrupted()) return;
                runOnUiThread(() -> {
                    if (!activityDestroyed && currentSong == song
                        && playToken == playbackRequestSerial) {
                        statusView.setText("当前播放正常，但后台缓存失败：" + error.getMessage());
                    }
                });
            }
        });
    }

    private void persistSearchCacheToPlaylistCopies'''

main = regex_once(
    main,
    r"    private void cacheSearchPlaybackAsync\(Song song, SearchQuickPlayback\.Candidate candidate,.*?\n    }\n\n    private void persistSearchCacheToPlaylistCopies",
    cache_method,
    "serialized search cache method",
)

navigation_methods = r'''    private void playPlaylistOffset(int offset) {
        if (offset == 0) {
            performPlaylistOffset(0);
            return;
        }
        long combined = (long) pendingNavigationOffset + offset;
        pendingNavigationOffset = (int) Math.max(-1000L, Math.min(1000L, combined));
        playbackNavigationHandler.removeCallbacks(playbackNavigationRunnable);
        playbackNavigationHandler.postDelayed(
            playbackNavigationRunnable, PLAYBACK_NAVIGATION_DEBOUNCE_MS);
        if (statusView != null) statusView.setText("正在切换歌曲...");
    }

    private void performPlaylistOffset(int offset) {
        if (playingSearchQueue) {
            if (searchResults.isEmpty()) {
                toast("搜索队列为空");
                return;
            }
            int nextIndex = searchSongIndex;
            if (nextIndex < 0 || nextIndex >= searchResults.size()) {
                nextIndex = 0;
            } else {
                nextIndex = (nextIndex + offset % searchResults.size()
                    + searchResults.size()) % searchResults.size();
            }
            playSongFromSearch(nextIndex);
            return;
        }
        Playlist playlist = currentPlaylist();
        if (playlist.songs.isEmpty()) {
            toast("当前歌单为空");
            return;
        }
        int nextIndex = currentSongIndex;
        if (nextIndex < 0 || nextIndex >= playlist.songs.size()) {
            nextIndex = 0;
        } else if (playMode == 2 && offset != 0) {
            nextIndex = random.nextInt(playlist.songs.size());
        } else {
            nextIndex = (nextIndex + offset % playlist.songs.size()
                + playlist.songs.size()) % playlist.songs.size();
        }
        playSongFromPlaylist(nextIndex);
    }

    private void clearPendingPlaybackNavigation() {
        pendingNavigationOffset = 0;
        playbackNavigationHandler.removeCallbacks(playbackNavigationRunnable);
    }

    private void playAfterCompletion'''

main = regex_once(
    main,
    r"    private void playPlaylistOffset\(int offset\) \{.*?\n    }\n\n    private void playAfterCompletion",
    navigation_methods,
    "debounced playlist navigation",
)

main = replace_once(
    main,
    "        if (playingSearchQueue) {\n            playPlaylistOffset(1);\n            return;\n        }\n        if (playMode == 0) {\n            playSong(currentSong);\n        } else {\n            playPlaylistOffset(1);\n        }",
    "        if (playingSearchQueue) {\n            performPlaylistOffset(1);\n            return;\n        }\n        if (playMode == 0) {\n            playSong(currentSong);\n        } else {\n            performPlaylistOffset(1);\n        }",
    "completion bypasses manual debounce",
)

start_method = r'''    private void startLocalPlayback(Song song, int playToken, Runnable onStarted, Runnable onFailed) {
        stopPlayback();
        String playbackUri = song.uri == null ? "" : song.uri.trim();
        if (playbackUri.isEmpty()) {
            clearPlaybackTransition();
            if (onFailed != null) onFailed.run();
            return;
        }
        boolean online = playbackUri.startsWith("http://") || playbackUri.startsWith("https://");
        statusView.setText(online ? "正在异步打开在线音频..." : "缓存已就绪，正在异步打开音频...");
        int openSerial = ++mediaOpenSerial;
        mediaSourceOpenFuture = mediaSourceExecutor.submit(() -> {
            MediaPlayer preparedPlayer = null;
            try {
                if (Thread.currentThread().isInterrupted() || activityDestroyed
                    || playToken != foregroundPlaybackSerial || openSerial != mediaOpenSerial) return;
                preparedPlayer = createWakefulMediaPlayer();
                preparedPlayer.setDataSource(this, Uri.parse(playbackUri));
                if (Thread.currentThread().isInterrupted() || activityDestroyed
                    || playToken != foregroundPlaybackSerial || openSerial != mediaOpenSerial) {
                    releaseMediaPlayer(preparedPlayer);
                    return;
                }
                MediaPlayer readyPlayer = preparedPlayer;
                runOnUiThread(() -> {
                    if (activityDestroyed || currentSong != song
                        || playToken != playbackRequestSerial || openSerial != mediaOpenSerial) {
                        releaseMediaPlayer(readyPlayer);
                        return;
                    }
                    MediaPlayer previous = mediaPlayer;
                    mediaPlayer = null;
                    releaseMediaPlayer(previous);
                    mediaPlayer = readyPlayer;
                    readyPlayer.setOnCompletionListener(player -> {
                        if (mediaPlayer == player && currentSong == song
                            && playToken == playbackRequestSerial) {
                            playAfterCompletion();
                        }
                    });
                    readyPlayer.setOnErrorListener((player, what, extra) -> {
                        if (mediaPlayer == player && currentSong == song
                            && playToken == playbackRequestSerial) {
                            mediaPlayer = null;
                            releaseMediaPlayer(player);
                            lyricHandler.removeCallbacks(lyricTicker);
                            resetPlaybackProgress();
                            playButton.setText("▶");
                            statusView.setText("播放失败：当前来源不可用（" + what + "/" + extra + "）");
                            clearPlaybackTransition();
                            if (onFailed != null) onFailed.run();
                            publishPlaybackControlState(true);
                        } else {
                            releaseMediaPlayer(player);
                        }
                        return true;
                    });
                    readyPlayer.setOnPreparedListener(player -> {
                        if (mediaPlayer != player || currentSong != song
                            || playToken != playbackRequestSerial || openSerial != mediaOpenSerial) {
                            if (mediaPlayer != player) releaseMediaPlayer(player);
                            return;
                        }
                        try {
                            player.start();
                            onPlaybackStarted(song, onStarted);
                        } catch (Exception error) {
                            mediaPlayer = null;
                            releaseMediaPlayer(player);
                            lyricHandler.removeCallbacks(lyricTicker);
                            resetPlaybackProgress();
                            playButton.setText("▶");
                            statusView.setText("播放失败：" + error.getMessage());
                            clearPlaybackTransition();
                            if (onFailed != null) onFailed.run();
                        }
                    });
                    try {
                        readyPlayer.prepareAsync();
                    } catch (Exception error) {
                        mediaPlayer = null;
                        releaseMediaPlayer(readyPlayer);
                        playButton.setText("▶");
                        statusView.setText("播放失败：" + error.getMessage());
                        clearPlaybackTransition();
                        if (onFailed != null) onFailed.run();
                    }
                });
            } catch (Throwable error) {
                releaseMediaPlayer(preparedPlayer);
                runOnUiThread(() -> {
                    if (activityDestroyed || currentSong != song
                        || playToken != playbackRequestSerial || openSerial != mediaOpenSerial) return;
                    playButton.setText("▶");
                    statusView.setText("打开音频失败：" + error.getClass().getSimpleName()
                        + (error.getMessage() == null ? "" : "：" + error.getMessage()));
                    clearPlaybackTransition();
                    if (onFailed != null) onFailed.run();
                });
            }
        });
    }

    private void onPlaybackStarted'''

main = regex_once(
    main,
    r"    private void startLocalPlayback\(Song song, int playToken, Runnable onStarted, Runnable onFailed\) \{.*?\n    }\n\n    private void onPlaybackStarted",
    start_method,
    "serialized media-source opening",
)

main = replace_once(
    main,
    "    private void onPlaybackStarted(Song song, Runnable onStarted) {\n        playButton.setText(\"Ⅱ\");",
    "    private void onPlaybackStarted(Song song, Runnable onStarted) {\n        clearPlaybackTransition();\n        playButton.setText(\"Ⅱ\");",
    "clear playback breadcrumb on successful start",
)

release_methods = r'''    private void stopPlayback() {
        cancelMediaSourceOpenTask();
        MediaPlayer player = mediaPlayer;
        mediaPlayer = null;
        releaseMediaPlayer(player);
        lyricHandler.removeCallbacks(lyricTicker);
        resetPlaybackProgress();
        publishPlaybackControlState(true);
    }

    private void cancelMediaSourceOpenTask() {
        mediaOpenSerial++;
        Future<?> task = mediaSourceOpenFuture;
        mediaSourceOpenFuture = null;
        if (task != null) task.cancel(true);
    }

    private void cancelSearchCacheTask() {
        Future<?> task = searchCacheFuture;
        searchCacheFuture = null;
        if (task != null) task.cancel(true);
    }

    private void releaseMediaPlayer(MediaPlayer player) {
        if (player == null) return;
        try {
            player.setOnPreparedListener(null);
            player.setOnCompletionListener(null);
            player.setOnErrorListener(null);
        } catch (Exception ignored) {
        }
        try {
            player.stop();
        } catch (Exception ignored) {
        }
        try {
            player.reset();
        } catch (Exception ignored) {
        }
        try {
            player.release();
        } catch (Exception ignored) {
        }
    }

    private LinearLayout buildDrawerPanel'''

main = regex_once(
    main,
    r"    private void stopPlayback\(\) \{.*?\n    }\n\n    private LinearLayout buildDrawerPanel",
    release_methods,
    "safe player release and task cancellation",
)

search = replace_once(
    search,
    "        try {\n            Candidate downloadCandidate = downloadWithFreshAddress(playbackCandidate, partial);",
    "        try {\n            throwIfInterrupted();\n            Candidate downloadCandidate = downloadWithFreshAddress(playbackCandidate, partial);\n            throwIfInterrupted();",
    "search cache interruption before decode",
)

search = replace_once(
    search,
    "            AudioPlaybackVerifier.Probe probe = AudioPlaybackVerifier.probeFile(source);",
    "            throwIfInterrupted();\n            AudioPlaybackVerifier.Probe probe = AudioPlaybackVerifier.probeFile(source);",
    "search cache interruption before probe",
)

search = replace_once(
    search,
    "            String storedUri = CacheStorage.storeAudio(context, key, extension, source,",
    "            throwIfInterrupted();\n            String storedUri = CacheStorage.storeAudio(context, key, extension, source,",
    "search cache interruption before store",
)

search = replace_once(
    search,
    "        for (int attempt = 0; attempt < DOWNLOAD_ATTEMPTS; attempt++) {",
    "        for (int attempt = 0; attempt < DOWNLOAD_ATTEMPTS; attempt++) {\n            throwIfInterrupted();",
    "search retry interruption",
)

search = replace_once(
    search,
    "            while (!complete) {\n                if (writtenTotal >= MAX_AUDIO_BYTES)",
    "            while (!complete) {\n                throwIfInterrupted();\n                if (writtenTotal >= MAX_AUDIO_BYTES)",
    "range segment interruption",
)

search = replace_once(
    search,
    "                        while ((read = input.read(buffer)) >= 0) {\n                            if (read == 0) continue;",
    "                        while ((read = input.read(buffer)) >= 0) {\n                            throwIfInterrupted();\n                            if (read == 0) continue;",
    "range read interruption",
)

search = replace_once(
    search,
    "        for (int redirect = 0; redirect <= MAX_REDIRECTS; redirect++) {",
    "        for (int redirect = 0; redirect <= MAX_REDIRECTS; redirect++) {\n            throwIfInterrupted();",
    "redirect interruption",
)

search = replace_once(
    search,
    "    private static long parseContentRangeTotal(String value) {",
    "    private static void throwIfInterrupted() {\n"
    "        if (Thread.currentThread().isInterrupted()) {\n"
    "            throw new IllegalStateException(\"搜索歌曲后台缓存已取消\");\n"
    "        }\n"
    "    }\n\n"
    "    private static long parseContentRangeTotal(String value) {",
    "interruption helper",
)

main_path.write_text(main, encoding="utf-8")
search_path.write_text(search, encoding="utf-8")
print("v152 playback stability source patch applied")
