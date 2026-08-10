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
g = g.replace("versionCode 2026080877", "versionCode 2026080878", 1)
g = g.replace(
    'versionName "2026.08.08.v177-cache-recognition-anr"',
    'versionName "2026.08.10.v178-playlist-open-rapid-next-stability"',
    1,
)
if "versionCode 2026080878" not in g:
    raise SystemExit("v178 version patch failed")
p.write_text(g, encoding="utf-8")


# ---------------------------------------------------------------------------
# MainActivity: make playlist open/playback-start work O(visible rows), not O(N^2)
# ---------------------------------------------------------------------------
p = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = p.read_text(encoding="utf-8")

# Dirty flag: hidden ListView does not need repeated notifyDataSetChanged while
# next/previous is being pressed. It refreshes once when the page becomes visible.
old = '''    private final ExecutorService playlistPersistenceExecutor = Executors.newSingleThreadExecutor();\n    private volatile int playlistPersistenceSerial = 0;'''
new = '''    private final ExecutorService playlistPersistenceExecutor = Executors.newSingleThreadExecutor();\n    private volatile int playlistPersistenceSerial = 0;\n    private boolean playlistUiDirty = false;'''
text = replace_once(text, old, new, "playlist ui dirty field")

old = '''    private void showPlaylistPage() {\n        hideKeyboardAndClearFocus(null);\n        if (headerBar != null) headerBar.setVisibility(View.GONE);\n        if (statusView != null) statusView.setVisibility(View.GONE);\n        if (playerPanel != null) playerPanel.setVisibility(View.GONE);\n        if (searchPanel != null) searchPanel.setVisibility(View.GONE);\n        if (playlistPanel != null) playlistPanel.setVisibility(View.VISIBLE);\n    }'''
new = '''    private void showPlaylistPage() {\n        // Page switching must stay a pure UI operation. Cache verification and\n        // persistence are never started from this click path.\n        View focused = getCurrentFocus();\n        if (focused instanceof EditText) hideKeyboardAndClearFocus(focused);\n        if (headerBar != null) headerBar.setVisibility(View.GONE);\n        if (statusView != null) statusView.setVisibility(View.GONE);\n        if (playerPanel != null) playerPanel.setVisibility(View.GONE);\n        if (searchPanel != null) searchPanel.setVisibility(View.GONE);\n        if (playlistPanel != null) playlistPanel.setVisibility(View.VISIBLE);\n        if (playlistUiDirty && playlistAdapter != null) {\n            playlistAdapter.notifyDataSetChanged();\n            playlistUiDirty = false;\n        }\n    }'''
text = replace_once(text, old, new, "fast playlist page open")

# The first UI pass trusts only fields already present on the Song object. The
# background verifier is already responsible for SAF / Media3 index recovery.
old = '''            if (!songHasRecordedCache(song)) playlistOneClickTargets.add(song);'''
new = '''            if (!songHasRecordedCacheQuick(song)) playlistOneClickTargets.add(song);'''
text = replace_once(text, old, new, "instant playlist cache classification")

# Background verification used to call recoverCachedSongState for each recognized
# row; that helper scans every playlist again, producing O(N^2) work on the UI
# thread for a large playlist. Apply each recognized URI to its row exactly once.
old = '''                    boolean changed = false;\n                    for (Song song : playlist.songs) {\n                        String identity = cacheRecognitionIdentity(song);\n                        String uri = friendlyUris.get(identity);\n                        if (uri != null && !uri.isEmpty()) {\n                            changed |= recoverCachedSongState(song, uri);\n                        }\n                    }\n                    playlistOneClickTargets.removeIf(\n                        item -> recognized.contains(cacheRecognitionIdentity(item)));\n                    if (changed) savePlaylists();\n                    refreshRetainedOneClickButton();\n                    if (playlistAdapter != null) playlistAdapter.notifyDataSetChanged();'''
new = '''                    boolean changed = false;\n                    for (Song song : playlist.songs) {\n                        String identity = cacheRecognitionIdentity(song);\n                        String uri = friendlyUris.get(identity);\n                        if (uri != null && !uri.isEmpty()) {\n                            changed |= applyRecoveredCacheState(song, uri);\n                        }\n                    }\n                    playlistOneClickTargets.removeIf(\n                        item -> recognized.contains(cacheRecognitionIdentity(item)));\n                    if (changed) savePlaylists();\n                    refreshRetainedOneClickButton();\n                    if (changed) notifyPlaylistAdapterStateChanged();'''
text = replace_once(text, old, new, "linear background cache reconciliation")

# Add lightweight adapter notification helper before refreshRetainedOneClickButton.
anchor = '''    private void refreshRetainedOneClickButton() {'''
helper = '''    private void notifyPlaylistAdapterStateChanged() {\n        if (playlistAdapter == null) return;\n        if (playlistPanel != null && playlistPanel.getVisibility() == View.VISIBLE) {\n            playlistAdapter.notifyDataSetChanged();\n            playlistUiDirty = false;\n        } else {\n            playlistUiDirty = true;\n        }\n    }\n\n''' + anchor
text = replace_once(text, anchor, helper, "playlist adapter dirty helper")

# Playback start used to run recoverCachedSongState (full cross-playlist scan),
# save the complete playlist snapshot even when nothing changed, and launch an
# unnecessary Media3 full-cache inspection on every song. Replace it with an
# O(1) current-row update. The actual cache/export worker remains authoritative.
start = text.find('    private void confirmSuccessfulPlaybackCacheState(Song song) {')
end = text.find('    private boolean songHasPlayableCache(Song song) {', start)
if start < 0 or end < 0:
    raise SystemExit("anchor missing: confirmSuccessfulPlaybackCacheState block")
new_block = '''    private void confirmSuccessfulPlaybackCacheState(Song song) {\n        if (song == null || !song.isNetworkCatalog()) return;\n        boolean playlistSong = isPlaylistSongObject(song);\n        boolean changed = false;\n\n        if (playlistSong) {\n            if (song.unavailable || song.autoUnavailable || song.manualUnavailable\n                || song.manualAttempt || song.cacheFailed) {\n                song.unavailable = false;\n                song.autoUnavailable = false;\n                song.manualUnavailable = false;\n                song.manualAttempt = false;\n                song.cacheFailed = false;\n                changed = true;\n            }\n        }\n\n        String uri = song.uri == null ? "" : song.uri.trim();\n        if (playlistSong && (uri.startsWith("file:") || uri.startsWith("content:"))) {\n            // The file just reached Media3 READY and start() was accepted. That is\n            // stronger evidence than a second filesystem/index scan. Update only\n            // this actual playlist row; cache workers handle any other copies.\n            changed |= applyRecoveredCacheState(song, uri);\n            String identity = cacheRecognitionIdentity(song);\n            playlistOneClickTargets.removeIf(\n                item -> identity.equals(cacheRecognitionIdentity(item)));\n            refreshRetainedOneClickButton();\n        }\n\n        if (changed) {\n            savePlaylists();\n            notifyPlaylistAdapterStateChanged();\n        }\n    }\n\n'''
text = text[:start] + new_block + text[end:]

# A playback-interruption report collected after the Activity has already lost
# foreground focus is secondary evidence (and can be caused by audio-focus/window
# transitions). Do not auto-restart/report from the Activity watchdog in that state.
old = '''    private void checkPlaybackHealth() {\n        if (!playbackExpectedPlaying || playbackPreparing || playbackUserPaused\n            || activityDestroyed) return;\n        UnifiedMediaPlayer player = mediaPlayer;'''
new = '''    private void checkPlaybackHealth() {\n        if (!playbackExpectedPlaying || playbackPreparing || playbackUserPaused\n            || activityDestroyed) return;\n        if (!activityResumed || !windowFocused) {\n            playbackLastProgressTime = System.currentTimeMillis();\n            playbackSilentStopReported = false;\n            return;\n        }\n        UnifiedMediaPlayer player = mediaPlayer;'''
text = replace_once(text, old, new, "foreground-only activity playback watchdog")

p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# UnifiedMediaPlayer: move ExoPlayer's application looper off the UI thread.
# Rapid next used to queue multiple ExoPlayer.release() calls on the main looper;
# opening the playlist while that queue drained could freeze or kill the Activity.
# ---------------------------------------------------------------------------
p = Path("app/src/main/java/com/jianglab/babywife/UnifiedMediaPlayer.java")
text = p.read_text(encoding="utf-8")

text = replace_once(
    text,
    'import android.os.Handler;\nimport android.os.Looper;',
    'import android.os.Handler;\nimport android.os.HandlerThread;\nimport android.os.Looper;',
    'HandlerThread import',
)

old = '''final class UnifiedMediaPlayer {\n    interface OnPreparedListener {'''
new = '''final class UnifiedMediaPlayer {\n    private static final HandlerThread PLAYER_THREAD;\n    private static final Handler PLAYER_HANDLER;\n\n    static {\n        PLAYER_THREAD = new HandlerThread("babywife-media3-player");\n        PLAYER_THREAD.start();\n        PLAYER_HANDLER = new Handler(PLAYER_THREAD.getLooper());\n    }\n\n    interface OnPreparedListener {'''
text = replace_once(text, old, new, "shared Media3 playback thread")

old = '''    private OnPreparedListener preparedListener;\n    private OnCompletionListener completionListener;\n    private OnErrorListener errorListener;\n    private boolean preparedDelivered;\n    private boolean released;'''
new = '''    private volatile OnPreparedListener preparedListener;\n    private volatile OnCompletionListener completionListener;\n    private volatile OnErrorListener errorListener;\n    private boolean preparedDelivered;\n    private volatile boolean released;\n    private volatile boolean snapshotPlaying;\n    private volatile int snapshotDurationMs;\n    private volatile int snapshotPositionMs;'''
text = replace_once(text, old, new, "nonblocking player snapshots")

text = text.replace('            mainHandler.postDelayed(this, 400L);',
                    '            PLAYER_HANDLER.postDelayed(this, 400L);', 1)
text = text.replace('        runOnMain(this::prepareInternal);',
                    '        runOnPlayer(this::prepareInternal);', 1)
text = text.replace('.setLooper(Looper.getMainLooper())',
                    '.setLooper(PLAYER_THREAD.getLooper())', 1)

old = '''                    if (playbackState == Player.STATE_READY && !preparedDelivered) {\n                        preparedDelivered = true;\n                        OnPreparedListener listener = preparedListener;\n                        if (listener != null) listener.onPrepared(UnifiedMediaPlayer.this);\n                    } else if (playbackState == Player.STATE_ENDED) {\n                        OnCompletionListener listener = completionListener;\n                        if (listener != null) listener.onCompletion(UnifiedMediaPlayer.this);\n                    }'''
new = '''                    updateSnapshot();\n                    if (playbackState == Player.STATE_READY && !preparedDelivered) {\n                        preparedDelivered = true;\n                        OnPreparedListener listener = preparedListener;\n                        if (listener != null) {\n                            mainHandler.post(() -> {\n                                if (!released && preparedListener == listener) {\n                                    listener.onPrepared(UnifiedMediaPlayer.this);\n                                }\n                            });\n                        }\n                    } else if (playbackState == Player.STATE_ENDED) {\n                        OnCompletionListener listener = completionListener;\n                        if (listener != null) {\n                            mainHandler.post(() -> {\n                                if (!released && completionListener == listener) {\n                                    listener.onCompletion(UnifiedMediaPlayer.this);\n                                }\n                            });\n                        }\n                    }'''
text = replace_once(text, old, new, "main-thread listener delivery")

old = '''                @Override\n                public void onPlayerError(PlaybackException error) {'''
new = '''                @Override\n                public void onIsPlayingChanged(boolean isPlaying) {\n                    snapshotPlaying = isPlaying;\n                    updateSnapshot();\n                }\n\n                @Override\n                public void onPlayerError(PlaybackException error) {'''
text = replace_once(text, old, new, "snapshot isPlaying callback")

# Player commands operate only on the Media3 looper.
text = text.replace('        runOnMain(() -> {\n            userRequestedPlayback = true;',
                    '        runOnPlayer(() -> {\n            userRequestedPlayback = true;', 1)
text = text.replace('        runOnMain(() -> {\n            userRequestedPlayback = false;\n            communicationPaused = false;\n            if (player != null && !released) player.pause();',
                    '        runOnPlayer(() -> {\n            userRequestedPlayback = false;\n            communicationPaused = false;\n            snapshotPlaying = false;\n            if (player != null && !released) player.pause();', 1)
text = text.replace('        runOnMain(() -> {\n            userRequestedPlayback = false;\n            communicationPaused = false;\n            if (player != null && !released) player.stop();',
                    '        runOnPlayer(() -> {\n            userRequestedPlayback = false;\n            communicationPaused = false;\n            snapshotPlaying = false;\n            if (player != null && !released) player.stop();', 1)
text = text.replace('        runOnMain(() -> {\n            userRequestedPlayback = false;\n            communicationPaused = false;\n            if (player != null && !released) {',
                    '        runOnPlayer(() -> {\n            userRequestedPlayback = false;\n            communicationPaused = false;\n            snapshotPlaying = false;\n            if (player != null && !released) {', 1)

old = '''        mainHandler.removeCallbacks(communicationModeWatcher);\n        // Always enqueue the real ExoPlayer release. Calling existing.release()\n        // inline from a song-row MotionEvent can block Xiaomi/Android 16 input\n        // dispatch long enough to trigger a 5-second ANR.\n        mainHandler.post(this::releaseInternalPlayer);'''
new = '''        PLAYER_HANDLER.removeCallbacks(communicationModeWatcher);\n        snapshotPlaying = false;\n        // ExoPlayer.release() now runs on the dedicated Media3 looper. Even if a\n        // device codec/cache teardown is slow, it cannot block MotionEvent/layout.\n        PLAYER_HANDLER.post(this::releaseInternalPlayer);'''
text = replace_once(text, old, new, "off-main ExoPlayer release")

# Nonblocking state getters: never make the UI thread wait for Media3. A refresh is
# queued and the last known snapshot is returned immediately.
old = '''    boolean isPlaying() {\n        return callOnMain(() -> player != null && !released && player.isPlaying(), false);\n    }\n\n    int getDuration() {\n        long value = callOnMain(() -> player == null ? C.TIME_UNSET : player.getDuration(),\n            C.TIME_UNSET);\n        if (value == C.TIME_UNSET || value < 0L) return 0;\n        return (int) Math.min(Integer.MAX_VALUE, value);\n    }\n\n    int getCurrentPosition() {\n        long value = callOnMain(() -> player == null ? 0L : player.getCurrentPosition(), 0L);\n        return (int) Math.max(0L, Math.min(Integer.MAX_VALUE, value));\n    }\n\n    void seekTo(int positionMs) {\n        runOnMain(() -> {\n            if (player != null && !released) player.seekTo(Math.max(0, positionMs));\n        });\n    }'''
new = '''    boolean isPlaying() {\n        requestSnapshot();\n        return snapshotPlaying;\n    }\n\n    int getDuration() {\n        requestSnapshot();\n        return Math.max(0, snapshotDurationMs);\n    }\n\n    int getCurrentPosition() {\n        requestSnapshot();\n        return Math.max(0, snapshotPositionMs);\n    }\n\n    void seekTo(int positionMs) {\n        int safe = Math.max(0, positionMs);\n        snapshotPositionMs = safe;\n        runOnPlayer(() -> {\n            if (player != null && !released) player.seekTo(safe);\n        });\n    }'''
text = replace_once(text, old, new, "nonblocking state getters")

old = '''    private void scheduleCommunicationModeWatch() {\n        mainHandler.removeCallbacks(communicationModeWatcher);\n        if (!released) mainHandler.post(communicationModeWatcher);\n    }'''
new = '''    private void scheduleCommunicationModeWatch() {\n        PLAYER_HANDLER.removeCallbacks(communicationModeWatcher);\n        if (!released) PLAYER_HANDLER.post(communicationModeWatcher);\n    }'''
text = replace_once(text, old, new, "communication watcher playback thread")

old = '''    private void notifyError(int what, int extra) {\n        OnErrorListener listener = errorListener;\n        if (listener != null) listener.onError(this, what, extra);\n    }'''
new = '''    private void notifyError(int what, int extra) {\n        OnErrorListener listener = errorListener;\n        if (listener == null) return;\n        mainHandler.post(() -> {\n            if (!released && errorListener == listener) {\n                listener.onError(this, what, extra);\n            }\n        });\n    }'''
text = replace_once(text, old, new, "main-thread error callback")

old = '''    private void releaseInternalPlayer() {\n        ExoPlayer existing = player;\n        player = null;\n        if (existing != null) {\n            try {\n                existing.release();\n            } catch (Exception ignored) {\n            }\n        }\n    }\n\n    private void runOnMain(Runnable action) {\n        if (Looper.myLooper() == Looper.getMainLooper()) {\n            action.run();\n        } else {\n            mainHandler.post(action);\n        }\n    }\n\n    private interface ValueCall<T> {\n        T call();\n    }\n\n    private <T> T callOnMain(ValueCall<T> action, T fallback) {\n        if (Looper.myLooper() == Looper.getMainLooper()) {\n            try {\n                return action.call();\n            } catch (Throwable ignored) {\n                return fallback;\n            }\n        }\n        AtomicReference<T> result = new AtomicReference<>(fallback);\n        CountDownLatch latch = new CountDownLatch(1);\n        mainHandler.post(() -> {\n            try {\n                result.set(action.call());\n            } catch (Throwable ignored) {\n            } finally {\n                latch.countDown();\n            }\n        });\n        try {\n            latch.await(2, TimeUnit.SECONDS);\n        } catch (InterruptedException interrupted) {\n            Thread.currentThread().interrupt();\n        }\n        return result.get();\n    }'''
new = '''    private void releaseInternalPlayer() {\n        ExoPlayer existing = player;\n        player = null;\n        snapshotPlaying = false;\n        snapshotDurationMs = 0;\n        snapshotPositionMs = 0;\n        if (existing != null) {\n            try {\n                existing.release();\n            } catch (Exception ignored) {\n            }\n        }\n    }\n\n    private void requestSnapshot() {\n        if (!released) PLAYER_HANDLER.post(this::updateSnapshot);\n    }\n\n    private void updateSnapshot() {\n        ExoPlayer current = player;\n        if (current == null || released) {\n            snapshotPlaying = false;\n            return;\n        }\n        try {\n            snapshotPlaying = current.isPlaying();\n            long duration = current.getDuration();\n            snapshotDurationMs = duration == C.TIME_UNSET || duration < 0L\n                ? 0 : (int) Math.min(Integer.MAX_VALUE, duration);\n            long position = current.getCurrentPosition();\n            snapshotPositionMs = (int) Math.max(0L, Math.min(Integer.MAX_VALUE, position));\n        } catch (Throwable ignored) {\n        }\n    }\n\n    private void runOnPlayer(Runnable action) {\n        if (Looper.myLooper() == PLAYER_THREAD.getLooper()) {\n            action.run();\n        } else {\n            PLAYER_HANDLER.post(action);\n        }\n    }'''
text = replace_once(text, old, new, "dedicated player looper helpers")

# Remove now-unused blocking helper imports (javac allows unused imports, but keep source clean).
text = text.replace('import java.util.concurrent.CountDownLatch;\n', '')
text = text.replace('import java.util.concurrent.TimeUnit;\n', '')
text = text.replace('import java.util.concurrent.atomic.AtomicReference;\n', '')

p.write_text(text, encoding="utf-8")
