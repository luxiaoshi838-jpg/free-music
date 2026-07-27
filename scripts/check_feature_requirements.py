from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java').read_text(encoding='utf-8')
cache = (root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java').read_text(encoding='utf-8')
network = (root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java').read_text(encoding='utf-8')
picker = (root / 'app/src/main/java/com/jianglab/babywife/SongVersionPicker.java').read_text(encoding='utf-8')
catalog = (root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java').read_text(encoding='utf-8')
gradle = (root / 'app/build.gradle').read_text(encoding='utf-8')
project_log = (root / 'PROJECT_LOG.md').read_text(encoding='utf-8')
changelog = (root / 'docs/CHANGELOG.md').read_text(encoding='utf-8')

checks = {
    'broom button': 'confirmClearTransientCache' in main and '\\uD83E\\uDDF9' in main,
    'single cache folder': 'useDocumentTree' in cache and '歌单缓存位置' in main,
    'search/playlist context': 'KEY_LAST_CONTEXT' in main and 'switchPlaybackToPlaylist' in main,
    'replacement scoring': 'replacementScore' in catalog and 'onUnavailable()' in picker,
    'delayed red marking': 'autoUnavailable && song.manualUnavailable' in main,
    'csv import/export': '歌名,歌手,专辑,时长秒,平台,平台代码,歌曲ID,歌词版本' in main,
    'jianglab flavor gate': 'REQUIRE_FIRST_RUN_PASSPHRASE' in gradle and 'signingCertificateCommonName' in main,
    'cache abstraction used': 'CacheStorage.storeAudio' in network and 'CacheStorage.clearExcept' in network,
    'logs synchronized': '## 2026-07-27' in project_log and '## 2026-07-27' in changelog,
    'no literal passphrase': '姜Lab欢迎你' not in ''.join([main, cache, network, picker, catalog, gradle, project_log, changelog]),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('Feature verification failed: ' + ', '.join(failed))
print('Feature requirements check passed: ' + ', '.join(checks))
