from pathlib import Path

root = Path(__file__).resolve().parents[1]
search = (root / "app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java").read_text(encoding="utf-8")
gradle = (root / "app/build.gradle").read_text(encoding="utf-8")

checks = {
    "v151 metadata": (
        "versionCode 2026080151" in gradle
        and 'versionName "2026.08.05.v151-search-range-cache"' in gradle
    ),
    "background cache uses byte ranges": (
        'connection.setRequestProperty("Range", "bytes=" + start + "-" + end)' in search
        and "RANGE_CHUNK_BYTES" in search
        and "downloadByRanges" in search
    ),
    "manual redirects preserve download headers": (
        "setInstanceFollowRedirects(false)" in search
        and "MAX_REDIRECTS" in search
        and 'getHeaderField("Location")' in search
        and "new URL(current, location.trim())" in search
    ),
    "range response handling": (
        "HttpURLConnection.HTTP_PARTIAL" in search
        and 'getHeaderField("Content-Range")' in search
        and "parseContentRangeTotal" in search
    ),
    "empty response has diagnostics": (
        "Range 响应正文为 0 字节" in search
        and "Content-Length=" in search
        and "Content-Range=" in search
        and "已写入=" in search
    ),
    "fresh address resolution retained": (
        "resolveFreshCandidate" in search
        and "resolveCatalog(new JSONObject(playbackCandidate.catalogJson))" in search
    ),
    "v149 cleanup and cache state retained": (
        "CacheFileState.exists(context, storedUri)" in search
        and "CacheStorage.deleteOtherSongCaches" in search
        and "SodaM4aDecryptor.isEncryptedM4a" in search
    ),
}

failed = [name for name, passed in checks.items() if not passed]
for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
if failed:
    raise SystemExit("v151 search range cache checks failed: " + ", ".join(failed))
