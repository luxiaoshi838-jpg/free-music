from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / "app/src/main/java/com/jianglab/babywife/MainActivity.java").read_text(encoding="utf-8")
search = (root / "app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java").read_text(encoding="utf-8")
reporter = (root / "app/src/main/java/com/jianglab/babywife/PlaybackProblemReporter.java").read_text(encoding="utf-8")
duration_guard = (root / "app/src/main/java/com/jianglab/babywife/PlaybackDurationGuard.java").read_text(encoding="utf-8")
gradle = (root / "app/build.gradle").read_text(encoding="utf-8")

checks = {
    "v153 metadata": (
        "versionCode 2026080153" in gradle
        and 'versionName "2026.08.06.v153-playback-stop-report"' in gradle
    ),
    "short Range response is not completion": (
        "segmentBytes < RANGE_CHUNK_BYTES" not in search
        and "private static final class ContentRange" in search
        and "response.statusCode == 416" in search
        and "Range 正文长度与 Content-Range 不一致" in search
        and "Range 下载长度不完整" in search
    ),
    "Range continuity verified": (
        "bounds.start != writtenTotal" in search
        and "writtenTotal != expectedTotal" in search
        and "HTTP 206 缺少有效 Content-Range" in search
    ),
    "playback errors stored": (
        "PlaybackProblemReporter.store" in main
        and '"media-player-error"' in main
        and "what" in reporter
        and "extra" in reporter
        and "positionMs" in reporter
        and "durationMs" in reporter
    ),
    "silent stops detected": (
        "PLAYBACK_HEALTH_CHECK_INTERVAL_MS = 2000L" in main
        and "PLAYBACK_STALL_REPORT_MS = 12000L" in main
        and '"playback-stopped-without-callback"' in main
        and '"playback-position-stalled"' in main
        and '"player-disappeared-without-error-callback"' in main
    ),
    "silent stopped player recovery attempted": (
        "checkPlaybackHealth()" in main
        and "player.start();" in main
        and "检测到播放意外停止" in main
    ),
    "cached duration validated": (
        "PlaybackDurationGuard.clearlyShort" in main
        and '"cached-duration-short-before-start"' in main
        and '"cached-audio-ended-before-catalog-duration"' in main
        and "deleteIncompletePlaybackCache" in main
        and "NetworkMediaCache.deleteCatalogCache" in main
        and "duration_ms" in duration_guard
    ),
    "activity destruction reported": (
        '"activity-destroyed-during-active-playback"' in main
        and "playbackHealthHandler.removeCallbacks(playbackHealthTicker)" in main
    ),
    "manual pause excluded": (
        "playbackUserPaused = true" in main
        and "stopPlaybackHealthWatch();" in main
        and "playbackUserPaused" in main
        and 'report.append("userPaused=")' in reporter
    ),
    "existing v152 serialized player retained": (
        "mediaSourceExecutor = Executors.newSingleThreadExecutor()" in main
        and "searchCacheExecutor = Executors.newSingleThreadExecutor()" in main
        and "PLAYBACK_NAVIGATION_DEBOUNCE_MS = 220L" in main
    ),
    "temporary patch files removed": (
        not (root / ".github/workflows/apply-v153-range-completeness.yml").exists()
        and not (root / ".github/workflows/apply-v153-main-script.yml").exists()
        and not (root / ".github/workflows/apply-v153-playback-report.yml").exists()
        and not (root / "scripts/apply_v153_main_playback_report.py").exists()
    ),
}

failed = []
for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
    if not passed:
        failed.append(name)

if failed:
    raise SystemExit("v153 checks failed: " + ", ".join(failed))
