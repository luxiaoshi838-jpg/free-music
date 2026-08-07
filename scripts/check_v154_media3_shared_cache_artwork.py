from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / "app/src/main/java/com/jianglab/babywife/MainActivity.java").read_text(encoding="utf-8")
gradle = (root / "app/build.gradle").read_text(encoding="utf-8")
player = (root / "app/src/main/java/com/jianglab/babywife/UnifiedMediaPlayer.java").read_text(encoding="utf-8")
store = (root / "app/src/main/java/com/jianglab/babywife/Media3CacheStore.java").read_text(encoding="utf-8")
exporter = (root / "app/src/main/java/com/jianglab/babywife/Media3FriendlyCacheExporter.java").read_text(encoding="utf-8")
service = (root / "app/src/main/java/com/jianglab/babywife/PlaybackControlService.java").read_text(encoding="utf-8")
artwork = (root / "app/src/main/java/com/jianglab/babywife/PlaybackArtworkLoader.java").read_text(encoding="utf-8")
cache = (root / "app/src/main/java/com/jianglab/babywife/CacheStorage.java").read_text(encoding="utf-8")

checks = {
    "v154 metadata": (
        "versionCode 2026080154" in gradle
        and 'versionName "2026.08.06.v154-media3-shared-cache"' in gradle
    ),
    "Media3 1.9.3 dependencies compatible with existing SDK line": all(token in gradle for token in (
        'def media3_version = "1.9.3"',
        'compileSdk 35',
        'targetSdk 35',
        'media3-exoplayer:$media3_version',
        'media3-datasource:$media3_version',
        'media3-database:$media3_version',
    )),
    "MainActivity migrated without Android MediaPlayer": (
        "private UnifiedMediaPlayer mediaPlayer" in main
        and "android.media.MediaPlayer" not in main
        and "new UnifiedMediaPlayer(this)" in main
    ),
    "online playback uses stable Media3 cache key": (
        "Media3CacheStore.keyFor" in main
        and "setCustomCacheKey(cacheKey)" in player
        and (
            'return "media3|" + logical.trim()' in store
            or 'return "media3|catalog|" + catalogKey.trim()' in store
        )
    ),
    "playback and cache share CacheDataSource": (
        "Media3CacheStore.dataSourceFactory" in player
        and "CacheDataSource.Factory" in store
        and "SimpleCache" in store
    ),
    "background completion reuses cached spans": (
        (
            "CacheWriter" in exporter
            and "createDataSourceForDownloading" in exporter
            and "Media3CacheStore.get(context).isCached" in exporter
        )
        or (
            "copyReadThroughResource" in exporter
            and "setCacheWriteDataSinkFactory(null)" in exporter
            and "FLAG_IGNORE_CACHE_ON_ERROR" in exporter
            and "Media3CacheStore.cachedBytes" in exporter
        )
    ),
    "friendly audio export retained": (
        "CacheStorage.storeAudio" in exporter
        and "CacheStorage.deleteOtherSongCaches" in exporter
        and 'record.title + " - " + record.artist' in cache
    ),
    "encrypted M4A export retained": (
        "SodaM4aDecryptor.isEncryptedM4a" in exporter
        and "SodaM4aDecryptor.decrypt" in exporter
        and "playAuth" in exporter
    ),
    "playlist add no longer waits for cache": (
        "addSongToCurrentPlaylistReady(song);" in main
        and "歌曲还在缓存，完成后再加入歌单" not in main
    ),
    "active search song identity retained after add": (
        "currentSong == song ? song : copySongForPlaylist(song)" in main
    ),
    "playlist can stream before friendly cache completes": (
        "歌单没有完整友好缓存" in main
        and "trySearchPlaybackCandidate(song, playToken, 0);" in main
    ),
    "old Range downloader not used for search background completion": (
        "Media3FriendlyCacheExporter.cacheAndExport" in main
        and "SearchQuickPlayback.cache(" not in main
    ),
    "broom also clears non-playlist Media3 spans": (
        "Media3CacheStore.removeExcept" in main
        and "keepMedia3Keys" in main
    ),
    "notification receives catalog and media URI": (
        "notificationCatalog" in main
        and "notificationUri" in main
        and "EXTRA_CATALOG_JSON" in service
        and "EXTRA_MEDIA_URI" in service
    ),
    "online and local artwork supported": (
        "findArtworkUrl" in artwork
        and "MediaMetadataRetriever" in artwork
        and "getEmbeddedPicture" in artwork
    ),
    "artwork cached and bounded": (
        'playback_artwork_cache' in artwork
        and "MAX_CACHE_FILES" in artwork
        and "MAX_CACHE_BYTES" in artwork
        and "prune(directory)" in artwork
    ),
    "lock screen MediaSession receives artwork": all(token in service for token in (
        "METADATA_KEY_ALBUM_ART", "METADATA_KEY_ART", "METADATA_KEY_DISPLAY_ICON"
    )),
    "notification uses cover and colorized background": (
        "setLargeIcon(artwork)" in service
        and "setColorized(true)" in service
        and "PlaybackArtworkLoader.averageColor" in service
    ),
    "previous play pause next seek retained": all(token in service for token in (
        "ACTION_SKIP_TO_PREVIOUS", "ACTION_SKIP_TO_NEXT", "ACTION_SEEK_TO",
        "COMMAND_TOGGLE", "COMMAND_PREVIOUS", "COMMAND_NEXT", "COMMAND_SEEK"
    )),
    "temporary migration files removed": (
        not (root / ".github/workflows/apply-v154-mainactivity.yml").exists()
        and not (root / "scripts/apply_v154_mainactivity.py").exists()
    ),
}

for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("v154 Media3/artwork checks failed: " + ", ".join(failed))
