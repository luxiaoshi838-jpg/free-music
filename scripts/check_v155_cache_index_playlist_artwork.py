from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
V154_BASELINE = "be6db615b2952bc16f57778d54faa22ef6209fa3"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


main = read("app/src/main/java/com/jianglab/babywife/MainActivity.java")
gradle = read("app/build.gradle")
store = read("app/src/main/java/com/jianglab/babywife/Media3CacheStore.java")
index = read("app/src/main/java/com/jianglab/babywife/Media3PlaybackCacheIndex.java")
exporter = read("app/src/main/java/com/jianglab/babywife/Media3FriendlyCacheExporter.java")
cache_storage = read("app/src/main/java/com/jianglab/babywife/CacheStorage.java")
service = read("app/src/main/java/com/jianglab/babywife/PlaybackControlService.java")
artwork = read("app/src/main/java/com/jianglab/babywife/PlaybackArtworkLoader.java")

changed = set(filter(None, git("diff", "--name-only", V154_BASELINE, "HEAD").splitlines()))
ui_prefixes = (
    "app/src/main/res/layout/",
    "app/src/main/res/drawable/",
    "app/src/main/res/mipmap-",
    "app/src/main/res/values/",
)
ui_changes = sorted(path for path in changed if path.startswith(ui_prefixes))

checks = {
    "v155 metadata": (
        "versionCode 2026080155" in gradle
        and 'versionName "2026.08.06.v155-cache-index-playlist-artwork"' in gradle
    ),
    "UI resources unchanged from v154": not ui_changes,
    "real Media3 cache has persistent song index": all(token in index for token in (
        'PREFS = "media3_playback_cache_index"',
        'object.put("key", key.trim())',
        'object.put("title", safe(title))',
        'object.put("artist", safe(artist))',
        'object.put("cachedBytes", Math.max(0L, cachedBytes))',
        'object.put("complete"',
        'object.put("friendlyUri"',
        'object.put("artworkUrl"',
    )),
    "online playback registers real cache immediately": (
        "Media3PlaybackCacheIndex.record(this, media3Key" in main
        and "preparedPlayer.setDataSource(" in main
        and main.find("Media3PlaybackCacheIndex.record(this, media3Key")
            < main.find("preparedPlayer.setDataSource(",
                        main.find("Media3PlaybackCacheIndex.record(this, media3Key"))
    ),
    "playback cache completion survives song switching": (
        "Executors.newFixedThreadPool(2)" in main
        and "Playback cache completion is intentionally not cancelled by song switches" in main
        and "if (!activityDestroyed) return;" in main
        and "searchCacheExecutor.submit" in main
        and "if (activityDestroyed || currentSong != song) return;" in main
    ),
    "background completion exports friendly file automatically": (
        "Media3FriendlyCacheExporter.cacheAndExport" in main
        and "CacheStorage.storeAudio" in exporter
        and "Media3PlaybackCacheIndex.markExported" in exporter
        and "persistSearchCacheToPlaylistCopies" in main
    ),
    "friendly filename format remains title artist extension": (
        'record.title + " - " + record.artist' in cache_storage
        and 'String fileName = baseName + "." + safeExtension' in cache_storage
    ),
    "cache settings recognise internal playback cache": (
        "Media3PlaybackCacheIndex.summary(context).displayText()" in cache_storage
        and 'return "播放缓存："' in index
        and "partialResources" in index
        and "completeResources" in index
    ),
    "broom can remove real Media3 spans and index": (
        "Media3CacheStore.removeExcept" in main
        and "Media3PlaybackCacheIndex.remove(context, key)" in store
        and "Media3PlaybackCacheIndex.pruneToKeys" in store
    ),
    "playlist without friendly file preserves useful spans": (
        "boolean hasFriendly" in main
        and "!hasFriendly) keepMedia3Keys.add(media3Key)" in main
    ),
    "playlist with friendly file allows duplicate spans to be cleaned": (
        "attachExistingFriendlyCache(song);" in main
        and "CacheFileState.exists(this, song.cachedUri)" in main
    ),
    "existing friendly export is recognised before playlist playback and add": (
        main.count("attachExistingFriendlyCache(song);") >= 3
        and "Media3PlaybackCacheIndex.friendlyUri" in main
        and "CacheStorage.findAudioUri" in main
    ),
    "song model persists independent artwork URL": all(token in main for token in (
        "String artworkUrl;",
        'object.put("artworkUrl", artworkUrl)',
        'object.optString("artworkUrl"',
        "copy.artworkUrl = song.artworkUrl",
        "keeper.artworkUrl = candidate.artworkUrl",
    )),
    "search and fallback resolution propagate artwork": (
        "song.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(resolved.catalogJson)" in main
        and "item.artworkUrl = song.artworkUrl" in main
        and "item.artworkUrl = !song.artworkUrl.isEmpty()" in main
    ),
    "song replacement resets old cover": (
        "item.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(pendingSongCatalogJson)" in main
        and "target.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(pendingSongCatalogJson)" in main
    ),
    "old playlists recover artwork from catalog JSON": (
        "PlaybackArtworkLoader.extractArtworkUrl(this.catalogJson)" in main
        and "PlaybackArtworkLoader.extractArtworkUrl(song.catalogJson)" in main
    ),
    "notification receives explicit playlist artwork URL": (
        "currentSong == null ? \"\" : currentSong.artworkUrl" in main
        and "EXTRA_ARTWORK_URL" in service
        and "requestArtworkUrl" in service
    ),
    "late artwork arrival forces notification reload": (
        '+ "|art=" + artworkUrl.trim()' in service
        and "artworkRequestedIdentity = \"\"" in service
        and "artworkRequestSerial++" in service
    ),
    "playlist artwork has URL then catalog then embedded fallback": (
        "explicitArtworkUrl" in artwork
        and "findArtworkUrl(catalogJson)" in artwork
        and "MediaMetadataRetriever" in artwork
        and "getEmbeddedPicture" in artwork
    ),
    "lock screen MediaSession still receives cover": all(token in service for token in (
        "METADATA_KEY_ALBUM_ART",
        "METADATA_KEY_ART",
        "METADATA_KEY_DISPLAY_ICON",
        "setLargeIcon(artwork)",
    )),
    "temporary v155 patch files removed": all(not (ROOT / path).exists() for path in (
        ".github/workflows/apply-v155-cache-cover.yml",
        ".github/workflows/fix-v155-patch-script.yml",
        ".github/workflows/fix-v155-first-match.yml",
        ".github/workflows/apply-v155-followup.yml",
        ".github/workflows/cleanup-v155-temp.yml",
        "scripts/apply_v155_cache_cover_fix.py",
        "scripts/apply_v155_followup.py",
    )),
}

for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
if ui_changes:
    print("Unexpected UI resource changes:")
    for item in ui_changes:
        print("  " + item)
failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("v155 checks failed: " + ", ".join(failed))
