from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
network_path = root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java'
cache_path = root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'


def read_preserve(path: Path) -> str:
    with path.open('r', encoding='utf-8', newline='') as stream:
        return stream.read()


def write_preserve(path: Path, text: str) -> None:
    with path.open('w', encoding='utf-8', newline='') as stream:
        stream.write(text)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 1:
        return text.replace(old, new, 1)
    pattern = r'\r?\n'.join(re.escape(part) for part in old.split('\n'))
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise SystemExit(f'{label}: expected one match, found {len(matches)}')
    match = matches[0]
    newline = '\r\n' if '\r\n' in match.group(0) else '\n'
    replacement = new.replace('\n', newline)
    return text[:match.start()] + replacement + text[match.end():]


def replace_section(text: str, start: str, end: str, replacement: str, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise SystemExit(f'{label}: start marker missing')
    end_index = text.find(end, start_index + len(start))
    if end_index < 0:
        raise SystemExit(f'{label}: end marker missing')
    newline = '\r\n' if '\r\n' in text[start_index:end_index] else '\n'
    return text[:start_index] + replacement.replace('\n', newline) + text[end_index:]


network = read_preserve(network_path)
network = replace_section(
    network,
    '    static CacheResult cache(Context context, String catalogJson, StatusCallback callback) throws Exception {',
    '    private static final class ResolvedAudioAddress {',
    '''    static CacheResult cache(Context context, String catalogJson, StatusCallback callback) throws Exception {
        if (context == null) throw new IllegalArgumentException("context is required");
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        if (requestedSource.isEmpty() || requestedId.isEmpty()) {
            throw new IllegalArgumentException("歌曲目录缺少来源或 ID");
        }

        String requestedKey = sha256(requestedSource + "|" + requestedId);
        String requestedTitle = catalogTitle(requestedCatalog);
        String requestedArtist = catalogArtist(requestedCatalog);
        String requestedAlbum = catalogAlbum(requestedCatalog);
        CacheStorage.ensureFriendlyNames(context, requestedKey, requestedTitle, requestedArtist,
            requestedAlbum, requestedCatalog.toString());

        String requestedAudioUri = CacheStorage.findAudioUri(context, requestedKey);
        String requestedLyric = CacheStorage.readLyric(context, requestedKey);
        if (!requestedAudioUri.isEmpty()
            && PlayableAudioResolver.cachedAudioExists(context, requestedAudioUri)) {
            boolean lyricFromCache = !requestedLyric.trim().isEmpty();
            if (!lyricFromCache) {
                status(callback, "正在按原平台读取歌词...");
                requestedLyric = fetchLyrics(requestedCatalog.toString());
                if (!requestedLyric.trim().isEmpty()) {
                    CacheStorage.writeLyric(context, requestedKey, requestedLyric,
                        requestedTitle, requestedArtist, requestedAlbum, requestedCatalog.toString());
                }
            }
            status(callback, "已读取并验证可播放的歌曲缓存");
            return new CacheResult(requestedAudioUri, requestedLyric, true, lyricFromCache,
                requestedCatalog.toString(), requestedSource, false);
        }
        if (!requestedAudioUri.isEmpty()) {
            CacheStorage.deleteKey(context, requestedKey);
            status(callback, "旧缓存无法播放，已删除并重新获取...");
        }

        PlayableAudioResolver.Result prepared =
            PlayableAudioResolver.prepare(context, requestedCatalog, callback);
        JSONObject actualCatalog = canonicalCatalog(prepared.catalogJson);
        String actualSource = actualCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String actualId = actualCatalog.optString("id", "").trim();
        boolean sourceChanged = !requestedSource.equals(actualSource) || !requestedId.equals(actualId);
        String actualKey = sha256(actualSource + "|" + actualId);
        String actualTitle = catalogTitle(actualCatalog);
        String actualArtist = catalogArtist(actualCatalog);
        String actualAlbum = catalogAlbum(actualCatalog);

        CacheStorage.ensureFriendlyNames(context, actualKey, actualTitle, actualArtist,
            actualAlbum, actualCatalog.toString());
        String lyric = CacheStorage.readLyric(context, actualKey);
        boolean lyricFromCache = !lyric.trim().isEmpty();
        if (!lyricFromCache) {
            status(callback, sourceChanged
                ? "正在从实际平台读取匹配歌词..." : "正在按原平台读取歌词...");
            lyric = fetchLyrics(actualCatalog.toString());
            if (!lyric.trim().isEmpty()) {
                CacheStorage.writeLyric(context, actualKey, lyric, actualTitle, actualArtist,
                    actualAlbum, actualCatalog.toString());
            }
        }
        status(callback, prepared.fromCache
            ? "已读取可播放缓存" : "歌曲已通过实际播放校验并完成缓存");
        return new CacheResult(prepared.audioUri, lyric, prepared.fromCache, lyricFromCache,
            actualCatalog.toString(), actualSource, sourceChanged);
    }

''',
    'network cache entry point',
)
network = replace_section(
    network,
    '    static boolean cachedAudioExists(Context context, String uriText) {',
    '    private static String catalogTitle(JSONObject catalog) {',
    '''    static boolean cachedAudioExists(Context context, String uriText) {
        return PlayableAudioResolver.cachedAudioExists(context, uriText);
    }

''',
    'cached playback verification',
)
write_preserve(network_path, network)

cache = read_preserve(cache_path)
cache = replace_once(
    cache,
    '''            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            if (existing != null) record.lyricFile = existing.lyricFile;
            String fileName = friendlyBaseForTree(context, tree, record, existing) + "." + safeExtension;
            removeDocumentsForKey(context, tree, key, false, true, false);
            Uri target = createOrReplaceDocument(context, tree, fileName, audioMime(safeExtension));''',
    '''            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            if (existing != null) record.lyricFile = existing.lyricFile;
            String baseName = friendlyBase(record);
            removeDocumentsForKey(context, tree, key, false, true, false);
            removeTreeAudioWithBase(context, tree, baseName);
            String fileName = baseName + "." + safeExtension;
            Uri target = createOrReplaceDocument(context, tree, fileName, audioMime(safeExtension));''',
    'tree deterministic audio name',
)
cache = replace_once(
    cache,
    '''        MetadataRecord existing = readMetadataFromInternal(root, key);
        if (existing != null) record.lyricFile = existing.lyricFile;
        String fileName = friendlyBaseForInternal(root, record, existing) + "." + safeExtension;
        removeInternalForKey(root, key, false, true, false);
        File target = new File(root, fileName);''',
    '''        MetadataRecord existing = readMetadataFromInternal(root, key);
        if (existing != null) record.lyricFile = existing.lyricFile;
        String baseName = friendlyBase(record);
        removeInternalForKey(root, key, false, true, false);
        removeInternalAudioWithBase(root, baseName);
        String fileName = baseName + "." + safeExtension;
        File target = new File(root, fileName);''',
    'internal deterministic audio name',
)
cache = replace_once(
    cache,
    '''    private static String friendlyBase(MetadataRecord record) {
        String base = record.title + " - " + record.artist;
        if (base.length() > 140) base = base.substring(0, 140).trim();
        return base;
    }
''',
    '''    private static String friendlyBase(MetadataRecord record) {
        String base = record.title + " - " + record.artist;
        if (base.length() > 140) base = base.substring(0, 140).trim();
        return base;
    }

    private static void removeInternalAudioWithBase(File root, String baseName) {
        File[] files = root == null ? null : root.listFiles();
        if (files == null) return;
        for (File file : files) {
            if (!file.isFile()) continue;
            String name = file.getName();
            if (isMetadataName(name) || isLyricName(name)
                || name.endsWith(".part") || name.endsWith(".move_part")) continue;
            if (fileBase(name).equalsIgnoreCase(baseName)) deleteFile(file);
        }
    }

    private static void removeTreeAudioWithBase(Context context, Uri tree,
                                                String baseName) throws Exception {
        for (DocumentEntry entry : listDocumentsStrict(context, tree, false)) {
            String name = entry.name;
            if (isMetadataName(name) || isLyricName(name)
                || name.endsWith(".part") || name.endsWith(".move_part")) continue;
            if (!fileBase(name).equalsIgnoreCase(baseName)) continue;
            try {
                DocumentsContract.deleteDocument(context.getContentResolver(), entry.uri);
            } catch (Exception ignored) {
            }
        }
    }
''',
    'cross-format replacement helpers',
)
cache = replace_once(
    cache,
    '''    private static String extensionOf(String name) {
        int dot = name == null ? -1 : name.lastIndexOf('.');
        return sanitizeExtension(dot < 0 ? "mp3" : name.substring(dot + 1));
    }

    private static String sanitizeExtension(String value) {
        String extension = value == null ? "" : value.toLowerCase(Locale.ROOT)
            .replaceAll("[^a-z0-9]", "");
        if (extension.equals("flac") || extension.equals("m4a") || extension.equals("aac")
            || extension.equals("ogg") || extension.equals("opus") || extension.equals("wav")
            || extension.equals("wma") || extension.equals("mp3") || extension.equals("webm")) {
            return extension;
        }
        return "mp3";
    }
''',
    '''    private static String extensionOf(String name) {
        int dot = name == null ? -1 : name.lastIndexOf('.');
        return sanitizeExtension(dot < 0 ? "audio" : name.substring(dot + 1));
    }

    private static String sanitizeExtension(String value) {
        String extension = value == null ? "" : value.toLowerCase(Locale.ROOT)
            .replaceAll("[^a-z0-9]", "");
        if (extension.isEmpty()) return "audio";
        return extension.length() > 12 ? extension.substring(0, 12) : extension;
    }
''',
    'unrestricted safe extensions',
)
cache = replace_once(
    cache,
    '''    private static String audioMime(String extension) {
        if ("flac".equals(extension)) return "audio/flac";
        if ("m4a".equals(extension) || "aac".equals(extension) || "mp4".equals(extension)) return "audio/mp4";
        if ("ogg".equals(extension) || "opus".equals(extension)) return "audio/ogg";
        if ("wav".equals(extension)) return "audio/wav";
        if ("webm".equals(extension)) return "audio/webm";
        return "audio/mpeg";
    }
''',
    '''    private static String audioMime(String extension) {
        if ("mp3".equals(extension)) return "audio/mpeg";
        if ("flac".equals(extension)) return "audio/flac";
        if ("m4a".equals(extension) || "mp4".equals(extension)) return "audio/mp4";
        if ("aac".equals(extension)) return "audio/aac";
        if ("ogg".equals(extension)) return "audio/ogg";
        if ("opus".equals(extension)) return "audio/opus";
        if ("wav".equals(extension)) return "audio/wav";
        if ("webm".equals(extension)) return "audio/webm";
        if ("amr".equals(extension)) return "audio/amr";
        if ("aiff".equals(extension) || "aif".equals(extension)) return "audio/aiff";
        if ("mid".equals(extension) || "midi".equals(extension)) return "audio/midi";
        if ("wma".equals(extension)) return "audio/x-ms-wma";
        if ("ac3".equals(extension)) return "audio/ac3";
        if ("eac3".equals(extension)) return "audio/eac3";
        return "application/octet-stream";
    }
''',
    'generic audio MIME types',
)
write_preserve(cache_path, cache)

gradle = gradle_path.read_text(encoding='utf-8')
gradle = replace_once(gradle, 'versionCode 2026080130', 'versionCode 2026080131', 'version code')
gradle = replace_once(
    gradle,
    'versionName "2026.08.03.dialog-confirm-labels"',
    'versionName "2026.08.03.playable-format-priority"',
    'version name',
)
gradle_path.write_text(gradle, encoding='utf-8')

check = check_path.read_text(encoding='utf-8')
check = replace_once(
    check,
    "catalog = (root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java').read_text(encoding='utf-8')",
    "catalog = (root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java').read_text(encoding='utf-8')\n"
    "playable_resolver = (root / 'app/src/main/java/com/jianglab/babywife/PlayableAudioResolver.java').read_text(encoding='utf-8')\n"
    "playback_verifier = (root / 'app/src/main/java/com/jianglab/babywife/AudioPlaybackVerifier.java').read_text(encoding='utf-8')",
    'verification source reads',
)
check = replace_once(
    check,
    '''    'm4a network source accepted': (
        '"m4a".equals(extension)' in network
        and 'detectAudioExtension' in network
        and 'audio/mp4' in cache
    ),''',
    '''    'all formats require real playback verification': (
        'PlayableAudioResolver.prepare' in network
        and 'PlayableAudioResolver.cachedAudioExists' in network
        and 'REQUEST_FORMATS = {"mp3", "flac", "m4a", ""}' in playable_resolver
        and 'formatPriority' in playable_resolver
        and 'MP3＞FLAC＞M4A＞其他' in playable_resolver
        and 'AudioPlaybackVerifier.probeFile' in playable_resolver
        and 'AudioPlaybackVerifier.isPlayableUri' in playable_resolver
        and 'MediaExtractor' in playback_verifier
        and 'MediaPlayer' in playback_verifier
        and 'playableCachedExtension' not in network
    ),
    'consistent filenames across formats': (
        'String baseName = friendlyBase(record);' in cache
        and 'removeInternalAudioWithBase' in cache
        and 'removeTreeAudioWithBase' in cache
        and 'String fileName = baseName + "." + safeExtension;' in cache
        and 'return "mp3";' not in cache[cache.find('private static String sanitizeExtension'):cache.find('private static String safeNamePart')]
    ),''',
    'format and filename checks',
)
check = replace_once(check, "'versionCode 2026080130' in gradle", "'versionCode 2026080131' in gradle", 'version check')
check_path.write_text(check, encoding='utf-8')

with (root / 'docs/CHANGELOG.md').open('a', encoding='utf-8') as output:
    output.write('\n- v131: remove the fixed format allowlist. Resolve candidates in MP3 > FLAC > M4A > other order, but only cache a candidate after Android MediaExtractor and MediaPlayer both verify it. Failed candidates are discarded and the next format/source is tried automatically.\n')
    output.write('- v131: every final audio file uses the same `歌曲名 - 歌手.真实扩展名` rule. A newly selected format replaces older same-name formats instead of creating hash or numbered duplicates.\n')
with (root / 'PROJECT_LOG.md').open('a', encoding='utf-8') as output:
    output.write('\n- v131 accepts any format that the current Android device can actually prepare for playback. Acquisition priority is MP3 > FLAC > M4A > other; unplayable downloads are deleted before becoming cache files.\n')
    output.write('- v131 enforces one consistent cache basename (`title - artist`) across formats and removes older same-basename audio when the chosen format changes.\n')

print('Applied v131 playable-format priority patch')
