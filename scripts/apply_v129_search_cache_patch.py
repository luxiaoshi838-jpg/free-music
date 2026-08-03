from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
cache_path = root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java'
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
catalog_path = root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) == 1:
        return text.replace(old, new, 1)
    pattern = r'\r?\n'.join(re.escape(part) for part in old.split('\n'))
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise SystemExit(f'{label}: expected one match, found {len(matches)}')
    match = matches[0]
    newline = '\r\n' if '\r\n' in match.group(0) else '\n'
    replacement = new.replace('\n', newline)
    return text[:match.start()] + replacement + text[match.end():]


with cache_path.open('r', encoding='utf-8', newline='') as stream:
    cache = stream.read()

normalize_all = r'''
    static int normalizeAllFriendlyNames(Context context) {
        if (context == null) return 0;
        Set<String> keys = new HashSet<>();
        Uri tree = selectedTree(context);
        if (tree != null) {
            try {
                for (DocumentEntry entry : listDocumentsStrict(context, tree, true)) {
                    String key = metadataKey(entry.name);
                    if (validKey(key)) keys.add(key);
                }
                int normalized = 0;
                for (String key : keys) {
                    try {
                        MetadataRecord record = readMetadataFromTree(context, tree, key);
                        if (record == null) continue;
                        ensureFriendlyNames(context, key, record.title, record.artist,
                            record.album, record.catalogJson);
                        normalized++;
                    } catch (Exception ignored) {
                    }
                }
                return normalized;
            } catch (Exception ignored) {
                return 0;
            }
        }

        File root = internalRoot(context);
        File[] files = root.listFiles();
        if (files == null) return 0;
        for (File file : files) {
            if (!file.isFile()) continue;
            String key = metadataKey(file.getName());
            if (validKey(key)) keys.add(key);
        }
        int normalized = 0;
        for (String key : keys) {
            try {
                MetadataRecord record = readMetadataFromInternal(root, key);
                if (record == null) continue;
                ensureFriendlyNames(context, key, record.title, record.artist,
                    record.album, record.catalogJson);
                normalized++;
            } catch (Exception ignored) {
            }
        }
        return normalized;
    }
'''
cache = replace_once(
    cache,
    '''    static String findAudioUri(Context context, String key) {''',
    normalize_all + '''
    static String findAudioUri(Context context, String key) {''',
    'insert full cache normalizer',
)
cache = replace_once(
    cache,
    '''    private static String metadataName(String key) {
        return META_PREFIX + key.toLowerCase(Locale.ROOT) + META_SUFFIX;
    }
''',
    '''    private static String metadataName(String key) {
        return META_PREFIX + key.toLowerCase(Locale.ROOT) + META_SUFFIX;
    }

    private static String metadataKey(String name) {
        if (name == null || !name.startsWith(META_PREFIX) || !name.endsWith(META_SUFFIX)) return "";
        int start = META_PREFIX.length();
        int end = name.length() - META_SUFFIX.length();
        return end > start ? name.substring(start, end).toLowerCase(Locale.ROOT) : "";
    }
''',
    'insert metadata key parser',
)
with cache_path.open('w', encoding='utf-8', newline='') as stream:
    stream.write(cache)

with main_path.open('r', encoding='utf-8', newline='') as stream:
    main = stream.read()
main = replace_once(
    main,
    '''            restoreLastSong(false);
            normalizePlaylistCacheFilesAsync();
            publishPlaybackControlState(true);''',
    '''            restoreLastSong(false);
            normalizeAllCacheFilesAsync();
            publishPlaybackControlState(true);''',
    'startup cache normalization call',
)
main = replace_once(
    main,
    '''    private void installCrashReporter() {''',
    '''    private void normalizeAllCacheFilesAsync() {
        new Thread(() -> {
            CacheStorage.normalizeAllFriendlyNames(this);
            runOnUiThread(this::normalizePlaylistCacheFilesAsync);
        }, "cache-name-normalizer").start();
    }

    private void installCrashReporter() {''',
    'insert startup cache normalization worker',
)
with main_path.open('w', encoding='utf-8', newline='') as stream:
    stream.write(main)

with catalog_path.open('r', encoding='utf-8', newline='') as stream:
    catalog = stream.read()
catalog = replace_once(
    catalog,
    '''    private static final int SOURCE_GROUP_SIZE = 4;''',
    '''    private static final int SOURCE_GROUP_SIZE = 6;''',
    'increase quick search source group',
)
catalog = replace_once(
    catalog,
    '''        private void appendVisibleSlices(List<Track> out, List<String> sourceOrder) {
            boolean added;
            do {
                added = false;
                for (String source : sourceOrder) {
                    if (out.size() >= DISPLAY_BATCH_SIZE) return;
                    List<Track> rows = sourceRows.get(source);
                    if (rows == null || rows.isEmpty()) continue;
                    int offset = visibleOffsets.containsKey(source) ? visibleOffsets.get(source) : 0;
                    int taken = 0;
                    while (offset < rows.size() && taken < PER_SOURCE_SLICE && out.size() < DISPLAY_BATCH_SIZE) {
                        Track track = rows.get(offset++);
                        if (track != null && !track.id.isEmpty() && emittedKeys.add(track.key())) {
                            out.add(track);
                            taken++;
                            added = true;
                        }
                    }
                    visibleOffsets.put(source, offset);
                }
            } while (added && out.size() < DISPLAY_BATCH_SIZE);
        }''',
    '''        private void appendVisibleSlices(List<Track> out, List<String> sourceOrder) {
            while (out.size() < DISPLAY_BATCH_SIZE) {
                String bestSource = null;
                Track bestTrack = null;
                int bestScore = Integer.MIN_VALUE;

                for (String source : sourceOrder) {
                    List<Track> rows = sourceRows.get(source);
                    if (rows == null || rows.isEmpty()) continue;
                    int offset = visibleOffsets.containsKey(source) ? visibleOffsets.get(source) : 0;
                    while (offset < rows.size()) {
                        Track candidate = rows.get(offset);
                        if (candidate == null || candidate.id.isEmpty() || emittedKeys.contains(candidate.key())) {
                            offset++;
                            visibleOffsets.put(source, offset);
                            continue;
                        }
                        int candidateScore = score(candidate, keyword);
                        if (bestTrack == null || candidateScore > bestScore) {
                            bestSource = source;
                            bestTrack = candidate;
                            bestScore = candidateScore;
                        }
                        break;
                    }
                }

                if (bestTrack == null || bestSource == null) return;
                int offset = visibleOffsets.containsKey(bestSource) ? visibleOffsets.get(bestSource) : 0;
                visibleOffsets.put(bestSource, offset + 1);
                if (emittedKeys.add(bestTrack.key())) out.add(bestTrack);
            }
        }''',
    'global relevance merge',
)
catalog = replace_once(
    catalog,
    '''    private static void sortByRelevance(List<Track> rows, String keyword) {
        final String wanted = normalize(keyword);
        Collections.sort(rows, (left, right) -> score(right, wanted) - score(left, wanted));
    }

    private static int score(Track track, String wanted) {
        String title = normalize(track.title);
        String artist = normalize(track.artist);
        if (title.equals(wanted)) return 1000;
        if (title.contains(wanted)) return 800 - Math.abs(title.length() - wanted.length());
        if (wanted.contains(title) && title.length() > 1) return 650 + title.length();
        if (artist.contains(wanted)) return 350;
        return 0;
    }
''',
    '''    private static void sortByRelevance(List<Track> rows, String keyword) {
        Collections.sort(rows, (left, right) ->
            Integer.compare(score(right, keyword), score(left, keyword)));
    }

    private static int score(Track track, String keyword) {
        if (track == null) return 0;
        String wanted = normalize(keyword);
        String title = normalize(track.title);
        String artist = normalize(track.artist);
        if (wanted.isEmpty() || (title.isEmpty() && artist.isEmpty())) return 0;

        String titleArtist = title + artist;
        String artistTitle = artist + title;
        if (wanted.equals(titleArtist) || wanted.equals(artistTitle)) return 10000;

        int score = 0;
        if (title.equals(wanted)) score += 7600;
        else if (artist.equals(wanted)) score += 7000;
        else if (title.contains(wanted)) score += 5600 - Math.abs(title.length() - wanted.length());
        else if (wanted.contains(title) && title.length() > 1) score += 4700 + title.length();
        else if (artist.contains(wanted)) score += 4300;

        List<String> tokens = queryTokens(keyword);
        boolean allMatched = !tokens.isEmpty();
        int tokenScore = 0;
        for (String token : tokens) {
            if (title.equals(token)) tokenScore += 1700;
            else if (artist.equals(token)) tokenScore += 1600;
            else if (title.contains(token)) tokenScore += 1200;
            else if (artist.contains(token)) tokenScore += 1100;
            else {
                allMatched = false;
                tokenScore -= 600;
            }
        }
        if (allMatched && tokens.size() > 1) score += 5200;
        score += tokenScore;

        if (titleArtist.contains(wanted) || artistTitle.contains(wanted)) score += 2200;
        return Math.max(0, score);
    }

    private static List<String> queryTokens(String value) {
        List<String> tokens = new ArrayList<>();
        if (value == null) return tokens;
        String prepared = value.toLowerCase(Locale.ROOT)
            .replace("（", " ")
            .replace("）", " ")
            .replaceAll("[\\s\\p{Punct}《》【】\\[\\]·•]+", " ")
            .replaceAll("(?<=[a-z0-9])(?=[\\p{IsHan}])|(?<=[\\p{IsHan}])(?=[a-z0-9])", " ")
            .trim();
        for (String part : prepared.split("\\s+")) {
            String token = normalize(part);
            if (!token.isEmpty() && !tokens.contains(token)) tokens.add(token);
        }
        return tokens;
    }
''',
    'search relevance scoring',
)
with catalog_path.open('w', encoding='utf-8', newline='') as stream:
    stream.write(catalog)

gradle = gradle_path.read_text(encoding='utf-8')
gradle = replace_once(gradle, 'versionCode 2026080128', 'versionCode 2026080129', 'version code')
gradle = replace_once(gradle, 'versionName "2026.08.03.m4a-decryption"',
                      'versionName "2026.08.03.search-priority-cache-name"', 'version name')
gradle_path.write_text(gradle, encoding='utf-8')

check = check_path.read_text(encoding='utf-8')
check = replace_once(check, "'versionCode 2026080128' in gradle", "'versionCode 2026080129' in gradle", 'version check')
check = replace_once(
    check,
    '''    'settings width and status bar': ('0.70f' in main and 'setStatusBarColor(opening ? Color.rgb(22, 24, 34)' in main and 'statusBarHeight() + dp(20)' in main),''',
    '''    'all managed cache names normalized on startup': (
        'normalizeAllFriendlyNames' in cache
        and 'metadataKey(' in cache
        and 'normalizeAllCacheFilesAsync()' in main
        and '"cache-name-normalizer"' in main
    ),
    'title and artist search priority': (
        'wanted.equals(titleArtist)' in catalog
        and 'wanted.equals(artistTitle)' in catalog
        and 'queryTokens(keyword)' in catalog
        and 'candidateScore = score(candidate, keyword)' in catalog
        and 'SOURCE_GROUP_SIZE = 6' in catalog
    ),
    'settings width and status bar': ('0.70f' in main and 'setStatusBarColor(opening ? Color.rgb(22, 24, 34)' in main and 'statusBarHeight() + dp(20)' in main),''',
    'insert v129 checks',
)
check_path.write_text(check, encoding='utf-8')

with (root / 'docs/CHANGELOG.md').open('a', encoding='utf-8') as output:
    output.write('\n- v129: normalize every managed cache file at startup to `歌曲名 - 歌手`, removing legacy hash suffixes even for songs outside playlists.\n')
    output.write('- v129: rank exact `歌名 + 歌手` matches first, split adjacent Latin/Chinese query text, and merge multi-source results by global relevance.\n')
with (root / 'PROJECT_LOG.md').open('a', encoding='utf-8') as output:
    output.write('\n- v129 corrects remaining legacy cache names and search ordering: `miyaki米芽奇` now prioritizes tracks whose title/artist combination exactly matches both terms.\n')

print('Applied v129 search and cache naming patch')
