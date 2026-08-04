from pathlib import Path

root = Path(__file__).resolve().parents[1]
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
cache_path = root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java'
network_path = root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'
project_log_path = root / 'PROJECT_LOG.md'
changelog_path = root / 'docs/CHANGELOG.md'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'v140 patch target missing: {label}')
    return text.replace(old, new, 1)


main = main_path.read_text(encoding='utf-8')
cache = cache_path.read_text(encoding='utf-8')
network = network_path.read_text(encoding='utf-8')
gradle = gradle_path.read_text(encoding='utf-8')
check = check_path.read_text(encoding='utf-8')
project_log = project_log_path.read_text(encoding='utf-8')
changelog = changelog_path.read_text(encoding='utf-8')

# Version.
gradle = replace_once(
    gradle,
    'versionCode 2026080139\n        versionName "2026.08.04.complete-search-song-actions"',
    'versionCode 2026080140\n        versionName "2026.08.04.stable-local-lyric-cache"',
    'version bump',
)

# CacheStorage: persistent lightweight identity -> exact lyric key index.
cache = replace_once(
    cache,
    'private static final String PREFS = "cache_storage";\n    private static final String KEY_TREE_URI = "tree_uri";',
    'private static final String PREFS = "cache_storage";\n    private static final String LYRIC_INDEX_PREFS = "lyric_cache_index";\n    private static final String LYRIC_INDEX_PREFIX = "song|";\n    private static final String KEY_TREE_URI = "tree_uri";',
    'lyric index constants',
)

cache = replace_once(
    cache,
    '''    static int deleteOtherSongCaches(Context context, String title, String artist, String keepKey) {
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
''',
    '''    static int deleteOtherSongCaches(Context context, String title, String artist, String keepKey) {
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

        String preservedLyric = validKey(keepKey) ? readLyric(context, keepKey) : "";
        if (preservedLyric.trim().isEmpty() && validKey(keepKey)) {
            for (String oldKey : remove) {
                String oldLyric = readLyric(context, oldKey);
                if (oldLyric.trim().isEmpty()) continue;
                MetadataRecord keepRecord = metadataRecord(context, keepKey);
                String keepTitle = keepRecord == null ? title : keepRecord.title;
                String keepArtist = keepRecord == null ? artist : keepRecord.artist;
                String keepAlbum = keepRecord == null ? "" : keepRecord.album;
                String keepCatalog = keepRecord == null ? "" : keepRecord.catalogJson;
                try {
                    writeLyric(context, keepKey, oldLyric, keepTitle, keepArtist,
                        keepAlbum, keepCatalog);
                    preservedLyric = oldLyric;
                } catch (Exception ignored) {
                }
                break;
            }
        }
        if (!preservedLyric.trim().isEmpty() && validKey(keepKey)) {
            rememberLyricKey(context, title, artist, keepKey);
        }

        int removed = 0;
        for (String key : remove) removed += deleteKey(context, key);
        return removed;
    }
''',
    'preserve lyric before duplicate cache cleanup',
)

cache = replace_once(
    cache,
    '''    static String logicalIdentity(String title, String artist) {
        String normalizedTitle = normalizeIdentityPart(title);
        String normalizedArtist = normalizeIdentityPart(artist);
        if (normalizedTitle.isEmpty() || normalizedArtist.isEmpty()) return "";
        return normalizedTitle + "|" + normalizedArtist;
    }
''',
    '''    static String logicalIdentity(String title, String artist) {
        String normalizedTitle = normalizeIdentityPart(title);
        String normalizedArtist = normalizeIdentityPart(artist);
        if (normalizedTitle.isEmpty() || normalizedArtist.isEmpty()) return "";
        return normalizedTitle + "|" + normalizedArtist;
    }

    private static String lyricIndexEntry(String title, String artist) {
        String identity = logicalIdentity(title, artist);
        return identity.isEmpty() ? "" : LYRIC_INDEX_PREFIX + identity;
    }

    private static void rememberLyricKey(Context context, String title, String artist, String key) {
        if (context == null || !validKey(key)) return;
        String entry = lyricIndexEntry(title, artist);
        if (entry.isEmpty()) return;
        context.getSharedPreferences(LYRIC_INDEX_PREFS, Context.MODE_PRIVATE)
            .edit().putString(entry, key.toLowerCase(Locale.ROOT)).apply();
    }

    private static String indexedLyricKey(Context context, String title, String artist) {
        if (context == null) return "";
        String entry = lyricIndexEntry(title, artist);
        if (entry.isEmpty()) return "";
        String key = context.getSharedPreferences(LYRIC_INDEX_PREFS, Context.MODE_PRIVATE)
            .getString(entry, "");
        return validKey(key) ? key : "";
    }
''',
    'lyric identity index helpers',
)

cache = replace_once(
    cache,
    '''                        MetadataRecord record = readMetadataFromTree(context, tree, key);
                        if (record == null) continue;
                        ensureFriendlyNames(context, key, record.title, record.artist,
                            record.album, record.catalogJson);
''',
    '''                        MetadataRecord record = readMetadataFromTree(context, tree, key);
                        if (record == null) continue;
                        if (!record.lyricFile.isEmpty()) {
                            rememberLyricKey(context, record.title, record.artist, key);
                        }
                        ensureFriendlyNames(context, key, record.title, record.artist,
                            record.album, record.catalogJson);
''',
    'rebuild external lyric index',
)

cache = replace_once(
    cache,
    '''                MetadataRecord record = readMetadataFromInternal(root, key);
                if (record == null) continue;
                ensureFriendlyNames(context, key, record.title, record.artist,
                    record.album, record.catalogJson);
''',
    '''                MetadataRecord record = readMetadataFromInternal(root, key);
                if (record == null) continue;
                if (!record.lyricFile.isEmpty()) {
                    rememberLyricKey(context, record.title, record.artist, key);
                }
                ensureFriendlyNames(context, key, record.title, record.artist,
                    record.album, record.catalogJson);
''',
    'rebuild internal lyric index',
)

cache = replace_once(
    cache,
    '''    static void writeLyric(Context context, String key, String text, String title, String artist,
                           String album, String catalogJson) throws Exception {
''',
    '''    static String readLyricForSong(Context context, String preferredKey,
                                         String title, String artist) {
        String direct = readLyric(context, preferredKey);
        if (!direct.trim().isEmpty()) {
            rememberLyricKey(context, title, artist, preferredKey);
            return direct;
        }
        String indexedKey = indexedLyricKey(context, title, artist);
        if (indexedKey.isEmpty() || indexedKey.equalsIgnoreCase(preferredKey)) return "";
        String fallback = readLyric(context, indexedKey);
        if (fallback.trim().isEmpty()) return "";

        MetadataRecord preferred = metadataRecord(context, preferredKey);
        if (preferred != null && validKey(preferredKey)) {
            try {
                writeLyric(context, preferredKey, fallback, preferred.title, preferred.artist,
                    preferred.album, preferred.catalogJson);
            } catch (Exception ignored) {
            }
        }
        return fallback;
    }

    static void writeLyric(Context context, String key, String text, String title, String artist,
                           String album, String catalogJson) throws Exception {
''',
    'identity lyric read method',
)

cache = replace_once(
    cache,
    '''            record.lyricFile = name;
            writeMetadataToTree(context, tree, record);
            return;
''',
    '''            record.lyricFile = name;
            writeMetadataToTree(context, tree, record);
            rememberLyricKey(context, record.title, record.artist, key);
            return;
''',
    'remember external lyric key',
)

cache = replace_once(
    cache,
    '''        record.lyricFile = name;
        writeMetadataToInternal(root, record);
    }

    static String storeAudio''',
    '''        record.lyricFile = name;
        writeMetadataToInternal(root, record);
        rememberLyricKey(context, record.title, record.artist, key);
    }

    static String storeAudio''',
    'remember internal lyric key',
)

# Network cache reads lyrics by song identity, then migrates to the actual source key.
network = replace_once(
    network,
    '''        String lyric = CacheStorage.readLyric(context, actualKey);
        boolean lyricFromCache = !lyric.trim().isEmpty();
''',
    '''        String lyric = CacheStorage.readLyricForSong(context, actualKey,
            actualTitle, actualArtist);
        boolean lyricFromCache = !lyric.trim().isEmpty();
''',
    'network identity lyric lookup',
)

# Main player: never start lyric matching before source commit/playback.
main = replace_once(
    main,
    '''                    artistView.setText(song.artist + " · " + song.source);
                    showSongLyrics(song);
                    startLocalPlayback(song, playToken,
''',
    '''                    artistView.setText(song.artist + " · " + song.source);
                    startLocalPlayback(song, playToken,
''',
    'remove pre-play lyric matching',
)

main = replace_once(
    main,
    '''                    stopPlayback();
                    playButton.setText("▶");
                    showSongLyrics(song);
                    markPlaybackFailure(song, false);
''',
    '''                    stopPlayback();
                    playButton.setText("▶");
                    lyricView.setText("音频未开始播放，未启动在线歌词匹配");
                    markPlaybackFailure(song, false);
''',
    'do not match lyrics after audio cache failure',
)

main = replace_once(
    main,
    '''        statusView.setText("当前播放：" + song.title);
        if (song.isNetworkCatalog()) showSongLyrics(song);
        if (onStarted != null) onStarted.run();
        publishPlaybackControlState(true);
''',
    '''        statusView.setText("当前播放：" + song.title);
        if (onStarted != null) onStarted.run();
        if (song.isNetworkCatalog()) showSongLyrics(song);
        publishPlaybackControlState(true);
''',
    'commit source before lyric lookup',
)

main = replace_once(
    main,
    '''        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        if (key.isEmpty()) return;
        String cachedLyric = CacheStorage.readLyric(this, key);
''',
    '''        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        if (key.isEmpty()) return;
        String cachedLyric = CacheStorage.readLyricForSong(this, key, song.title, song.artist);
''',
    'main identity lyric lookup',
)

# Feature checks.
check = replace_once(
    check,
    '''    'version bumped': 'versionCode 2026080139' in gradle,
''',
    '''    'stable local lyric cache across source changes': (
        'LYRIC_INDEX_PREFS = "lyric_cache_index"' in cache
        and 'readLyricForSong(Context context, String preferredKey' in cache
        and 'rememberLyricKey(context, record.title, record.artist, key);' in cache
        and 'writeLyric(context, keepKey, oldLyric' in cache
        and 'CacheStorage.readLyricForSong(context, actualKey' in network
        and 'CacheStorage.readLyricForSong(this, key, song.title, song.artist)' in main
        and main.find('if (onStarted != null) onStarted.run();')
            < main.find('if (song.isNetworkCatalog()) showSongLyrics(song);',
                main.find('private void onPlaybackStarted'))
        and 'artistView.setText(song.artist + " · " + song.source);\n                    showSongLyrics(song);\n                    startLocalPlayback' not in main
        and '音频未开始播放，未启动在线歌词匹配' in main
    ),
    'version bumped': 'versionCode 2026080140' in gradle,
''',
    'v140 feature checks',
)

project_log += '''

## 2026-08-04 - Restore stable local lyric cache reads

- Removed the remaining pre-playback lyric matching call from the audio cache completion path.
- Playback now commits the resolved source/catalog before reading local lyrics or starting online matching.
- Added a lightweight title+artist lyric-key index so source fallback does not orphan an existing local LRC.
- Duplicate source cache cleanup migrates an existing lyric to the retained source key before deleting old files.
- Startup cache normalization rebuilds the lyric-key index for previously saved LRC files.
'''

changelog += '''

## 2026.08.04.stable-local-lyric-cache

- Fixed cached lyrics being ignored after a song switched to another source.
- Local lyric cache is now resolved by stable song identity as well as exact source ID.
- Existing lyrics are migrated to the retained source before duplicate cache cleanup.
- Online lyric matching starts only after audio playback and resolved-source commit.
'''

main_path.write_text(main, encoding='utf-8')
cache_path.write_text(cache, encoding='utf-8')
network_path.write_text(network, encoding='utf-8')
gradle_path.write_text(gradle, encoding='utf-8')
check_path.write_text(check, encoding='utf-8')
project_log_path.write_text(project_log, encoding='utf-8')
changelog_path.write_text(changelog, encoding='utf-8')

print('Applied v140 stable local lyric cache repair')
