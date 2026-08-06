from pathlib import Path
import re

path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = path.read_text(encoding="utf-8")


def once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    text = text.replace(old, new, 1)


once(
    "    private static final long PLAYBACK_NAVIGATION_DEBOUNCE_MS = 220L;\n",
    "    private static final long PLAYBACK_NAVIGATION_DEBOUNCE_MS = 220L;\n"
    "    private static final long PLAYBACK_HEALTH_CHECK_INTERVAL_MS = 2000L;\n"
    "    private static final long PLAYBACK_STALL_REPORT_MS = 12000L;\n",
    "playback health constants",
)

once(
    "    private final Handler responsivenessHandler = new Handler(Looper.getMainLooper());\n",
    "    private final Handler responsivenessHandler = new Handler(Looper.getMainLooper());\n"
    "    private final Handler playbackHealthHandler = new Handler(Looper.getMainLooper());\n",
    "playback health handler",
)

once(
    "    private volatile boolean activityDestroyed = false;\n",
    "    private volatile boolean activityDestroyed = false;\n"
    "    private boolean playbackPreparing = false;\n"
    "    private boolean playbackExpectedPlaying = false;\n"
    "    private boolean playbackUserPaused = false;\n"
    "    private boolean playbackSilentStopReported = false;\n"
    "    private long playbackLastObservedPosition = -1L;\n"
    "    private long playbackLastProgressTime = 0L;\n",
    "playback health state",
)

on_create_boundary = "\n\n    @Override\n    protected void onCreate(Bundle savedInstanceState) {"
ticker = """
    private final Runnable playbackHealthTicker = new Runnable() {
        @Override
        public void run() {
            checkPlaybackHealth();
            if (playbackExpectedPlaying && !activityDestroyed) {
                playbackHealthHandler.postDelayed(
                    this, PLAYBACK_HEALTH_CHECK_INTERVAL_MS);
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {"""
once(on_create_boundary, "\n\n" + ticker, "playback health ticker")

report_anchor = "    private void persistCrashReport(Thread thread, Throwable throwable) {"
methods = """    private void reportPlaybackProblem(String reason, MediaPlayer player,
                                               int what, int extra, String playbackUri) {
        Playlist playlist = currentPlaylist();
        Song song = currentSong;
        PlaybackProblemReporter.store(
            this,
            reason,
            player,
            what,
            extra,
            playingSearchQueue ? "search" : "playlist",
            currentPlaylistIndex,
            currentSongIndex,
            playlist == null ? "" : playlist.name,
            song == null ? "" : song.title,
            song == null ? "" : song.artist,
            song == null ? "" : song.source,
            playbackUri,
            song == null ? "" : song.cachedUri,
            song == null ? "" : song.catalogJson,
            activityResumed,
            windowFocused,
            isDeviceInteractive(),
            playbackPreparing,
            playbackExpectedPlaying,
            playbackUserPaused
        );
    }

    private long safePlaybackPosition(MediaPlayer player) {
        if (player == null) return -1L;
        try {
            return player.getCurrentPosition();
        } catch (Exception ignored) {
            return -1L;
        }
    }

    private long safePlaybackDuration(MediaPlayer player) {
        if (player == null) return -1L;
        try {
            return player.getDuration();
        } catch (Exception ignored) {
            return -1L;
        }
    }

    private boolean safePlaybackIsPlaying(MediaPlayer player) {
        if (player == null) return false;
        try {
            return player.isPlaying();
        } catch (Exception ignored) {
            return false;
        }
    }

    private void startPlaybackHealthWatch(MediaPlayer player) {
        playbackPreparing = false;
        playbackExpectedPlaying = true;
        playbackUserPaused = false;
        playbackSilentStopReported = false;
        playbackLastObservedPosition = safePlaybackPosition(player);
        playbackLastProgressTime = System.currentTimeMillis();
        playbackHealthHandler.removeCallbacks(playbackHealthTicker);
        playbackHealthHandler.postDelayed(
            playbackHealthTicker, PLAYBACK_HEALTH_CHECK_INTERVAL_MS);
    }

    private void stopPlaybackHealthWatch() {
        playbackExpectedPlaying = false;
        playbackHealthHandler.removeCallbacks(playbackHealthTicker);
    }

    private void checkPlaybackHealth() {
        if (!playbackExpectedPlaying || playbackPreparing || playbackUserPaused
            || activityDestroyed) return;
        MediaPlayer player = mediaPlayer;
        if (player == null) {
            if (!playbackSilentStopReported) {
                playbackSilentStopReported = true;
                reportPlaybackProblem(
                    "player-disappeared-without-error-callback",
                    null, 0, 0, currentSong == null ? "" : currentSong.uri);
            }
            stopPlaybackHealthWatch();
            return;
        }

        long now = System.currentTimeMillis();
        long position = safePlaybackPosition(player);
        long duration = safePlaybackDuration(player);
        boolean playing = safePlaybackIsPlaying(player);
        if (position >= 0L && position > playbackLastObservedPosition + 250L) {
            playbackLastObservedPosition = position;
            playbackLastProgressTime = now;
            playbackSilentStopReported = false;
            return;
        }

        boolean nearEnd = duration > 0L && position >= 0L
            && position + 3000L >= duration;
        if (nearEnd || now - playbackLastProgressTime < PLAYBACK_STALL_REPORT_MS
            || playbackSilentStopReported) return;

        playbackSilentStopReported = true;
        reportPlaybackProblem(
            playing ? "playback-position-stalled"
                : "playback-stopped-without-callback",
            player, 0, 0, currentSong == null ? "" : currentSong.uri);
        if (playing) {
            if (statusView != null) {
                statusView.setText("播放进度长时间未变化，已生成播放问题报告");
            }
            return;
        }

        try {
            player.start();
            playbackLastProgressTime = now;
            playbackSilentStopReported = false;
            if (statusView != null) {
                statusView.setText("检测到播放意外停止，已自动尝试恢复并生成报告");
            }
            publishPlaybackControlState(true);
        } catch (Exception error) {
            stopPlaybackHealthWatch();
            if (playButton != null) playButton.setText("▶");
            if (statusView != null) {
                statusView.setText("播放意外停止，自动恢复失败，已生成报告");
            }
            publishPlaybackControlState(true);
        }
    }

    private void deleteIncompletePlaybackCache(Song song, String playbackUri) {
        try {
            CacheFileState.deleteDirect(this, playbackUri);
        } catch (Exception ignored) {
        }
        if (song == null) return;
        try {
            NetworkMediaCache.deleteCatalogCache(this, song.catalogJson);
        } catch (Exception ignored) {
        }
        song.cachedUri = "";
        song.uri = "";
        savePlaylists();
    }

"""
once(report_anchor, methods + report_anchor, "playback report methods")

once(
    "    private void startLocalPlayback(Song song, int playToken, Runnable onStarted, Runnable onFailed) {\n"
    "        stopPlayback();\n",
    "    private void startLocalPlayback(Song song, int playToken, Runnable onStarted, Runnable onFailed) {\n"
    "        stopPlayback();\n"
    "        playbackPreparing = true;\n"
    "        playbackUserPaused = false;\n",
    "playback preparing state",
)

once(
    "        if (playbackUri.isEmpty()) {\n"
    "            clearPlaybackTransition();\n",
    "        if (playbackUri.isEmpty()) {\n"
    "            playbackPreparing = false;\n"
    "            clearPlaybackTransition();\n",
    "empty playback URI state",
)

completion_pattern = re.compile(
    r"                    readyPlayer\.setOnCompletionListener\(player -> \{\n"
    r"                        if \(mediaPlayer == player && currentSong == song\n"
    r"                            && playToken == playbackRequestSerial\) \{\n"
    r"                            playAfterCompletion\(\);\n"
    r"                        \}\n"
    r"                    \}\);"
)
completion_replacement = """                    readyPlayer.setOnCompletionListener(player -> {
                        if (mediaPlayer == player && currentSong == song
                            && playToken == playbackRequestSerial) {
                            stopPlaybackHealthWatch();
                            playbackPreparing = false;
                            long actualDuration = safePlaybackDuration(player);
                            if (PlaybackDurationGuard.clearlyShort(
                                song.catalogJson, playbackUri,
                                song.isNetworkCatalog(), actualDuration)) {
                                reportPlaybackProblem(
                                    "cached-audio-ended-before-catalog-duration",
                                    player, 0, 0, playbackUri);
                                mediaPlayer = null;
                                releaseMediaPlayer(player);
                                deleteIncompletePlaybackCache(song, playbackUri);
                                if (statusView != null) {
                                    statusView.setText("检测到缓存歌曲不完整，已删除并重新获取");
                                }
                                if (onFailed != null) onFailed.run();
                                return;
                            }
                            playAfterCompletion();
                        }
                    });"""
text, count = completion_pattern.subn(completion_replacement, text, count=1)
if count != 1:
    raise SystemExit(f"completion listener: expected one match, found {count}")

error_pattern = re.compile(
    r"                    readyPlayer\.setOnErrorListener\(\(player, what, extra\) -> \{.*?\n"
    r"                        return true;\n"
    r"                    \}\);",
    re.S,
)
error_replacement = """                    readyPlayer.setOnErrorListener((player, what, extra) -> {
                        if (mediaPlayer == player && currentSong == song
                            && playToken == playbackRequestSerial) {
                            reportPlaybackProblem(
                                "media-player-error", player, what, extra, playbackUri);
                            playbackPreparing = false;
                            stopPlaybackHealthWatch();
                            mediaPlayer = null;
                            releaseMediaPlayer(player);
                            lyricHandler.removeCallbacks(lyricTicker);
                            resetPlaybackProgress();
                            playButton.setText("▶");
                            statusView.setText("播放失败：当前来源不可用（"
                                + what + "/" + extra + "），已生成播放问题报告");
                            clearPlaybackTransition();
                            if (onFailed != null) onFailed.run();
                            publishPlaybackControlState(true);
                        } else {
                            releaseMediaPlayer(player);
                        }
                        return true;
                    });"""
text, count = error_pattern.subn(error_replacement, text, count=1)
if count != 1:
    raise SystemExit(f"error listener: expected one match, found {count}")

prepared_anchor = """                        try {
                            player.start();
                            onPlaybackStarted(song, onStarted);
                        } catch (Exception error) {"""
prepared_replacement = """                        try {
                            long actualDuration = safePlaybackDuration(player);
                            if (PlaybackDurationGuard.clearlyShort(
                                song.catalogJson, playbackUri,
                                song.isNetworkCatalog(), actualDuration)) {
                                reportPlaybackProblem(
                                    "cached-duration-short-before-start",
                                    player, 0, 0, playbackUri);
                                playbackPreparing = false;
                                mediaPlayer = null;
                                releaseMediaPlayer(player);
                                deleteIncompletePlaybackCache(song, playbackUri);
                                if (statusView != null) {
                                    statusView.setText("检测到缓存歌曲时长不完整，已删除并重新获取");
                                }
                                if (onFailed != null) onFailed.run();
                                return;
                            }
                            player.start();
                            onPlaybackStarted(song, onStarted);
                        } catch (Exception error) {"""
once(prepared_anchor, prepared_replacement, "prepared duration guard")

once(
    "                        } catch (Exception error) {\n"
    "                            mediaPlayer = null;\n"
    "                            releaseMediaPlayer(player);\n"
    "                            lyricHandler.removeCallbacks(lyricTicker);\n",
    "                        } catch (Exception error) {\n"
    "                            reportPlaybackProblem(\n"
    "                                \"player-start-exception\", player, 0, 0, playbackUri);\n"
    "                            playbackPreparing = false;\n"
    "                            stopPlaybackHealthWatch();\n"
    "                            mediaPlayer = null;\n"
    "                            releaseMediaPlayer(player);\n"
    "                            lyricHandler.removeCallbacks(lyricTicker);\n",
    "player start exception report",
)

once(
    "                    } catch (Exception error) {\n"
    "                        mediaPlayer = null;\n"
    "                        releaseMediaPlayer(readyPlayer);\n",
    "                    } catch (Exception error) {\n"
    "                        reportPlaybackProblem(\n"
    "                            \"prepare-async-exception\", readyPlayer, 0, 0, playbackUri);\n"
    "                        playbackPreparing = false;\n"
    "                        stopPlaybackHealthWatch();\n"
    "                        mediaPlayer = null;\n"
    "                        releaseMediaPlayer(readyPlayer);\n",
    "prepareAsync exception report",
)

once(
    "            } catch (Throwable error) {\n"
    "                releaseMediaPlayer(preparedPlayer);\n",
    "            } catch (Throwable error) {\n"
    "                playbackPreparing = false;\n"
    "                releaseMediaPlayer(preparedPlayer);\n",
    "source open exception state",
)

once(
    "    private void onPlaybackStarted(Song song, Runnable onStarted) {\n"
    "        clearPlaybackTransition();\n",
    "    private void onPlaybackStarted(Song song, Runnable onStarted) {\n"
    "        startPlaybackHealthWatch(mediaPlayer);\n"
    "        clearPlaybackTransition();\n",
    "start playback health watch",
)

once(
    "        if (mediaPlayer.isPlaying()) {\n"
    "            mediaPlayer.pause();\n",
    "        if (mediaPlayer.isPlaying()) {\n"
    "            playbackUserPaused = true;\n"
    "            stopPlaybackHealthWatch();\n"
    "            mediaPlayer.pause();\n",
    "user pause state",
)

resume_anchor = """        } else {
            mediaPlayer.start();
            playButton.setText("Ⅱ");
            lyricHandler.post(lyricTicker);
        }
        publishPlaybackControlState(true);"""
resume_replacement = """        } else {
            mediaPlayer.start();
            playbackUserPaused = false;
            startPlaybackHealthWatch(mediaPlayer);
            playButton.setText("Ⅱ");
            lyricHandler.post(lyricTicker);
        }
        publishPlaybackControlState(true);"""
once(resume_anchor, resume_replacement, "user resume state")

once(
    "    private void stopPlayback() {\n"
    "        cancelMediaSourceOpenTask();\n",
    "    private void stopPlayback() {\n"
    "        playbackPreparing = false;\n"
    "        playbackUserPaused = false;\n"
    "        stopPlaybackHealthWatch();\n"
    "        cancelMediaSourceOpenTask();\n",
    "stop playback health state",
)

once(
    "    protected void onDestroy() {\n"
    "        activityDestroyed = true;\n",
    "    protected void onDestroy() {\n"
    "        if (playbackExpectedPlaying && mediaPlayer != null) {\n"
    "            reportPlaybackProblem(\n"
    "                \"activity-destroyed-during-active-playback\",\n"
    "                mediaPlayer, 0, 0, currentSong == null ? \"\" : currentSong.uri);\n"
    "        }\n"
    "        activityDestroyed = true;\n"
    "        playbackHealthHandler.removeCallbacks(playbackHealthTicker);\n",
    "activity destroy playback report",
)

text = text.replace(
    'makeButton("\\u95ea\\u9000/\\u65e0\\u54cd\\u5e94\\u62a5\\u544a", false)',
    'makeButton("播放/闪退报告", false)',
)
text = text.replace(
    '.setTitle("\\u4e0a\\u6b21\\u95ea\\u9000/\\u65e0\\u54cd\\u5e94\\u62a5\\u544a")',
    '.setTitle("上次播放/闪退问题报告")',
)
text = text.replace(
    'toast("\\u6682\\u65e0\\u95ea\\u9000/\\u65e0\\u54cd\\u5e94\\u62a5\\u544a")',
    'toast("暂无播放/闪退问题报告")',
)
text = text.replace(
    'toast("\\u95ea\\u9000/\\u65e0\\u54cd\\u5e94\\u62a5\\u544a\\u5df2\\u590d\\u5236")',
    'toast("播放/闪退问题报告已复制")',
)

required = [
    "PLAYBACK_HEALTH_CHECK_INTERVAL_MS",
    "player-disappeared-without-error-callback",
    "playback-stopped-without-callback",
    "media-player-error",
    "activity-destroyed-during-active-playback",
    "PlaybackDurationGuard.clearlyShort",
    "PlaybackProblemReporter.store",
]
for token in required:
    if token not in text:
        raise SystemExit(f"required v153 token missing: {token}")

path.write_text(text, encoding="utf-8")
