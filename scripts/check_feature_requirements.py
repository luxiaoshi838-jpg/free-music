from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java').read_text(encoding='utf-8')
cache = (root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java').read_text(encoding='utf-8')
network = (root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java').read_text(encoding='utf-8')
broom = (root / 'app/src/main/java/com/jianglab/babywife/BroomIconView.java').read_text(encoding='utf-8')
metadata = (root / 'app/src/main/java/com/jianglab/babywife/AudioMetadataWriter.java').read_text(encoding='utf-8')
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
        'drawerParams.topMargin = statusBarHeight() + dp(8)' in main
        and 'drawerParams.bottomMargin = dp(8)' in main
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
    'version bumped': 'versionCode 2026072702' in gradle,
    'logs synchronized': (
        '卸载缓存、导入入口与歌曲文件信息修正' in project_log
        and 'Uninstall cache, import menu and named media follow-up' in changelog
    ),
    'no literal passphrase': '姜Lab欢迎你' not in ''.join(
        [main, cache, network, broom, metadata, picker, catalog, gradle, project_log, changelog]),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('Feature verification failed: ' + ', '.join(failed))
print('Feature requirements check passed: ' + ', '.join(checks))
