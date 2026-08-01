#!/usr/bin/env python3
from pathlib import Path
import argparse


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {count}')
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    java_root = root / 'app/src/main/java/com/jianglab/babywife'

    catalog_path = java_root / 'CatalogSearch.java'
    catalog = catalog_path.read_text(encoding='utf-8')
    old_method = '''    static List<Track> findExactAlternatives(Context context, String catalogJson) {
        List<Track> matches = new ArrayList<>();
        try {
            JSONObject selected = new JSONObject(catalogJson == null ? "{}" : catalogJson);
            String selectedSource = selected.optString("source", "").trim().toLowerCase(Locale.ROOT);
            String selectedTitle = selected.optString("name", "");
            String selectedArtist = selected.optString("artist", "");
            if (normalize(selectedTitle).isEmpty()) return matches;
            String searchKeyword = isUnknownArtist(selectedArtist)
                ? selectedTitle : selectedTitle + " " + selectedArtist;

            List<String> sources = new ArrayList<>(ALL_SOURCES);
            sources.remove(selectedSource);
            ExecutorService pool = Executors.newFixedThreadPool(4);
            try {
                Map<String, Future<List<Track>>> futures = new LinkedHashMap<>();
                for (String source : sources) {
                    futures.put(source, pool.submit(() -> searchOneSource(context, false, source, searchKeyword)));
                }
                for (String source : sources) {
                    Future<List<Track>> future = futures.get(source);
                    if (future == null) continue;
                    List<Track> rows;
                    try {
                        rows = future.get(12, TimeUnit.SECONDS);
                    } catch (Exception ignored) {
                        continue;
                    }
                    for (Track track : rows) {
                        if (replacementScore(selectedTitle, selectedArtist, track) >= 700) matches.add(track);
                    }
                }
            } finally {
                pool.shutdownNow();
            }
        } catch (Exception ignored) {
        }
        Collections.sort(matches, (left, right) ->
            replacementScore(selectedTitleSafe(catalogJson), selectedArtistSafe(catalogJson), right)
                - replacementScore(selectedTitleSafe(catalogJson), selectedArtistSafe(catalogJson), left));
        return matches;
    }

    static List<Track> findExactAlternatives(String catalogJson) {
        return findExactAlternatives(null, catalogJson);
    }
'''
    new_method = '''    static List<Track> findExactAlternatives(Context context, String catalogJson,
                                                  boolean manualPriority) {
        List<Track> matches = new ArrayList<>();
        try {
            JSONObject selected = new JSONObject(catalogJson == null ? "{}" : catalogJson);
            String selectedSource = selected.optString("source", "").trim().toLowerCase(Locale.ROOT);
            String selectedTitle = selected.optString("name", "");
            String selectedArtist = selected.optString("artist", "");
            if (normalize(selectedTitle).isEmpty() || normalize(selectedArtist).isEmpty()) {
                return matches;
            }
            String searchKeyword = selectedTitle + " " + selectedArtist;

            List<String> sources = new ArrayList<>(ALL_SOURCES);
            sources.remove(selectedSource);
            ExecutorService pool = Executors.newFixedThreadPool(4);
            try {
                Map<String, Future<List<Track>>> futures = new LinkedHashMap<>();
                for (String source : sources) {
                    futures.put(source, pool.submit(() ->
                        searchOneSource(context, manualPriority, source, searchKeyword)));
                }
                for (String source : sources) {
                    Future<List<Track>> future = futures.get(source);
                    if (future == null) continue;
                    List<Track> rows;
                    try {
                        rows = future.get(12, TimeUnit.SECONDS);
                    } catch (Exception ignored) {
                        continue;
                    }
                    for (Track track : rows) {
                        if (sameIdentity(selectedTitle, selectedArtist, track)) matches.add(track);
                    }
                }
            } finally {
                pool.shutdownNow();
            }
        } catch (Exception ignored) {
        }
        return matches;
    }

    static List<Track> findExactAlternatives(Context context, String catalogJson) {
        return findExactAlternatives(context, catalogJson, false);
    }

    static List<Track> findExactAlternatives(String catalogJson) {
        return findExactAlternatives(null, catalogJson, false);
    }
'''
    catalog = replace_once(catalog, old_method, new_method,
                           'private exact alternative lookup')
    catalog_path.write_text(catalog, encoding='utf-8')

    picker_path = java_root / 'SongVersionPicker.java'
    picker = picker_path.read_text(encoding='utf-8')
    picker = replace_once(
        picker,
        '    private static final String CACHE_PREFS = "song_version_directory_v2";',
        '    private static final String CACHE_PREFS = "song_version_directory_v3_exact_identity";',
        'picker cache namespace'
    )
    picker = replace_once(
        picker,
        '        this.session = CatalogSearch.newSession(activity, this.title, "全部平台", true);',
        '        this.session = CatalogSearch.newSession(activity, (this.title + " " + this.artist).trim(), "全部平台", true);',
        'picker title artist query'
    )
    picker = replace_once(
        picker,
        '            .setTitle("选择歌曲版本")',
        '            .setTitle("选择同歌名同歌手版本")',
        'picker dialog title'
    )
    picker = replace_once(
        picker,
        '            status.setText("正在搜索可播放的相近歌曲版本…");',
        '            status.setText("正在按歌名和歌手搜索对应版本…");',
        'picker initial status'
    )
    picker = replace_once(
        picker,
        '        if (callback != null) callback.onStatus("手动搜索优先，正在查找替换歌曲版本…");',
        '        if (callback != null) callback.onStatus("手动搜索优先，正在查找同歌名同歌手版本…");',
        'picker callback status'
    )
    old_filter = '''                for (CatalogSearch.Track track : batch.tracks) {
                    if (track == null || track.id.isEmpty()) continue;
                    if (CatalogSearch.replacementScore(title, artist, track) < 420) continue;
                    if (emitted.add(track.key())) accepted.add(track);
                }
                Collections.sort(accepted, new Comparator<CatalogSearch.Track>() {
                    @Override
                    public int compare(CatalogSearch.Track left, CatalogSearch.Track right) {
                        return CatalogSearch.replacementScore(title, artist, right)
                            - CatalogSearch.replacementScore(title, artist, left);
                    }
                });
'''
    new_filter = '''                for (CatalogSearch.Track track : batch.tracks) {
                    if (track == null || track.id.isEmpty()) continue;
                    if (!CatalogSearch.sameIdentity(title, artist, track)) continue;
                    if (emitted.add(track.key())) accepted.add(track);
                }
'''
    picker = replace_once(picker, old_filter, new_filter,
                          'picker strict identity filter')
    picker = replace_once(
        picker,
        '                status.setText("已找到 " + rows.size() + " 个相近歌曲版本"',
        '                status.setText("已找到 " + rows.size() + " 个同歌名同歌手版本"',
        'picker result status'
    )
    picker = replace_once(
        picker,
        '                if (track.id.isEmpty() || !emitted.add(track.key())) continue;',
        '                if (track.id.isEmpty() || !CatalogSearch.sameIdentity(title, artist, track)\n                    || !emitted.add(track.key())) continue;',
        'picker cached identity filter'
    )
    picker_path.write_text(picker, encoding='utf-8')

    network_path = java_root / 'NetworkMediaCache.java'
    network = network_path.read_text(encoding='utf-8')
    old_playback = '''    static CacheResult cacheForPlayback(Context context, String catalogJson,
                                        StatusCallback callback) throws Exception {
        return cacheInternal(context, catalogJson, false, false, callback);
    }

'''
    new_playback = '''    static CacheResult cacheForPlayback(Context context, String catalogJson,
                                        StatusCallback callback) throws Exception {
        return cachePrivateStylePlayback(context, catalogJson, callback);
    }

    /**
     * Lightweight playback path matching the original private repository:
     * show catalog results immediately, resolve only after selection, try the
     * original source first, then exact normalized title+artist alternatives.
     * It intentionally skips one-minute, forced-format and decoder validation;
     * those remain exclusive to cacheForAutomatic / one-click caching.
     */
    private static CacheResult cachePrivateStylePlayback(Context context, String catalogJson,
                                                         StatusCallback callback) throws Exception {
        checkInterrupted();
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
        String requestedAudio = CacheStorage.findAudioUri(context, requestedKey);
        String requestedLyric = CacheStorage.readLyric(context, requestedKey);
        if (!requestedAudio.isEmpty() && CacheStorage.exists(context, requestedAudio)) {
            status(callback, "已读取歌曲缓存");
            return new CacheResult(requestedAudio, requestedLyric, true,
                !requestedLyric.trim().isEmpty(), requestedCatalog.toString(), requestedSource, false);
        }

        status(callback, "正在按原平台解析歌曲地址...");
        ResolvedChoice choice = null;
        try {
            choice = new ResolvedChoice(requestedCatalog,
                resolvePrivateStyle(requestedCatalog.toString()));
        } catch (Exception ignored) {
        }
        if (choice == null || choice.audioUrl().isEmpty()) {
            status(callback, "原来源不可用，正在查找同歌手同名的其他平台版本...");
            choice = findPrivateStyleFallback(context, requestedCatalog, callback);
        }
        if (choice == null || choice.audioUrl().isEmpty()) {
            throw new IllegalStateException("未找到同歌手同名的可播放版本，请手动使用替换歌曲");
        }
        return storePrivateStyleChoice(context, requestedCatalog, choice, callback);
    }

    private static ResolvedChoice findPrivateStyleFallback(Context context,
                                                            JSONObject requestedCatalog,
                                                            StatusCallback callback) {
        List<CatalogSearch.Track> alternatives = CatalogSearch.findExactAlternatives(
            context, requestedCatalog.toString(), true);
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        for (CatalogSearch.Track alternative : alternatives) {
            try {
                checkInterrupted();
                JSONObject catalog = canonicalCatalog(alternative.rawJson);
                String source = catalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
                String id = catalog.optString("id", "").trim();
                if (source.isEmpty() || id.isEmpty()) continue;
                if (requestedSource.equals(source) && requestedId.equals(id)) continue;
                JSONObject resolved = resolvePrivateStyle(catalog.toString());
                ResolvedChoice choice = new ResolvedChoice(catalog, resolved);
                if (!choice.audioUrl().isEmpty()) {
                    status(callback, "已匹配到同歌手同名的"
                        + CatalogSearch.labelForSource(source) + "版本");
                    return choice;
                }
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                return null;
            } catch (Exception ignored) {
            }
        }
        return null;
    }

    private static CacheResult storePrivateStyleChoice(Context context,
                                                       JSONObject requestedCatalog,
                                                       ResolvedChoice choice,
                                                       StatusCallback callback) throws Exception {
        checkInterrupted();
        JSONObject actualCatalog = canonicalCatalog(choice.catalog.toString());
        String requestedSource = requestedCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        String actualSource = actualCatalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String actualId = actualCatalog.optString("id", "").trim();
        if (actualSource.isEmpty() || actualId.isEmpty()) {
            throw new IllegalStateException("替换歌曲目录不完整");
        }
        boolean sourceChanged = !requestedSource.equals(actualSource) || !requestedId.equals(actualId);
        String key = sha256(actualSource + "|" + actualId);
        try (CacheKeyLock ignored = CacheKeyLock.acquire(context, key)) {
            String title = catalogTitle(actualCatalog);
            String artist = catalogArtist(actualCatalog);
            String album = catalogAlbum(actualCatalog);
            CacheStorage.ensureFriendlyNames(context, key, title, artist, album,
                actualCatalog.toString());
            String lyric = CacheStorage.readLyric(context, key);
            String existingAudio = CacheStorage.findAudioUri(context, key);
            if (!existingAudio.isEmpty() && CacheStorage.exists(context, existingAudio)) {
                status(callback, sourceChanged ? "已切换并读取其他平台缓存" : "歌曲缓存已存在");
                return new CacheResult(existingAudio, lyric, true, !lyric.trim().isEmpty(),
                    actualCatalog.toString(), actualSource, sourceChanged);
            }

            File tempRoot = new File(context.getCacheDir(), "network_download");
            if (!tempRoot.exists() && !tempRoot.mkdirs()) {
                throw new IllegalStateException("无法创建下载临时目录");
            }
            String hintedExtension = choiceExtension(choice);
            File partial = new File(tempRoot, key + "." + hintedExtension + "."
                + android.os.Process.myPid() + "." + Thread.currentThread().getId() + ".part");
            if (partial.exists()) partial.delete();
            status(callback, sourceChanged
                ? "原来源不可用，正在从" + CatalogSearch.labelForSource(actualSource) + "缓存歌曲..."
                : "正在缓存歌曲...");
            try {
                download(context, choice.audioUrl(), actualSource, partial, callback);
                checkInterrupted();
                if (partial.length() <= 0L) throw new IllegalStateException("歌曲缓存为空");
                String actualExtension = detectAudioExtension(partial, hintedExtension);
                String storedUri = CacheStorage.storeAudio(context, key, actualExtension, partial,
                    title, artist, album, actualCatalog.toString());
                status(callback, "歌曲缓存完成");
                return new CacheResult(storedUri, lyric, false, !lyric.trim().isEmpty(),
                    actualCatalog.toString(), actualSource, sourceChanged);
            } finally {
                if (partial.exists()) partial.delete();
            }
        }
    }

    private static JSONObject resolvePrivateStyle(String catalogJson) throws Exception {
        JSONObject response = new JSONObject(Bridge.resolve(catalogJson));
        if (!response.optBoolean("ok", false)) {
            throw new IllegalStateException(response.optString("error", "歌曲解析失败"));
        }
        JSONObject data = response.optJSONObject("data");
        if (data == null) throw new IllegalStateException("歌曲解析结果为空");
        return data;
    }

'''
    network = replace_once(network, old_playback, new_playback,
                           'private style playback path')
    network_path.write_text(network, encoding='utf-8')

    gradle_path = root / 'app/build.gradle'
    gradle = gradle_path.read_text(encoding='utf-8')
    gradle = gradle.replace('versionCode 2026080110', 'versionCode 2026080111')
    gradle = gradle.replace(
        'versionName "2026.08.01.manual-priority-background-resolve"',
        'versionName "2026.08.02.private-simple-playback"'
    )
    gradle_path.write_text(gradle, encoding='utf-8')

    checks_path = root / 'scripts/check_feature_requirements.py'
    checks = checks_path.read_text(encoding='utf-8')
    checks = checks.replace(
        "'version bumped': 'versionCode 2026080110' in gradle,",
        "'version bumped': 'versionCode 2026080111' in gradle,"
    )
    marker = "    'media player error containment': (\n"
    addition = '''    'private style instant search and simple playback replacement': (
        'song_version_directory_v3_exact_identity' in picker
        and '(this.title + " " + this.artist).trim()' in picker
        and 'CatalogSearch.sameIdentity(title, artist, track)' in picker
        and 'findExactAlternatives(Context context, String catalogJson,' in catalog
        and 'sameIdentity(selectedTitle, selectedArtist, track)' in catalog
        and 'cachePrivateStylePlayback' in network
        and 'resolvePrivateStyle' in network
        and 'findPrivateStyleFallback' in network
        and '未找到同歌手同名的可播放版本' in network
        and 'PlaybackCompatibility.isPlayable(partial)' in network
        and 'cacheForAutomatic' in network
    ),
'''
    if addition not in checks:
        checks = checks.replace(marker, addition + marker, 1)
    checks_path.write_text(checks, encoding='utf-8')

    project_log_path = root / 'PROJECT_LOG.md'
    project_log = project_log_path.read_text(encoding='utf-8')
    if '私有库式即时搜索与轻量播放替换' not in project_log:
        project_log_path.write_text(project_log + '''\n\n## 2026-08-02 私有库式即时搜索与轻量播放替换\n\n- 普通搜索恢复为只获取目录并立即显示，不在搜索阶段逐首解析或探测音频。\n- 搜索结果点击播放及加入歌单后的自动替换使用私有库原逻辑：原来源先解析，失败后以“歌名+歌手”搜索，并仅接受标准化歌名与歌手组合完全一致的版本。\n- 播放路径不再强制MP3、不做一分钟过滤、不做MediaCodec解码探测，也不限制为四个评分候选；找到首个可解析URL的严格匹配版本即缓存播放。\n- 一键缓存继续保留当前独立进程、时长过滤、格式识别与解码稳定性校验。\n- 替换搜索结果继续按歌曲保留，并支持下拉或滚到底部加载更多。\n- 版本提升为 `2026080111 / 2026.08.02.private-simple-playback`。\n''', encoding='utf-8')

    changelog_path = root / 'docs/CHANGELOG.md'
    changelog = changelog_path.read_text(encoding='utf-8')
    if 'Private-style instant search and lightweight playback fallback' not in changelog:
        changelog_path.write_text(changelog + '''\n\n## 2026-08-02 Private-style instant search and lightweight playback fallback\n\n- Restored instant metadata-only catalog search with no per-result URL prevalidation.\n- Routed selected-song playback and playlist playback fallback through the original private-repository flow: original source first, then exact normalized title and artist alternatives, first resolvable URL wins.\n- Removed forced MP3, one-minute gating, decoder probing and fuzzy four-candidate scoring from playback fallback only.\n- Retained the existing strict duration and decoder validation pipeline for one-click batch caching.\n- Kept retained replacement results, incremental loading and manual-search priority.\n- Bumped versionCode to 2026080111.\n''', encoding='utf-8')

    print('private_simple_playback_fix=applied')


if __name__ == '__main__':
    main()
