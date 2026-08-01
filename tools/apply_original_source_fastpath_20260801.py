#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
NETWORK = ROOT / "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java"
CHECKS = ROOT / "scripts/check_feature_requirements.py"
GRADLE = ROOT / "app/build.gradle"
PROJECT_LOG = ROOT / "PROJECT_LOG.md"
CHANGELOG = ROOT / "docs/CHANGELOG.md"


def replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"method anchor missing: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError(f"method brace missing: {signature}")
    depth = 0
    in_string = False
    escaped = False
    quote = ""
    for index in range(brace, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue
        if char in ('"', "'"):
            in_string = True
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement.rstrip() + text[index + 1:]
    raise RuntimeError(f"method end missing: {signature}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 1:
        return text.replace(old, new, 1)
    if count == 0 and new in text:
        return text
    raise RuntimeError(f"{label}: expected one old anchor, found {count}")


def patch_network() -> None:
    text = NETWORK.read_text(encoding="utf-8")
    text = text.replace("import java.util.ArrayList;\n", "")
    text = replace_once(
        text,
        "    private static final int MAX_AUTOMATIC_CHOICES = 8;\n",
        "    private static final int MAX_FALLBACK_ATTEMPTS = 4;\n",
        "fallback limit",
    )

    text = replace_method(
        text,
        "    static CacheResult cache(Context context, String catalogJson, StatusCallback callback) throws Exception {",
        r'''    static CacheResult cache(Context context, String catalogJson, StatusCallback callback) throws Exception {
        checkInterrupted();
        if (context == null) throw new IllegalArgumentException("context is required");
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        if (requestedSource.isEmpty() || requestedId.isEmpty()) throw new IllegalArgumentException("歌曲目录缺少来源或 ID");

        String requestedKey = sha256(requestedSource + "|" + requestedId);
        String requestedTitle = catalogTitle(requestedCatalog);
        String requestedArtist = catalogArtist(requestedCatalog);
        String requestedAlbum = catalogAlbum(requestedCatalog);
        CacheStorage.ensureFriendlyNames(context, requestedKey, requestedTitle, requestedArtist,
            requestedAlbum, requestedCatalog.toString());
        String requestedAudioUri = CacheStorage.findAudioUri(context, requestedKey);
        String requestedLyric = CacheStorage.readLyric(context, requestedKey);
        if (!requestedAudioUri.isEmpty() && isAcceptableCachedAudio(context, requestedAudioUri)) {
            boolean lyricFromCache = !requestedLyric.trim().isEmpty();
            if (!lyricFromCache) {
                status(callback, "正在按原平台读取歌词...");
                requestedLyric = fetchLyrics(requestedCatalog.toString());
                if (!requestedLyric.trim().isEmpty()) {
                    CacheStorage.writeLyric(context, requestedKey, requestedLyric, requestedTitle,
                        requestedArtist, requestedAlbum, requestedCatalog.toString());
                }
            }
            status(callback, "已读取原来源歌曲缓存");
            return new CacheResult(requestedAudioUri, requestedLyric, true, lyricFromCache,
                requestedCatalog.toString(), requestedSource, false);
        }

        Exception primaryError = null;
        status(callback, "正在使用歌单原来源解析歌曲...");
        try {
            long duration = catalogDurationMs(requestedCatalog);
            if (duration > 0L && duration < MIN_AUTOMATIC_DURATION_MS) {
                throw new IllegalStateException("原来源歌曲时长不足1分钟");
            }
            ResolvedChoice original = new ResolvedChoice(requestedCatalog,
                resolve(requestedCatalog.toString()));
            CacheResult result = cacheChoice(context, requestedCatalog, original, callback);
            if (result != null) return result;
        } catch (InterruptedException interrupted) {
            throw interrupted;
        } catch (Exception error) {
            primaryError = error;
        }

        status(callback, "原来源不可用，才开始查找其他平台版本...");
        return cacheFirstUsableAlternative(context, requestedCatalog, callback, primaryError);
    }''',
    )

    text = replace_method(
        text,
        "    private static List<ResolvedChoice> findAutomaticChoices(JSONObject requestedCatalog,",
        r'''    private static CacheResult cacheFirstUsableAlternative(Context context,
                                                               JSONObject requestedCatalog,
                                                               StatusCallback callback,
                                                               Exception primaryError) throws Exception {
        List<CatalogSearch.Track> alternatives = CatalogSearch.findExactAlternatives(requestedCatalog.toString());
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        Exception lastError = primaryError;
        int attempted = 0;

        for (CatalogSearch.Track alternative : alternatives) {
            checkInterrupted();
            if (attempted >= MAX_FALLBACK_ATTEMPTS) break;
            try {
                JSONObject catalog = canonicalCatalog(alternative.rawJson);
                String source = catalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
                String id = catalog.optString("id", "").trim();
                if (source.isEmpty() || id.isEmpty()) continue;
                if (requestedSource.equals(source) && requestedId.equals(id)) continue;
                long duration = catalogDurationMs(catalog);
                if (duration > 0L && duration < MIN_AUTOMATIC_DURATION_MS) continue;

                attempted++;
                status(callback, "正在尝试其他平台候选 " + attempted + "/" + MAX_FALLBACK_ATTEMPTS
                    + "：" + CatalogSearch.labelForSource(source));
                ResolvedChoice choice = new ResolvedChoice(catalog, resolve(catalog.toString()));
                CacheResult result = cacheChoice(context, requestedCatalog, choice, callback);
                if (result != null) return result;
            } catch (InterruptedException interrupted) {
                throw interrupted;
            } catch (Exception error) {
                lastError = error;
            }
        }

        String detail = lastError == null || lastError.getMessage() == null
            ? "" : "：" + lastError.getMessage();
        throw new IllegalStateException("未找到时长不低于1分钟的可播放音频，请手动使用替换歌曲" + detail);
    }''',
    )

    # Remove the old helper method left after replacing the candidate collector.
    start = text.find("    private static void addResolvedChoice(")
    if start >= 0:
        text = replace_method(text, "    private static void addResolvedChoice(", "")

    required = [
        "正在使用歌单原来源解析歌曲",
        "原来源不可用，才开始查找其他平台版本",
        "cacheFirstUsableAlternative",
        "MAX_FALLBACK_ATTEMPTS = 4",
        "if (attempted >= MAX_FALLBACK_ATTEMPTS) break;",
        "CacheResult result = cacheChoice(context, requestedCatalog, original, callback);",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("fast-path contract missing: " + ", ".join(missing))
    forbidden = [
        "findAutomaticChoices",
        "choices.sort",
        "正在比较其他平台的 MP3、FLAC 和其他格式版本",
        "MAX_AUTOMATIC_CHOICES",
    ]
    present = [item for item in forbidden if item in text]
    if present:
        raise RuntimeError("slow pre-resolution flow remains: " + ", ".join(present))
    NETWORK.write_text(text, encoding="utf-8")


def patch_checks() -> None:
    text = CHECKS.read_text(encoding="utf-8")
    old = '''    'multi-format priority and one-minute validation': (
        'MIN_AUTOMATIC_DURATION_MS = 60_000L' in network
        and 'choiceFormatRank' in network
        and 'if ("mp3".equals(extension)) return 0;' in network
        and 'if ("flac".equals(extension)) return 1;' in network
        and 'isAcceptableCachedAudio' in network
        and 'mediaDurationMs' in network
        and 'AudioTranscoder.ensureMp3' not in network
        and 'AudioMetadataWriter.applyAndVerify' not in network
    ),'''
    new = '''    'original-source fast path and one-minute validation': (
        'MIN_AUTOMATIC_DURATION_MS = 60_000L' in network
        and 'MAX_FALLBACK_ATTEMPTS = 4' in network
        and '正在使用歌单原来源解析歌曲' in network
        and '原来源不可用，才开始查找其他平台版本' in network
        and 'cacheFirstUsableAlternative' in network
        and 'findAutomaticChoices' not in network
        and 'choices.sort' not in network
        and 'isAcceptableCachedAudio' in network
        and 'mediaDurationMs' in network
        and 'AudioTranscoder.ensureMp3' not in network
        and 'AudioMetadataWriter.applyAndVerify' not in network
    ),'''
    text = replace_once(text, old, new, "feature check")
    text = text.replace(
        "    'version bumped': 'versionCode 2026080101' in gradle,",
        "    'version bumped': 'versionCode 2026080102' in gradle,",
    )
    CHECKS.write_text(text, encoding="utf-8")


def patch_version_and_logs() -> None:
    gradle = GRADLE.read_text(encoding="utf-8")
    gradle = re.sub(r"versionCode\s+\d+", "versionCode 2026080102", gradle, count=1)
    gradle = re.sub(
        r'versionName\s+"[^"]+"',
        'versionName "2026.08.01.original-source-fastpath"',
        gradle,
        count=1,
    )
    GRADLE.write_text(gradle, encoding="utf-8")

    project = PROJECT_LOG.read_text(encoding="utf-8")
    entry = '''\n## 2026-08-01 原来源快速播放修正\n\n- 修正歌曲匹配会在原来源可用时仍预先解析全部其他平台的问题。\n- 现在优先立即解析、下载并验证歌单保存的原来源；成功后直接播放，不调用跨平台搜索。\n- 原来源内部仍先请求 MP3，无法取得 MP3 时使用该来源返回的原始音频格式。\n- 只有原来源解析失败、下载失败、设备不可读或实际时长不足 60 秒时，才进入跨平台匹配。\n- 跨平台候选改为边解析边验证，首个合格资源立即返回，最多尝试 4 个，不再先解析全部候选再排序。\n'''
    if "原来源快速播放修正" not in project:
        PROJECT_LOG.write_text(project.rstrip() + "\n" + entry, encoding="utf-8")

    changelog = CHANGELOG.read_text(encoding="utf-8")
    entry_en = '''\n## 2026-08-01 Original-source playback fast path\n\n- Fixed the cache path resolving every cross-platform candidate even when the playlist's original source was valid.\n- The original source is now resolved, downloaded, validated, and returned immediately before any alternative search.\n- MP3 is still requested first within the original source; its source format is used when MP3 is unavailable.\n- Cross-platform matching runs only after an original-source resolve, download, readability, or 60-second validation failure.\n- Alternatives are resolved and validated one at a time, returning the first valid result, with at most four attempts.\n'''
    if "Original-source playback fast path" not in changelog:
        CHANGELOG.write_text(changelog.rstrip() + "\n" + entry_en, encoding="utf-8")


def main() -> None:
    patch_network()
    patch_checks()
    patch_version_and_logs()
    print("original_source_attempted_first=pass")
    print("cross_platform_search_only_after_failure=pass")
    print("fallback_attempt_limit=4")
    print("pre_resolve_all_candidates=disabled")


if __name__ == "__main__":
    main()
