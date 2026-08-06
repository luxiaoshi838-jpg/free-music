from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "74d1832bb3b3cf61d11ee56bdcca35ade771ff67"  # v156 upgrade-compatible source


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


main = read("app/src/main/java/com/jianglab/babywife/MainActivity.java")
store = read("app/src/main/java/com/jianglab/babywife/Media3CacheStore.java")
exporter = read("app/src/main/java/com/jianglab/babywife/Media3FriendlyCacheExporter.java")
quick = read("app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java")
gradle = read("app/build.gradle")
cache_storage = read("app/src/main/java/com/jianglab/babywife/CacheStorage.java")

candidate_start = main.find("    private void trySearchPlaybackCandidate(")
candidate_end = main.find("    private void cacheSearchPlaybackAsync(", candidate_start)
candidate_block = main[candidate_start:candidate_end] if candidate_start >= 0 and candidate_end > candidate_start else ""

changed = set(filter(None, git("diff", "--name-only", BASELINE, "HEAD").splitlines()))
ui_prefixes = (
    "app/src/main/res/layout/",
    "app/src/main/res/drawable/",
    "app/src/main/res/mipmap-",
    "app/src/main/res/values/",
)
ui_changes = sorted(path for path in changed if path.startswith(ui_prefixes))

checks = {
    "v157 metadata and upgrade code": (
        "versionCode 2026080757" in gradle
        and 'versionName "2026.08.06.v157-source-faithful-cache-export"' in gradle
    ),
    "UI resources unchanged from v156": not ui_changes,
    "search click resolves selected source only": (
        "trySearchPlaybackCandidate(song, playToken, 0, false);" in main
        and "int maxStage = allowCrossSourceFallback ? 2 : 0;" in main
        and "结果没有返回可播放地址，请选择其他来源结果" in main
    ),
    "selected source mismatch rejected": (
        "!requestedSource.equals(resolved.sourceCode)" in candidate_block
        and "来源校验失败：选择的是" in candidate_block
    ),
    "cross-source fallback limited to playlist replacement": (
        "酷我（歌单自动替代）" in candidate_block
        and "网易云（歌单自动替代）" in candidate_block
        and "trySearchPlaybackCandidate(song, playToken, stage, !playingSearchQueue);" in candidate_block
    ),
    "resolved metadata installed before player opens": (
        candidate_block.find("song.catalogJson = resolved.catalogJson;") >= 0
        and candidate_block.find("song.catalogJson = resolved.catalogJson;")
            < candidate_block.find("startLocalPlayback(song, playToken, () ->")
        and "song.source = resolved.sourceLabel;" in candidate_block
        and "song.uri = resolved.playbackUrl;" in candidate_block
    ),
    "Media3 key is source and catalog specific": (
        'return "media3|catalog|" + catalogKey.trim();' in store
        and '"media3|logical|" + logical.trim()' in store
        and "NetworkMediaCache.cacheKeyForCatalog(catalogJson)" in store
    ),
    "search cache reuse requires exact source and ID": (
        "sameCatalogIdentity(playlistMatch.catalogJson, song.catalogJson)" in main
        and "catalogIdentity(candidate.catalogJson)" in main
    ),
    "playback immediately starts friendly export": (
        "播放后自动生成本地缓存文件" in candidate_block
        and "cacheSearchPlaybackAsync(song, resolved, playToken);" in candidate_block
        and "加入当前歌单" in main
    ),
    "cache tasks are per source key and survive song switch": (
        "ConcurrentHashMap<String, Future<?>> searchCacheTasks" in main
        and "searchCacheTasks.get(media3Key)" in main
        and "searchCacheTasks.put(media3Key, submitted)" in main
        and "searchCacheTasks.remove(media3Key)" in main
        and "if (!activityDestroyed) return;" in main
    ),
    "existing friendly file reused before network": (
        "CacheStorage.findAudioUri(context, storageKey)" in exporter
        and "return existingUri;" in exporter
    ),
    "unknown Content-Length still exports completed cache": (
        "contiguousCachedBytesFromZero" in store
        and "contentLength = Media3CacheStore.contiguousCachedBytesFromZero" in exporter
        and ".setLength(contentLength)" in exporter
        and "copyCachedResource(cacheFactory, exportSpec" in exporter
    ),
    "friendly filename format retained": (
        'record.title + " - " + record.artist' in cache_storage
        and 'String fileName = baseName + "." + safeExtension' in cache_storage
        and "CacheStorage.storeAudio" in exporter
    ),
    "same source used for retry": (
        "refreshed.sourceCode.equals" in main
        and "exportCandidate.sourceCode" in main
    ),
    "legacy forced search fallback text removed": (
        "搜索结果、酷我和网易云均没有可播放地址" not in main
        and "搜索结果自身来源" not in main
    ),
    "underlying resolver still supports playlist fallback stages": (
        'stage == 1 ? "kuwo"' in quick
        and 'stage == 2 ? "netease"' in quick
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
    raise SystemExit("v157 checks failed: " + ", ".join(failed))
