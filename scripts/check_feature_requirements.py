from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java').read_text(encoding='utf-8')
cache = (root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java').read_text(encoding='utf-8')
network = (root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java').read_text(encoding='utf-8')
compat = (root / 'app/src/main/java/com/jianglab/babywife/PlaybackCompatibility.java').read_text(encoding='utf-8')
batch_service = (root / 'app/src/main/java/com/jianglab/babywife/PlaylistBatchCacheService.java').read_text(encoding='utf-8')
cache_lock = (root / 'app/src/main/java/com/jianglab/babywife/CacheKeyLock.java').read_text(encoding='utf-8')
manifest = (root / 'app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')
broom = (root / 'app/src/main/java/com/jianglab/babywife/BroomIconView.java').read_text(encoding='utf-8')
metadata = (root / 'app/src/main/java/com/jianglab/babywife/AudioMetadataWriter.java').read_text(encoding='utf-8')
transcoder = (root / 'app/src/main/java/com/jianglab/babywife/AudioTranscoder.java').read_text(encoding='utf-8')
picker = (root / 'app/src/main/java/com/jianglab/babywife/SongVersionPicker.java').read_text(encoding='utf-8')
catalog = (root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java').read_text(encoding='utf-8')
priority = (root / 'app/src/main/java/com/jianglab/babywife/SearchPriorityCoordinator.java').read_text(encoding='utf-8')
playback_service = (root / 'app/src/main/java/com/jianglab/babywife/PlaybackControlService.java').read_text(encoding='utf-8')
gradle = (root / 'app/build.gradle').read_text(encoding='utf-8')
project_log = (root / 'PROJECT_LOG.md').read_text(encoding='utf-8')
changelog = (root / 'docs/CHANGELOG.md').read_text(encoding='utf-8')
icon = root / 'app/src/main/res/drawable-nodpi/broom_clean_icon.webp'

song_id_pos = main.find('key.contains("歌曲id")')
title_pos = main.find('key.equals("歌名")')
background_button_pos = main.find('Button chooseBackground = makeButton')
change_icon_pos = main.find('Button changeIcon = makeButton')

checks = {
    'user broom artwork': (
        icon.is_file() and icon.stat().st_size > 1000
        and 'R.drawable.broom_clean_icon' in broom
        and '0.82f' in broom
        and 'BroomIconView clearCacheButton' in main
        and '🧹' not in main
    ),
    'playlist manager below status bar': (
        '0.70f' in main
        and 'statusBarHeight() + dp(20)' in main
        and 'drawerParams.topMargin = statusBarHeight() + dp(8)' not in main
    ),
    'uninstall cleanup storage switch': (
        '卸载软件时清理缓存' in main
        and 'CacheStorage.uninstallCleanupEnabled(this)' in main
        and '选择保留文件夹' in main
        and '迁回并开启' in main
        and 'KEY_DELETE_CACHE_WITH_ENTRY' not in main
    ),
    'deleting entries keeps cache': (
        'cleanupCachesForRemovedSongs' not in main
        and '删除歌单/歌曲时同步清理缓存' not in main
        and '缓存已保留，可用扫把清理' in main
    ),
    'merged local import entry': (
        'makeButton("导入本地歌曲"' in main
        and 'showLocalAudioImportOptions' in main
        and '"选择歌曲", "选择文件夹"' in main
        and 'makeButton("选择文件夹导入全部歌曲"' not in main
    ),
    'merged playlist import entry': (
        'makeButton("导入歌单"' in main
        and 'showPlaylistImportOptions' in main
        and '"CSV 文件", "歌单链接"' in main
        and 'makeButton("导入网易/酷狗/汽水歌单链接"' not in main
    ),
    'background directly before icon control': (
        background_button_pos >= 0 and change_icon_pos >= 0 and background_button_pos < change_icon_pos
        and main[background_button_pos:change_icon_pos].count('makeButton(') == 1
    ),
    'paired title-artist audio and LRC filenames': (
        'String base = record.title + " - " + record.artist;' in cache
        and 'uniqueInternalPairBase' in cache
        and 'uniqueDocumentPairBase' in cache
        and 'base + ".lrc"' in cache
        and 'application/octet-stream' in cache
        and 'lower.endsWith(".lrc") || lower.endsWith(".txt")' in cache
        and '" [" + shortKey' not in cache
        and 'record.audioFile' in cache
        and 'record.lyricFile' in cache
    ),
    'playlist and cache index metadata only': (
        'object.put("title", title)' in cache
        and 'object.put("artist", artist)' in cache
        and 'object.put("album", album)' in cache
        and 'AudioMetadataWriter.apply' not in network
        and '不向音频文件写入歌名' in network
    ),
    'copy-first cache migration': (
        'copyFilesToTree' in cache
        and 'copyDocumentsToTree' in cache
        and 'copyDocumentsToInternal' in cache
        and '旧文件未删除' in main
    ),
    'broom clears only non-playlist cache': (
        'confirmClearTransientCache' in main
        and 'NetworkMediaCache.clearExcept(this, keepKeys)' in main
        and ('只删除未加入任何歌单' in main or '\\u53ea\\u5220\\u9664\\u672a\\u52a0\\u5165\\u4efb\\u4f55\\u6b4c\\u5355' in main)
    ),
    'csv song id cannot overwrite title': (
        song_id_pos >= 0 and title_pos >= 0 and song_id_pos < title_pos
        and 'key.contains("歌曲")' not in main
    ),
    'search/playlist context': 'KEY_LAST_CONTEXT' in main and 'switchPlaybackToPlaylist' in main,
    'replacement scoring': 'replacementScore' in catalog and 'onUnavailable()' in picker,
    'delayed red marking': 'autoUnavailable && song.manualUnavailable' in main,
    'csv import/export': '歌名,歌手,专辑,时长秒,平台,平台代码,歌曲ID,歌词版本' in main,
    'jianglab flavor gate': 'REQUIRE_FIRST_RUN_PASSPHRASE' in gradle and 'signingCertificateCommonName' in main,
    'original-source fast path and one-minute validation': (
        'MIN_AUTOMATIC_DURATION_MS = 60_000L' in network
        and 'MAX_FALLBACK_ATTEMPTS = 4' in network
        and '正在使用歌单原来源解析歌曲' in network
        and '原来源不可用，才开始查找其他平台版本' in network
        and 'cacheFirstUsableAlternative' in network
        and 'findAutomaticChoices' not in network
        and 'choices.sort' not in network
        and 'isAcceptableCachedAudio' in network
        and 'mediaDurationMs' in network
        and 'AudioTranscoder.ensureMp3' not in network
        and 'AudioMetadataWriter.applyAndVerify' not in network
    ),
    'real decoder playback validation': (
        'MediaExtractor' in compat
        and 'MediaCodecList' in compat
        and 'MediaCodec.createByCodecName' in compat
        and 'dequeueOutputBuffer' in compat
        and 'outputInfo.size > 0' in compat
        and 'decodeProbe(extractor, audioFormat, decoderName, 0L)' in compat
        and 'decodeProbe(extractor, audioFormat, decoderName, seekTargetUs)' in compat
        and 'PlaybackCompatibility.isPlayable(partial)' in network
        and 'validateCatalogCache' in network
        and 'NetworkMediaCache.validateCatalogCache(this, song.catalogJson)' in main
        and 'return CacheStorage.exists(context, uriText);' in network
    ),
    'isolated resumable playlist cache state machine': (
        '暂停一键缓存' in main
        and '任务已停滞，点击重启' in main
        and 'cachePlaylistButton.setVisibility(View.GONE)' in main
        and 'PlaylistBatchCacheService.pause(this)' in main
        and 'PlaylistBatchCacheService.restart(this, currentPlaylistIndex, request)' in main
        and 'readPendingBatchCacheResults' not in main
        and 'readPendingResults' in main
        and 'android:process=":playlist_cache"' in manifest
        and 'FOREGROUND_SERVICE_DATA_SYNC' in manifest
        and 'ACTION_PAUSE' in batch_service
        and 'ACTION_RESTART' in batch_service
        and 'PROGRESS_STALE_MS' in batch_service
        and 'android.os.Process.killProcess' in batch_service
        and 'RESULTS_FOLDER' in batch_service
        and 'CacheKeyLock.acquire(context, key)' in network
        and 'FileChannel' in cache_lock
        and 'tryLock' in cache_lock
    ),
    'nonblocking batch result merge and isolated notification': (
        'requestBatchCacheSync(true)' in main
        and 'PlaylistBatchUiSync' in main
        and 'batchCacheSyncRunning.compareAndSet(false, true)' in main
        and 'readPendingResults(appContext)' in main
        and 'consumePendingBatchCacheResults' not in main
        and 'song.cachedUri == null || song.cachedUri.trim().isEmpty()' in main
        and 'publishPlaybackControlState(true);\n        saveLastSong(0);' in main
        and 'android:process=":playback_control"' in manifest
        and 'lastBroadcastMs' in batch_service
        and 'now - lastBroadcastMs >= 1200L' in batch_service
    ),
    'foreground playback priority and resilient batch progression': (
        'beginForegroundWork(this)' in main
        and '&& !song.autoUnavailable' in main
        and 'ForegroundPriorityException' in network
        and 'yieldIfForegroundRequested(context)' in network
        and 'THREAD_PRIORITY_BACKGROUND' in batch_service
        and 'SONG_STALL_SKIP_MS = 45000L' in batch_service
        and 'for (int index = done; index < total; index++)' in batch_service
        and 'skipStalledSongAndRestart' in batch_service
        and '缓存失败并已跳过后续自动重试' in batch_service
    ),
    'manual search priority persistent picker and background resolve': (
        'SearchPriorityCoordinator.searchManual' in catalog
        and 'SearchPriorityCoordinator.searchAutomatic' in catalog
        and 'bridge_search.lock' in priority
        and 'manual_search.lease' in priority
        and 'song_version_directory_v3_exact_identity' in picker
        and 'restoreNextSourceIndex' in picker
        and '下拉或滚到底部' in picker
        and 'IME_ACTION_SEARCH' in main
        and 'ACTION_RESOLVE_RESULT' in main
        and 'resolveForImmediatePlayback' in main
        and 'cacheForPlayback' in network
        and 'cacheForAutomatic' in network
        and 'enforceRequestedMinimum' in network
        and 'enforceMinimumDuration' in network
        and 'eagerLyrics' in network
        and 'PlaybackResolveWorker' in playback_service
        and 'mediaPlayback|dataSync' in manifest
    ),
    'private style instant search and simple playback replacement': (
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
    'instant stream playback without pre-download gate': (
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
    'media player error containment': (
        'attachPlaybackErrorHandler' in main
        and 'handlePlaybackFailure' in main
        and 'setOnErrorListener' in main
    ),
    'audio file tags untouched': ('AudioMetadataWriter.apply' not in network and '不向音频文件写入歌名' in network),
    'managed cache accepts source formats': (
        '受管理歌曲缓存必须是 MP3' not in cache
        and 'storeAudio(context, key, actualExtension' in network
        and 'return "application/octet-stream";' in cache
    ),
    'settings width and status bar': ('0.70f' in main and 'setStatusBarColor(opening ? Color.rgb(22, 24, 34)' in main and 'statusBarHeight() + dp(20)' in main),
    'short manager labels': ('makeSmallButton("新建"' in main and 'makeSmallButton("导出"' in main and '新建在线"' not in main and '导出CSV"' not in main),
    'short cache folder label': ('（卸载后保留）' not in cache[cache.find('static String description'):cache.find('static String details')]),
    'version bumped': 'versionCode 2026080112' in gradle,
    'logs synchronized': (
        '多格式缓存优先级与一分钟过滤' in project_log
        and 'Multi-format cache priority and one-minute filter' in changelog
    ),
    'no literal passphrase': '姜Lab欢迎你' not in ''.join(
        [main, cache, network, broom, metadata, picker, catalog, gradle, project_log, changelog]),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('Feature verification failed: ' + ', '.join(failed))
print('Feature requirements check passed: ' + ', '.join(checks))
