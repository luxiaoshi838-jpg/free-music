from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java').read_text(encoding='utf-8')
cache = (root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java').read_text(encoding='utf-8')
network = (root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java').read_text(encoding='utf-8')
broom = (root / 'app/src/main/java/com/jianglab/babywife/BroomIconView.java').read_text(encoding='utf-8')
picker = (root / 'app/src/main/java/com/jianglab/babywife/SongVersionPicker.java').read_text(encoding='utf-8')
catalog = (root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java').read_text(encoding='utf-8')
gradle = (root / 'app/build.gradle').read_text(encoding='utf-8')
project_log = (root / 'PROJECT_LOG.md').read_text(encoding='utf-8')
changelog = (root / 'docs/CHANGELOG.md').read_text(encoding='utf-8')

song_id_pos = main.find('key.contains("歌曲id")')
title_pos = main.find('key.equals("歌名")')
cache_button_pos = main.find('cacheLocationButton = makeButton')
background_button_pos = main.find('Button chooseBackground = makeButton')

checks = {
    'monochrome broom button': (
        'BroomIconView clearCacheButton' in main
        and 'confirmClearTransientCache' in main
        and 'Color.WHITE' in broom
        and '\\uD83E\\uDDF9' not in main
        and '🧹' not in main
    ),
    'cache button above background button': (
        cache_button_pos >= 0 and background_button_pos >= 0 and cache_button_pos < background_button_pos
    ),
    'legacy cache path visible': 'CacheStorage.details(this)' in main and 'defaultLocation' in cache,
    'copy-first cache migration': (
        'copyFilesToTree' in cache
        and 'copyDocumentsToTree' in cache
        and 'copyDocumentsToInternal' in cache
        and '旧文件未删除' in main
    ),
    'managed cache safety': 'isManagedCacheName' in cache and 'dot != 64' in cache,
    'delete-cache toggle': (
        'KEY_DELETE_CACHE_WITH_ENTRY' in main
        and '删除歌单/歌曲时同步清理缓存' in main
        and 'cleanupCachesForRemovedSongs' in main
        and 'deleteCatalogCache' in network
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
    'cache abstraction used': 'CacheStorage.storeAudio' in network and 'CacheStorage.clearExcept' in network,
    'logs synchronized': 'CSV 导入、旧版缓存核查与缓存管理二次修正' in project_log and 'CSV, legacy cache' in changelog,
    'no literal passphrase': '姜Lab欢迎你' not in ''.join([main, cache, network, broom, picker, catalog, gradle, project_log, changelog]),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('Feature verification failed: ' + ', '.join(failed))
print('Feature requirements check passed: ' + ', '.join(checks))
