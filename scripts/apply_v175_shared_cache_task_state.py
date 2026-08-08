from pathlib import Path


def replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise SystemExit("method not found: " + signature)
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit("method brace not found: " + signature)
    depth = 0
    in_string = False
    escape = False
    in_char = False
    for i in range(brace, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if in_char:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                in_char = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "'":
            in_char = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement + text[i + 1:]
    raise SystemExit("unterminated method: " + signature)


path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = path.read_text(encoding="utf-8")

field_anchor = '''    private final ConcurrentHashMap<String, Future<?>> searchCacheTasks = new ConcurrentHashMap<>();\n'''
field_new = field_anchor + '''    private final Set<String> activeSongCacheKeys = ConcurrentHashMap.newKeySet();\n'''
if "activeSongCacheKeys" not in text:
    if field_anchor not in text:
        raise SystemExit("cache task field anchor missing")
    text = text.replace(field_anchor, field_new, 1)

helper_marker = "    private void releaseMediaPlayer(UnifiedMediaPlayer player) {"
helpers = r'''    private String cacheOperationKey(String title, String artist, String catalogJson) {
        String catalogKey = NetworkMediaCache.cacheKeyForCatalog(catalogJson);
        if (catalogKey != null && !catalogKey.trim().isEmpty()) {
            return "catalog|" + catalogKey.trim();
        }
        String logical = CacheStorage.logicalIdentity(title, artist);
        return logical == null || logical.trim().isEmpty()
            ? "" : "logical|" + logical.trim();
    }

    private String cacheOperationKey(Song song) {
        if (song == null) return "";
        return cacheOperationKey(song.title, song.artist, song.catalogJson);
    }

    private boolean beginSongCacheTask(String key) {
        return key == null || key.trim().isEmpty() || activeSongCacheKeys.add(key.trim());
    }

    private void endSongCacheTask(String key) {
        if (key != null && !key.trim().isEmpty()) activeSongCacheKeys.remove(key.trim());
    }

    private boolean isSongCacheTaskActive(Song song) {
        String key = cacheOperationKey(song);
        return !key.isEmpty() && activeSongCacheKeys.contains(key);
    }

'''
if "private String cacheOperationKey(String title" not in text:
    if helper_marker not in text:
        raise SystemExit("helper insertion marker missing")
    text = text.replace(helper_marker, helpers + helper_marker, 1)

search_cache = r'''    private void cacheSearchPlaybackAsync(Song song,
                                          SearchQuickPlayback.Candidate candidate,
                                          int playToken) {
        if (song == null || candidate == null || !song.isNetworkCatalog()) return;
        final String media3Key = Media3CacheStore.keyFor(
            song.title, song.artist, candidate.catalogJson);
        if (media3Key.isEmpty()) return;
        final String operationKey = cacheOperationKey(
            song.title, song.artist, candidate.catalogJson);
        final String originalKey = song.key();
        if (song.artworkUrl == null || song.artworkUrl.trim().isEmpty()) {
            song.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(candidate.catalogJson);
        }

        synchronized (searchCacheTasks) {
            Future<?> existingTask = searchCacheTasks.get(media3Key);
            if (existingTask != null && !existingTask.isDone()) return;
            if (!beginSongCacheTask(operationKey)) {
                if (currentSong == song && statusView != null) {
                    statusView.setText("该歌曲已有缓存任务，直接复用现有任务");
                }
                return;
            }
            try {
                Future<?> submitted = searchCacheExecutor.submit(() -> {
                    try {
                        NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
                            this,
                            candidate.catalogJson,
                            true,
                            message -> {
                                if (activityDestroyed) {
                                    throw new IllegalStateException("页面已关闭，停止后台缓存");
                                }
                                runOnUiThread(() -> {
                                    if (!activityDestroyed && currentSong == song && statusView != null) {
                                        statusView.setText(message);
                                    }
                                });
                            }
                        );

                        runOnUiThread(() -> {
                            if (activityDestroyed) return;
                            if (cached.catalogJson != null && !cached.catalogJson.trim().isEmpty()) {
                                song.catalogJson = cached.catalogJson;
                            }
                            if (cached.sourceCode != null && !cached.sourceCode.trim().isEmpty()) {
                                song.source = CatalogSearch.labelForSource(cached.sourceCode);
                            }
                            if (cached.audioUri != null && !cached.audioUri.trim().isEmpty()) {
                                song.cachedUri = cached.audioUri;
                                song.uri = cached.audioUri;
                            }
                            if ((song.lyric == null || song.lyric.trim().isEmpty())
                                && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                                song.lyric = cached.lyric;
                            }
                            String artwork = PlaybackArtworkLoader.extractArtworkUrl(song.catalogJson);
                            if (artwork != null && !artwork.trim().isEmpty()) song.artworkUrl = artwork;
                            song.cacheFailed = false;
                            song.unavailable = false;
                            song.autoUnavailable = false;
                            song.manualUnavailable = false;
                            song.manualAttempt = false;

                            // The exact current playback object is also the object added
                            // to the playlist. Copies with the same original identity are
                            // updated as well, so one-click cache immediately sees it.
                            persistResolvedCatalogToPlaylistCopies(song, originalKey);
                            savePlaylists();
                            renderCurrentPlaylist();
                            updatePlaylistCacheButtonVisibility();
                            if (resultAdapter != null) resultAdapter.notifyDataSetChanged();
                            if (playlistAdapter != null) playlistAdapter.notifyDataSetChanged();
                            if (currentSong == song && statusView != null) {
                                statusView.setText("已完成当前播放歌曲缓存：" + song.title);
                            }
                        });
                    } catch (Exception error) {
                        runOnUiThread(() -> {
                            if (activityDestroyed) return;
                            // Cache failure never means the search result cannot be added
                            // to a playlist. Container/codec is not used as an admission rule.
                            song.cacheFailed = false;
                            if (currentSong == song && statusView != null) {
                                String detail = error.getMessage() == null
                                    ? "后台缓存暂未完成" : error.getMessage();
                                statusView.setText("歌曲仍可正常播放；" + detail);
                            }
                        });
                    } finally {
                        endSongCacheTask(operationKey);
                        synchronized (searchCacheTasks) {
                            searchCacheTasks.remove(media3Key);
                        }
                    }
                });
                searchCacheTasks.put(media3Key, submitted);
            } catch (Throwable submitError) {
                endSongCacheTask(operationKey);
                throw submitError;
            }
        }
    }'''
text = replace_method(text, "    private void cacheSearchPlaybackAsync(Song song,", search_cache)

one_click = r'''    private void cacheCurrentPlaylistOneClick() {
        final Playlist playlist = currentPlaylist();
        if (playlist == null || playlist.songs.isEmpty()) {
            toast("当前歌单为空");
            return;
        }
        if (playlistCacheRunning) {
            toast("当前歌单正在缓存");
            return;
        }

        final List<Song> songSnapshot = new ArrayList<>(playlist.songs);
        final int cacheStartSerial = foregroundPlaybackSerial;
        playlistCacheRunning = true;
        ++playlistCacheScanSerial;
        if (playlistCacheButton != null) {
            playlistCacheButton.setVisibility(View.VISIBLE);
            playlistCacheButton.setEnabled(false);
            playlistCacheButton.setText("正在检查缓存状态…");
        }
        if (statusView != null) statusView.setText("正在检查当前歌单的缓存状态…");

        new Thread(() -> {
            List<Song> targets = uncachedNetworkSongs(songSnapshot);
            if (targets.isEmpty()) {
                runOnUiThread(() -> {
                    playlistCacheRunning = false;
                    updatePlaylistCacheButtonVisibility();
                    toast("当前歌单都已缓存");
                });
                return;
            }

            runOnUiThread(() -> {
                if (statusView != null) {
                    statusView.setText("开始缓存未缓存歌曲：" + playlist.name
                        + "，共 " + targets.size() + " 首");
                }
            });

            int done = 0;
            int skipped = 0;
            int waitingExisting = 0;
            int failed = 0;
            boolean pausedForPlayback = false;
            for (int i = 0; i < targets.size(); i++) {
                if (foregroundPlaybackSerial != cacheStartSerial) {
                    pausedForPlayback = true;
                    break;
                }
                Song song = targets.get(i);
                if (song == null || !song.isNetworkCatalog()) {
                    skipped++;
                    continue;
                }
                if (songHasRecordedCache(song)) {
                    done++;
                    continue;
                }

                // Search playback/replacement/one-click all share this key. If the
                // song is already being cached, never start a second download.
                final String operationKey = cacheOperationKey(song);
                if (!beginSongCacheTask(operationKey)) {
                    waitingExisting++;
                    final int index = i + 1;
                    runOnUiThread(() -> {
                        if (statusView != null) {
                            statusView.setText("已有缓存任务 " + index + "/" + targets.size()
                                + "：" + song.title + "，不重复下载");
                        }
                    });
                    continue;
                }

                final int index = i + 1;
                runOnUiThread(() -> {
                    if (statusView != null) {
                        statusView.setText("正在缓存 " + index + "/" + targets.size()
                            + "：" + song.title);
                    }
                });
                try {
                    // Do not skip old cacheFailed entries. The resolver is now
                    // format-agnostic; previous MP3/FLAC-biased failures may succeed.
                    song.cacheFailed = false;
                    NetworkMediaCache.CacheResult cached = cachePlaylistSongWithTimeout(song, cacheStartSerial);
                    if (foregroundPlaybackSerial != cacheStartSerial) {
                        pausedForPlayback = true;
                        break;
                    }
                    String originalKey = song.key();
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
                        song.lyric = cached.lyric;
                    }
                    song.cacheFailed = false;
                    song.unavailable = false;
                    song.autoUnavailable = false;
                    song.manualUnavailable = false;
                    song.manualAttempt = false;
                    recoverCachedSongState(song, cached.audioUri);
                    persistResolvedCatalogToPlaylistCopies(song, originalKey);
                    done++;
                } catch (Exception error) {
                    if (foregroundPlaybackSerial != cacheStartSerial) {
                        pausedForPlayback = true;
                        break;
                    }
                    // Cache failure is not equivalent to "song unavailable". It can
                    // be a transient network/download problem; playback remains allowed.
                    song.cacheFailed = true;
                    failed++;
                } finally {
                    endSongCacheTask(operationKey);
                }
            }
            int finalDone = done;
            int finalSkipped = skipped;
            int finalWaitingExisting = waitingExisting;
            int finalFailed = failed;
            boolean finalPausedForPlayback = pausedForPlayback;
            runOnUiThread(() -> {
                playlistCacheRunning = false;
                savePlaylists();
                renderCurrentPlaylist();
                updatePlaylistCacheButtonVisibility();
                if (statusView == null) return;
                if (finalPausedForPlayback) {
                    statusView.setText("已因前台播放切换而暂停一键缓存");
                } else {
                    statusView.setText("一键缓存完成：成功 " + finalDone
                        + "，复用已有任务 " + finalWaitingExisting
                        + "，跳过 " + finalSkipped + "，新失败 " + finalFailed);
                }
            });
        }, "playlist-one-click-cache").start();
    }'''
text = replace_method(text, "    private void cacheCurrentPlaylistOneClick()", one_click)

# Replacement caching uses the same lock so it cannot race one-click/search cache.
replacement = r'''    private void cacheReplacedPlaylistSongAsync(Song song, int cacheSerial) {
        if (song == null || !song.isNetworkCatalog()) return;
        final String requestedCatalog = song.catalogJson == null ? "" : song.catalogJson.trim();
        final String originalKey = song.key();
        final String operationKey = cacheOperationKey(song.title, song.artist, requestedCatalog);
        if (requestedCatalog.isEmpty()) return;
        if (!beginSongCacheTask(operationKey)) {
            if (currentSong == song && statusView != null) {
                statusView.setText("该歌曲已有缓存任务，替换后直接复用现有任务");
            }
            return;
        }

        try {
            searchCacheExecutor.submit(() -> {
                try {
                    NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
                        this,
                        requestedCatalog,
                        true,
                        message -> {
                            if (message == null || message.trim().isEmpty()) return;
                            runOnUiThread(() -> {
                                if (activityDestroyed || cacheSerial != replacementCacheSerial) return;
                                if (currentSong == song && statusView != null) {
                                    statusView.setText("替换版本正在后台缓存：" + message);
                                }
                            });
                        }
                    );
                    runOnUiThread(() -> {
                        if (activityDestroyed || cacheSerial != replacementCacheSerial) return;
                        if (cached.catalogJson != null && !cached.catalogJson.trim().isEmpty()) {
                            song.catalogJson = cached.catalogJson;
                        }
                        if (cached.sourceCode != null && !cached.sourceCode.trim().isEmpty()) {
                            song.source = CatalogSearch.labelForSource(cached.sourceCode);
                        }
                        if (song.artworkUrl == null || song.artworkUrl.trim().isEmpty()) {
                            song.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(song.catalogJson);
                        }
                        song.cachedUri = cached.audioUri;
                        song.uri = cached.audioUri;
                        song.cacheFailed = false;
                        song.unavailable = false;
                        song.autoUnavailable = false;
                        song.manualUnavailable = false;
                        if ((song.lyric == null || song.lyric.trim().isEmpty())
                            && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                            song.lyric = cached.lyric;
                            song.lyricLabel = song.title + " · " + song.artist + " · " + song.source;
                        }
                        persistResolvedCatalogToPlaylistCopies(song, originalKey);
                        savePlaylists();
                        renderCurrentPlaylist();
                        updatePlaylistCacheButtonVisibility();
                        if (currentSong == song && statusView != null) {
                            statusView.setText("替换歌曲版本缓存已完成");
                        }
                    });
                } catch (Exception error) {
                    runOnUiThread(() -> {
                        if (activityDestroyed || cacheSerial != replacementCacheSerial) return;
                        updatePlaylistCacheButtonVisibility();
                        if (currentSong == song && statusView != null) {
                            statusView.setText("替换版本可继续播放；自动缓存未完成，可稍后重试");
                        }
                    });
                } finally {
                    endSongCacheTask(operationKey);
                }
            });
        } catch (Throwable submitError) {
            endSongCacheTask(operationKey);
            throw submitError;
        }
    }'''
text = replace_method(text, "    private void cacheReplacedPlaylistSongAsync(Song song, int cacheSerial)", replacement)

path.write_text(text, encoding="utf-8")
