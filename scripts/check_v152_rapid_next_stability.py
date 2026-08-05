from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / "app/src/main/java/com/jianglab/babywife/MainActivity.java").read_text(encoding="utf-8")
search = (root / "app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java").read_text(encoding="utf-8")
gradle = (root / "app/build.gradle").read_text(encoding="utf-8")

start_playback = main[
    main.index("private void startLocalPlayback"):
    main.index("private void onPlaybackStarted")
]
stop_playback = main[
    main.index("private void stopPlayback"):
    main.index("private LinearLayout buildDrawerPanel")
]

checks = {
    "v152 metadata": (
        "versionCode 2026080152" in gradle
        and 'versionName "2026.08.05.v152-rapid-next-stability"' in gradle
    ),
    "manual navigation debounced": (
        "PLAYBACK_NAVIGATION_DEBOUNCE_MS = 220L" in main
        and "pendingNavigationOffset" in main
        and "playbackNavigationHandler.postDelayed" in main
        and "performPlaylistOffset" in main
    ),
    "media source opening serialized": (
        "mediaSourceExecutor = Executors.newSingleThreadExecutor()" in main
        and "mediaSourceExecutor.submit" in start_playback
        and 'new Thread(() ->' not in start_playback
        and '"media-source-open"' not in start_playback
    ),
    "stale source tasks cancelable": (
        "Future<?> mediaSourceOpenFuture" in main
        and "cancelMediaSourceOpenTask" in main
        and "task.cancel(true)" in stop_playback
        and "private volatile int mediaOpenSerial" in main
        and "openSerial != mediaOpenSerial" in start_playback
    ),
    "search background cache serialized and cancelable": (
        "searchCacheExecutor = Executors.newSingleThreadExecutor()" in main
        and "Future<?> searchCacheFuture" in main
        and "cancelSearchCacheTask" in main
        and "throwIfInterrupted" in search
    ),
    "media player released safely": (
        "releaseMediaPlayer" in stop_playback
        and "player.setOnPreparedListener(null)" in stop_playback
        and "player.setOnCompletionListener(null)" in stop_playback
        and "player.setOnErrorListener(null)" in stop_playback
        and "player.reset()" in stop_playback
        and "player.release()" in stop_playback
    ),
    "stale callbacks release their player": (
        "if (mediaPlayer == player) mediaPlayer = null" in start_playback
        and "releaseMediaPlayer(player)" in start_playback
    ),
    "system process exit history captured": (
        "getHistoricalProcessExitReasons" in main
        and "ApplicationExitInfo.REASON_CRASH_NATIVE" in main
        and "ApplicationExitInfo.REASON_ANR" in main
        and "ApplicationExitInfo.REASON_LOW_MEMORY" in main
        and "Process exit report" in main
    ),
    "playback transition breadcrumb recorded": (
        'KEY_PLAYBACK_TRANSITION_PENDING = "playback_transition_pending"' in main
        and "recordPlaybackTransition" in main
        and "pendingPlaybackTransition=" in main
        and "clearPlaybackTransition" in main
    ),
    "dismissed report can be replaced": (
        "boolean existingPending" in main
        and "KEY_CRASH_REPORT_DISMISSED" in main
        and "if (existingPending) return" in main
    ),
    "temporary source workflow removed": not (root / ".github/workflows/apply-v152-source.yml").exists(),
}

failed = [name for name, passed in checks.items() if not passed]
for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
if failed:
    raise SystemExit("v152 rapid-next stability checks failed: " + ", ".join(failed))
