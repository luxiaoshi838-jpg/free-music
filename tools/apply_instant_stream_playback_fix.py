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

    # Catalog fallback must stop at the first source that yields a strict
    # title+artist identity match instead of waiting for every platform.
    catalog_path = java_root / 'CatalogSearch.java'
    catalog = catalog_path.read_text(encoding='utf-8')
    anchor = '''    static List<Track> findExactAlternatives(Context context, String catalogJson) {
        return findExactAlternatives(context, catalogJson, false);
    }

    static List<Track> findExactAlternatives(String catalogJson) {
        return findExactAlternatives(null, catalogJson, false);
    }
'''
    addition = '''    static List<Track> findExactAlternatives(Context context, String catalogJson) {
        return findExactAlternatives(context, catalogJson, false);
    }

    static List<String> exactAlternativeSourceOrder(String catalogJson) {
        List<String> sources = new ArrayList<>(ALL_SOURCES);
        try {
            JSONObject selected = new JSONObject(catalogJson == null ? "{}" : catalogJson);
            String selectedSource = selected.optString("source", "")
                .trim().toLowerCase(Locale.ROOT);
            sources.remove(selectedSource);
        } catch (Exception ignored) {
        }
        return sources;
    }

    static List<Track> findExactAlternativesInSource(Context context, String catalogJson,
                                                      String source, boolean manualPriority) {
        List<Track> matches = new ArrayList<>();
        try {
            JSONObject selected = new JSONObject(catalogJson == null ? "{}" : catalogJson);
            String selectedTitle = selected.optString("name", "");
            String selectedArtist = selected.optString("artist", "");
            if (normalize(selectedTitle).isEmpty() || normalize(selectedArtist).isEmpty()) {
                return matches;
            }
            String searchKeyword = selectedTitle + " " + selectedArtist;
            for (Track track : searchOneSource(context, manualPriority, source, searchKeyword)) {
                if (sameIdentity(selectedTitle, selectedArtist, track)) matches.add(track);
            }
        } catch (Exception ignored) {
        }
        return matches;
    }

    static List<Track> findExactAlternatives(String catalogJson) {
        return findExactAlternatives(null, catalogJson, false);
    }
'''
    catalog = replace_once(catalog, anchor, addition,
                           'source-by-source exact alternatives')
    catalog_path.write_text(catalog, encoding='utf-8')

    network_path = java_root / 'NetworkMediaCache.java'
    network = network_path.read_text(encoding='utf-8')

    cache_result_end = '''    static final class CacheResult {
        final String audioUri;
        final String lyric;
        final boolean audioFromCache;
        final boolean lyricFromCache;
        final String catalogJson;
        final String sourceCode;
        final boolean sourceChanged;

        CacheResult(String audioUri, String lyric, boolean audioFromCache, boolean lyricFromCache,
                    String catalogJson, String sourceCode, boolean sourceChanged) {
            this.audioUri = audioUri == null ? "" : audioUri;
            this.lyric = lyric == null ? "" : lyric;
            this.audioFromCache = audioFromCache;
            this.lyricFromCache = lyricFromCache;
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.sourceCode = sourceCode == null ? "" : sourceCode;
            this.sourceChanged = sourceChanged;
        }
    }
'''
    cache_result_new = cache_result_end + '''
    static final class ImmediatePlaybackResult {
        final String audioUri;
        final String catalogJson;
        final String sourceCode;
        final boolean sourceChanged;
        final boolean fromCache;

        ImmediatePlaybackResult(String audioUri, String catalogJson, String sourceCode,
                                boolean sourceChanged, boolean fromCache) {
            this.audioUri = audioUri == null ? "" : audioUri;
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.sourceCode = sourceCode == null ? "" : sourceCode;
            this.sourceChanged = sourceChanged;
            this.fromCache = fromCache;
        }
    }
'''
    network = replace_once(network, cache_result_end, cache_result_new,
                           'immediate playback result class')

    playback_anchor = '''    static CacheResult cacheForPlayback(Context context, String catalogJson,
                                        StatusCallback callback) throws Exception {
        return cachePrivateStylePlayback(context, catalogJson, callback);
    }

'''
    playback_new = playback_anchor + '''    /**
     * Resolve only enough information to start playback. No audio download,
     * duration check, format coercion or decoder probe is performed here.
     * Existing managed cache is preferred; otherwise the raw resolved URL is
     * returned immediately to MediaPlayer.prepareAsync().
     */
    static ImmediatePlaybackResult resolveForImmediatePlayback(Context context,
                                                               String catalogJson,
                                                               StatusCallback callback) throws Exception {
        checkInterrupted();
        if (context == null) throw new IllegalArgumentException("context is required");
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
        String requestedSource = requestedCatalog.optString("source", "")
            .trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        if (requestedSource.isEmpty() || requestedId.isEmpty()) {
            throw new IllegalArgumentException("歌曲目录缺少来源或 ID");
        }

        String requestedKey = sha256(requestedSource + "|" + requestedId);
        String requestedCached = CacheStorage.findAudioUri(context, requestedKey);
        if (!requestedCached.isEmpty() && CacheStorage.exists(context, requestedCached)) {
            status(callback, "已读取歌曲缓存");
            return new ImmediatePlaybackResult(requestedCached, requestedCatalog.toString(),
                requestedSource, false, true);
        }

        ResolvedChoice choice = null;
        status(callback, "正在连接原来源...");
        try {
            choice = new ResolvedChoice(requestedCatalog,
                resolvePrivateStyle(requestedCatalog.toString()));
        } catch (Exception ignored) {
        }
        if (choice == null || choice.audioUrl().isEmpty()) {
            status(callback, "原来源不可用，正在按歌名和歌手切换来源...");
            choice = findPrivateStyleFallback(context, requestedCatalog, callback);
        }
        if (choice == null || choice.audioUrl().isEmpty()) {
            throw new IllegalStateException("未找到同歌手同名的可播放版本，请手动使用替换歌曲");
        }

        JSONObject actualCatalog = canonicalCatalog(choice.catalog.toString());
        String actualSource = actualCatalog.optString("source", "")
            .trim().toLowerCase(Locale.ROOT);
        String actualId = actualCatalog.optString("id", "").trim();
        if (actualSource.isEmpty() || actualId.isEmpty()) {
            throw new IllegalStateException("歌曲目录不完整");
        }
        boolean sourceChanged = !requestedSource.equals(actualSource)
            || !requestedId.equals(actualId);
        String actualKey = sha256(actualSource + "|" + actualId);
        String actualCached = CacheStorage.findAudioUri(context, actualKey);
        boolean fromCache = !actualCached.isEmpty()
            && CacheStorage.exists(context, actualCached);
        String audioUri = fromCache ? actualCached : choice.audioUrl();
        return new ImmediatePlaybackResult(audioUri, actualCatalog.toString(),
            actualSource, sourceChanged, fromCache);
    }

'''
    network = replace_once(network, playback_anchor, playback_new,
                           'immediate URL playback resolver')

    old_fallback = '''    private static ResolvedChoice findPrivateStyleFallback(Context context,
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
'''
    new_fallback = '''    private static ResolvedChoice findPrivateStyleFallback(Context context,
                                                            JSONObject requestedCatalog,
                                                            StatusCallback callback) {
        String requestedSource = requestedCatalog.optString("source", "")
            .trim().toLowerCase(Locale.ROOT);
        String requestedId = requestedCatalog.optString("id", "").trim();
        for (String sourceToSearch : CatalogSearch.exactAlternativeSourceOrder(
                 requestedCatalog.toString())) {
            try {
                checkInterrupted();
                status(callback, "正在尝试"
                    + CatalogSearch.labelForSource(sourceToSearch) + "版本...");
                List<CatalogSearch.Track> alternatives =
                    CatalogSearch.findExactAlternativesInSource(
                        context, requestedCatalog.toString(), sourceToSearch, true);
                for (CatalogSearch.Track alternative : alternatives) {
                    JSONObject catalog = canonicalCatalog(alternative.rawJson);
                    String source = catalog.optString("source", "")
                        .trim().toLowerCase(Locale.ROOT);
                    String id = catalog.optString("id", "").trim();
                    if (source.isEmpty() || id.isEmpty()) continue;
                    if (requestedSource.equals(source) && requestedId.equals(id)) continue;
                    try {
                        JSONObject resolved = resolvePrivateStyle(catalog.toString());
                        ResolvedChoice choice = new ResolvedChoice(catalog, resolved);
                        if (!choice.audioUrl().isEmpty()) {
                            status(callback, "已切换到"
                                + CatalogSearch.labelForSource(source) + "版本");
                            return choice;
                        }
                    } catch (Exception ignored) {
                    }
                }
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                return null;
            } catch (Exception ignored) {
            }
        }
        return null;
    }
'''
    network = replace_once(network, old_fallback, new_fallback,
                           'stop-on-first-source playback fallback')
    network_path.write_text(network, encoding='utf-8')

    main_path = java_root / 'MainActivity.java'
    main = main_path.read_text(encoding='utf-8')
    main = replace_once(
        main,
        '                lyricView.setText("正在优先寻找可播放音频，歌词将在开始播放后匹配…");',
        '                lyricView.setText("正在连接歌曲，开始播放后再匹配歌词…");',
        'remove old playback-search lyric message'
    )

    old_cache_and_play = '''    private void cacheAndPlay(Song song) {
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
'''
    new_cache_and_play = '''    private void cacheAndPlay(Song song) {
        final long requestId = System.nanoTime();
        playbackResolveRequestId = requestId;
        playbackResolveSong = song;
        playbackResolveOriginalKey = song.key();
        statusView.setText("正在连接原来源...");
        new Thread(() -> {
            NetworkMediaCache.ImmediatePlaybackResult resolved = null;
            Throwable failure = null;
            try (NetworkMediaCache.ForegroundLease ignored =
                     NetworkMediaCache.beginForegroundWork(this)) {
                resolved = NetworkMediaCache.resolveForImmediatePlayback(
                    this,
                    song.catalogJson,
                    message -> runOnUiThread(() -> {
                        if (requestId == playbackResolveRequestId
                            && currentSong == song && statusView != null
                            && message != null && !message.trim().isEmpty()) {
                            statusView.setText(message);
                        }
                    })
                );
            } catch (Throwable error) {
                failure = error;
            }
            NetworkMediaCache.ImmediatePlaybackResult result = resolved;
            Throwable error = failure;
            runOnUiThread(() -> {
                if (requestId != playbackResolveRequestId || currentSong != song) return;
                if (error != null || result == null || result.audioUri.trim().isEmpty()) {
                    handleImmediatePlaybackResolveFailure(song, error);
                    return;
                }
                song.uri = result.audioUri;
                if (result.fromCache) song.cachedUri = result.audioUri;
                if (!result.catalogJson.trim().isEmpty()) song.catalogJson = result.catalogJson;
                if (!result.sourceCode.trim().isEmpty()) {
                    song.source = CatalogSearch.labelForSource(result.sourceCode);
                }
                persistResolvedCatalogToPlaylistCopies(song, playbackResolveOriginalKey);
                song.autoUnavailable = false;
                song.manualUnavailable = false;
                song.manualAttempt = false;
                markSongUnavailable(song, false);
                artistView.setText(song.artist + " · " + song.source);
                if (result.sourceChanged) {
                    toast("原来源不可用，已切换并记住" + song.source + "版本");
                    renderResults();
                }
                if (isSongInAnyPlaylist(song)) savePlaylists();
                startLocalPlayback(song);
            });
        }, "ImmediatePlaybackResolve").start();
    }

    private void handleImmediatePlaybackResolveFailure(Song song, Throwable error) {
        stopPlayback();
        if (playButton != null) playButton.setText("▶");
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
        String detail = error == null || error.getMessage() == null
            || error.getMessage().trim().isEmpty()
            ? "歌曲资源不可用" : error.getMessage().trim();
        if (statusView != null) statusView.setText("连接失败：" + detail);
        toast("该歌曲当前无法播放");
    }
'''
    main = replace_once(main, old_cache_and_play, new_cache_and_play,
                        'replace service-gated playback with immediate URL playback')

    remote_prepared = '''                mediaPlayer.setOnPreparedListener(player -> {
                    player.start();
                    playButton.setText("Ⅱ");
                    statusView.setText("当前播放：" + song.title);
                    updatePlaybackProgress();
                    lyricHandler.removeCallbacks(lyricTicker);
                    lyricHandler.post(lyricTicker);
                    publishPlaybackControlState(true);
                });
'''
    remote_prepared_new = '''                mediaPlayer.setOnPreparedListener(player -> {
                    player.start();
                    playButton.setText("Ⅱ");
                    statusView.setText("当前播放：" + song.title);
                    updatePlaybackProgress();
                    lyricHandler.removeCallbacks(lyricTicker);
                    lyricHandler.post(lyricTicker);
                    publishPlaybackControlState(true);
                    beginLyricsAfterPlayback(song);
                });
'''
    main = replace_once(main, remote_prepared, remote_prepared_new,
                        'lyrics only after remote audio starts')

    local_started = '''                lyricHandler.removeCallbacks(lyricTicker);
                lyricHandler.post(lyricTicker);
                publishPlaybackControlState(true);
            }
'''
    local_started_new = '''                lyricHandler.removeCallbacks(lyricTicker);
                lyricHandler.post(lyricTicker);
                publishPlaybackControlState(true);
                beginLyricsAfterPlayback(song);
            }
'''
    main = replace_once(main, local_started, local_started_new,
                        'lyrics after cached audio starts')

    method_anchor = '''    private void attachPlaybackErrorHandler(MediaPlayer player, Song song) {
'''
    method_new = '''    private void beginLyricsAfterPlayback(Song song) {
        lyricHandler.post(() -> {
            if (currentSong == song) showSongLyrics(song);
        });
    }

    private void attachPlaybackErrorHandler(MediaPlayer player, Song song) {
'''
    main = replace_once(main, method_anchor, method_new,
                        'post-playback lyric helper')
    main_path.write_text(main, encoding='utf-8')

    gradle_path = root / 'app/build.gradle'
    gradle = gradle_path.read_text(encoding='utf-8')
    gradle = replace_once(gradle, 'versionCode 2026080111',
                          'versionCode 2026080112', 'version code')
    gradle = replace_once(
        gradle,
        'versionName "2026.08.02.private-simple-playback"',
        'versionName "2026.08.02.instant-stream-playback"',
        'version name'
    )
    gradle_path.write_text(gradle, encoding='utf-8')

    checks_path = root / 'scripts/check_feature_requirements.py'
    checks = checks_path.read_text(encoding='utf-8')
    checks = checks.replace(
        "and 'resolveForPlayback' in main",
        "and 'resolveForImmediatePlayback' in main",
    )
    checks = checks.replace(
        "'version bumped': 'versionCode 2026080111' in gradle,",
        "'version bumped': 'versionCode 2026080112' in gradle,",
    )
    marker = "    'media player error containment': (\n"
    addition_check = '''    'instant stream playback without pre-download gate': (
        'ImmediatePlaybackResolve' in main
        and 'resolveForImmediatePlayback' in main
        and 'PlaybackControlService.resolveForPlayback(' not in main
        and '正在优先寻找可播放音频' not in main
        and 'beginLyricsAfterPlayback' in main
        and 'static ImmediatePlaybackResult resolveForImmediatePlayback' in network
        and 'No audio download' in network
        and 'findExactAlternativesInSource' in catalog
        and 'exactAlternativeSourceOrder' in catalog
        and 'cacheForAutomatic' in network
        and 'MIN_AUTOMATIC_DURATION_MS = 60_000L' in network
    ),
'''
    if addition_check not in checks:
        checks = checks.replace(marker, addition_check + marker, 1)
    checks_path.write_text(checks, encoding='utf-8')

    project_log_path = root / 'PROJECT_LOG.md'
    project_log = project_log_path.read_text(encoding='utf-8')
    if '搜索点击即时流式播放修正' not in project_log:
        project_log_path.write_text(project_log + '''\n\n## 2026-08-02 搜索点击即时流式播放修正\n\n- 修正上一版遗漏：搜索结果点击仍经过 `PlaybackControlService.resolveForPlayback()`，导致必须等待完整缓存后才播放。\n- 搜索结果和歌单网络歌曲现在只解析原来源URL；拿到URL后立即交给 `MediaPlayer.prepareAsync()`，不再等待音频完整下载。\n- 播放前不做一分钟过滤、格式强制、MediaCodec探测或歌词匹配。歌词只在音频真正开始后异步匹配。\n- 原来源失败后按平台顺序逐一搜索，严格匹配标准化歌名与歌手组合；首个可解析版本立即使用，不再等待全部平台完成。\n- 已有缓存仍优先直接播放；一键缓存继续保留60秒过滤、格式识别和真实解码校验。\n- 版本提升为 `2026080112 / 2026.08.02.instant-stream-playback`。\n''', encoding='utf-8')

    changelog_path = root / 'docs/CHANGELOG.md'
    changelog = changelog_path.read_text(encoding='utf-8')
    if 'Instant streaming playback correction' not in changelog:
        changelog_path.write_text(changelog + '''\n\n## 2026-08-02 Instant streaming playback correction\n\n- Removed the remaining `PlaybackControlService.resolveForPlayback()` gate from search-result and playlist-song clicks.\n- Playback now resolves only the source URL and immediately calls asynchronous MediaPlayer preparation without waiting for a full download.\n- Lyrics start only after audio playback begins.\n- Exact title-and-artist fallback now searches one source at a time and stops at the first resolvable match instead of waiting for every platform.\n- Existing cache remains preferred; one-click batch caching keeps duration and decoder validation.\n- Bumped versionCode to 2026080112.\n''', encoding='utf-8')

    print('instant_stream_playback_fix=applied')


if __name__ == '__main__':
    main()
