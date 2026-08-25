from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "app/build.gradle"
PLAYER = ROOT / "app/src/main/java/com/jianglab/babywife/UnifiedMediaPlayer.java"
MAIN = ROOT / "app/src/main/java/com/jianglab/babywife/MainActivity.java"


def replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"method not found: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError(f"opening brace not found: {signature}")
    depth = 0
    i = brace
    in_string = False
    in_char = False
    escape = False
    while i < len(text):
        ch = text[i]
        if escape:
            escape = False
        elif ch == "\\" and (in_string or in_char):
            escape = True
        elif ch == '"' and not in_char:
            in_string = not in_string
        elif ch == "'" and not in_string:
            in_char = not in_char
        elif not in_string and not in_char:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[:start] + replacement.rstrip() + text[i + 1:]
        i += 1
    raise RuntimeError(f"closing brace not found: {signature}")


# Version bump.
build = BUILD.read_text(encoding="utf-8")
build = re.sub(r'versionCode\s+2026080882', 'versionCode 2026080883', build, count=1)
build = re.sub(r'versionName\s+"2026\.08\.17\.v182-jianle-brand"',
               'versionName "2026.08.25.v183-atomic-playback-health"', build, count=1)
if 'versionCode 2026080883' not in build:
    raise RuntimeError('versionCode bump failed')
BUILD.write_text(build, encoding="utf-8")

# UnifiedMediaPlayer: publish one immutable snapshot object so a health check can
# never combine position from one moment with state/timestamp from another.
player = PLAYER.read_text(encoding="utf-8")
if "static final class PlaybackSnapshot" not in player:
    marker = "    interface OnErrorListener {\n        boolean onError(UnifiedMediaPlayer player, int what, int extra);\n    }\n"
    snapshot_class = marker + r'''

    static final class PlaybackSnapshot {
        final long sequence;
        final int positionMs;
        final int durationMs;
        final boolean playing;
        final long updatedAtMs;
        final int playbackState;
        final boolean playWhenReady;
        final int suppressionReason;

        PlaybackSnapshot(long sequence, int positionMs, int durationMs,
                         boolean playing, long updatedAtMs, int playbackState,
                         boolean playWhenReady, int suppressionReason) {
            this.sequence = sequence;
            this.positionMs = positionMs;
            this.durationMs = durationMs;
            this.playing = playing;
            this.updatedAtMs = updatedAtMs;
            this.playbackState = playbackState;
            this.playWhenReady = playWhenReady;
            this.suppressionReason = suppressionReason;
        }

        long ageMs(long nowMs) {
            if (updatedAtMs <= 0L) return Long.MAX_VALUE;
            return Math.max(0L, nowMs - updatedAtMs);
        }
    }
'''
    if marker not in player:
        raise RuntimeError("OnErrorListener marker not found")
    player = player.replace(marker, snapshot_class, 1)

if "private volatile PlaybackSnapshot playbackSnapshot" not in player:
    marker = "    private volatile int snapshotSuppressionReason = Player.PLAYBACK_SUPPRESSION_REASON_NONE;\n"
    addition = marker + "    private long snapshotSequence = 0L;\n" \
        + "    private volatile PlaybackSnapshot playbackSnapshot = new PlaybackSnapshot(\n" \
        + "        0L, 0, 0, false, 0L, Player.STATE_IDLE, false,\n" \
        + "        Player.PLAYBACK_SUPPRESSION_REASON_NONE);\n"
    if marker not in player:
        raise RuntimeError("snapshot field marker not found")
    player = player.replace(marker, addition, 1)

# Keep legacy getters for UI code, but health monitoring can take exactly one object.
if "PlaybackSnapshot getPlaybackSnapshot()" not in player:
    marker = "    long getSnapshotAgeMs() {"
    method = r'''    PlaybackSnapshot getPlaybackSnapshot() {
        PlaybackSnapshot current = playbackSnapshot;
        requestSnapshot();
        return current;
    }

'''
    if marker not in player:
        raise RuntimeError("getSnapshotAgeMs marker not found")
    player = player.replace(marker, method + marker, 1)

player = replace_method(player, "    private void releaseInternalPlayer()", r'''    private void releaseInternalPlayer() {
        ExoPlayer existing = player;
        player = null;
        long now = System.currentTimeMillis();
        snapshotPlaying = false;
        snapshotDurationMs = 0;
        snapshotPositionMs = 0;
        snapshotPlaybackState = Player.STATE_IDLE;
        snapshotPlayWhenReady = false;
        snapshotSuppressionReason = Player.PLAYBACK_SUPPRESSION_REASON_NONE;
        snapshotUpdatedAtMs = now;
        playbackSnapshot = new PlaybackSnapshot(
            ++snapshotSequence, 0, 0, false, now, Player.STATE_IDLE, false,
            Player.PLAYBACK_SUPPRESSION_REASON_NONE);
        if (existing != null) {
            try {
                existing.release();
            } catch (Exception ignored) {
            }
        }
    }''')

player = replace_method(player, "    private void updateSnapshot()", r'''    private void updateSnapshot() {
        ExoPlayer current = player;
        long now = System.currentTimeMillis();
        if (current == null || released) {
            snapshotPlaying = false;
            snapshotDurationMs = 0;
            snapshotPositionMs = 0;
            snapshotPlaybackState = Player.STATE_IDLE;
            snapshotPlayWhenReady = false;
            snapshotSuppressionReason = Player.PLAYBACK_SUPPRESSION_REASON_NONE;
            snapshotUpdatedAtMs = now;
            playbackSnapshot = new PlaybackSnapshot(
                ++snapshotSequence, 0, 0, false, now, Player.STATE_IDLE, false,
                Player.PLAYBACK_SUPPRESSION_REASON_NONE);
            return;
        }
        try {
            boolean playing = current.isPlaying();
            int playbackState = current.getPlaybackState();
            boolean playWhenReady = current.getPlayWhenReady();
            int suppressionReason = current.getPlaybackSuppressionReason();
            long duration = current.getDuration();
            int durationMs = duration == C.TIME_UNSET || duration < 0L
                ? 0 : (int) Math.min(Integer.MAX_VALUE, duration);
            long position = current.getCurrentPosition();
            int positionMs = (int) Math.max(0L, Math.min(Integer.MAX_VALUE, position));

            snapshotPlaying = playing;
            snapshotPlaybackState = playbackState;
            snapshotPlayWhenReady = playWhenReady;
            snapshotSuppressionReason = suppressionReason;
            snapshotDurationMs = durationMs;
            snapshotPositionMs = positionMs;
            snapshotUpdatedAtMs = now;
            // Single volatile publication: every field below belongs to the same
            // ExoPlayer read on the same player looper turn.
            playbackSnapshot = new PlaybackSnapshot(
                ++snapshotSequence, positionMs, durationMs, playing, now,
                playbackState, playWhenReady, suppressionReason);
        } catch (Throwable ignored) {
            // Do not publish a half-updated state if Media3 throws while sampling.
        }
    }''')
PLAYER.write_text(player, encoding="utf-8")

# MainActivity: health decision must consume one immutable snapshot and only count
# genuinely new snapshot sequences. A confirmed real stall gets a non-destructive
# seek-to-current-position restart; it never marks the song red or deletes cache.
main = MAIN.read_text(encoding="utf-8")
if "playbackHealthSnapshotPlayer" not in main:
    marker = "    private int playbackFreshStallSamples = 0;\n"
    addition = marker \
        + "    private long playbackLastSnapshotSequence = -1L;\n" \
        + "    private UnifiedMediaPlayer playbackHealthSnapshotPlayer;\n"
    if marker not in main:
        raise RuntimeError("playbackFreshStallSamples marker not found")
    main = main.replace(marker, addition, 1)

main = replace_method(main, "    private void checkPlaybackHealth()", r'''    private void checkPlaybackHealth() {
        if (!playbackExpectedPlaying || playbackPreparing || playbackUserPaused
            || activityDestroyed) return;
        if (!activityResumed || !windowFocused) {
            playbackLastProgressTime = System.currentTimeMillis();
            playbackSilentStopReported = false;
            playbackFreshStallSamples = 0;
            return;
        }

        UnifiedMediaPlayer player = mediaPlayer;
        if (player == null) return;
        long now = System.currentTimeMillis();
        UnifiedMediaPlayer.PlaybackSnapshot snapshot = player.getPlaybackSnapshot();
        if (snapshot == null) return;

        // A newly-created player has its own sequence space. Never compare it with
        // the previous song/player's samples after rapid next/previous presses.
        if (playbackHealthSnapshotPlayer != player) {
            playbackHealthSnapshotPlayer = player;
            playbackLastSnapshotSequence = snapshot.sequence;
            playbackLastObservedPosition = snapshot.positionMs;
            playbackLastProgressTime = now;
            playbackFreshStallSamples = 0;
            playbackSilentStopReported = false;
            return;
        }

        long snapshotAgeMs = snapshot.ageMs(now);
        int playbackState = snapshot.playbackState;
        boolean playWhenReady = snapshot.playWhenReady;
        int suppressionReason = snapshot.suppressionReason;
        boolean playing = snapshot.playing;
        long position = snapshot.positionMs;
        long duration = snapshot.durationMs;

        if (snapshotAgeMs > PLAYBACK_SNAPSHOT_MAX_AGE_MS
            || playbackState == Player.STATE_BUFFERING
            || suppressionReason != Player.PLAYBACK_SUPPRESSION_REASON_NONE) {
            playbackFreshStallSamples = 0;
            playbackLastProgressTime = now;
            playbackSilentStopReported = false;
            playbackLastSnapshotSequence = snapshot.sequence;
            playbackLastObservedPosition = position;
            return;
        }

        if (playbackState == Player.STATE_ENDED) {
            playbackFreshStallSamples = 0;
            playbackLastProgressTime = now;
            return;
        }

        if (playbackState != Player.STATE_READY || !playWhenReady) {
            playbackFreshStallSamples = 0;
            playbackLastProgressTime = now;
            playbackLastSnapshotSequence = snapshot.sequence;
            return;
        }

        // The same immutable snapshot must never count twice. This is the key fix
        // for false stalls caused by asynchronous state getters racing each other.
        if (snapshot.sequence == playbackLastSnapshotSequence) return;
        playbackLastSnapshotSequence = snapshot.sequence;

        if (playbackLastObservedPosition < 0L
            || position > playbackLastObservedPosition
            || position + 1000L < playbackLastObservedPosition) {
            playbackLastObservedPosition = position;
            playbackLastProgressTime = now;
            playbackFreshStallSamples = 0;
            playbackSilentStopReported = false;
            return;
        }

        playbackFreshStallSamples++;
        if (playbackFreshStallSamples < PLAYBACK_STALL_FRESH_SAMPLE_MIN
            || now - playbackLastProgressTime < PLAYBACK_STALL_REPORT_MS
            || playbackSilentStopReported) return;

        playbackSilentStopReported = true;
        reportPlaybackProblem(
            playing ? "playback-position-stalled-atomic-confirmed"
                : "playback-ready-not-playing-atomic-confirmed",
            player, 0, 0, currentSong == null ? "" : currentSong.uri);

        // This is now a real, same-snapshot confirmed stall. Recover without
        // touching cache validity or failure/red flags: re-seek the same position
        // so Media3 rebuilds the read/decoder path, then keep playWhenReady active.
        try {
            int resumePosition = (int) Math.max(0L,
                Math.min(Integer.MAX_VALUE, Math.min(position,
                    duration > 0L ? Math.max(0L, duration - 1L) : position)));
            player.seekTo(resumePosition);
            player.start();
        } catch (Throwable ignored) {
        }
        playbackLastProgressTime = now;
        playbackFreshStallSamples = 0;
        if (statusView != null) {
            statusView.setText("检测到真实播放停滞，已自动从当前位置恢复播放");
        }
    }''')

MAIN.write_text(main, encoding="utf-8")

print("v183 atomic playback health patch applied")
