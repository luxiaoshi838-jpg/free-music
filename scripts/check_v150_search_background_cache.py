from pathlib import Path

root = Path(__file__).resolve().parents[1]
search = (root / "app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java").read_text(encoding="utf-8")
network = (root / "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java").read_text(encoding="utf-8")
state = (root / "app/src/main/java/com/jianglab/babywife/CacheFileState.java").read_text(encoding="utf-8")
cleaner = (root / "app/src/main/java/com/jianglab/babywife/TransientCacheCleaner.java").read_text(encoding="utf-8")
gradle = (root / "app/build.gradle").read_text(encoding="utf-8")

cache_method = search[
    search.index("static String cache"):
    search.index("private static Candidate downloadWithFreshAddress")
]
fresh_download = search[
    search.index("private static Candidate downloadWithFreshAddress"):
    search.index("private static void download")
]
download_method = search[
    search.index("private static void download"):
    search.index("private static String userAgent")
]
network_exists = network[
    network.index("static boolean cachedAudioExists"):
    network.index("private static String catalogTitle")
]

checks = {
    "v150 metadata": (
        "versionCode 2026080150" in gradle
        and 'versionName "2026.08.05.v150-search-background-cache"' in gradle
    ),
    "background download resolves a fresh address": (
        "downloadWithFreshAddress(playbackCandidate, partial)" in cache_method
        and "resolveFreshCandidate(playbackCandidate)" in fresh_download
        and "resolveCatalog(new JSONObject(playbackCandidate.catalogJson))" in fresh_download
    ),
    "empty downloads are retried with new resolves": (
        "DOWNLOAD_ATTEMPTS = 3" in search
        and "for (int attempt = 0; attempt < DOWNLOAD_ATTEMPTS; attempt++)" in fresh_download
        and "搜索歌曲下载为空" in fresh_download
        and "搜索歌曲后台下载失败" in fresh_download
    ),
    "search downloader matches formal request headers": (
        "connection.setUseCaches(false)" in download_method
        and 'setRequestProperty("User-Agent", userAgent(candidate.sourceCode))' in download_method
        and 'setRequestProperty("Accept", "audio/*,application/octet-stream;q=0.9,*/*;q=0.1")' in download_method
        and 'setRequestProperty("Accept-Encoding", "identity")' in download_method
        and "referer(candidate.sourceCode)" in download_method
    ),
    "zero-byte body fails inside downloader": (
        "long written = 0L" in download_method
        and "if (written <= 0) throw new IllegalStateException(\"搜索歌曲下载为空\")" in download_method
    ),
    "fresh candidate metadata drives decrypt and storage": (
        "downloadCandidate.playAuth" in cache_method
        and "downloadCandidate.extension" in cache_method
        and "downloadCandidate.catalogJson" in cache_method
    ),
    "v149 readable uri protection remains": (
        "CacheFileState.exists(context, storedUri)" in cache_method
        and "CacheFileState.deleteDirect(context, storedUri)" in cache_method
        and "openInputStream" in state
    ),
    "playlist add still uses readable cache state": (
        "CacheFileState.exists(context, uriText)" in network_exists
        and "SodaM4aDecryptor.isEncryptedM4a" in network_exists
    ),
    "non-playlist orphan cleanup remains": (
        'STATE_PREFS = "babywife_state"' in cleaner
        and 'KEY_PLAYLISTS = "playlists_v2"' in cleaner
        and "isFriendlyCacheFile(entry.name)" in cleaner
        and "DocumentsContract.deleteDocument" in cleaner
    ),
}

failed = [name for name, passed in checks.items() if not passed]
for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
if failed:
    raise SystemExit("v150 search background cache checks failed: " + ", ".join(failed))
