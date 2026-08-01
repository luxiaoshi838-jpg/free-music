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
    'multi-format priority and one-minute validation': (
        'MIN_AUTOMATIC_DURATION_MS = 60_000L' in network
        and 'choiceFormatRank' in network
        and 'if ("mp3".equals(extension)) return 0;' in network
        and 'if ("flac".equals(extension)) return 1;' in network
        and 'isAcceptableCachedAudio' in network
        and 'mediaDurationMs' in network
        and 'AudioTranscoder.ensureMp3' not in network
        and 'AudioMetadataWriter.applyAndVerify' not in network
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
    'version bumped': 'versionCode 2026080101' in gradle,
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
