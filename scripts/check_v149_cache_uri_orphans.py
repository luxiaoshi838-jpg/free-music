from pathlib import Path

root = Path(__file__).resolve().parents[1]
search = (root / "app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java").read_text(encoding="utf-8")
network = (root / "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java").read_text(encoding="utf-8")
state = (root / "app/src/main/java/com/jianglab/babywife/CacheFileState.java").read_text(encoding="utf-8")
cleaner = (root / "app/src/main/java/com/jianglab/babywife/TransientCacheCleaner.java").read_text(encoding="utf-8")
gradle = (root / "app/build.gradle").read_text(encoding="utf-8")

search_post_store = search[
    search.index("String storedUri = CacheStorage.storeAudio"):
    search.index("CacheStorage.deleteOtherSongCaches")
]
network_exists = network[
    network.index("static boolean cachedAudioExists"):
    network.index("private static String catalogTitle")
]

checks = {
    "v149 metadata": (
        "versionCode 2026080149" in gradle
        and 'versionName "2026.08.05.v149-cache-uri-orphan-fix"' in gradle
    ),
    "content uri checked by reading bytes": (
        "openInputStream" in state
        and "input.read() >= 0" in state
        and "READ_ATTEMPTS" in state
    ),
    "search cache no longer trusts provider length": (
        "CacheFileState.exists(context, storedUri)" in search_post_store
        and "CacheStorage.exists(context, storedUri)" not in search_post_store
    ),
    "failed search cache deletes direct uri": (
        "CacheFileState.deleteDirect(context, storedUri)" in search_post_store
    ),
    "playlist add uses readable-byte check": (
        "CacheFileState.exists(context, uriText)" in network_exists
        and "SodaM4aDecryptor.isEncryptedM4a" in network_exists
    ),
    "cleaner reads saved playlists": (
        'STATE_PREFS = "babywife_state"' in cleaner
        and 'KEY_PLAYLISTS = "playlists_v2"' in cleaner
        and 'song.optString("cachedUri"' in cleaner
        and 'song.optString("uri"' in cleaner
    ),
    "cleaner preserves playlist uri and filename": (
        "playlistUris.contains(entry.uri.toString())" in cleaner
        and "savedPlaylistFileNames" in cleaner
        and "keepNames.contains(entry.name)" in cleaner
    ),
    "cleaner removes metadata-free friendly orphans": (
        "isFriendlyCacheFile(entry.name)" in cleaner
        and 'base.contains(" - ")' in cleaner
        and "DocumentsContract.deleteDocument" in cleaner
    ),
}

failed = [name for name, passed in checks.items() if not passed]
for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
if failed:
    raise SystemExit("v149 cache URI/orphan checks failed: " + ", ".join(failed))
