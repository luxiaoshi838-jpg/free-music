from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / "app/src/main/java/com/jianglab/babywife/MainActivity.java").read_text(encoding="utf-8")
resolver = (root / "app/src/main/java/com/jianglab/babywife/PlayableAudioResolver.java").read_text(encoding="utf-8")
network = (root / "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java").read_text(encoding="utf-8")
cleaner = (root / "app/src/main/java/com/jianglab/babywife/TransientCacheCleaner.java").read_text(encoding="utf-8")
gradle = (root / "app/build.gradle").read_text(encoding="utf-8")

cached_method = resolver[
    resolver.index("static boolean cachedAudioExists"):
    resolver.index("private static List<JSONObject> candidateCatalogs")
]
post_store = resolver[
    resolver.index("String storedUri = CacheStorage.storeAudio"):
    resolver.index('status(callback, "唯一正式缓存写入完成')
]
clear_method = network[
    network.index("static int clearExcept"):
    network.index("static int deleteCatalogCache")
]

checks = {
    "v148 metadata": (
        "versionCode 2026080148" in gradle
        and 'versionName "2026.08.05.v148-cache-state-cleanup"' in gradle
    ),
    "audio is still verified before storage": (
        "SodaM4aDecryptor.decrypt" in resolver
        and "AudioPlaybackVerifier.probeFile(decodedSource)" in resolver
        and "AudioMetadataWriter.applyAndVerify" in resolver
    ),
    "cache completion uses stored-file state": (
        "CacheStorage.exists(context, uriText)" in cached_method
        and "SodaM4aDecryptor.isEncryptedM4a(context, uriText)" in cached_method
        and "AudioPlaybackVerifier.isPlayableUri" not in cached_method
    ),
    "post-store provider false negative removed": (
        "CacheStorage.exists(context, storedUri)" in post_store
        and "SodaM4aDecryptor.isEncryptedM4a(context, storedUri)" in post_store
        and "AudioPlaybackVerifier.isPlayableUri" not in post_store
    ),
    "playlist add still requires registered cache": (
        "歌曲还在缓存，完成后再加入歌单" in main
        and "CacheStorage.findAudioUri(this, key)" in main
        and "NetworkMediaCache.cachedAudioExists(this, existingUri)" in main
    ),
    "document-tree cleanup runs before legacy cleanup": (
        "TransientCacheCleaner.clearDocumentTreeExcept" in clear_method
        and clear_method.index("TransientCacheCleaner.clearDocumentTreeExcept")
            < clear_method.index("CacheStorage.clearExcept")
    ),
    "friendly files are deleted from metadata": (
        'metadata.optString("audioFile"' in cleaner
        and 'metadata.optString("lyricFile"' in cleaner
        and "listAllDocuments" in cleaner
        and "DocumentsContract.deleteDocument" in cleaner
        and "managedOnly" not in cleaner
    ),
}

failed = [name for name, passed in checks.items() if not passed]
for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
if failed:
    raise SystemExit("v148 cache-state/cleanup checks failed: " + ", ".join(failed))
