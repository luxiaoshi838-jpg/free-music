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

song_id_pos = main.find('key.contains("??id")')
title_pos = main.find('key.equals("??")')
background_button_pos = main.find('Button chooseBackground = makeButton')
change_icon_pos = main.find('Button changeIcon = makeButton')

checks = {
    'user broom artwork': (
        icon.is_file() and icon.stat().st_size > 1000
        and 'R.drawable.broom_clean_icon' in broom
        and '0.82f' in broom
        and 'BroomIconView clearCacheButton' in main
        and '??' not in main
    ),
    'playlist manager below status bar': (
        '0.70f' in main
        and 'statusBarHeight() + dp(20)' in main
        and 'drawerParams.topMargin = statusBarHeight() + dp(8)' not in main
    ),
    'uninstall cleanup storage switch': (
        '?????????' in main
        and 'CacheStorage.uninstallCleanupEnabled(this)' in main
        and '???????' in main
        and '?????' in main
        and 'KEY_DELETE_CACHE_WITH_ENTRY' not in main
    ),
    'deleting entries keeps cache': (
        'cleanupCachesForRemovedSongs' not in main
        and '????/?????????' not in main
        and '????????????' in main
    ),
    'merged local import entry': (
        'makeButton("??????"' in main
        and 'showLocalAudioImportOptions' in main
        and '"????", "?????"' in main
        and 'makeButton("???????????"' not in main
    ),
    'merged playlist import entry': (
        'makeButton("????"' in main
        and 'showPlaylistImportOptions' in main
        and '"CSV ??", "????"' in main
        and 'makeButton("????/??/??????"' not in main
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
        and '??????' in main
    ),
    'broom clears only non-playlist cache': (
        'confirmClearTransientCache' in main
        and 'NetworkMediaCache.clearExcept(this, keepKeys)' in main
        and ('??????????' in main or '\\u53ea\\u5220\\u9664\\u672a\\u52a0\\u5165\\u4efb\\u4f55\\u6b4c\\u5355' in main)
    ),
    'csv song id cannot overwrite title': (
        song_id_pos >= 0 and title_pos >= 0 and song_id_pos < title_pos
        and 'key.contains("??")' not in main
    ),
    'search/playlist context': 'KEY_LAST_CONTEXT' in main and 'switchPlaybackToPlaylist' in main,
    'replacement scoring': 'replacementScore' in catalog and 'onUnavailable()' in picker,
    'delayed red marking': 'autoUnavailable && song.manualUnavailable' in main,
    'csv import/export': '??,??,??,???,??,????,??ID,????' in main,
    'jianglab flavor gate': 'REQUIRE_FIRST_RUN_PASSPHRASE' in gradle and 'signingCertificateCommonName' in main,
    'mp3 source preference with source-format fallback': (
        'format", "mp3' in network
        and 'AudioTranscoder.ensureMp3' in network
        and '??????' in network
        and 'detectAudioExtension' in network
        and 'ffmpeg-kit' not in gradle.lower()
        and 'FFmpegKit' not in transcoder
        and 'libmp3lame' not in transcoder
    ),
    'verified mp3 metadata': ('AudioMetadataWriter.applyAndVerify' in network and 'MP3 ??????????' in metadata and '"TIT2"' in metadata and '"TPE1"' in metadata and '"TALB"' in metadata),
    'managed cache source formats': ('?????????? MP3' not in cache and 'storeAudio(context, key, actualExtension' in network),
    'settings width and status bar': ('0.70f' in main and 'setStatusBarColor(opening ? Color.rgb(22, 24, 34)' in main and 'statusBarHeight() + dp(20)' in main),
    'deferred flag commit after playback starts': (
        'playbackRequestSerial' in main
        and 'PendingPlaybackCommit' in main
        and 'commitResolvedPlayback(song, commit, playToken)' in main
        and 'setOnErrorListener' in main
        and '???????' in main
    ),
    'short manager labels': ('makeSmallButton("??"' in main and 'makeSmallButton("??"' in main and '????"' not in main and '??CSV"' not in main),
    'short cache folder label': ('???????' not in cache[cache.find('static String description'):cache.find('static String details')]),
    'version bumped': 'versionCode 2026072901' in gradle,
    'logs synchronized': (
        'MP3 ????????????' in project_log
        and 'MP3 cache normalization and settings drawer follow-up' in changelog
    ),
    'no literal passphrase': '?Lab???' not in ''.join(
        [main, cache, network, broom, metadata, picker, catalog, gradle, project_log, changelog]),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('Feature verification failed: ' + ', '.join(failed))
print('Feature requirements check passed: ' + ', '.join(checks))
