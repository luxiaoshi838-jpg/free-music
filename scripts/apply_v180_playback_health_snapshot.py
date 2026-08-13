from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


# Version
p = Path("app/build.gradle")
g = p.read_text(encoding="utf-8")
g = g.replace("versionCode 2026080879", "versionCode 2026080880", 1)
g = g.replace(
    'versionName "2026.08.10.v179-cache-read-ui-action-log"',
    'versionName "2026.08.13.v180-playback-health-snapshot"',
    1,
)
if "versionCode 2026080880" not in g:
    raise SystemExit("v180 version patch failed")
p.write_text(g, encoding="utf-8")


# ---------------------------------------------------------------------------
# UnifiedMediaPlayer: make asynchronous snapshots self-describing.
# Health checks must know whether a position/isPlaying value is fresh or stale.
# ---------------------------------------------------------------------------
p = Path("app/src/main/java/com/jianglab/babywife/UnifiedMediaPlayer.java")
text = p.read_text(encoding="utf-8")

old = '''    private volatile boolean snapshotPlaying;\n    private volatile int snapshotDurationMs;\n    private volatile int snapshotPositionMs;'''
new = '''    private volatile boolean snapshotPlaying;\n    private volatile int snapshotDurationMs;\n    private volatile int snapshotPositionMs;\n    private volatile long snapshotUpdatedElapsedMs;\n    private volatile int snapshotPlaybackState = Player.STATE_IDLE;\n    private volatile boolean snapshotPlayWhenReady;\n    private volatile int snapshotSuppressionReason = Player.PLAYBACK_SUPPRESSION_REASON_NONE;'''
text = replace_once(text, old, new, "snapshot metadata fields")

old = '''    boolean isPlaying() {\n        requestSnapshot();\n        return snapshotPlaying;\n    }\n\n    int getDuration() {\n        requestSnapshot();\n        return Math.max(0, snapshotDurationMs);\n    }\n\n    int getCurrentPosition() {\n        requestSnapshot();\n        return Math.max(0, snapshotPositionMs);\n    }'''
new = '''    boolean isPlaying() {\n        requestSnapshot();\n        return snapshotPlaying;\n    }\n\n    int getDuration() {\n        requestSnapshot();\n        return Math.max(0, snapshotDurationMs);\n    }\n\n    int getCurrentPosition() {\n        requestSnapshot();\n        return Math.max(0, snapshotPositionMs);\n    }\n\n    void refreshSnapshotAsync() {\n        requestSnapshot();\n    }\n\n    long getSnapshotAgeMs() {\n        long updated = snapshotUpdatedElapsedMs;\n        if (updated <= 0L) return Long.MAX_VALUE;\n        return Math.max(0L, android.os.SystemClock.elapsedRealtime() - updated);\n    }\n\n    int getPlaybackStateSnapshot() {\n        return snapshotPlaybackState;\n    }\n\n    boolean getPlayWhenReadySnapshot() {\n        return snapshotPlayWhenReady;\n    }\n\n    int getPlaybackSuppressionReasonSnapshot() {\n        return snapshotSuppressionReason;\n    }'''
text = replace_once(text, old, new, "snapshot metadata getters")

old = '''        snapshotPlaying = false;\n        snapshotDurationMs = 0;\n        snapshotPositionMs = 0;\n        if (existing != null) {'''
new = '''        snapshotPlaying = false;\n        snapshotDurationMs = 0;\n        snapshotPositionMs = 0;\n        snapshotUpdatedElapsedMs = android.os.SystemClock.elapsedRealtime();\n        snapshotPlaybackState = Player.STATE_IDLE;\n        snapshotPlayWhenReady = false;\n        snapshotSuppressionReason = Player.PLAYBACK_SUPPRESSION_REASON_NONE;\n        if (existing != null) {'''
text = replace_once(text, old, new, "released snapshot state")

old = '''            snapshotPlaying = current.isPlaying();\n            long duration = current.getDuration();\n            snapshotDurationMs = duration == C.TIME_UNSET || duration < 0L\n                ? 0 : (int) Math.min(Integer.MAX_VALUE, duration);\n            long position = current.getCurrentPosition();\n            snapshotPositionMs = (int) Math.max(0L, Math.min(Integer.MAX_VALUE, position));\n        } catch (Throwable ignored) {\n        }'''
new = '''            snapshotPlaying = current.isPlaying();\n            snapshotPlaybackState = current.getPlaybackState();\n            snapshotPlayWhenReady = current.getPlayWhenReady();\n            snapshotSuppressionReason = current.getPlaybackSuppressionReason();\n            long duration = current.getDuration();\n            snapshotDurationMs = duration == C.TIME_UNSET || duration < 0L\n                ? 0 : (int) Math.min(Integer.MAX_VALUE, duration);\n            long position = current.getCurrentPosition();\n            snapshotPositionMs = (int) Math.max(0L, Math.min(Integer.MAX_VALUE, position));\n            snapshotUpdatedElapsedMs = android.os.SystemClock.elapsedRealtime();\n        } catch (Throwable ignored) {\n        }'''
text = replace_once(text, old, new, "snapshot freshness update")

p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# MainActivity: never diagnose a stall from an old asynchronous player snapshot.
# Require fresh repeated evidence and treat Media3 BUFFERING/suppression as normal.
# ---------------------------------------------------------------------------
p = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = p.read_text(encoding="utf-8")

old = '''    private long playbackLastObservedPosition = -1L;\n    private long playbackLastProgressTime = 0L;'''
new = '''    private long playbackLastObservedPosition = -1L;\n    private long playbackLastProgressTime = 0L;\n    private int playbackFreshStallSamples = 0;'''
text = replace_once(text, old, new, "health fresh sample field")

old = '''        playbackSilentStopReported = false;\n        playbackLastObservedPosition = safePlaybackPosition(player);\n        playbackLastProgressTime = System.currentTimeMillis();'''
new = '''        playbackSilentStopReported = false;\n        playbackFreshStallSamples = 0;\n        if (player != null) player.refreshSnapshotAsync();\n        playbackLastObservedPosition = safePlaybackPosition(player);\n        playbackLastProgressTime = System.currentTimeMillis();'''
text = replace_once(text, old, new, "health watch initialization")

old = '''    private void stopPlaybackHealthWatch() {\n        playbackExpectedPlaying = false;\n        playbackHealthHandler.removeCallbacks(playbackHealthTicker);\n    }'''
new = '''    private void stopPlaybackHealthWatch() {\n        playbackExpectedPlaying = false;\n        playbackFreshStallSamples = 0;\n        playbackHealthHandler.removeCallbacks(playbackHealthTicker);\n    }'''
text = replace_once(text, old, new, "health sample reset")

start = text.find('    private void checkPlaybackHealth() {')
end = text.find('    private void deleteIncompletePlaybackCache(', start)
if start < 0 or end < 0:
    raise SystemExit("anchor missing: checkPlaybackHealth block")
new_block = '''    private void checkPlaybackHealth() {\n        if (!playbackExpectedPlaying || playbackPreparing || playbackUserPaused\n            || activityDestroyed) return;\n        if (!activityResumed || !windowFocused) {\n            playbackLastProgressTime = System.currentTimeMillis();\n            playbackSilentStopReported = false;\n            playbackFreshStallSamples = 0;\n            return;\n        }\n        UnifiedMediaPlayer player = mediaPlayer;\n        if (player == null) {\n            if (!playbackSilentStopReported) {\n                playbackSilentStopReported = true;\n                reportPlaybackProblem(\n                    "player-disappeared-without-error-callback",\n                    null, 0, 0, currentSong == null ? "" : currentSong.uri);\n            }\n            stopPlaybackHealthWatch();\n            return;\n        }\n\n        // UnifiedMediaPlayer lives on a dedicated Media3 looper. Its getters are\n        // intentionally non-blocking snapshots. Ask for the next snapshot now,\n        // but only diagnose using the already-published snapshot when it is fresh.\n        player.refreshSnapshotAsync();\n        long now = System.currentTimeMillis();\n        long snapshotAge = player.getSnapshotAgeMs();\n        long position = safePlaybackPosition(player);\n        long duration = safePlaybackDuration(player);\n        boolean playing = safePlaybackIsPlaying(player);\n        int playbackState = player.getPlaybackStateSnapshot();\n        boolean playWhenReady = player.getPlayWhenReadySnapshot();\n        int suppressionReason = player.getPlaybackSuppressionReasonSnapshot();\n\n        // A stale snapshot means the player looper has not published fresh state\n        // yet. It must never be interpreted as frozen playback.\n        if (snapshotAge > 5000L) {\n            playbackFreshStallSamples = 0;\n            playbackLastProgressTime = now;\n            return;\n        }\n\n        if (position >= 0L && position > playbackLastObservedPosition + 250L) {\n            playbackLastObservedPosition = position;\n            playbackLastProgressTime = now;\n            playbackSilentStopReported = false;\n            playbackFreshStallSamples = 0;\n            return;\n        }\n\n        boolean nearEnd = duration > 0L && position >= 0L\n            && position + 3000L >= duration;\n        if (nearEnd) {\n            playbackFreshStallSamples = 0;\n            return;\n        }\n\n        // BUFFERING is a valid network/cache state, not an unexpected stop. Audio\n        // focus suppression is also expected and must not be force-resumed here.\n        if (playbackState == androidx.media3.common.Player.STATE_BUFFERING\n            || suppressionReason != androidx.media3.common.Player.PLAYBACK_SUPPRESSION_REASON_NONE) {\n            playbackFreshStallSamples = 0;\n            playbackLastProgressTime = now;\n            playbackSilentStopReported = false;\n            return;\n        }\n\n        if (now - playbackLastProgressTime < PLAYBACK_STALL_REPORT_MS\n            || playbackSilentStopReported) return;\n\n        if (playing) {\n            // isPlaying=true with no position movement is only actionable after\n            // several consecutive fresh snapshots. This prevents the v179 false\n            // positive where the old position snapshot lagged behind playback.\n            playbackFreshStallSamples++;\n            if (playbackFreshStallSamples < 3) return;\n            playbackSilentStopReported = true;\n            reportPlaybackProblem(\n                "playback-position-stalled-confirmed",\n                player, 0, 0, currentSong == null ? "" : currentSong.uri);\n            if (statusView != null) {\n                statusView.setText("播放进度连续多次确认未变化，已生成播放问题报告");\n            }\n            return;\n        }\n\n        playbackFreshStallSamples = 0;\n        // READY + playWhenReady=false can be a legitimate Media3/audio-focus\n        // transition. Only try recovery when the player is unexpectedly IDLE.\n        if (playbackState != androidx.media3.common.Player.STATE_IDLE || !playWhenReady) {\n            playbackLastProgressTime = now;\n            return;\n        }\n\n        playbackSilentStopReported = true;\n        reportPlaybackProblem(\n            "playback-idle-without-callback",\n            player, 0, 0, currentSong == null ? "" : currentSong.uri);\n        try {\n            player.start();\n            playbackLastProgressTime = now;\n            playbackSilentStopReported = false;\n            if (statusView != null) {\n                statusView.setText("检测到播放器意外进入空闲状态，已尝试恢复并生成报告");\n            }\n            publishPlaybackControlState(true);\n        } catch (Exception error) {\n            stopPlaybackHealthWatch();\n            if (playButton != null) playButton.setText("▶");\n            if (statusView != null) {\n                statusView.setText("播放器意外停止，自动恢复失败，已生成报告");\n            }\n            publishPlaybackControlState(true);\n        }\n    }\n\n'''
text = text[:start] + new_block + text[end:]

p.write_text(text, encoding="utf-8")
