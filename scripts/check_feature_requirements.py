from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java').read_text(encoding='utf-8')
cache = (root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java').read_text(encoding='utf-8')
network = (root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java').read_text(encoding='utf-8')
broom = (root / 'app/src/main/java/com/jianglab/babywife/BroomIconView.java').read_text(encoding='utf-8')
metadata = (root / 'app/src/main/java/com/jianglab/babywife/AudioMetadataWriter.java').read_text(encoding='utf-8')
transcoder = (root / 'app/src/main/java/com/jianglab/babywife/AudioTranscoder.java').read_text(encoding='utf-8')
picker = (root / 'app/src/main/java/com/jianglab/babywife/SongVersionPicker.java').read_text(encoding='utf-8')
catalog = (root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java').read_text(encoding='utf-8')
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
    'friendly cache filenames': (
        'friendlyBase' in cache
        and '" - " + record.artist' in cache
        and 'record.audioFile' in cache
        and 'record.lyricFile' in cache
        and 'META_PREFIX = ".babywife_"' in cache
    ),
    'song metadata records': (
        'object.put("title", title)' in cache
        and 'object.put("artist", artist)' in cache
        and 'object.put("album", album)' in cache
        and 'AudioMetadataWriter.apply' in network
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
        and 'AudioTranscoder.ensureMp3' in network
        and '按原格式缓存' in network
        and 'detectAudioExtension' in network
        and 'ffmpeg-kit' not in gradle.lower()
        and 'FFmpegKit' not in transcoder
        and 'libmp3lame' not in transcoder
    ),
    'verified mp3 metadata': ('AudioMetadataWriter.applyAndVerify' in network and 'MP3 歌曲信息写入校验失败' in metadata and '"TIT2"' in metadata and '"TPE1"' in metadata and '"TALB"' in metadata),
    'managed cache source formats': ('受管理歌曲缓存必须是 MP3' not in cache and 'storeAudio(context, key, actualExtension' in network),
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
    'version bumped': 'versionCode 2026080126' in gradle,
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
