from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
V158_BASELINE = "50846752e1866d603557af30ba8734671cd3d89d"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


main = read("app/src/main/java/com/jianglab/babywife/MainActivity.java")
gradle = read("app/build.gradle")
cache_storage = read("app/src/main/java/com/jianglab/babywife/CacheStorage.java")
exporter = read("app/src/main/java/com/jianglab/babywife/Media3FriendlyCacheExporter.java")

changed = set(filter(None, git("diff", "--name-only", V158_BASELINE, "HEAD").splitlines()))
ui_prefixes = (
    "app/src/main/res/layout/",
    "app/src/main/res/drawable/",
    "app/src/main/res/mipmap-",
    "app/src/main/res/values/",
)
ui_changes = sorted(path for path in changed if path.startswith(ui_prefixes))

checks = {
    "v159 metadata": (
        "versionCode 2026080759" in gradle
        and 'versionName "2026.08.07.v159-cache-state-recovery"' in gradle
    ),
    "UI resources unchanged from v158": not ui_changes,
    "playlist cache scan verifies real cache instead of stale recorded URI": (
        "if (songHasPlayableCache(song)) continue;" in main
        and main.count("if (songHasPlayableCache(song))") >= 2
    ),
    "recorded friendly file clears stale red state": (
        "recoverCachedSongState(song, recorded)" in main
        and "NetworkMediaCache.cachedAudioExists(this, recorded)" in main
    ),
    "storage lookup and Media3 index both recover friendly cache": (
        "CacheStorage.findAudioUri(this, key)" in main
        and "Media3PlaybackCacheIndex.friendlyUri(this, media3Key)" in main
        and "recoverCachedSongState(song, existingUri)" in main
    ),
    "cache recovery clears every failure flag": all(token in main for token in (
        "song.unavailable = false;",
        "song.autoUnavailable = false;",
        "song.manualUnavailable = false;",
        "song.manualAttempt = false;",
        "song.cacheFailed = false;",
    )),
    "cache recovery updates same logical playlist copies": (
        "boolean sameLogicalSong = dedupeKey(item).equals(logicalKey);" in main
        and "boolean sameCatalog" in main
        and "applyRecoveredCacheState(item, uri)" in main
    ),
    "attaching old cache immediately refreshes playlist row state": (
        "boolean changed = recoverCachedSongState(song, uri);" in main
        and "playlistAdapter.notifyDataSetChanged()" in main
        and "resultAdapter.notifyDataSetChanged()" in main
        and "updatePlaylistCacheButtonVisibility();" in main
    ),
    "cache migration refresh clears stale flags too": (
        "recoverCachedSongState(song, uri);" in main
        and "private void refreshCachedUri" in main
    ),
    "playback-export success clears manual failure state": (
        "item.manualUnavailable = false;" in main
        and "item.manualAttempt = false;" in main
        and "persistSearchCacheToPlaylistCopies" in main
    ),
    "one-click success recovers all playlist copies": (
        "recoverCachedSongState(song, cached.audioUri);" in main
        and "cacheCurrentPlaylistOneClick" in main
    ),
    "red rendering still depends only on unavailable state": (
        "int color = song.unavailable ? Color.rgb(255, 96, 96) : TEXT_MAIN;" in main
    ),
    "friendly cache filename unchanged": (
        'record.title + " - " + record.artist' in cache_storage
        and 'String fileName = baseName + "." + safeExtension' in cache_storage
    ),
    "v158 nonblocking export retained": (
        "setCacheWriteDataSinkFactory(null)" in exporter
        and "copyReadThroughResource" in exporter
        and "CacheWriter" not in exporter
        and "FLAG_BLOCK_ON_CACHE" not in exporter
    ),
}

for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
if ui_changes:
    print("Unexpected UI changes:")
    for path in ui_changes:
        print("  " + path)
failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("v159 checks failed: " + ", ".join(failed))
