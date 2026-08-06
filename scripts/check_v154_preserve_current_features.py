from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "e1f26d6763c390cab9dd6fc5b1d8c5f87c37e81c"  # completed v153 source


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


main = read("app/src/main/java/com/jianglab/babywife/MainActivity.java")
cache = read("app/src/main/java/com/jianglab/babywife/CacheStorage.java")
service = read("app/src/main/java/com/jianglab/babywife/PlaybackControlService.java")
search_cache = read("app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java")
media3_export = read("app/src/main/java/com/jianglab/babywife/Media3FriendlyCacheExporter.java")
gradle = read("app/build.gradle")
manifest = read("app/src/main/AndroidManifest.xml")

changed = set(filter(None, git("diff", "--name-only", BASELINE, "HEAD").splitlines()))
forbidden_prefixes = (
    "app/src/main/res/layout/",
    "app/src/main/res/drawable/",
    "app/src/main/res/mipmap-",
    "app/src/main/res/values/",
)
forbidden_exact = {"app/src/main/AndroidManifest.xml"}
ui_changes = sorted(
    path for path in changed
    if path in forbidden_exact or path.startswith(forbidden_prefixes)
)

checks = {
    "UI resources unchanged from v153": not ui_changes,
    "four brand flavors retained": all(token in gradle for token in (
        "babywifeclassic", "lidacaizhu", "jianglab", "niubi"
    )),
    "four package identities retained": all(token in gradle for token in (
        'applicationId "com.jianglab.babywife"',
        'applicationIdSuffix ".lidacaizhu"',
        'applicationIdSuffix ".jianglab"',
        'applicationIdSuffix ".niubi"',
    )),
    "JiangLab passphrase retained": (
        'REQUIRE_FIRST_RUN_PASSPHRASE' in gradle
        and 'maybeRequireJiangLabPassphrase' in main
    ),
    "search and source selector retained": all(token in main for token in (
        "CatalogSearch.Session", "sourceSpinner", "searchResultsList",
        "activeSearchKeyword", "searchLoadMoreView"
    )),
    "playlist create rename delete merge clear retained": all(token in main for token in (
        "promptNewPlaylist", "promptRenamePlaylist", "deleteCurrentPlaylist",
        "mergePlaylistsIntoCurrent", "clearCurrentPlaylist"
    )),
    "playlist CSV and link import export retained": all(token in main for token in (
        "REQUEST_EXPORT_PLAYLIST", "REQUEST_IMPORT_PLAYLIST_CSV",
        "exportCurrentPlaylistCsv", "importPlaylistCsv", "promptImportPlaylistLink"
    )),
    "local audio and folder import retained": all(token in main for token in (
        "REQUEST_AUDIO_FILES", "REQUEST_AUDIO_FOLDER", "MAX_IMPORT_COUNT",
        "chooseAudioFiles", "chooseAudioFolder"
    )),
    "lyrics and manual replacement retained": all(token in main for token in (
        "lyricVersionButton", "confirmLyricButton", "pendingReplacementType",
        "REPLACEMENT_LYRIC", "REPLACEMENT_SONG", "updateLyricProgress",
        "showSongVersionPicker", "showLyricVersionPicker"
    )),
    "play modes seek previous next retained": all(token in main for token in (
        "KEY_PLAY_MODE", "playPlaylistOffset", "performPlaylistOffset",
        "COMMAND_PREVIOUS", "COMMAND_NEXT", "COMMAND_SEEK", "togglePlayback"
    )),
    "notification playback service retained": (
        "PlaybackControlService.ensureStarted" in main
        and "PlaybackControlService" in manifest
        and "Notification.MediaStyle" in service
    ),
    "progress restore retained": all(token in main for token in (
        "KEY_LAST_PLAYLIST", "KEY_LAST_SONG", "KEY_LAST_POSITION",
        "restoreLastSong", "saveLastSong"
    )),
    "cache folder selection and migration retained": all(token in cache for token in (
        "useDocumentTree", "useInternalStorage", "takePersistableUriPermission",
        "copyDocumentsToInternal", "copyFilesToTree"
    )),
    "friendly cache filename format retained": (
        'record.title + " - " + record.artist' in cache
        and 'String fileName = baseName + "." + safeExtension' in cache
        and "ensureFriendlyNames" in cache
    ),
    "playlist-safe broom cleanup retained": (
        "clearExcept" in cache and "deleteKey" in cache
        and "confirmClearTransientCache" in main and "clearTransientCache" in main
    ),
    "one-click playlist cache retained": all(token in main for token in (
        "cacheCurrentPlaylistOneClick", "cachePlaylistSongWithTimeout",
        "PLAYLIST_CACHE_TRACK_TIMEOUT_SECONDS"
    )),
    "M4A decryption retained": (
        "SodaM4aDecryptor" in search_cache
        and "SodaM4aDecryptor" in media3_export
    ),
    "playback and crash report retained": all(token in main for token in (
        "PlaybackProblemReporter", "showPendingCrashReport",
        "captureLastProcessExitReport", "startResponsivenessWatchdog"
    )),
    "background and launcher icon controls retained": all(token in main for token in (
        "chooseBackgroundImage", "showBuiltInBackgroundPicker",
        "showLauncherIconPicker", "switchLauncherIcon"
    )),
    "v154 metadata": (
        "versionCode 2026080154" in gradle
        and 'versionName "2026.08.06.v154-media3-shared-cache"' in gradle
    ),
}

for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
if ui_changes:
    print("Forbidden UI/manifest changes:")
    for path in ui_changes:
        print("  " + path)
failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("v154 preservation checks failed: " + ", ".join(failed))
