from pathlib import Path

root = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'Cannot find {label} in {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def append_once(path: Path, marker: str, block: str) -> None:
    text = path.read_text(encoding='utf-8')
    if marker in text:
        return
    path.write_text(text.rstrip() + '\n\n' + block.rstrip() + '\n', encoding='utf-8')

main = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
cache = root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java'
network = root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java'
resolver = root / 'app/src/main/java/com/jianglab/babywife/PlayableAudioResolver.java'
gradle = root / 'app/build.gradle'
checks = root / 'scripts/check_feature_requirements.py'
project_log = root / 'PROJECT_LOG.md'
changelog = root / 'docs/CHANGELOG.md'

replace_once(
    gradle,
    'versionCode 2026080133\n        versionName "2026.08.03.full-cache-folder-migration"',
    'versionCode 2026080134\n        versionName "2026.08.04.single-cache-search-flow"',
    'v134 version',
)

replace_once(
    cache,
    'import java.security.MessageDigest;\n',
    'import java.security.MessageDigest;\nimport java.text.Normalizer;\n',
    'Normalizer import',
)

replace_once(
    cache,
    '''    static final class MigrationResult {
        final int copied;
        final int removedFromOldLocation;
        final int retainedInOldLocation;
        final boolean changed;

        MigrationResult(int copied, int removedFromOldLocation, boolean changed) {
            this.copied = copied;
            this.removedFromOldLocation = removedFromOldLocation;
            this.retainedInOldLocation = Math.max(0, copied - removedFromOldLocation);
            this.changed = changed;
        }
    }
''',
    '''    static final class MigrationResult {
        final int copied;
        final int removedFromOldLocation;
        final int retainedInOldLocation;
        final boolean changed;

        MigrationResult(int copied, int removedFromOldLocation, boolean changed) {
            this.copied = copied;
            this.removedFromOldLocation = removedFromOldLocation;
            this.retainedInOldLocation = Math.max(0, copied - removedFromOldLocation);
            this.changed = changed;
        }
    }

    static final class AudioMatch {
        final String key;
        final String audioUri;
        final String catalogJson;

        AudioMatch(String key, String audioUri, String catalogJson) {
            this.key = key == null ? "" : key;
            this.audioUri = audioUri == null ? "" : audioUri;
            this.catalogJson = catalogJson == null ? "" : catalogJson;
        }
    }
''',
    'AudioMatch class',
)

insert_before_read_lyric = '''    static List<AudioMatch> findAudioMatches(Context context, String title, String artist) {
        List<AudioMatch> matches = new ArrayList<>();
        if (context == null) return matches;
        String wanted = logicalIdentity(title, artist);
        if (wanted.isEmpty()) return matches;
        Set<String> keys = metadataKeys(context);
        for (String key : keys) {
            MetadataRecord record = metadataRecord(context, key);
            if (record == null || !wanted.equals(logicalIdentity(record.title, record.artist))) continue;
            String uri = findAudioUri(context, key);
            if (!uri.isEmpty()) matches.add(new AudioMatch(key, uri, record.catalogJson));
        }
        return matches;
    }

    static int deleteOtherSongCaches(Context context, String title, String artist, String keepKey) {
        if (context == null) return 0;
        String wanted = logicalIdentity(title, artist);
        if (wanted.isEmpty()) return 0;
        List<String> remove = new ArrayList<>();
        for (String key : metadataKeys(context)) {
            if (key.equalsIgnoreCase(keepKey == null ? "" : keepKey)) continue;
            MetadataRecord record = metadataRecord(context, key);
            if (record != null && wanted.equals(logicalIdentity(record.title, record.artist))) {
                remove.add(key);
            }
        }
        int removed = 0;
        for (String key : remove) removed += deleteKey(context, key);
        return removed;
    }

    static String logicalIdentity(String title, String artist) {
        String normalizedTitle = normalizeIdentityPart(title);
        String normalizedArtist = normalizeIdentityPart(artist);
        if (normalizedTitle.isEmpty() || normalizedArtist.isEmpty()) return "";
        return normalizedTitle + "|" + normalizedArtist;
    }

    private static String normalizeIdentityPart(String value) {
        String raw = value == null ? "" : Normalizer.normalize(value, Normalizer.Form.NFKC)
            .toLowerCase(Locale.ROOT);
        StringBuilder normalized = new StringBuilder(raw.length());
        for (int offset = 0; offset < raw.length();) {
            int codePoint = raw.codePointAt(offset);
            if (Character.isLetterOrDigit(codePoint)) normalized.appendCodePoint(codePoint);
            offset += Character.charCount(codePoint);
        }
        return normalized.toString();
    }

    private static Set<String> metadataKeys(Context context) {
        Set<String> keys = new HashSet<>();
        Uri tree = selectedTree(context);
        if (tree != null) {
            try {
                for (DocumentEntry entry : listDocumentsStrict(context, tree, true)) {
                    String key = metadataKey(entry.name);
                    if (validKey(key)) keys.add(key);
                }
            } catch (Exception ignored) {
            }
        }
        File[] files = internalRoot(context).listFiles();
        if (files != null) {
            for (File file : files) {
                if (!file.isFile()) continue;
                String key = metadataKey(file.getName());
                if (validKey(key)) keys.add(key);
            }
        }
        return keys;
    }

    private static MetadataRecord metadataRecord(Context context, String key) {
        Uri tree = selectedTree(context);
        if (tree != null) {
            MetadataRecord record = readMetadataFromTree(context, tree, key);
            if (record != null) return record;
        }
        return readMetadataFromInternal(internalRoot(context), key);
    }

'''
replace_once(
    cache,
    '    static String readLyric(Context context, String key) {',
    insert_before_read_lyric + '    static String readLyric(Context context, String key) {',
    'logical cache lookup methods',
)

# NetworkMediaCache: serialize same-song requests and use logical cache identity before any network lookup.
replace_once(
    network,
    '    private static final long MAX_AUDIO_BYTES = 512L * 1024L * 1024L;\n',
    '    private static final long MAX_AUDIO_BYTES = 512L * 1024L * 1024L;\n'
    '    private static final Object[] CACHE_LOCKS = createCacheLocks();\n',
    'cache lock field',
)

old_cache_start = '''    static CacheResult cache(Context context, String catalogJson, StatusCallback callback) throws Exception {
        if (context == null) throw new IllegalArgumentException("context is required");
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
'''
new_cache_start = '''    static CacheResult cache(Context context, String catalogJson, StatusCallback callback) throws Exception {
        if (context == null) throw new IllegalArgumentException("context is required");
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
        String identity = CacheStorage.logicalIdentity(catalogTitle(requestedCatalog), catalogArtist(requestedCatalog));
        Object lock = CACHE_LOCKS[Math.floorMod(identity.hashCode(), CACHE_LOCKS.length)];
        synchronized (lock) {
            return cacheLocked(context, requestedCatalog, callback);
        }
    }

    private static CacheResult cacheLocked(Context context, JSONObject requestedCatalog,
                                           StatusCallback callback) throws Exception {
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
'''
replace_once(network, old_cache_start, new_cache_start, 'serialized cache entry')

old_requested_lookup = '''        String requestedKey = sha256(requestedSource + "|" + requestedId);
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
'''
new_requested_lookup = '''        String requestedKey = sha256(requestedSource + "|" + requestedId);
        String requestedTitle = catalogTitle(requestedCatalog);
        String requestedArtist = catalogArtist(requestedCatalog);
        String requestedAlbum = catalogAlbum(requestedCatalog);

        status(callback, "正在检查这首歌是否已有可播放缓存...");
        for (CacheStorage.AudioMatch match :
            CacheStorage.findAudioMatches(context, requestedTitle, requestedArtist)) {
            if (!PlayableAudioResolver.cachedAudioExists(context, match.audioUri)) {
                CacheStorage.deleteKey(context, match.key);
                continue;
            }
            JSONObject matchedCatalog;
            try {
                matchedCatalog = canonicalCatalog(match.catalogJson);
            } catch (Exception ignored) {
                matchedCatalog = requestedCatalog;
            }
            String matchedSource = matchedCatalog.optString("source", "")
                .trim().toLowerCase(Locale.ROOT);
            String matchedId = matchedCatalog.optString("id", "").trim();
            if (matchedSource.isEmpty() || matchedId.isEmpty()) {
                matchedCatalog = requestedCatalog;
                matchedSource = requestedSource;
                matchedId = requestedId;
            }
            String lyric = CacheStorage.readLyric(context, match.key);
            boolean lyricFromCache = !lyric.trim().isEmpty();
            if (!lyricFromCache) {
                status(callback, "已有音频缓存，正在补充歌词...");
                lyric = fetchLyrics(matchedCatalog.toString());
                if (!lyric.trim().isEmpty()) {
                    CacheStorage.writeLyric(context, match.key, lyric,
                        requestedTitle, requestedArtist, requestedAlbum, matchedCatalog.toString());
                }
            }
            CacheStorage.deleteOtherSongCaches(context, requestedTitle, requestedArtist, match.key);
            boolean sourceChanged = !requestedSource.equals(matchedSource)
                || !requestedId.equals(matchedId);
            status(callback, "已找到同歌名和歌手的现有缓存，直接播放");
            return new CacheResult(match.audioUri, lyric, true, lyricFromCache,
                matchedCatalog.toString(), matchedSource, sourceChanged);
        }

        CacheStorage.ensureFriendlyNames(context, requestedKey, requestedTitle, requestedArtist,
            requestedAlbum, requestedCatalog.toString());
        String requestedAudioUri = CacheStorage.findAudioUri(context, requestedKey);
        if (!requestedAudioUri.isEmpty()) {
            if (PlayableAudioResolver.cachedAudioExists(context, requestedAudioUri)) {
                String requestedLyric = CacheStorage.readLyric(context, requestedKey);
                boolean lyricFromCache = !requestedLyric.trim().isEmpty();
                status(callback, "已找到原来源缓存，直接播放");
                return new CacheResult(requestedAudioUri, requestedLyric, true, lyricFromCache,
                    requestedCatalog.toString(), requestedSource, false);
            }
            CacheStorage.deleteKey(context, requestedKey);
            status(callback, "原有缓存不可播放，已清理；开始寻找唯一可用版本...");
        }
'''
replace_once(network, old_requested_lookup, new_requested_lookup, 'logical cache lookup')

old_final_return = '''        status(callback, prepared.fromCache
            ? "已读取可播放缓存" : "歌曲已通过实际播放校验并完成缓存");
        return new CacheResult(prepared.audioUri, lyric, prepared.fromCache, lyricFromCache,
            actualCatalog.toString(), actualSource, sourceChanged);
    }
'''
new_final_return = '''        CacheStorage.deleteOtherSongCaches(context, requestedTitle, requestedArtist, actualKey);
        if (!CacheStorage.logicalIdentity(requestedTitle, requestedArtist).equals(
            CacheStorage.logicalIdentity(actualTitle, actualArtist))) {
            CacheStorage.deleteOtherSongCaches(context, actualTitle, actualArtist, actualKey);
        }
        status(callback, prepared.fromCache
            ? "已读取唯一可播放缓存" : "唯一正式缓存已完成，其他来源候选已清理");
        return new CacheResult(prepared.audioUri, lyric, prepared.fromCache, lyricFromCache,
            actualCatalog.toString(), actualSource, sourceChanged);
    }

    private static Object[] createCacheLocks() {
        Object[] locks = new Object[32];
        for (int index = 0; index < locks.length; index++) locks[index] = new Object();
        return locks;
    }
'''
replace_once(network, old_final_return, new_final_return, 'deduplicate final cache')

# Resolver: all source/format files remain temporary until one final winner is written.
old_candidate_existing = '''                    String key = sha256(source + "|" + id);
                    String title = title(catalog);
                    String artist = artist(catalog);
                    String album = album(catalog);
                    CacheStorage.ensureFriendlyNames(context, key, title, artist, album,
                        catalog.toString());

                    String existing = CacheStorage.findAudioUri(context, key);
                    if (!existing.isEmpty()) {
                        if (cachedAudioExists(context, existing)) {
                            return new Result(catalog.toString(), existing, true);
                        }
                        CacheStorage.deleteKey(context, key);
                    }

                    JSONObject resolved;
'''
new_candidate_existing = '''                    JSONObject resolved;
'''
replace_once(resolver, old_candidate_existing, new_candidate_existing, 'remove source-key cache shortcut')

replace_once(
    resolver,
    '                        status(callback, "正在获取" + CatalogSearch.labelForSource(source)\n'
    '                            + "的 " + formatLabel + " 候选...");',
    '                        status(callback, "正在下载候选：" + CatalogSearch.labelForSource(source)\n'
    '                            + " / " + formatLabel + "（尚未写入正式缓存）");',
    'candidate download status',
)
replace_once(
    resolver,
    '                        status(callback, "已验证可播放：" + displayFormat(actualExtension)\n'
    '                            + "（" + Math.max(0L, probe.durationMs / 1000L) + " 秒）");',
    '                        status(callback, "候选可播放：" + displayFormat(actualExtension)\n'
    '                            + "（" + Math.max(0L, probe.durationMs / 1000L) + " 秒），继续比较优先级");',
    'candidate verification status',
)
replace_once(
    resolver,
    '                        status(callback, "该候选无法播放，继续尝试下一格式或来源");',
    '                        status(callback, "候选不可播放，临时文件已删除；继续下一格式或来源");',
    'candidate failure status',
)
replace_once(
    resolver,
    '                            status(callback, "正在缓存歌曲：" + percent + "%");',
    '                            status(callback, "候选下载进度：" + percent + "%");',
    'candidate progress status',
)

old_final_metadata = '''            JSONObject catalog = canonicalCatalog(best.catalog.toString());
            String source = source(catalog);
            String id = catalog.optString("id", "").trim();
            String key = sha256(source + "|" + id);
            String title = title(catalog);
            String artist = artist(catalog);
            String album = album(catalog);
            File cacheSource = bestFile;

            if ("mp3".equals(best.extension)) {
                AudioTranscoder.ensureMp3(bestFile, mp3Ready);
                AudioMetadataWriter.applyAndVerify(mp3Ready, title, artist, album);
'''
new_final_metadata = '''            JSONObject catalog = canonicalCatalog(best.catalog.toString());
            String source = source(catalog);
            String id = catalog.optString("id", "").trim();
            String key = sha256(source + "|" + id);
            String title = title(requestedCatalog);
            String artist = artist(requestedCatalog);
            String album = firstNonEmpty(album(requestedCatalog), album(catalog));
            File cacheSource = bestFile;

            if ("mp3".equals(best.extension)) {
                AudioTranscoder.ensureMp3(bestFile, mp3Ready);
                AudioMetadataWriter.applyAndVerify(mp3Ready, title, artist, album);
'''
replace_once(resolver, old_final_metadata, new_final_metadata, 'requested identity for final cache')

replace_once(
    resolver,
    '            status(callback, "最终采用 " + displayFormat(best.extension)\n'
    '                + "，获取优先级为 MP3＞FLAC＞M4A＞其他");',
    '            status(callback, "已选定 " + displayFormat(best.extension)\n'
    '                + "，正在写入唯一正式缓存；优先级 MP3＞FLAC＞M4A＞其他");',
    'final store status',
)
replace_once(
    resolver,
    '            return new Result(catalog.toString(), storedUri, false);',
    '            status(callback, "唯一正式缓存写入完成，所有临时候选已清理");\n'
    '            return new Result(catalog.toString(), storedUri, false);',
    'final completion status',
)

# MainActivity: cancelled play requests must stop their old network candidate work.
replace_once(
    main,
    '        statusView.setText("正在缓存歌曲并匹配歌词...");',
    '        statusView.setText("正在检查已有缓存...");',
    'initial cache status',
)
old_callback = '''                    message -> runOnUiThread(() -> {
                        if (currentSong == song && playToken == playbackRequestSerial) statusView.setText(message);
                    })
'''
new_callback = '''                    message -> {
                        if (currentSong != song || playToken != playbackRequestSerial) {
                            throw new IllegalStateException("播放请求已切换，停止旧候选下载");
                        }
                        runOnUiThread(() -> {
                            if (currentSong == song && playToken == playbackRequestSerial) {
                                statusView.setText(message);
                            }
                        });
                    }
'''
replace_once(main, old_callback, new_callback, 'cancel stale candidate download')

# Static checks.
replace_once(
    checks,
    "    'version bumped': 'versionCode 2026080133' in gradle,",
    "    'single logical cache per song and clear search flow': (\n"
    "        'static final class AudioMatch' in cache\n"
    "        and 'logicalIdentity(String title, String artist)' in cache\n"
    "        and 'findAudioMatches(Context context, String title, String artist)' in cache\n"
    "        and 'deleteOtherSongCaches' in cache\n"
    "        and 'CACHE_LOCKS = createCacheLocks()' in network\n"
    "        and 'cacheLocked(context, requestedCatalog, callback)' in network\n"
    "        and '已找到同歌名和歌手的现有缓存，直接播放' in network\n"
    "        and '唯一正式缓存已完成，其他来源候选已清理' in network\n"
    "        and '尚未写入正式缓存' in playable_resolver\n"
    "        and '候选下载进度' in playable_resolver\n"
    "        and '唯一正式缓存写入完成' in playable_resolver\n"
    "        and 'CacheStorage.findAudioUri(context, key)' not in playable_resolver[playable_resolver.find('for (JSONObject catalog : catalogs)'):playable_resolver.find('if (best == null')]\n"
    "        and '播放请求已切换，停止旧候选下载' in main\n"
    "    ),\n"
    "    'version bumped': 'versionCode 2026080134' in gradle,",
    'v134 checks',
)

append_once(
    project_log,
    'Single logical cache per song and deterministic search flow',
    '''## 2026-08-04 - Single logical cache per song and deterministic search flow

- Cache reuse is now keyed first by normalized song title and artist, not only by source platform and catalog ID.
- Same-song playback/cache requests are serialized to stop repeated taps from downloading multiple source candidates concurrently.
- Source and format downloads remain temporary candidates until one final playable winner is selected.
- Only the winner is written to the user cache folder; other same-song source caches and temporary candidates are removed.
- Status text now distinguishes candidate download, candidate verification, final selection, and final cache completion.''',
)
append_once(
    changelog,
    'single-cache-search-flow',
    '''## 2026.08.04.single-cache-search-flow

- Fixed playlist tracks searching again even when the same title and artist already had a playable cache from another source.
- Prevented concurrent duplicate downloads for the same song.
- Candidate FLAC/MP3/M4A files stay in the app temporary directory and are deleted after comparison.
- The selected winner is the only formal cache; duplicate same-song source caches are cleaned.
- Reworded progress messages so a downloaded candidate is never reported as a completed cache.''',
)

print('v134 single-cache search flow patch applied')
