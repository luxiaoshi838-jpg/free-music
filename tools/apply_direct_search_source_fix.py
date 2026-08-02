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
    catalog = replace_once(
        catalog,
        '''        final String sourceLabel;
        final String rawJson;
''',
        '''        final String sourceLabel;
        final String directUrl;
        final String rawJson;
''',
        'track direct URL field'
    )
    catalog = replace_once(
        catalog,
        '''            this.sourceCode = canonicalSource;
            this.sourceLabel = labelForSource(sourceCode);
            this.rawJson = object.toString();
''',
        '''            this.sourceCode = canonicalSource;
            this.sourceLabel = labelForSource(sourceCode);
            this.directUrl = object.optString("url", "").trim();
            this.rawJson = object.toString();
''',
        'track direct URL assignment'
    )
    catalog_path.write_text(catalog, encoding='utf-8')

    main_path = java_root / 'MainActivity.java'
    main = main_path.read_text(encoding='utf-8')
    main = replace_once(
        main,
        '''                "",
                "",
                track.rawJson,
                ""
''',
        '''                "",
                track.directUrl,
                track.rawJson,
                ""
''',
        'preserve clicked search URL in Song'
    )

    old_method = '''    private void cacheAndPlay(Song song) {
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
'''
    new_method = '''    private void cacheAndPlay(Song song) {
        // Only true playlist automation uses the one-minute validation path.
        // Search-only songs and user-confirmed manual replacements stay on the
        // direct-source path and never perform the one-minute review.
        boolean automaticPlaylist = isSongInAnyPlaylist(song) && !song.manualAttempt;
        if (automaticPlaylist) {
            cacheAutomaticPlaylistAndPlay(song);
            return;
        }
        cacheImmediateAndPlay(song);
    }

    private void cacheImmediateAndPlay(Song song) {
        final long requestId = System.nanoTime();
        playbackResolveRequestId = requestId;
        playbackResolveSong = song;
        playbackResolveOriginalKey = song.key();
        statusView.setText(song.uri != null && !song.uri.trim().isEmpty()
            ? "正在打开所选歌曲来源..." : "正在连接所选歌曲来源...");
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
        }, "DirectSearchSourcePlayback").start();
    }

    private void cacheAutomaticPlaylistAndPlay(Song song) {
        final long requestId = System.nanoTime();
        playbackResolveRequestId = requestId;
        playbackResolveSong = song;
        playbackResolveOriginalKey = song.key();
        statusView.setText("歌单歌曲正在按一分钟规则寻找可用版本...");
        new Thread(() -> {
            NetworkMediaCache.CacheResult cached = null;
            Throwable failure = null;
            try (NetworkMediaCache.ForegroundLease ignored =
                     NetworkMediaCache.beginForegroundWork(this)) {
                cached = NetworkMediaCache.cacheForAutomatic(
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
            NetworkMediaCache.CacheResult result = cached;
            Throwable error = failure;
            runOnUiThread(() -> {
                if (requestId != playbackResolveRequestId || currentSong != song) return;
                if (error != null || result == null || result.audioUri.trim().isEmpty()) {
                    song.autoUnavailable = true;
                    markSongUnavailable(song, song.autoUnavailable && song.manualUnavailable);
                    savePlaylists();
                    renderCurrentPlaylist();
                    String detail = error == null || error.getMessage() == null
                        || error.getMessage().trim().isEmpty()
                        ? "歌曲资源不可用" : error.getMessage().trim();
                    statusView.setText("歌单自动寻找失败：" + detail);
                    toast("歌单歌曲未找到符合一分钟规则的版本");
                    return;
                }
                song.cachedUri = result.audioUri;
                song.uri = result.audioUri;
                if (!result.catalogJson.trim().isEmpty()) song.catalogJson = result.catalogJson;
                if (!result.sourceCode.trim().isEmpty()) {
                    song.source = CatalogSearch.labelForSource(result.sourceCode);
                }
                if ((song.lyric == null || song.lyric.trim().isEmpty())
                    && result.lyric != null && !result.lyric.trim().isEmpty()) {
                    song.lyric = result.lyric;
                }
                persistResolvedCatalogToPlaylistCopies(song, playbackResolveOriginalKey);
                song.autoUnavailable = false;
                markSongUnavailable(song, false);
                artistView.setText(song.artist + " · " + song.source);
                savePlaylists();
                startLocalPlayback(song);
            });
        }, "AutomaticPlaylistPlayback").start();
    }
'''
    main = replace_once(main, old_method, new_method,
                        'split direct search and automatic playlist playback')
    main_path.write_text(main, encoding='utf-8')

    network_path = java_root / 'NetworkMediaCache.java'
    network = network_path.read_text(encoding='utf-8')
    anchor = '''        String requestedCached = CacheStorage.findAudioUri(context, requestedKey);
        if (!requestedCached.isEmpty() && CacheStorage.exists(context, requestedCached)) {
            status(callback, "已读取歌曲缓存");
            return new ImmediatePlaybackResult(requestedCached, requestedCatalog.toString(),
                requestedSource, false, true);
        }

        ResolvedChoice choice = null;
'''
    replacement = '''        String requestedCached = CacheStorage.findAudioUri(context, requestedKey);
        if (!requestedCached.isEmpty() && CacheStorage.exists(context, requestedCached)) {
            status(callback, "已读取歌曲缓存");
            return new ImmediatePlaybackResult(requestedCached, requestedCatalog.toString(),
                requestedSource, false, true);
        }

        // Catalog search can already provide the selected row's playback URL.
        // Preserve and use it before invoking Bridge.resolve or any title/artist
        // replacement search. This is the core non-playlist click fast path.
        String requestedDirectUrl = requestedCatalog.optString("url", "").trim();
        if (requestedDirectUrl.startsWith("http://")
            || requestedDirectUrl.startsWith("https://")) {
            status(callback, "正在打开搜索结果自带的播放源...");
            return new ImmediatePlaybackResult(requestedDirectUrl,
                requestedCatalog.toString(), requestedSource, false, false);
        }

        ResolvedChoice choice = null;
'''
    network = replace_once(network, anchor, replacement,
                           'use clicked search URL before re-resolving')
    network_path.write_text(network, encoding='utf-8')

    gradle_path = root / 'app/build.gradle'
    gradle = gradle_path.read_text(encoding='utf-8')
    gradle = replace_once(gradle, 'versionCode 2026080112',
                          'versionCode 2026080113', 'version code')
    gradle = replace_once(
        gradle,
        'versionName "2026.08.02.instant-stream-playback"',
        'versionName "2026.08.02.direct-search-source"',
        'version name'
    )
    gradle_path.write_text(gradle, encoding='utf-8')

    checks_path = root / 'scripts/check_feature_requirements.py'
    checks = checks_path.read_text(encoding='utf-8')
    checks = checks.replace(
        "'version bumped': 'versionCode 2026080112' in gradle,",
        "'version bumped': 'versionCode 2026080113' in gradle,",
    )
    marker = "    'media player error containment': (\n"
    addition = '''    'clicked search source preserved and playlist minute rule isolated': (
        'final String directUrl;' in catalog
        and 'this.directUrl = object.optString("url", "").trim();' in catalog
        and 'track.directUrl' in main
        and 'boolean automaticPlaylist = isSongInAnyPlaylist(song) && !song.manualAttempt;' in main
        and 'cacheImmediateAndPlay(song);' in main
        and 'cacheAutomaticPlaylistAndPlay(song);' in main
        and 'NetworkMediaCache.cacheForAutomatic' in main
        and 'DirectSearchSourcePlayback' in main
        and 'requestedDirectUrl' in network
        and '搜索结果自带的播放源' in network
        and 'MIN_AUTOMATIC_DURATION_MS = 60_000L' in network
    ),
'''
    if addition not in checks:
        checks = checks.replace(marker, addition + marker, 1)
    checks_path.write_text(checks, encoding='utf-8')

    project_log_path = root / 'PROJECT_LOG.md'
    project_log = project_log_path.read_text(encoding='utf-8')
    if '搜索结果播放源直传与一分钟规则分流' not in project_log:
        project_log_path.write_text(project_log + '''\n\n## 2026-08-02 搜索结果播放源直传与一分钟规则分流\n\n- 修复目录结果中的 `url` 在 `Track -> Song` 转换时被丢弃的问题；搜索结果现在完整保留 `url/source/id/catalogJson`。\n- 非歌单搜索歌曲点击后优先直接使用该结果自带URL，不再先按歌名和歌手重新搜索。\n- 无直接URL时才解析所点击结果的原 `source + id`；原来源失败后才严格同歌名同歌手自动替换。\n- 非歌单搜索歌曲和手动确认的替换版本不执行一分钟审查。\n- 只有歌单自动播放/自动替换调用 `cacheForAutomatic` 并继续执行60秒规则。\n- 版本提升为 `2026080113 / 2026.08.02.direct-search-source`。\n''', encoding='utf-8')

    changelog_path = root / 'docs/CHANGELOG.md'
    changelog = changelog_path.read_text(encoding='utf-8')
    if 'Direct clicked search source and isolated minute rule' not in changelog:
        changelog_path.write_text(changelog + '''\n\n## 2026-08-02 Direct clicked search source and isolated minute rule\n\n- Preserved the catalog row's direct URL through Track-to-Song conversion.\n- Non-playlist search clicks now use the selected row's URL/source/id before any title-and-artist fallback search.\n- Non-playlist automatic replacement and confirmed manual replacement skip the one-minute review.\n- Only automatic playlist playback/replacement uses `cacheForAutomatic` and the 60-second minimum.\n- Bumped versionCode to 2026080113.\n''', encoding='utf-8')

    print('direct_search_source_fix=applied')


if __name__ == '__main__':
    main()
