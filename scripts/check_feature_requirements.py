from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java').read_text(encoding='utf-8')
cache = (root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java').read_text(encoding='utf-8')
network = (root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java').read_text(encoding='utf-8')
broom = (root / 'app/src/main/java/com/jianglab/babywife/BroomIconView.java').read_text(encoding='utf-8')
metadata = (root / 'app/src/main/java/com/jianglab/babywife/AudioMetadataWriter.java').read_text(encoding='utf-8')
transcoder = (root / 'app/src/main/java/com/jianglab/babywife/AudioTranscoder.java').read_text(encoding='utf-8')
soda_decryptor = (root / 'app/src/main/java/com/jianglab/babywife/SodaM4aDecryptor.java').read_text(encoding='utf-8')
picker = (root / 'app/src/main/java/com/jianglab/babywife/SongVersionPicker.java').read_text(encoding='utf-8')
catalog = (root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java').read_text(encoding='utf-8')
playable_resolver = (root / 'app/src/main/java/com/jianglab/babywife/PlayableAudioResolver.java').read_text(encoding='utf-8')
playback_verifier = (root / 'app/src/main/java/com/jianglab/babywife/AudioPlaybackVerifier.java').read_text(encoding='utf-8')
gradle = (root / 'app/build.gradle').read_text(encoding='utf-8')
manifest = (root / 'app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')
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
    'friendly cache filenames': (
        'friendlyBase' in cache
        and 'record.title + " - " + record.artist' in cache
        and '" [" + shortKey + "]"' not in cache
        and 'friendlyBaseForInternal' in cache
        and 'friendlyBaseForTree' in cache
        and 'plain + " (" + index + ")"' in cache
        and 'record.audioFile' in cache
        and 'record.lyricFile' in cache
        and 'META_PREFIX = ".babywife_"' in cache
    ),
    'song metadata records': (
        'object.put("title", title)' in cache
        and 'object.put("artist", artist)' in cache
        and 'object.put("album", album)' in cache
        and 'AudioMetadataWriter.apply' in playable_resolver
        and '"TIT2"' in metadata and '"TPE1"' in metadata and '"TALB"' in metadata
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
    'mp3 source preference with source-format fallback': (
        'format", "mp3' in network
        and 'AudioTranscoder.ensureMp3' in playable_resolver
        and 'MP3＞FLAC＞M4A＞其他' in playable_resolver
        and 'detectAudioExtension' in playable_resolver
        and 'ffmpeg-kit' not in gradle.lower()
        and 'FFmpegKit' not in transcoder
        and 'libmp3lame' not in transcoder
    ),
    'verified mp3 metadata': ('AudioMetadataWriter.applyAndVerify' in playable_resolver and 'MP3 歌曲信息写入校验失败' in metadata and '"TIT2"' in metadata and '"TPE1"' in metadata and '"TALB"' in metadata),
    'managed cache source formats': ('受管理歌曲缓存必须是 MP3' not in cache and 'CacheStorage.storeAudio(context, key, best.extension' in playable_resolver),
    'all formats require real playback verification': (
        'PlayableAudioResolver.prepare' in network
        and 'PlayableAudioResolver.cachedAudioExists' in network
        and 'REQUEST_FORMATS = {"mp3", "flac", "m4a", ""}' in playable_resolver
        and 'formatPriority' in playable_resolver
        and 'MP3＞FLAC＞M4A＞其他' in playable_resolver
        and 'AudioPlaybackVerifier.probeFile' in playable_resolver
        and 'AudioPlaybackVerifier.isPlayableUri' in playable_resolver
        and 'MediaExtractor' in playback_verifier
        and 'MediaPlayer' in playback_verifier
        and 'playableCachedExtension' not in network
    ),
    'consistent filenames across formats': (
        'String baseName = friendlyBase(record);' in cache
        and 'removeInternalAudioWithBase' in cache
        and 'removeTreeAudioWithBase' in cache
        and 'String fileName = baseName + "." + safeExtension;' in cache
        and 'return "mp3";' not in cache[cache.find('private static String sanitizeExtension'):cache.find('private static String safeNamePart')]
    ),
    'encrypted soda m4a decrypted': (
        'Address.parse' in playable_resolver
        and '#auth=' in playable_resolver
        and 'SodaM4aDecryptor.decrypt' in playable_resolver
        and 'SodaM4aDecryptor.isEncryptedM4a(context, uriText)' in playable_resolver
        and 'AES/CTR/NoPadding' in soda_decryptor
        and 'PlayAuth' in soda_decryptor
        and 'enca' in soda_decryptor and 'mp4a' in soda_decryptor
        and 'NetworkMediaCache.cachedAudioExists(this, currentSong.cachedUri)' in main
    ),
    'all managed cache names normalized on startup': (
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
    'dialog action labels match operations': (
        'setTitle("删除歌曲")' in main
        and main[main.find('private void confirmDeletePlaylistSong'):main.find('private void addSongToCurrentPlaylist')].find('setPositiveButton("\\u786e\\u5b9a"') >= 0
        and main[main.find('private void promptText'):main.find('private void deleteCurrentPlaylist')].find('setPositiveButton("\\u786e\\u5b9a"') >= 0
        and main[main.find('private void deleteCurrentPlaylist'):main.find('private void clearCurrentPlaylist')].find('setPositiveButton("\\u786e\\u5b9a"') >= 0
        and main[main.find('private void mergePlaylistsIntoCurrent'):main.find('private boolean containsSong')].find('setPositiveButton("\\u5408\\u5e76"') >= 0
        and main.count('setPositiveButton("\\u590d\\u5236"') == 1
    ),
    'settings width and status bar': ('0.70f' in main and 'setStatusBarColor(opening ? Color.rgb(22, 24, 34)' in main and 'statusBarHeight() + dp(20)' in main),
    'deferred flag commit after playback starts': (
        'playbackRequestSerial' in main
        and 'PendingPlaybackCommit' in main
        and 'commitResolvedPlayback(song, commit, playToken)' in main
        and 'setOnErrorListener' in main
        and '未写入替换来源' in main
    ),
    'short manager labels': ('makeSmallButton("新建"' in main and 'makeSmallButton("导出"' in main and '新建在线"' not in main and '导出CSV"' not in main),
    'short cache folder label': ('（卸载后保留）' not in cache[cache.find('static String description'):cache.find('static String details')]),
    'search keyboards close after submit': (
        'import android.view.inputmethod.InputMethodManager;' in main
        and 'hideKeyboardAndClearFocus(searchInput);' in main
        and 'playlistSearchInput.setImeOptions(EditorInfo.IME_ACTION_SEARCH);' in main
        and 'hideKeyboardAndClearFocus(playlistSearchInput);' in main
    ),
    'playlist search clear control': (
        'TextView clearPlaylistSearchButton = new TextView(this);' in main
        and 'clearPlaylistSearchButton.setText("×")' in main
        and 'clearPlaylistSearchButton.setVisibility(View.GONE)' in main
        and 'playlistSearchInput.setText("")' in main
        and 'panel.addView(playlistSearchBox, searchParams);' in main
    ),
    'all main button press feedback': (
        'attachPressFeedbackTree(shellView);' in main
        and 'attachSubtlePressFeedback(button);' in main
        and 'root instanceof BroomIconView' in main
        and 'root instanceof BackChevronView' in main
        and 'root instanceof TextView' in main
        and '.scaleX(0.96f)' in main
        and '.scaleY(0.96f)' in main
    ),
    'full cache folder migration and file management permission': (
        'android.permission.MANAGE_EXTERNAL_STORAGE' in manifest
        and 'Environment.isExternalStorageManager()' in main
        and 'Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION' in main
        and 'requestFileManagementThenChooseCacheFolder()' in main
        and 'listDocumentsStrict(context, oldTree, false)' in cache
        and 'listAllInternalFiles(context)' in cache
        and 'copyAndDigest' in cache
        and 'verifyDocumentDigest' in cache
        and 'retainedInOldLocation' in cache
        and 'listDocumentsStrict(context, oldTree, true)' not in cache
    ),
    'playlist playback uses recorded URI without folder scan': (
        'playPlaylistSongFromCacheFirst(song, playToken)' in main
        and '已读取歌单记录缓存，正在启动播放' in main
        and '歌单没有记录缓存，立即获取音频' in main
        and '歌单记录缓存无法播放，立即重新获取音频' in main
        and '"playlist-cache-lookup"' not in main
        and '"playlist-exact-cache-lookup"' not in main
        and 'CacheStorage.findAudioUri(this, exactKey)' not in main
        and 'CacheStorage.findAudioMatches(this, song.title, song.artist)' not in main
    ),
    'search candidates write only one formal cache': (
        'static final class AudioMatch' in cache
        and 'logicalIdentity(String title, String artist)' in cache
        and 'findAudioMatches(Context context, String title, String artist)' in cache
        and 'CACHE_LOCKS = createCacheLocks()' in network
        and 'cacheLocked(context, requestedCatalog, callback)' in network
        and '唯一正式缓存已完成，其他来源候选已清理' in network
        and '尚未写入正式缓存' in playable_resolver
        and '候选下载进度' in playable_resolver
        and '唯一正式缓存写入完成' in playable_resolver
        and 'CacheStorage.findAudioUri(context, key)' not in playable_resolver[playable_resolver.find('for (JSONObject catalog : catalogs)'):playable_resolver.find('if (best == null')]
        and '播放请求已切换，停止旧候选下载' in main
    ),
    'cached audio starts without waiting for lyrics or cleanup': (
        'cleanupDuplicateSongCachesAsync' in network
        and '"duplicate-cache-cleanup"' in network
        and '缓存已就绪，正在启动播放' in main
        and 'mediaPlayer.prepareAsync();' in main
        and 'mediaPlayer.prepare();' not in main[main.find('private void startLocalPlayback'):main.find('private void onPlaybackStarted')]
        and 'fetchLyrics(matchedCatalog.toString())' not in network
        and 'fetchLyrics(actualCatalog.toString())' not in network
    ),
    'no cache-folder scan in playback path': (
        'playPlaylistSongFromCacheFirst' in main
        and 'playPlaylistSongFromExactCache' not in main
        and '歌单没有记录缓存，立即获取音频' in main
        and '本次搜索缓存' in main
        and '正在准备音频，播放开始后再匹配歌词' in main
        and 'if (song.isNetworkCatalog()) showSongLyrics(song);' in main
        and '未使用播放前缓存扫描，立即获取可播放音频' in network
        and 'findAudioMatches(context, requestedTitle, requestedArtist)' not in network[network.find('private static CacheResult cacheLocked'):network.find('private static Object[] createCacheLocks')]
        and 'CacheStorage.findAudioUri(context, requestedKey)' not in network[network.find('private static CacheResult cacheLocked'):network.find('private static Object[] createCacheLocks')]
        and 'CacheStorage.findAudioUri(this, exactKey)' not in main
    ),
    'version bumped': 'versionCode 2026080137' in gradle,
    'logs synchronized': (
        'Guard cache migration I/O and add playback/search feedback' in project_log
        and 'migration-refresh ANR' in changelog
    ),
    'one-click cache target scan avoids SAF lookup': (
        'songHasRecordedCache(song)' in main
        and 'List<Song> targets = uncachedNetworkSongs(songSnapshot)' in main
        and main[main.find('private List<Song> uncachedNetworkSongs(List<Song> songs)'):main.find('private boolean songHasPlayableCache')].find('CacheStorage.findAudioUri') < 0
    ),
    'migration refresh runs provider lookup on worker': (
        'private void refreshCachedUrisAfterMigrationAsync()' in main
        and 'new Thread(() -> {' in main[main.find('private void refreshCachedUrisAfterMigrationAsync()'):main.find('private void refreshCachedUri(')]
        and '"cache-uri-refresh"' in main[main.find('private void refreshCachedUrisAfterMigrationAsync()'):main.find('private void refreshCachedUri(')]
        and 'for (Song song : snapshot) refreshCachedUri(song, visited);' in main
    ),
    'previous and next press feedback': (
        'attachSubtlePressFeedback(previous);' in main
        and 'attachSubtlePressFeedback(next);' in main
        and '.scaleX(0.96f)' in main
        and '.scaleY(0.96f)' in main
    ),
    'search text clear control': (
        'TextView clearSearchButton = new TextView(this);' in main
        and 'clearSearchButton.setText("×")' in main
        and 'clearSearchButton.setVisibility(View.GONE)' in main
        and 'searchInput.setText("")' in main
    ),
    'no literal passphrase': '姜Lab欢迎你' not in ''.join(
        [main, cache, network, broom, metadata, picker, catalog, gradle, project_log, changelog]),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('Feature verification failed: ' + ', '.join(failed))
print('Feature requirements check passed: ' + ', '.join(checks))
