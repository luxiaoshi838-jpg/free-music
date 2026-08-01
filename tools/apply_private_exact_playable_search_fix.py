#!/usr/bin/env python3
from pathlib import Path
import argparse
import shutil


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
    tools_root = Path(__file__).resolve().parents[1]
    java_root = root / 'app/src/main/java/com/jianglab/babywife'

    shutil.copyfile(
        tools_root / 'tools/templates/SongVersionPickerExactPlayable.java',
        java_root / 'SongVersionPicker.java'
    )

    catalog_path = java_root / 'CatalogSearch.java'
    catalog = catalog_path.read_text(encoding='utf-8')
    catalog = replace_once(
        catalog,
        '''            if (normalize(selectedTitle).isEmpty()) return matches;
            String searchKeyword = isUnknownArtist(selectedArtist)
                ? selectedTitle : selectedTitle + " " + selectedArtist;
''',
        '''            if (normalize(selectedTitle).isEmpty() || normalize(selectedArtist).isEmpty()) {
                return matches;
            }
            String searchKeyword = selectedTitle + " " + selectedArtist;
''',
        'private-library fallback query'
    )
    catalog = replace_once(
        catalog,
        '''                    for (Track track : rows) {
                        if (replacementScore(selectedTitle, selectedArtist, track) >= 700) matches.add(track);
                    }
''',
        '''                    for (Track track : rows) {
                        if (sameIdentity(selectedTitle, selectedArtist, track)) matches.add(track);
                    }
''',
        'private-library exact fallback match'
    )
    catalog = replace_once(
        catalog,
        '''        Collections.sort(matches, (left, right) ->
            replacementScore(selectedTitleSafe(catalogJson), selectedArtistSafe(catalogJson), right)
                - replacementScore(selectedTitleSafe(catalogJson), selectedArtistSafe(catalogJson), left));
        return matches;
''',
        '''        return matches;
''',
        'remove fuzzy fallback sorting'
    )
    catalog = replace_once(
        catalog,
        '''    static boolean sameIdentity(String title, String artist, Track candidate) {
''',
        '''    static String identityKey(String title, String artist) {
        return normalize(title) + "|" + artistSignature(artist);
    }

    static boolean sameIdentity(String title, String artist, Track candidate) {
''',
        'identity cache key'
    )
    catalog_path.write_text(catalog, encoding='utf-8')

    priority_path = java_root / 'SearchPriorityCoordinator.java'
    priority = priority_path.read_text(encoding='utf-8')
    priority = replace_once(
        priority,
        '''    static String searchAutomatic(Context context, String source, String keyword) throws Exception {
        return callBridge(context, false, source, keyword);
    }

    private static String callBridge(Context context, boolean manual,
''',
        '''    static String searchAutomatic(Context context, String source, String keyword) throws Exception {
        return callBridge(context, false, source, keyword);
    }

    static String resolveManual(Context context, String catalogJson) throws Exception {
        try (ManualLease ignored = beginManual(context)) {
            Context app = context == null ? null : context.getApplicationContext();
            while (true) {
                checkInterrupted();
                File lockFile = bridgeLockFile(app);
                try (RandomAccessFile randomAccess = new RandomAccessFile(lockFile, "rw");
                     FileChannel channel = randomAccess.getChannel();
                     FileLock lock = channel.lock()) {
                    checkInterrupted();
                    try {
                        return Bridge.resolve(catalogJson);
                    } catch (Throwable error) {
                        if (error instanceof InterruptedException) {
                            throw (InterruptedException) error;
                        }
                        throw new IllegalStateException("歌曲音频解析异常："
                            + error.getClass().getSimpleName() + safeMessage(error), error);
                    }
                }
            }
        }
    }

    private static String callBridge(Context context, boolean manual,
''',
        'manual resolve priority coordination'
    )
    priority_path.write_text(priority, encoding='utf-8')

    network_path = java_root / 'NetworkMediaCache.java'
    network = network_path.read_text(encoding='utf-8')
    network = replace_once(
        network,
        '''    private static final int MAX_FALLBACK_ATTEMPTS = 4;
''',
        '''    private static final int MAX_FALLBACK_ATTEMPTS = 4;
    private static final long MANUAL_RESOLVE_VALID_MS = 10L * 60L * 1000L;
    private static final String MANUAL_URL = "_manual_resolved_url";
    private static final String MANUAL_EXT = "_manual_resolved_ext";
    private static final String MANUAL_TYPE = "_manual_resolved_type";
    private static final String MANUAL_AT = "_manual_resolved_at";
''',
        'manual pre-resolve constants'
    )
    network = replace_once(
        network,
        '''    static CacheResult cacheForAutomatic(Context context, String catalogJson,
                                         StatusCallback callback) throws Exception {
        return cacheInternal(context, catalogJson, true, true, callback);
    }

    static CacheResult cacheForPlayback(Context context, String catalogJson,
                                        StatusCallback callback) throws Exception {
        return cacheInternal(context, catalogJson, false, false, callback);
    }

    private static CacheResult cacheInternal(Context context, String catalogJson,
                                             boolean enforceRequestedMinimum,
                                             boolean eagerLyrics,
                                             StatusCallback callback) throws Exception {
''',
        '''    static CacheResult cacheForAutomatic(Context context, String catalogJson,
                                         StatusCallback callback) throws Exception {
        return cacheInternal(context, catalogJson, true, true, true, callback);
    }

    static CacheResult cacheForPlayback(Context context, String catalogJson,
                                        StatusCallback callback) throws Exception {
        return cacheForPlayback(context, catalogJson, true, callback);
    }

    static CacheResult cacheForPlayback(Context context, String catalogJson,
                                        boolean allowAutomaticFallback,
                                        StatusCallback callback) throws Exception {
        return cacheInternal(context, catalogJson, false, false,
            allowAutomaticFallback, callback);
    }

    private static CacheResult cacheInternal(Context context, String catalogJson,
                                             boolean enforceRequestedMinimum,
                                             boolean eagerLyrics,
                                             boolean allowAutomaticFallback,
                                             StatusCallback callback) throws Exception {
''',
        'manual selection fallback flag'
    )
    network = replace_once(
        network,
        '''        status(callback, "原来源不可用，才开始查找其他平台版本...");
        return cacheFirstUsableAlternative(context, requestedCatalog, callback,
            primaryError, eagerLyrics);
''',
        '''        if (!allowAutomaticFallback) {
            String detail = primaryError == null || primaryError.getMessage() == null
                ? "" : "：" + primaryError.getMessage();
            throw new IllegalStateException(
                "手动选择的版本当前不可播放，已停止继续寻找其他来源" + detail);
        }
        status(callback, "原来源不可用，才开始查找其他平台版本...");
        return cacheFirstUsableAlternative(context, requestedCatalog, callback,
            primaryError, eagerLyrics);
''',
        'manual fail-fast before automatic fallback'
    )
    network = replace_once(
        network,
        '''    static String cacheKeyForCatalog(String catalogJson) {
''',
        '''    static String prepareManualCatalog(Context context, String catalogJson) {
        try {
            JSONObject catalog = canonicalCatalog(catalogJson);
            String source = catalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
            String id = catalog.optString("id", "").trim();
            if (source.isEmpty() || id.isEmpty()) return "";

            JSONObject request = new JSONObject(catalog.toString());
            request.put("format", "mp3");
            request.put("ext", "mp3");
            request.put("quality", "320k");
            request.put("br", 320000);
            JSONObject response = new JSONObject(
                SearchPriorityCoordinator.resolveManual(context, request.toString()));
            if (!response.optBoolean("ok", false)) {
                response = new JSONObject(
                    SearchPriorityCoordinator.resolveManual(context, catalog.toString()));
            }
            if (!response.optBoolean("ok", false)) return "";
            JSONObject data = response.optJSONObject("data");
            if (data == null) return "";
            String url = data.optString("url", "").trim();
            if (url.isEmpty() || !probeResolvedUrl(url, source)) return "";

            catalog.put(MANUAL_URL, url);
            catalog.put(MANUAL_EXT, firstNonEmpty(data.optString("ext"),
                extensionFromUrl(url)));
            catalog.put(MANUAL_TYPE, firstNonEmpty(data.optString("type"),
                data.optString("mime"), data.optString("contentType")));
            catalog.put(MANUAL_AT, System.currentTimeMillis());
            return catalog.toString();
        } catch (Throwable ignored) {
            return "";
        }
    }

    private static boolean probeResolvedUrl(String urlText, String source) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(urlText).openConnection();
            connection.setConnectTimeout(6000);
            connection.setReadTimeout(6000);
            connection.setInstanceFollowRedirects(true);
            connection.setUseCaches(false);
            connection.setRequestProperty("User-Agent", userAgent(source));
            connection.setRequestProperty("Accept", "audio/*,application/octet-stream;q=0.9,*/*;q=0.1");
            connection.setRequestProperty("Accept-Encoding", "identity");
            connection.setRequestProperty("Range", "bytes=0-1");
            String referer = referer(source);
            if (!referer.isEmpty()) connection.setRequestProperty("Referer", referer);
            int statusCode = connection.getResponseCode();
            if (statusCode < 200 || statusCode >= 400) return false;
            String contentType = connection.getContentType();
            String normalizedType = contentType == null ? "" : contentType.toLowerCase(Locale.ROOT);
            return !normalizedType.startsWith("text/")
                && !normalizedType.contains("json")
                && !normalizedType.contains("html")
                && !normalizedType.contains("xml");
        } catch (Exception ignored) {
            return false;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    static String cacheKeyForCatalog(String catalogJson) {
''',
        'manual catalog preparation'
    )
    network = replace_once(
        network,
        '''    private static JSONObject resolve(String catalogJson) throws Exception {
        JSONObject catalog = new JSONObject(catalogJson == null ? "{}" : catalogJson);
        catalog.put("format", "mp3");
''',
        '''    private static JSONObject resolve(String catalogJson) throws Exception {
        JSONObject catalog = new JSONObject(catalogJson == null ? "{}" : catalogJson);
        String preparedUrl = catalog.optString(MANUAL_URL, "").trim();
        long preparedAt = catalog.optLong(MANUAL_AT, 0L);
        long preparedAge = System.currentTimeMillis() - preparedAt;
        if (!preparedUrl.isEmpty() && preparedAt > 0L
            && preparedAge >= 0L && preparedAge <= MANUAL_RESOLVE_VALID_MS) {
            JSONObject prepared = new JSONObject();
            prepared.put("url", preparedUrl);
            prepared.put("ext", catalog.optString(MANUAL_EXT, ""));
            prepared.put("type", catalog.optString(MANUAL_TYPE, ""));
            prepared.put("_requested_mp3", false);
            return prepared;
        }
        catalog.remove(MANUAL_URL);
        catalog.remove(MANUAL_EXT);
        catalog.remove(MANUAL_TYPE);
        catalog.remove(MANUAL_AT);
        String originalCatalog = catalog.toString();
        catalog.put("format", "mp3");
''',
        'reuse verified manual URL'
    )
    network = replace_once(
        network,
        '''        if (!requestedMp3Resolved) {
            response = new JSONObject(Bridge.resolve(catalogJson));
        }
''',
        '''        if (!requestedMp3Resolved) {
            response = new JSONObject(Bridge.resolve(originalCatalog));
        }
''',
        'clean fallback catalog'
    )
    network_path.write_text(network, encoding='utf-8')

    service_path = java_root / 'PlaybackControlService.java'
    service = service_path.read_text(encoding='utf-8')
    service = replace_once(
        service,
        '''    static final String EXTRA_SOURCE_CHANGED = "source_changed";
''',
        '''    static final String EXTRA_SOURCE_CHANGED = "source_changed";
    static final String EXTRA_ALLOW_AUTOMATIC_FALLBACK = "allow_automatic_fallback";
''',
        'playback fallback extra'
    )
    service = replace_once(
        service,
        '''    static void resolveForPlayback(Context context, long requestId, String title,
                                   String artist, String catalogJson) {
        Intent intent = new Intent(context, PlaybackControlService.class)
''',
        '''    static void resolveForPlayback(Context context, long requestId, String title,
                                   String artist, String catalogJson) {
        resolveForPlayback(context, requestId, title, artist, catalogJson, true);
    }

    static void resolveForPlayback(Context context, long requestId, String title,
                                   String artist, String catalogJson,
                                   boolean allowAutomaticFallback) {
        Intent intent = new Intent(context, PlaybackControlService.class)
''',
        'playback fallback overload'
    )
    service = replace_once(
        service,
        '''            .putExtra(EXTRA_ARTIST, artist == null ? "" : artist)
            .putExtra(EXTRA_CATALOG_JSON, catalogJson == null ? "" : catalogJson);
''',
        '''            .putExtra(EXTRA_ARTIST, artist == null ? "" : artist)
            .putExtra(EXTRA_CATALOG_JSON, catalogJson == null ? "" : catalogJson)
            .putExtra(EXTRA_ALLOW_AUTOMATIC_FALLBACK, allowAutomaticFallback);
''',
        'playback fallback intent value'
    )
    service = replace_once(
        service,
        '''        String catalogJson = safe(intent.getStringExtra(EXTRA_CATALOG_JSON), "");
        if (requestId == 0L || catalogJson.isEmpty()) return;
''',
        '''        String catalogJson = safe(intent.getStringExtra(EXTRA_CATALOG_JSON), "");
        boolean allowAutomaticFallback = intent.getBooleanExtra(
            EXTRA_ALLOW_AUTOMATIC_FALLBACK, true);
        if (requestId == 0L || catalogJson.isEmpty()) return;
''',
        'read playback fallback flag'
    )
    service = replace_once(
        service,
        '''                    this,
                    catalogJson,
                    message -> {
''',
        '''                    this,
                    catalogJson,
                    allowAutomaticFallback,
                    message -> {
''',
        'pass playback fallback flag'
    )
    service_path.write_text(service, encoding='utf-8')

    main_path = java_root / 'MainActivity.java'
    main_text = main_path.read_text(encoding='utf-8')
    main_text = replace_once(
        main_text,
        '''        searchPageStatusView.setText("搜索只建立目录；滚动到底部继续加载，点击歌曲后缓存音频和歌词");
''',
        '''        searchPageStatusView.setText("搜索会先验证可播放音频；滚动到底部继续验证更多来源");
''',
        'search page playable explanation'
    )
    main_text = replace_once(
        main_text,
        '''                batch = session.loadNext();
                for (CatalogSearch.Track track : batch.tracks) rows.add(Song.fromCatalog(track));
''',
        '''                batch = session.loadNext();
                int checked = 0;
                for (CatalogSearch.Track track : batch.tracks) {
                    if (track == null || track.id.isEmpty()) continue;
                    if (checked >= 12 || rows.size() >= 8) break;
                    checked++;
                    String playableCatalog = NetworkMediaCache.prepareManualCatalog(
                        this, track.rawJson);
                    if (playableCatalog.isEmpty()) continue;
                    CatalogSearch.Track verified = new CatalogSearch.Track(
                        new JSONObject(playableCatalog), track.sourceCode);
                    rows.add(Song.fromCatalog(verified));
                }
''',
        'verify ordinary manual search rows'
    )
    main_text = replace_once(
        main_text,
        '''                    "已建立目录 " + searchResults.size() + " 首" + platformText
                        + (hasMore ? "；继续向下滚动或点击底部加载" : "；当前模式已加载完")
''',
        '''                    "已验证可播放结果 " + searchResults.size() + " 首" + platformText
                        + (hasMore ? "；继续向下滚动或点击底部验证更多" : "；当前模式已加载完")
''',
        'verified search result status'
    )
    main_text = replace_once(
        main_text,
        '''    private void playSongFromSearch(int index) {
        if (index < 0 || index >= searchResults.size()) return;
        playingSearchQueue = true;
        searchSongIndex = index;
        currentSongIndex = -1;
        playSong(searchResults.get(index));
    }
''',
        '''    private void playSongFromSearch(int index) {
        if (index < 0 || index >= searchResults.size()) return;
        playingSearchQueue = true;
        searchSongIndex = index;
        currentSongIndex = -1;
        Song selected = searchResults.get(index);
        selected.manualAttempt = true;
        playSong(selected);
    }
''',
        'manual search selection flag'
    )
    main_text = replace_once(
        main_text,
        '''            song.artist,
            song.catalogJson
        );
''',
        '''            song.artist,
            song.catalogJson,
            !song.manualAttempt
        );
''',
        'manual selection disables fallback'
    )
    main_text = replace_once(
        main_text,
        '''        if (!success) {
            stopPlayback();
            playButton.setText("▶");
            showSongLyrics(song);
            if (isSongInAnyPlaylist(song)) {
                if (song.manualAttempt) {
''',
        '''        if (!success) {
            boolean manualSelection = song.manualAttempt;
            stopPlayback();
            playButton.setText("▶");
            showSongLyrics(song);
            if (isSongInAnyPlaylist(song)) {
                if (song.manualAttempt) {
''',
        'remember manual failure state'
    )
    main_text = replace_once(
        main_text,
        '''            String error = intent.getStringExtra(PlaybackControlService.EXTRA_ERROR);
            statusView.setText("缓存失败：" + (error == null ? "歌曲资源不可用" : error));
            toast("该歌曲当前无法缓存播放");
            return;
''',
        '''            String error = intent.getStringExtra(PlaybackControlService.EXTRA_ERROR);
            if (manualSelection) {
                statusView.setText("该手动版本已失效；替换搜索结果仍保留，可重新打开选择");
                toast("手动选择版本不可播放，未继续自动寻找其他来源");
            } else {
                statusView.setText("缓存失败：" + (error == null ? "歌曲资源不可用" : error));
                toast("该歌曲当前无法缓存播放");
            }
            return;
''',
        'manual failure returns quickly'
    )
    main_path.write_text(main_text, encoding='utf-8')

    gradle_path = root / 'app/build.gradle'
    gradle = gradle_path.read_text(encoding='utf-8')
    gradle = gradle.replace('versionCode 2026080110', 'versionCode 2026080111')
    gradle = gradle.replace(
        'versionName "2026.08.01.manual-priority-background-resolve"',
        'versionName "2026.08.02.exact-playable-manual-search"'
    )
    gradle_path.write_text(gradle, encoding='utf-8')

    checks_path = root / 'scripts/check_feature_requirements.py'
    checks = checks_path.read_text(encoding='utf-8')
    checks = checks.replace(
        "'version bumped': 'versionCode 2026080110' in gradle,",
        "'version bumped': 'versionCode 2026080111' in gradle,"
    )
    marker = "    'media player error containment': (\n"
    addition = '''    'private exact identity and playable manual results': (
        'song_version_directory_v4_exact_playable' in picker
        and 'CatalogSearch.sameIdentity(title, artist, track)' in picker
        and 'prepareManualCatalog' in picker
        and '(this.title + " " + this.artist).trim()' in picker
        and 'static String identityKey' in catalog
        and 'if (sameIdentity(selectedTitle, selectedArtist, track))' in catalog
        and 'resolveManual' in priority
        and 'probeResolvedUrl' in network
        and 'MANUAL_RESOLVE_VALID_MS' in network
        and 'allowAutomaticFallback' in network
        and '已停止继续寻找其他来源' in network
        and '已验证可播放结果' in main
        and 'selected.manualAttempt = true' in main
        and '!song.manualAttempt' in main
        and 'EXTRA_ALLOW_AUTOMATIC_FALLBACK' in playback_service
    ),
'''
    if addition not in checks:
        checks = checks.replace(marker, addition + marker, 1)
    checks_path.write_text(checks, encoding='utf-8')

    project_log_path = root / 'PROJECT_LOG.md'
    project_log = project_log_path.read_text(encoding='utf-8')
    if '私有库严格匹配与可播放结果过滤' not in project_log:
        project_log_path.write_text(project_log + '''\n\n## 2026-08-02 私有库严格匹配与可播放结果过滤\n\n- 替换歌曲恢复私有库规则：搜索词使用“歌名+歌手”，歌名标准化后完全一致，歌手组合标准化后完全一致。\n- 普通手动搜索和替换搜索都先解析并探测音频地址，只显示当前能够取得有效音频响应的目录结果。\n- 旧版模糊替换结果缓存升级隔离，避免继续显示相似歌名、错误歌手或未经验证的旧结果。\n- 手动搜索结果与确认替换版本点击后不再再次自动跨平台寻找；版本失效时快速提示并保留搜索结果。\n- 歌单正常自动播放、一键缓存和自动替换仍保留跨平台自动寻找以及一分钟规则。\n- 版本提升为 `2026080111 / 2026.08.02.exact-playable-manual-search`。\n''', encoding='utf-8')

    changelog_path = root / 'docs/CHANGELOG.md'
    changelog = changelog_path.read_text(encoding='utf-8')
    if 'Exact identity and playable manual search results' not in changelog:
        changelog_path.write_text(changelog + '''\n\n## 2026-08-02 Exact identity and playable manual search results\n\n- Restored the private-library replacement rule: title plus artist query, exact normalized title identity and exact normalized artist-set identity.\n- Pre-resolved and lightly probed manual search results so metadata-only or unavailable catalog entries are not shown as playable choices.\n- Reused short-lived verified URLs to avoid immediately resolving the same selected result twice.\n- Disabled automatic cross-platform fallback for user-selected search and replacement results; expired manual choices now fail fast while retained results remain available.\n- Kept automatic fallback and the one-minute rule for normal playlist automation and one-click caching.\n- Bumped versionCode to 2026080111.\n''', encoding='utf-8')

    print('private_exact_playable_search_fix=applied')


if __name__ == '__main__':
    main()
