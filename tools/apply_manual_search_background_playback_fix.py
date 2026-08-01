#!/usr/bin/env python3
from pathlib import Path
import argparse
import shutil


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {count}')
    return text.replace(old, new, 1)


def replace_all_required(text, old, new, minimum, label):
    count = text.count(old)
    if count < minimum:
        raise RuntimeError(f'{label}: expected at least {minimum} anchors, found {count}')
    return text.replace(old, new)


def splice_between(text, start_marker, end_marker, replacement, label):
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f'{label}: start marker missing')
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f'{label}: end marker missing')
    return text[:start] + replacement + text[end:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    tool_root = Path(__file__).resolve().parents[1]
    java_root = root / 'app/src/main/java/com/jianglab/babywife'

    shutil.copyfile(tool_root / 'tools/templates/SearchPriorityCoordinator.java',
                    java_root / 'SearchPriorityCoordinator.java')
    shutil.copyfile(tool_root / 'tools/templates/SongVersionPicker.java',
                    java_root / 'SongVersionPicker.java')
    shutil.copyfile(tool_root / 'tools/templates/PlaybackControlService.java',
                    java_root / 'PlaybackControlService.java')

    catalog_path = java_root / 'CatalogSearch.java'
    catalog = catalog_path.read_text(encoding='utf-8')
    catalog = replace_once(catalog, 'package com.jianglab.babywife;\n\n',
                           'package com.jianglab.babywife;\n\nimport android.content.Context;\n\n',
                           'catalog context import')
    catalog = replace_once(
        catalog,
        '''    static Session newSession(String keyword, String modeLabel) {
        return new Session(keyword, modeLabel, sourcesForMode(modeLabel));
    }
''',
        '''    static Session newSession(Context context, String keyword, String modeLabel,
                              boolean manualPriority) {
        return new Session(context, keyword, modeLabel, sourcesForMode(modeLabel), manualPriority);
    }

    static Session newSession(String keyword, String modeLabel) {
        return new Session(null, keyword, modeLabel, sourcesForMode(modeLabel), false);
    }
''',
        'catalog session factory'
    )
    catalog = replace_once(
        catalog,
        '''        private final String keyword;
        private final String modeLabel;
        private final List<String> sourceQueue;
''',
        '''        private final Context context;
        private final String keyword;
        private final String modeLabel;
        private final List<String> sourceQueue;
        private final boolean manualPriority;
''',
        'catalog session fields'
    )
    catalog = replace_once(
        catalog,
        '''        Session(String keyword, String modeLabel, List<String> sourceQueue) {
            this.keyword = keyword == null ? "" : keyword.trim();
            this.modeLabel = modeLabel == null ? "快速搜索" : modeLabel;
            this.sourceQueue = sourceQueue;
        }
''',
        '''        Session(Context context, String keyword, String modeLabel,
                List<String> sourceQueue, boolean manualPriority) {
            this.context = context == null ? null : context.getApplicationContext();
            this.keyword = keyword == null ? "" : keyword.trim();
            this.modeLabel = modeLabel == null ? "快速搜索" : modeLabel;
            this.sourceQueue = sourceQueue;
            this.manualPriority = manualPriority;
        }
''',
        'catalog session constructor'
    )
    catalog = replace_once(
        catalog,
        '''        synchronized boolean hasMore() {
            if (nextSourceIndex < sourceQueue.size()) return true;
            for (Map.Entry<String, List<Track>> entry : sourceRows.entrySet()) {
                int offset = visibleOffsets.containsKey(entry.getKey()) ? visibleOffsets.get(entry.getKey()) : 0;
                if (offset < entry.getValue().size()) return true;
            }
            return false;
        }
''',
        '''        synchronized boolean hasMore() {
            if (nextSourceIndex < sourceQueue.size()) return true;
            for (Map.Entry<String, List<Track>> entry : sourceRows.entrySet()) {
                int offset = visibleOffsets.containsKey(entry.getKey()) ? visibleOffsets.get(entry.getKey()) : 0;
                if (offset < entry.getValue().size()) return true;
            }
            return false;
        }

        synchronized int nextSourceIndex() {
            return nextSourceIndex;
        }

        synchronized void restoreNextSourceIndex(int index) {
            nextSourceIndex = Math.max(0, Math.min(sourceQueue.size(), index));
        }
''',
        'catalog session cursor access'
    )
    catalog = replace_once(
        catalog,
        '                            return searchOneSource(source, keyword);',
        '                            return searchOneSource(context, manualPriority, source, keyword);',
        'catalog session priority search'
    )
    catalog = replace_once(
        catalog,
        '''    private static List<Track> searchOneSource(String source, String keyword) {
        List<Track> rows = new ArrayList<>();
        try {
            JSONObject response = new JSONObject(Bridge.search(source, keyword));
''',
        '''    private static List<Track> searchOneSource(Context context, boolean manualPriority,
                                                   String source, String keyword) {
        List<Track> rows = new ArrayList<>();
        try {
            String raw = manualPriority
                ? SearchPriorityCoordinator.searchManual(context, source, keyword)
                : SearchPriorityCoordinator.searchAutomatic(context, source, keyword);
            JSONObject response = new JSONObject(raw);
''',
        'catalog bridge search'
    )
    catalog = replace_once(
        catalog,
        '    static List<Track> findExactAlternatives(String catalogJson) {',
        '''    static List<Track> findExactAlternatives(Context context, String catalogJson) {''',
        'catalog automatic alternatives context'
    )
    catalog = replace_once(
        catalog,
        '                    futures.put(source, pool.submit(() -> searchOneSource(source, searchKeyword)));',
        '                    futures.put(source, pool.submit(() -> searchOneSource(context, false, source, searchKeyword)));',
        'catalog alternative priority'
    )
    insert_marker = '    private static String selectedTitleSafe(String catalogJson) {'
    catalog = replace_once(
        catalog,
        insert_marker,
        '''    static List<Track> findExactAlternatives(String catalogJson) {
        return findExactAlternatives(null, catalogJson);
    }

''' + insert_marker,
        'catalog compatibility overload'
    )
    catalog_path.write_text(catalog, encoding='utf-8')

    lyric_picker_path = java_root / 'LyricVersionPicker.java'
    lyric_picker = lyric_picker_path.read_text(encoding='utf-8')
    lyric_picker = lyric_picker.replace('import bridge.Bridge;\n', '')
    lyric_picker = replace_once(
        lyric_picker,
        '            JSONObject response = new JSONObject(Bridge.search(source, keyword));',
        '            JSONObject response = new JSONObject(SearchPriorityCoordinator.searchManual(activity, source, keyword));',
        'manual lyric search priority'
    )
    lyric_picker_path.write_text(lyric_picker, encoding='utf-8')

    matcher_path = java_root / 'PlaylistLyricMatcher.java'
    matcher = matcher_path.read_text(encoding='utf-8')
    matcher = replace_once(matcher, 'package com.jianglab.babywife;\n\n',
                           'package com.jianglab.babywife;\n\nimport android.content.Context;\n',
                           'matcher context import')
    matcher = matcher.replace('import bridge.Bridge;\n', '')
    matcher = replace_once(
        matcher,
        '''    static void matchAsync(String title, String artist, String catalogJson, Callback callback) {
        new Thread(() -> {
            Match result = find(title, artist, catalogJson);
''',
        '''    static void matchAsync(Context context, String title, String artist,
                           String catalogJson, Callback callback) {
        Context app = context == null ? null : context.getApplicationContext();
        new Thread(() -> {
            Match result = find(app, title, artist, catalogJson);
''',
        'matcher context entry'
    )
    matcher = replace_once(
        matcher,
        '''    static String fetchExactLyric(String catalogJson) {
''',
        '''    static void matchAsync(String title, String artist, String catalogJson, Callback callback) {
        matchAsync(null, title, artist, catalogJson, callback);
    }

    static String fetchExactLyric(String catalogJson) {
''',
        'matcher compatibility overload'
    )
    matcher = replace_once(
        matcher,
        '    private static Match find(String title, String artist, String catalogJson) {',
        '    private static Match find(Context context, String title, String artist, String catalogJson) {',
        'matcher find context'
    )
    matcher = replace_once(
        matcher,
        '            List<CatalogSearch.Track> alternatives = CatalogSearch.findExactAlternatives(catalogJson);',
        '            List<CatalogSearch.Track> alternatives = CatalogSearch.findExactAlternatives(context, catalogJson);',
        'matcher automatic alternatives'
    )
    matcher = replace_once(
        matcher,
        '                JSONObject response = new JSONObject(Bridge.search(source, keyword));',
        '                JSONObject response = new JSONObject(SearchPriorityCoordinator.searchAutomatic(context, source, keyword));',
        'matcher automatic bridge search'
    )
    matcher_path.write_text(matcher, encoding='utf-8')

    network_path = java_root / 'NetworkMediaCache.java'
    network = network_path.read_text(encoding='utf-8')
    cache_block = '''    /** Compatibility overload used by the final player source.
     * The boolean requests persistent caching; this implementation always persists selected tracks.
     */
    static CacheResult cache(Context context, String catalogJson, boolean persist,
                             StatusCallback callback) throws Exception {
        return cacheForAutomatic(context, catalogJson, callback);
    }

    static CacheResult cache(Context context, String catalogJson,
                             StatusCallback callback) throws Exception {
        return cacheForAutomatic(context, catalogJson, callback);
    }

    static CacheResult cacheForAutomatic(Context context, String catalogJson,
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
        checkInterrupted();
        if (context == null) throw new IllegalArgumentException("context is required");
        awaitBackgroundTurn(context);
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
            if (eagerLyrics && !lyricFromCache) {
                status(callback, "正在按原平台读取歌词...");
                yieldIfForegroundRequested(context);
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
        if (!requestedAudioUri.isEmpty() && CacheStorage.exists(context, requestedAudioUri)) {
            status(callback, "旧缓存无法稳定播放，正在重新匹配...");
            CacheStorage.deleteKey(context, requestedKey);
        }

        Exception primaryError = null;
        status(callback, "正在使用歌单原来源解析歌曲...");
        try {
            if (enforceRequestedMinimum) {
                long duration = catalogDurationMs(requestedCatalog);
                if (duration > 0L && duration < MIN_AUTOMATIC_DURATION_MS) {
                    throw new IllegalStateException("原来源歌曲时长不足1分钟");
                }
            }
            awaitBackgroundTurn(context);
            ResolvedChoice original = new ResolvedChoice(requestedCatalog,
                resolve(requestedCatalog.toString()));
            CacheResult result = cacheChoice(context, requestedCatalog, original,
                enforceRequestedMinimum, eagerLyrics, callback);
            if (result != null) return result;
        } catch (InterruptedException interrupted) {
            throw interrupted;
        } catch (Exception error) {
            primaryError = error;
        }

        status(callback, "原来源不可用，才开始查找其他平台版本...");
        return cacheFirstUsableAlternative(context, requestedCatalog, callback,
            primaryError, eagerLyrics);
    }

'''
    network = splice_between(
        network,
        '    /** Compatibility overload used by the final player source.',
        '    private static final class ResolvedChoice',
        cache_block,
        'network cache API split'
    )
    network = replace_once(
        network,
        '''    private static CacheResult cacheFirstUsableAlternative(Context context,
                                                               JSONObject requestedCatalog,
                                                               StatusCallback callback,
                                                               Exception primaryError) throws Exception {
        List<CatalogSearch.Track> alternatives = CatalogSearch.findExactAlternatives(requestedCatalog.toString());
''',
        '''    private static CacheResult cacheFirstUsableAlternative(Context context,
                                                               JSONObject requestedCatalog,
                                                               StatusCallback callback,
                                                               Exception primaryError,
                                                               boolean eagerLyrics) throws Exception {
        awaitBackgroundTurn(context);
        List<CatalogSearch.Track> alternatives = CatalogSearch.findExactAlternatives(
            context, requestedCatalog.toString());
''',
        'network automatic fallback signature'
    )
    network = replace_once(
        network,
        '                CacheResult result = cacheChoice(context, requestedCatalog, choice, callback);',
        '                CacheResult result = cacheChoice(context, requestedCatalog, choice, true, eagerLyrics, callback);',
        'network automatic fallback minimum'
    )
    network = replace_once(
        network,
        '''    private static CacheResult cacheChoice(Context context, JSONObject requestedCatalog,
                                           ResolvedChoice choice, StatusCallback callback) throws Exception {
''',
        '''    private static CacheResult cacheChoice(Context context, JSONObject requestedCatalog,
                                           ResolvedChoice choice, boolean enforceMinimumDuration,
                                           boolean eagerLyrics, StatusCallback callback) throws Exception {
''',
        'network cache choice flags'
    )
    network = replace_once(
        network,
        '''        long catalogDuration = catalogDurationMs(actualCatalog);
        if (catalogDuration > 0L && catalogDuration < MIN_AUTOMATIC_DURATION_MS) {
            throw new IllegalStateException("候选歌曲时长不足1分钟");
        }
''',
        '''        if (enforceMinimumDuration) {
            long catalogDuration = catalogDurationMs(actualCatalog);
            if (catalogDuration > 0L && catalogDuration < MIN_AUTOMATIC_DURATION_MS) {
                throw new IllegalStateException("候选歌曲时长不足1分钟");
            }
        }
''',
        'network catalog minimum conditional'
    )
    network = replace_all_required(
        network,
        '            if (!lyricFromCache) {',
        '            if (eagerLyrics && !lyricFromCache) {',
        2,
        'network deferred lyrics'
    )
    network = replace_once(
        network,
        '''            long actualDuration = mediaDurationMs(partial);
            if (actualDuration < MIN_AUTOMATIC_DURATION_MS) {
                if (actualDuration <= 0L) throw new IllegalStateException("设备无法识别候选音频或确认时长");
                throw new IllegalStateException("候选音频只有" + Math.max(1L, actualDuration / 1000L) + "秒");
            }
''',
        '''            if (enforceMinimumDuration) {
                long actualDuration = mediaDurationMs(partial);
                if (actualDuration < MIN_AUTOMATIC_DURATION_MS) {
                    if (actualDuration <= 0L) throw new IllegalStateException("设备无法识别候选音频或确认时长");
                    throw new IllegalStateException("候选音频只有" + Math.max(1L, actualDuration / 1000L) + "秒");
                }
            }
''',
        'network downloaded minimum conditional'
    )
    network_path.write_text(network, encoding='utf-8')

    batch_path = java_root / 'PlaylistBatchCacheService.java'
    batch = batch_path.read_text(encoding='utf-8')
    batch = replace_once(
        batch,
        '                    NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(\n',
        '                    NetworkMediaCache.CacheResult cached = NetworkMediaCache.cacheForAutomatic(\n',
        'batch automatic cache API'
    )
    batch = replace_once(
        batch,
        '''                        song.catalogJson,
                        true,
                        message -> {
''',
        '''                        song.catalogJson,
                        message -> {
''',
        'batch remove compatibility boolean'
    )
    batch_path.write_text(batch, encoding='utf-8')

    main_path = java_root / 'MainActivity.java'
    main_text = main_path.read_text(encoding='utf-8')
    main_text = replace_once(
        main_text,
        '''    private long lastPublishedPlaybackSecond = -1L;
    private boolean lastPublishedPlaying = false;
    private String lastPublishedSongKey = "";
''',
        '''    private long lastPublishedPlaybackSecond = -1L;
    private boolean lastPublishedPlaying = false;
    private String lastPublishedSongKey = "";
    private long playbackResolveRequestId;
    private Song playbackResolveSong;
    private String playbackResolveOriginalKey = "";
''',
        'main playback resolve fields'
    )
    main_text = replace_once(
        main_text,
        '''            if (intent == null) return;
            String command = intent.getStringExtra(PlaybackControlService.EXTRA_COMMAND);
''',
        '''            if (intent == null) return;
            String action = intent.getAction();
            if (PlaybackControlService.ACTION_RESOLVE_PROGRESS.equals(action)) {
                handlePlaybackResolveProgress(intent);
                return;
            }
            if (PlaybackControlService.ACTION_RESOLVE_RESULT.equals(action)) {
                handlePlaybackResolveResult(intent);
                return;
            }
            if (!PlaybackControlService.ACTION_COMMAND.equals(action)) return;
            String command = intent.getStringExtra(PlaybackControlService.EXTRA_COMMAND);
''',
        'main playback receiver actions'
    )
    main_text = replace_once(
        main_text,
        '        IntentFilter filter = new IntentFilter(PlaybackControlService.ACTION_COMMAND);',
        '''        IntentFilter filter = new IntentFilter(PlaybackControlService.ACTION_COMMAND);
        filter.addAction(PlaybackControlService.ACTION_RESOLVE_PROGRESS);
        filter.addAction(PlaybackControlService.ACTION_RESOLVE_RESULT);''',
        'main playback filter actions'
    )
    main_text = replace_once(
        main_text,
        '''        searchInput.setSingleLine(true);
        searchInput.setHint("搜索歌曲 / 歌手");
''',
        '''        searchInput.setSingleLine(true);
        searchInput.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH);
        searchInput.setOnEditorActionListener((view, actionId, event) -> {
            boolean enter = event != null
                && event.getKeyCode() == android.view.KeyEvent.KEYCODE_ENTER
                && event.getAction() == android.view.KeyEvent.ACTION_DOWN;
            if (actionId == android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH || enter) {
                performSearch();
                return true;
            }
            return false;
        });
        searchInput.setHint("搜索歌曲 / 歌手");
''',
        'main enter key search'
    )
    main_text = replace_once(
        main_text,
        '        activeSearchSession = CatalogSearch.newSession(keyword, mode);',
        '        activeSearchSession = CatalogSearch.newSession(this, keyword, mode, true);',
        'main manual search session'
    )
    old_load_thread = '''        new Thread(() -> {
            CatalogSearch.Batch batch = session.loadNext();
            List<Song> rows = new ArrayList<>();
            for (CatalogSearch.Track track : batch.tracks) rows.add(Song.fromCatalog(track));
            runOnUiThread(() -> {
                if (session != activeSearchSession) return;
                appendUnique(searchResults, rows);
                renderResults();
                searchPageLoading = false;
                String platformText = batch.attemptedSources.isEmpty()
                    ? ""
                    : "，新搜索平台 " + batch.attemptedSources.size() + " 个";
                boolean hasMore = batch.hasMore;
                searchPageStatusView.setText(
                    "已建立目录 " + searchResults.size() + " 首" + platformText
                        + (hasMore ? "；继续向下滚动或点击底部加载" : "；当前模式已加载完")
                );
                if (searchLoadMoreView != null) {
                    searchLoadMoreView.setEnabled(hasMore);
                    searchLoadMoreView.setVisibility(View.VISIBLE);
                    searchLoadMoreView.setText(hasMore
                        ? "继续加载下一批未搜索平台"
                        : "当前搜索模式已加载完");
                }
            });
        }).start();
'''
    new_load_thread = '''        new Thread(() -> {
            CatalogSearch.Batch batch = null;
            Throwable failure = null;
            List<Song> rows = new ArrayList<>();
            try {
                batch = session.loadNext();
                for (CatalogSearch.Track track : batch.tracks) rows.add(Song.fromCatalog(track));
            } catch (Throwable error) {
                failure = error;
            }
            CatalogSearch.Batch result = batch;
            Throwable error = failure;
            runOnUiThread(() -> {
                if (session != activeSearchSession) return;
                searchPageLoading = false;
                if (error != null || result == null) {
                    searchPageStatusView.setText("搜索过程异常，已保留现有结果，可再次按回车或点击搜索");
                    if (searchLoadMoreView != null) {
                        searchLoadMoreView.setEnabled(true);
                        searchLoadMoreView.setVisibility(View.VISIBLE);
                        searchLoadMoreView.setText("重新加载歌曲目录");
                    }
                    return;
                }
                appendUnique(searchResults, rows);
                renderResults();
                String platformText = result.attemptedSources.isEmpty()
                    ? ""
                    : "，新搜索平台 " + result.attemptedSources.size() + " 个";
                boolean hasMore = result.hasMore;
                searchPageStatusView.setText(
                    "已建立目录 " + searchResults.size() + " 首" + platformText
                        + (hasMore ? "；继续向下滚动或点击底部加载" : "；当前模式已加载完")
                );
                if (searchLoadMoreView != null) {
                    searchLoadMoreView.setEnabled(hasMore);
                    searchLoadMoreView.setVisibility(View.VISIBLE);
                    searchLoadMoreView.setText(hasMore
                        ? "继续加载下一批未搜索平台"
                        : "当前搜索模式已加载完");
                }
            });
        }, "manual-catalog-search").start();
'''
    main_text = replace_once(main_text, old_load_thread, new_load_thread,
                             'main search exception containment')
    main_text = replace_once(
        main_text,
        '        SongVersionPicker.show(this, song.title, song.artist, new SongVersionPicker.Callback() {',
        '        SongVersionPicker.show(this, song.key(), song.title, song.artist, new SongVersionPicker.Callback() {',
        'main song picker identity'
    )
    main_text = replace_all_required(
        main_text,
        '        PlaylistLyricMatcher.matchAsync(song.title, song.artist, song.catalogJson,',
        '        PlaylistLyricMatcher.matchAsync(this, song.title, song.artist, song.catalogJson,',
        2,
        'main lyric matcher context'
    )
    main_text = replace_once(
        main_text,
        '''        statusView.setText("当前选择：" + song.title);
        lyricHandler.post(() -> {
            if (currentSong == song) showSongLyrics(song);
        });

        if (song.isNetworkCatalog()) {
            stopPlayback();
            playButton.setText("▶");
            cacheAndPlay(song);
            return;
        }

        if (song.uri == null || song.uri.isEmpty()) {
''',
        '''        statusView.setText("当前选择：" + song.title);

        if (song.isNetworkCatalog()) {
            if (song.lyric != null && !song.lyric.trim().isEmpty()) {
                lyricHandler.post(() -> {
                    if (currentSong == song) showSongLyrics(song);
                });
            } else if (lyricView != null) {
                lyricView.setText("正在优先寻找可播放音频，歌词将在开始播放后匹配…");
            }
            stopPlayback();
            playButton.setText("▶");
            cacheAndPlay(song);
            return;
        }

        lyricHandler.post(() -> {
            if (currentSong == song) showSongLyrics(song);
        });
        if (song.uri == null || song.uri.isEmpty()) {
''',
        'main audio before lyrics'
    )
    old_cache_and_play = '''    private void cacheAndPlay(Song song) {
        String originalKey = song.key();
        statusView.setText("正在缓存歌曲并匹配歌词...");
        new Thread(() -> {
            try (NetworkMediaCache.ForegroundLease foregroundLease =
                     NetworkMediaCache.beginForegroundWork(this)) {
                NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
                    this,
                    song.catalogJson,
                    true,
                    message -> runOnUiThread(() -> {
                        if (currentSong == song) statusView.setText(message);
                    })
                );
                runOnUiThread(() -> {
                    if (currentSong != song) return;
                    song.cachedUri = cached.audioUri;
                    song.uri = cached.audioUri;
                    if (cached.catalogJson != null && !cached.catalogJson.trim().isEmpty()) {
                        song.catalogJson = cached.catalogJson;
                    }
                    if (cached.sourceCode != null && !cached.sourceCode.trim().isEmpty()) {
                        song.source = CatalogSearch.labelForSource(cached.sourceCode);
                    }
                    if ((song.lyric == null || song.lyric.trim().isEmpty())
                        && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                        String label = song.title + " · " + song.artist + " · " + song.source;
                        if (isSongInAnyPlaylist(song)) {
                            bindLyricToPlaylistCopies(song, cached.lyric, label);
                        } else {
                            song.lyric = cached.lyric;
                            song.lyricLabel = label;
                        }
                    }
                    persistResolvedCatalogToPlaylistCopies(song, originalKey);
                    song.autoUnavailable = false;
                    song.manualUnavailable = false;
                    song.manualAttempt = false;
                    markSongUnavailable(song, false);
                    artistView.setText(song.artist + " · " + song.source);
                    if (cached.sourceChanged) {
                        toast("原来源不可用，已切换并记住" + song.source + "版本");
                        renderResults();
                    }
                    if (isSongInAnyPlaylist(song)) savePlaylists();
                    showSongLyrics(song);
                    startLocalPlayback(song);
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (currentSong != song) return;
                    stopPlayback();
                    playButton.setText("▶");
                    showSongLyrics(song);
                    if (isSongInAnyPlaylist(song)) {
                        if (song.manualAttempt) {
                            song.manualUnavailable = true;
                            song.manualAttempt = false;
                        } else {
                            song.autoUnavailable = true;
                        }
                        markSongUnavailable(song, song.autoUnavailable && song.manualUnavailable);
                        savePlaylists();
                        renderCurrentPlaylist();
                    }
                    statusView.setText("缓存失败：" + error.getMessage());
                    toast("该歌曲当前无法缓存播放");
                });
            }
        }).start();
    }
'''
    new_cache_and_play = '''    private void cacheAndPlay(Song song) {
        playbackResolveRequestId = System.nanoTime();
        playbackResolveSong = song;
        playbackResolveOriginalKey = song.key();
        statusView.setText("正在优先寻找可播放音频；切到其他软件后仍会继续…");
        PlaybackControlService.resolveForPlayback(
            this,
            playbackResolveRequestId,
            song.title,
            song.artist,
            song.catalogJson
        );
    }

    private void handlePlaybackResolveProgress(Intent intent) {
        long requestId = intent.getLongExtra(PlaybackControlService.EXTRA_REQUEST_ID, 0L);
        if (requestId == 0L || requestId != playbackResolveRequestId) return;
        if (currentSong != playbackResolveSong || statusView == null) return;
        String message = intent.getStringExtra(PlaybackControlService.EXTRA_MESSAGE);
        if (message != null && !message.trim().isEmpty()) statusView.setText(message);
    }

    private void handlePlaybackResolveResult(Intent intent) {
        long requestId = intent.getLongExtra(PlaybackControlService.EXTRA_REQUEST_ID, 0L);
        if (requestId == 0L || requestId != playbackResolveRequestId) return;
        Song song = playbackResolveSong;
        if (song == null || currentSong != song) return;
        boolean success = intent.getBooleanExtra(PlaybackControlService.EXTRA_SUCCESS, false);
        if (!success) {
            stopPlayback();
            playButton.setText("▶");
            showSongLyrics(song);
            if (isSongInAnyPlaylist(song)) {
                if (song.manualAttempt) {
                    song.manualUnavailable = true;
                    song.manualAttempt = false;
                } else {
                    song.autoUnavailable = true;
                }
                markSongUnavailable(song, song.autoUnavailable && song.manualUnavailable);
                savePlaylists();
                renderCurrentPlaylist();
            }
            String error = intent.getStringExtra(PlaybackControlService.EXTRA_ERROR);
            statusView.setText("缓存失败：" + (error == null ? "歌曲资源不可用" : error));
            toast("该歌曲当前无法缓存播放");
            return;
        }

        String audioUri = intent.getStringExtra(PlaybackControlService.EXTRA_AUDIO_URI);
        if (audioUri == null || audioUri.trim().isEmpty()) {
            statusView.setText("没有取得可播放音频");
            return;
        }
        song.cachedUri = audioUri;
        song.uri = audioUri;
        String catalogJson = intent.getStringExtra(PlaybackControlService.EXTRA_CATALOG_JSON);
        if (catalogJson != null && !catalogJson.trim().isEmpty()) song.catalogJson = catalogJson;
        String sourceCode = intent.getStringExtra(PlaybackControlService.EXTRA_SOURCE_CODE);
        if (sourceCode != null && !sourceCode.trim().isEmpty()) {
            song.source = CatalogSearch.labelForSource(sourceCode);
        }
        String lyric = intent.getStringExtra(PlaybackControlService.EXTRA_LYRIC);
        if ((song.lyric == null || song.lyric.trim().isEmpty())
            && lyric != null && !lyric.trim().isEmpty()) {
            String label = song.title + " · " + song.artist + " · " + song.source;
            if (isSongInAnyPlaylist(song)) bindLyricToPlaylistCopies(song, lyric, label);
            else {
                song.lyric = lyric;
                song.lyricLabel = label;
            }
        }
        persistResolvedCatalogToPlaylistCopies(song, playbackResolveOriginalKey);
        song.autoUnavailable = false;
        song.manualUnavailable = false;
        song.manualAttempt = false;
        markSongUnavailable(song, false);
        artistView.setText(song.artist + " · " + song.source);
        if (intent.getBooleanExtra(PlaybackControlService.EXTRA_SOURCE_CHANGED, false)) {
            toast("原来源不可用，已切换并记住" + song.source + "版本");
            renderResults();
        }
        if (isSongInAnyPlaylist(song)) savePlaylists();
        showSongLyrics(song);
        startLocalPlayback(song);
    }
'''
    main_text = replace_once(main_text, old_cache_and_play, new_cache_and_play,
                             'main foreground service playback resolve')
    main_path.write_text(main_text, encoding='utf-8')

    manifest_path = root / 'app/src/main/AndroidManifest.xml'
    manifest = manifest_path.read_text(encoding='utf-8')
    manifest = replace_once(
        manifest,
        '            android:foregroundServiceType="mediaPlayback" />',
        '            android:foregroundServiceType="mediaPlayback|dataSync" />',
        'playback service data sync type'
    )
    manifest_path.write_text(manifest, encoding='utf-8')

    gradle_path = root / 'app/build.gradle'
    gradle = gradle_path.read_text(encoding='utf-8')
    gradle = gradle.replace('versionCode 2026080109', 'versionCode 2026080110')
    gradle = gradle.replace('versionName "2026.08.01.low-priority-resilient-batch"',
                            'versionName "2026.08.01.manual-priority-background-resolve"')
    gradle_path.write_text(gradle, encoding='utf-8')

    checks_path = root / 'scripts/check_feature_requirements.py'
    checks = checks_path.read_text(encoding='utf-8')
    checks = replace_once(
        checks,
        "catalog = (root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java').read_text(encoding='utf-8')\n",
        "catalog = (root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java').read_text(encoding='utf-8')\n"
        "priority = (root / 'app/src/main/java/com/jianglab/babywife/SearchPriorityCoordinator.java').read_text(encoding='utf-8')\n"
        "playback_service = (root / 'app/src/main/java/com/jianglab/babywife/PlaybackControlService.java').read_text(encoding='utf-8')\n",
        'feature check new files'
    )
    checks = checks.replace("'version bumped': 'versionCode 2026080109' in gradle,",
                            "'version bumped': 'versionCode 2026080110' in gradle,")
    marker = "    'media player error containment': (\n"
    addition = '''    'manual search priority persistent picker and background resolve': (
        'SearchPriorityCoordinator.searchManual' in catalog
        and 'SearchPriorityCoordinator.searchAutomatic' in catalog
        and 'bridge_search.lock' in priority
        and 'manual_search.lease' in priority
        and 'song_version_directory_v2' in picker
        and 'restoreNextSourceIndex' in picker
        and '下拉或滚到底部' in picker
        and 'IME_ACTION_SEARCH' in main
        and 'ACTION_RESOLVE_RESULT' in main
        and 'resolveForPlayback' in main
        and 'cacheForPlayback' in network
        and 'cacheForAutomatic' in network
        and 'enforceRequestedMinimum' in network
        and 'enforceMinimumDuration' in network
        and 'eagerLyrics' in network
        and 'PlaybackResolveWorker' in playback_service
        and 'mediaPlayback|dataSync' in manifest
    ),
'''
    if addition not in checks:
        checks = checks.replace(marker, addition + marker, 1)
    checks_path.write_text(checks, encoding='utf-8')

    project_log_path = root / 'PROJECT_LOG.md'
    project_log = project_log_path.read_text(encoding='utf-8')
    marker_cn = '手动搜索优先、结果保留与后台找歌'
    if marker_cn not in project_log:
        project_log_path.write_text(project_log + '''\n\n## 2026-08-01 手动搜索优先、结果保留与后台找歌\n\n- 手动普通搜索、手动替换歌曲和手动歌词搜索获得最高搜索优先级；底层目录桥接跨进程串行化，自动替换与一键缓存等待手动搜索。\n- 替换歌曲结果按当前歌曲身份保存，再次打开直接显示；下拉、滚到底部或点击底部继续加载，换到下一首使用独立结果。\n- 普通搜索输入框支持键盘回车/搜索键直接执行。\n- 点击网络歌曲后由独立前台播放服务解析和缓存，界面退到其他软件后仍继续；先取得音频，歌词随后异步匹配。\n- 手动搜索、手动替换和点击播放取消一分钟限制；一键缓存及自动替换继续保留一分钟判断。\n- 版本提升为 `2026080110 / 2026.08.01.manual-priority-background-resolve`。\n''', encoding='utf-8')

    changelog_path = root / 'docs/CHANGELOG.md'
    changelog = changelog_path.read_text(encoding='utf-8')
    marker_en = 'Manual-priority search, retained picker results and background resolve'
    if marker_en not in changelog:
        changelog_path.write_text(changelog + '''\n\n## 2026-08-01 Manual-priority search, retained picker results and background resolve\n\n- Serialized native catalog search across processes and gave manual search precedence over automatic fallback and playlist batch caching.\n- Persisted replacement-song results and source cursor per song, with pull-down, bottom-scroll and footer loading.\n- Added keyboard Enter/Search action handling to the main search field.\n- Moved playback catalog resolution and audio caching into the independent foreground playback service so work continues while another app is visible.\n- Deferred lyric matching until playable audio is ready.\n- Removed the one-minute gate from manual search, manual replacement and clicked playback while retaining it for one-click batch caching and automatic replacement.\n- Bumped versionCode to 2026080110.\n''', encoding='utf-8')

    print('manual_search_background_playback_fix=applied')


if __name__ == '__main__':
    main()
